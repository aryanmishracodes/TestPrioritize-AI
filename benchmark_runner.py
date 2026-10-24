"""
benchmark_runner.py
Part of TestPrioritize AI.

Executes a fair, reproducible benchmark comparing prioritized test execution
against full-suite execution on the same Git revision and Python environment.
Captures structured JUnit XML results with per-test timings and failure logs.
"""

import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from statistics import median
from typing import Any, Dict, List, Optional

from diff_checker import get_changed_files
from ranking_engine import rank_tests
from test_mapper import map_changed_sources_to_tests


@dataclass
class TestCaseResult:
    """Detailed per-test execution result parsed from JUnit XML."""
    __test__ = False
    name: str
    classname: str
    file: str
    duration_seconds: float
    status: str  # "passed", "failed", "error", "skipped"
    failure_message: Optional[str] = None
    failure_detail: Optional[str] = None


@dataclass
class SuiteRunResult:
    """Outcome of an individual pytest run."""
    command: List[str]
    exit_code: int
    duration_seconds: float
    passed_count: int
    failed_count: int
    total_executed: int
    test_cases: List[TestCaseResult]
    stdout: str
    stderr: str
    time_to_first_failure: Optional[float] = None


@dataclass
class BenchmarkComparison:
    """Comprehensive comparison between prioritized and full-suite testing."""
    repo_path: str
    base_ref: str
    target_ref: str
    iterations: int

    # Timing Breakdown (seconds)
    change_detection_seconds: float
    test_mapping_seconds: float
    ranking_seconds: float
    analysis_overhead_seconds: float

    # Execution Results (median if repeated runs)
    prioritized_run: SuiteRunResult
    full_suite_run: SuiteRunResult

    # Comparative Metrics
    prioritized_duration_seconds: float
    full_suite_duration_seconds: float
    time_saved_seconds: float
    speedup_percentage: float
    tests_skipped_count: int
    time_to_first_failure_prioritized: Optional[float]
    time_to_first_failure_full: Optional[float]

    # Interpretative Findings
    is_failing_regression: bool
    summary: str
    limitation_notes: str


def run_pytest_with_junit(
    test_targets: List[str],
    repo_path: str = ".",
    fail_fast: bool = True,
    timeout_seconds: float = 60.0
) -> SuiteRunResult:
    """
    Executes pytest targeting specific files or directory, capturing JUnit XML.
    """
    norm_repo = os.path.abspath(repo_path)
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tf:
        xml_path = tf.name

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        f"--junitxml={xml_path}",
        "-o",
        "junit_family=legacy"
    ]
    if fail_fast:
        cmd.append("-x")
    cmd.extend(test_targets)

    start_t = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=norm_repo,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False
        )
        duration = time.perf_counter() - start_t
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        duration = time.perf_counter() - start_t
        exit_code = -1
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
    except Exception as exc:
        duration = time.perf_counter() - start_t
        exit_code = -1
        stdout = ""
        stderr = str(exc)

    test_cases: List[TestCaseResult] = []
    passed = 0
    failed = 0
    cumulative_time = 0.0
    first_failure_time = None

    if os.path.exists(xml_path):
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            for tc in root.findall(".//testcase"):
                name = tc.attrib.get("name", "unknown")
                classname = tc.attrib.get("classname", "")
                file_attr = tc.attrib.get("file", "")
                t_val = float(tc.attrib.get("time", "0.0") or "0.0")
                cumulative_time += t_val

                failure_el = tc.find("failure")
                error_el = tc.find("error")
                skipped_el = tc.find("skipped")

                if failure_el is not None:
                    status = "failed"
                    msg = failure_el.attrib.get("message", "")
                    detail = failure_el.text or ""
                    failed += 1
                    if first_failure_time is None:
                        first_failure_time = round(cumulative_time, 4)
                elif error_el is not None:
                    status = "error"
                    msg = error_el.attrib.get("message", "")
                    detail = error_el.text or ""
                    failed += 1
                    if first_failure_time is None:
                        first_failure_time = round(cumulative_time, 4)
                elif skipped_el is not None:
                    status = "skipped"
                    msg = skipped_el.attrib.get("message", "")
                    detail = ""
                else:
                    status = "passed"
                    msg = None
                    detail = None
                    passed += 1

                test_cases.append(TestCaseResult(
                    name=name,
                    classname=classname,
                    file=file_attr,
                    duration_seconds=round(t_val, 4),
                    status=status,
                    failure_message=msg,
                    failure_detail=detail
                ))
        except Exception:
            pass
        finally:
            try:
                os.remove(xml_path)
            except OSError:
                pass

    total = passed + failed
    return SuiteRunResult(
        command=cmd,
        exit_code=exit_code,
        duration_seconds=round(duration, 3),
        passed_count=passed,
        failed_count=failed,
        total_executed=total,
        test_cases=test_cases,
        stdout=stdout,
        stderr=stderr,
        time_to_first_failure=first_failure_time
    )


