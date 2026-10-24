"""
pipeline.py
Part of TestPrioritize AI.

End-to-end pipeline orchestrator connecting:
1. Git change detection (diff_checker.py)
2. Test discovery and lexical source-to-test mapping (test_mapper.py)
3. External dependency intelligence via TinyFish (dependency_intelligence.py)
4. Deterministic, explainable ranking engine (ranking_engine.py)
5. Safe, prioritized test execution via pytest subprocess.
"""

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from dependency_intelligence import (
    DependencyIntelligenceReport,
    analyze_dependency_risks,
)
from diff_checker import (
    FileChange,
    GitDiffError,
    get_changed_files,
)
from ranking_engine import (
    RankingResult,
    rank_tests,
)
from test_mapper import (
    SourceMappingResult,
    discover_test_files,
    map_changed_sources_to_tests,
    normalize_path,
)

# Pipeline status constants
STATUS_SUCCESS = "success"
STATUS_NO_CHANGES = "no_changes"
STATUS_NO_CANDIDATE_TESTS = "no_candidate_tests"
STATUS_GIT_ERROR = "git_error"
STATUS_TEST_FAILURE = "test_failure"
STATUS_TIMEOUT = "timeout"
STATUS_ERROR = "error"


@dataclass(frozen=True)
class TestExecutionOutcome:
    """
    Structured outcome of running pytest in a safe subprocess.

    Attributes:
        executed: Whether test execution was actually attempted.
        command: Exact argument list executed.
        exit_code: Subprocess returncode (0 for all passed, 1 for test failure).
        stdout: Standard output captured from pytest.
        stderr: Standard error captured from pytest.
        duration_seconds: Real elapsed time taken by test run.
        passed_count: Number of passed tests parsed from output.
        failed_count: Number of failed tests parsed from output.
        total_executed: Total count of tests run.
        mode: Description of scope ("prioritized_subset" or "none").
        error_message: Error string if execution timed out or failed.
    """
    __test__ = False

    executed: bool
    command: List[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    passed_count: int = 0
    failed_count: int = 0
    total_executed: int = 0
    mode: str = "none"
    error_message: Optional[str] = None


@dataclass(frozen=True)
class PipelineResult:
    """
    Complete structured output of the TestPrioritize AI end-to-end pipeline.

    Attributes:
        status: Overall status code.
        changed_files: List of FileChange objects detected by Git diff.
        mapping_results: List of SourceMappingResult objects from test_mapper.
        dependency_report: Optional DependencyIntelligenceReport from TinyFish.
        ranking_result: Optional RankingResult from ranking_engine.
        execution_outcome: Optional TestExecutionOutcome from pytest runner.
        duration_seconds: Total pipeline wall-clock execution time.
        summary: Plain-English summary of the complete pipeline run.
        error_message: Error details if pipeline encountered a failure.
    """
    status: str
    changed_files: List[FileChange] = field(default_factory=list)
    mapping_results: List[SourceMappingResult] = field(default_factory=list)
    dependency_report: Optional[DependencyIntelligenceReport] = None
    ranking_result: Optional[RankingResult] = None
    execution_outcome: Optional[TestExecutionOutcome] = None
    duration_seconds: float = 0.0
    summary: str = ""
    error_message: Optional[str] = None


def parse_pytest_counts(output: str) -> Dict[str, int]:
    """
    Safely extracts passed, failed, and total test counts from pytest stdout.
    Examples handled:
      '=== 31 passed in 0.12s ==='
      '=== 1 failed, 30 passed in 0.45s ==='
    """
    counts = {"passed": 0, "failed": 0, "total": 0}
    if not output:
        return counts

    passed_match = re.search(r"(\d+)\s+passed", output)
    failed_match = re.search(r"(\d+)\s+failed", output)

    if passed_match:
        counts["passed"] = int(passed_match.group(1))
    if failed_match:
        counts["failed"] = int(failed_match.group(1))

    counts["total"] = counts["passed"] + counts["failed"]
    return counts


def execute_prioritized_tests(
    test_paths: List[str],
    repo_path: str = ".",
    fail_fast: bool = True,
    timeout_seconds: float = 60.0
) -> TestExecutionOutcome:
    """
    Safely executes prioritized tests using Python's pytest via subprocess.
    Uses argument list (shell=False) and strictly validates paths against repo.

    Args:
        test_paths: Ordered list of candidate test file paths.
        repo_path: Path to repository root.
        fail_fast: Whether to pass -x (stop on first failure).
        timeout_seconds: Subprocess timeout ceiling.

    Returns:
        TestExecutionOutcome containing exit code, stdout, stderr, and timings.
    """
    norm_repo = os.path.abspath(repo_path)
    if not test_paths:
        return TestExecutionOutcome(
            executed=False,
            command=[],
            exit_code=0,
            stdout="",
            stderr="",
            duration_seconds=0.0,
            passed_count=0,
            failed_count=0,
            total_executed=0,
            mode="none",
            error_message="No test paths provided to execute."
        )

    # Validate test paths against repository
    valid_paths: List[str] = []
    for tp in test_paths:
        clean_tp = normalize_path(tp)
        full_tp = os.path.join(norm_repo, clean_tp)
        if os.path.isfile(full_tp):
            valid_paths.append(clean_tp)

    if not valid_paths:
        return TestExecutionOutcome(
            executed=False,
            command=[],
            exit_code=1,
            stdout="",
            stderr="",
            duration_seconds=0.0,
            passed_count=0,
            failed_count=0,
            total_executed=0,
            mode="none",
            error_message="None of the specified test paths exist on disk."
        )

    cmd = [sys.executable, "-m", "pytest", "-v"]
    if fail_fast:
        cmd.append("-x")
    cmd.extend(valid_paths)

    start_time = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=norm_repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            timeout=timeout_seconds,
            check=False
        )
        duration = time.time() - start_time
        counts = parse_pytest_counts(proc.stdout)

        return TestExecutionOutcome(
            executed=True,
            command=cmd,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_seconds=round(duration, 3),
            passed_count=counts["passed"],
            failed_count=counts["failed"],
            total_executed=counts["total"],
            mode="prioritized_subset",
            error_message=None if proc.returncode == 0 else f"pytest exited with code {proc.returncode}"
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.time() - start_time
        return TestExecutionOutcome(
            executed=True,
            command=cmd,
            exit_code=-1,
            stdout=exc.stdout or "" if isinstance(exc.stdout, str) else "",
            stderr=exc.stderr or "" if isinstance(exc.stderr, str) else "",
            duration_seconds=round(duration, 3),
            passed_count=0,
            failed_count=0,
            total_executed=0,
            mode="prioritized_subset",
            error_message=f"Test execution timed out after {timeout_seconds} seconds."
        )
    except Exception as exc:
        duration = time.time() - start_time
        return TestExecutionOutcome(
            executed=False,
            command=cmd,
            exit_code=-1,
            stdout="",
            stderr="",
            duration_seconds=round(duration, 3),
            passed_count=0,
            failed_count=0,
            total_executed=0,
            mode="none",
            error_message=f"Failed to launch test runner subprocess: {exc}"
        )


def run_pipeline(
    base_ref: str,
    target_ref: str,
    repo_path: str = ".",
    enable_tinyfish: bool = True,
    execute_tests: bool = True,
    fail_fast: bool = True,
    test_timeout_seconds: float = 60.0,
    test_dir: str = "tests",
    api_key: Optional[str] = None
) -> PipelineResult:
    """
    Executes the end-to-end TestPrioritize AI workflow:
    1. Detects changed files via Git diff.
    2. Maps changed source files to candidate tests.
    3. Gathers dependency intelligence via TinyFish if enabled and applicable.
    4. Ranks candidate tests with explainable scoring.
    5. Optionally executes prioritized tests via pytest.

    Args:
        base_ref: Base Git revision (e.g. 'main', 'HEAD~1').
        target_ref: Target Git revision (e.g. 'feature-branch', 'HEAD').
        repo_path: Path to target repository root.
        enable_tinyfish: Whether to perform TinyFish dependency research.
        execute_tests: Whether to execute the ranked tests via pytest.
        fail_fast: Whether to stop pytest on the first failure (-x).
        test_timeout_seconds: Timeout ceiling for test execution.
        test_dir: Subdirectory containing test files.
        api_key: Optional explicit TinyFish API key.

    Returns:
        PipelineResult with all pipeline artifacts, timings, and statuses.
    """
    start_wall_time = time.time()
    norm_repo = os.path.abspath(repo_path)

    # Step 1: Detect changed files using diff_checker
    try:
        changed_files = get_changed_files(base_ref, target_ref, repo_path=norm_repo)
    except GitDiffError as err:
        duration = time.time() - start_wall_time
        return PipelineResult(
            status=STATUS_GIT_ERROR,
            duration_seconds=round(duration, 3),
            summary=f"Git change detection failed: {err}",
            error_message=str(err)
        )
    except Exception as err:
        duration = time.time() - start_wall_time
        return PipelineResult(
            status=STATUS_ERROR,
            duration_seconds=round(duration, 3),
            summary=f"Unexpected error in change detection: {err}",
            error_message=str(err)
        )

    if not changed_files:
        duration = time.time() - start_wall_time
        return PipelineResult(
            status=STATUS_NO_CHANGES,
            changed_files=[],
            duration_seconds=round(duration, 3),
            summary=f"No changed files detected between revision '{base_ref}' and '{target_ref}'."
        )

    changed_paths = [c.path for c in changed_files]

    # Step 2: Map changed source files to candidate test files
    mapping_results = map_changed_sources_to_tests(
        changed_files=changed_paths,
        repo_path=norm_repo,
        test_dir=test_dir
    )

    # Step 3: Run TinyFish Dependency Intelligence (if enabled)
    dep_report: Optional[DependencyIntelligenceReport] = None
    if enable_tinyfish:
        try:
            dep_report = analyze_dependency_risks(
                changed_files=changed_paths,
                repo_path=norm_repo,
                base_ref=base_ref,
                target_ref=target_ref,
                api_key=api_key
            )
        except Exception:
            dep_report = None

    # Step 4: Rank candidate tests using ranking_engine
    ranking_result = rank_tests(
        mapping_results=mapping_results,
        dependency_report=dep_report
    )

    if not ranking_result.ranked_tests:
        duration = time.time() - start_wall_time
        return PipelineResult(
            status=STATUS_NO_CANDIDATE_TESTS,
            changed_files=changed_files,
            mapping_results=mapping_results,
            dependency_report=dep_report,
            ranking_result=ranking_result,
            execution_outcome=None,
            duration_seconds=round(duration, 3),
            summary="Changed files were detected, but no candidate test mappings were found."
        )

    prioritized_test_paths = ranking_result.test_paths

    # Step 5: Safe execution of prioritized tests via pytest
    exec_outcome: Optional[TestExecutionOutcome] = None
    if execute_tests:
        exec_outcome = execute_prioritized_tests(
            test_paths=prioritized_test_paths,
            repo_path=norm_repo,
            fail_fast=fail_fast,
            timeout_seconds=test_timeout_seconds
        )

    duration = time.time() - start_wall_time

    # Determine final pipeline status
    if exec_outcome and exec_outcome.exit_code != 0:
        if exec_outcome.exit_code == -1 and "timed out" in (exec_outcome.error_message or ""):
            final_status = STATUS_TIMEOUT
            summary = (
                f"Prioritized {len(prioritized_test_paths)} test(s), but execution timed out "
                f"after {test_timeout_seconds}s."
            )
        else:
            final_status = STATUS_TEST_FAILURE
            summary = (
                f"Prioritized test execution caught failure: {exec_outcome.failed_count} failed, "
                f"{exec_outcome.passed_count} passed out of {exec_outcome.total_executed} run."
            )
    else:
        final_status = STATUS_SUCCESS
        exec_summary = ""
        if exec_outcome and exec_outcome.executed:
            exec_summary = f" All {exec_outcome.passed_count} prioritized test(s) passed."
        summary = (
            f"Successfully prioritized {len(prioritized_test_paths)} test file(s) for "
            f"{len(changed_files)} changed file(s).{exec_summary}"
        )

    return PipelineResult(
        status=final_status,
        changed_files=changed_files,
        mapping_results=mapping_results,
        dependency_report=dep_report,
        ranking_result=ranking_result,
        execution_outcome=exec_outcome,
        duration_seconds=round(duration, 3),
        summary=summary,
        error_message=exec_outcome.error_message if exec_outcome and exec_outcome.exit_code != 0 else None
    )