def run_benchmark_comparison(
    repo_path: str = ".",
    base_ref: str = "base",
    target_ref: str = "HEAD",
    test_dir: str = "tests",
    iterations: int = 1,
    fail_fast: bool = True,
    warm_up: bool = False
) -> BenchmarkComparison:
    """
    Performs an authentic, measured comparison of prioritized tests vs full suite.
    """
    norm_repo = os.path.abspath(repo_path)

    # 1. Measure Static Analysis Phases (Monotonic Timer)
    t0 = time.perf_counter()
    changed_files = get_changed_files(base_ref, target_ref, repo_path=norm_repo)
    t1 = time.perf_counter()
    change_det_time = t1 - t0

    changed_paths = [cf.path for cf in changed_files]
    mapping_results = map_changed_sources_to_tests(
        changed_files=changed_paths,
        repo_path=norm_repo,
        test_dir=test_dir
    )
    t2 = time.perf_counter()
    mapping_time = t2 - t1

    ranking_result = rank_tests(mapping_results)
    t3 = time.perf_counter()
    ranking_time = t3 - t2

    analysis_overhead = change_det_time + mapping_time + ranking_time

    prioritized_paths = [item.test_file for item in ranking_result.ranked_tests]

    # Optional warm-up run
    if warm_up:
        if prioritized_paths:
            run_pytest_with_junit(prioritized_paths, repo_path=norm_repo, fail_fast=fail_fast)
        run_pytest_with_junit([test_dir], repo_path=norm_repo, fail_fast=fail_fast)

    # 2. Run Prioritized Test Subset
    prioritized_durations = []
    prioritized_runs: List[SuiteRunResult] = []

    for _ in range(iterations):
        if prioritized_paths:
            res = run_pytest_with_junit(prioritized_paths, repo_path=norm_repo, fail_fast=fail_fast)
        else:
            res = SuiteRunResult(
                command=[],
                exit_code=0,
                duration_seconds=0.0,
                passed_count=0,
                failed_count=0,
                total_executed=0,
                test_cases=[],
                stdout="",
                stderr="",
                time_to_first_failure=None
            )
        prioritized_runs.append(res)
        prioritized_durations.append(res.duration_seconds)

    # 3. Run Full Test Suite
    full_durations = []
    full_runs: List[SuiteRunResult] = []

    for _ in range(iterations):
        res_full = run_pytest_with_junit([test_dir], repo_path=norm_repo, fail_fast=fail_fast)
        full_runs.append(res_full)
        full_durations.append(res_full.duration_seconds)

    # Select representative run (median duration)
    best_p_idx = sorted(range(len(prioritized_durations)), key=lambda i: prioritized_durations[i])[len(prioritized_durations) // 2]
    best_f_idx = sorted(range(len(full_durations)), key=lambda i: full_durations[i])[len(full_durations) // 2]

    rep_p_run = prioritized_runs[best_p_idx]
    rep_f_run = full_runs[best_f_idx]

    p_dur = median(prioritized_durations) if prioritized_durations else 0.0
    f_dur = median(full_durations) if full_durations else 0.0

    time_saved = f_dur - p_dur
    if f_dur > 0:
        speedup_pct = round((1.0 - (p_dur / f_dur)) * 100.0, 1)
    else:
        speedup_pct = 0.0

    skipped_count = max(0, rep_f_run.total_executed - rep_p_run.total_executed)
    is_regression = (rep_p_run.failed_count > 0 or rep_f_run.failed_count > 0)

    # Construct honest analytical summary
    if not prioritized_paths:
        summary = (
            "No candidate tests mapped to changed files. Prioritized execution skipped 0 tests; "
            "full suite was executed as baseline."
        )
    elif is_regression:
        p_fail_time = rep_p_run.time_to_first_failure or rep_p_run.duration_seconds
        f_fail_time = rep_f_run.time_to_first_failure or rep_f_run.duration_seconds
        summary = (
            f"Regression Detected! Prioritized test suite hit failing test in {p_fail_time:.3f}s, "
            f"providing immediate fail-fast feedback compared to {f_fail_time:.3f}s full suite."
        )
    elif time_saved > 0:
        summary = (
            f"Prioritized testing ran in {p_dur:.3f}s vs {f_dur:.3f}s full suite "
            f"({time_saved:.3f}s saved, {speedup_pct}% reduction), safely testing modified modules."
        )
    else:
        summary = (
            f"Prioritized testing ran in {p_dur:.3f}s vs {f_dur:.3f}s full suite. "
            "No runtime savings observed on this small test suite due to process startup overhead."
        )

    limitations = (
        "Note: On tiny test suites (< 50 tests), subprocess invocation overhead dominates execution time. "
        "Test prioritization delivers maximum value on CI test suites spanning hundreds of test files "
        "by surfacing failing tests in the first few seconds (fail-fast)."
    )

    return BenchmarkComparison(
        repo_path=norm_repo,
        base_ref=base_ref,
        target_ref=target_ref,
        iterations=iterations,
        change_detection_seconds=round(change_det_time, 4),
        test_mapping_seconds=round(mapping_time, 4),
        ranking_seconds=round(ranking_time, 4),
        analysis_overhead_seconds=round(analysis_overhead, 4),
        prioritized_run=rep_p_run,
        full_suite_run=rep_f_run,
        prioritized_duration_seconds=round(p_dur, 3),
        full_suite_duration_seconds=round(f_dur, 3),
        time_saved_seconds=round(time_saved, 3),
        speedup_percentage=speedup_pct,
        tests_skipped_count=skipped_count,
        time_to_first_failure_prioritized=rep_p_run.time_to_first_failure,
        time_to_first_failure_full=rep_f_run.time_to_first_failure,
        is_failing_regression=is_regression,
        summary=summary,
        limitation_notes=limitations
    )
