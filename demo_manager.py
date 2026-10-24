"""
demo_manager.py
Part of TestPrioritize AI.

Unified manager for demo repositories, interactive file selection,
reproducible regression scenarios, and isolated, non-destructive execution.
Guarantees original demo repositories under demo_repos/ are never mutated.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from ranking_engine import RankingResult, rank_tests
from test_mapper import (
    SourceMappingResult,
    discover_test_files,
    map_changed_sources_to_tests,
    normalize_path,
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DEMO_REPOS_ROOT = os.path.join(BASE_DIR, "demo_repos")

# Plugin code embedded into temporary run environments for high-resolution monotonic timing
TIMING_RECORDER_CODE = '''
import time, json, os

class TimingRecorder:
    def __init__(self, out_path):
        self.out_path = out_path
        self.start_time = None
        self.first_failure_time = None
        self.first_failure_node = None
        self.events = []

    def pytest_sessionstart(self, session):
        self.start_time = time.perf_counter()

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or (report.when == "setup" and report.failed):
            elapsed = time.perf_counter() - self.start_time
            if report.failed and self.first_failure_time is None:
                self.first_failure_time = elapsed
                self.first_failure_node = report.nodeid
            self.events.append({
                "nodeid": report.nodeid,
                "outcome": report.outcome,
                "duration": round(report.duration, 4),
                "elapsed": round(elapsed, 4)
            })

    def pytest_sessionfinish(self, session, exitstatus):
        with open(self.out_path, "w", encoding="utf-8") as f:
            json.dump({
                "total_elapsed": round(time.perf_counter() - self.start_time, 4),
                "first_failure_time": round(self.first_failure_time, 4) if self.first_failure_time is not None else None,
                "first_failure_node": self.first_failure_node,
                "events": self.events
            }, f)

def pytest_configure(config):
    out_path = os.environ.get("TESTPRIORITIZE_TIMING_OUT")
    if out_path:
        config.pluginmanager.register(TimingRecorder(out_path), "timing_recorder")
'''


@dataclass(frozen=True)
class DemoRepoInfo:
    """Descriptor for an available isolated demo repository."""
    id: str
    name: str
    path: str
    description: str
    test_count: int
    modules: List[str]
    scenarios: List[Dict[str, Any]]


@dataclass
class TestEventRecord:
    """Record of a single test execution event captured in monotonic time."""
    nodeid: str
    outcome: str
    duration_seconds: float
    elapsed_seconds: float
    sequence_num: int


@dataclass
class ModeExecutionResult:
    """Detailed results of a test suite execution in a specific mode."""
    mode_name: str
    exit_code: int
    duration_seconds: float
    total_executed: int
    passed_count: int
    failed_count: int
    first_failing_node: Optional[str] = None
    first_failing_position: Optional[int] = None
    tests_passed_before_failure: int = 0
    time_to_first_failure: Optional[float] = None
    ordered_test_targets: List[str] = field(default_factory=list)
    events: List[TestEventRecord] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""


@dataclass
class IsolatedRunReport:
    """Comprehensive, structured report returned after executing a demo run."""
    repo_id: str
    repo_name: str
    changed_files: List[str]
    scenario_id: str
    scenario_title: str
    is_regression: bool
    mode: str  # "standard", "prioritized", or "benchmark"

    # Static Analysis
    analysis_overhead_seconds: float
    mapping_results: List[SourceMappingResult]
    ranking_result: Optional[RankingResult]

    # Execution Outcomes
    standard_run: Optional[ModeExecutionResult] = None
    prioritized_run: Optional[ModeExecutionResult] = None

    # Comparative Metrics (Benchmark mode)
    time_saved_seconds: Optional[float] = None
    time_saved_percentage: Optional[float] = None
    tests_moved_ahead: Optional[int] = None
    total_runtime_difference: Optional[float] = None
    benchmark_summary: str = ""


def get_all_demo_repos() -> List[DemoRepoInfo]:
    """
    Discovers all 4 demo repositories under demo_repos/ and returns their descriptors.
    """
    if not os.path.exists(DEMO_REPOS_ROOT):
        # Auto-initialize if needed
        try:
            from setup_all_demo_repos import setup_all
            setup_all(DEMO_REPOS_ROOT)
        except Exception:
            pass

    repos: List[DemoRepoInfo] = []
    repo_definitions = [
        ("ecommerce", "E-Commerce Platform", "Orders, cart, checkout precision, discounts, and inventory management."),
        ("auth_service", "Authentication Service", "User accounts, token sessions, password hashing, and RBAC privileges."),
        ("payment_gateway", "Payment Gateway", "Credit card validation (Luhn), invoice totals, refunds, and charges."),
        ("booking_platform", "Booking & Scheduling Platform", "Slot scheduling, rate calculations, bookings, and customer alerts.")
    ]

    for rid, name, desc in repo_definitions:
        rpath = os.path.join(DEMO_REPOS_ROOT, rid)
        if not os.path.isdir(rpath):
            continue

        # Count tests
        test_dir = os.path.join(rpath, "tests")
        test_files = discover_test_files(rpath, "tests")

        # Load scenarios
        scenarios_path = os.path.join(rpath, "scenarios.json")
        scenarios = []
        if os.path.exists(scenarios_path):
            try:
                with open(scenarios_path, "r", encoding="utf-8") as sf:
                    scenarios = json.load(sf)
            except Exception:
                scenarios = []

        # Find modules in src/
        src_dir = os.path.join(rpath, "src")
        modules = []
        if os.path.isdir(src_dir):
            for f in sorted(os.listdir(src_dir)):
                if f.endswith(".py") and f != "__init__.py":
                    modules.append(f"src/{f}")

        # Quick count of tests by scanning test files
        test_count = 0
        for tf in test_files:
            full_tf = os.path.join(rpath, tf)
            try:
                with open(full_tf, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("def test_"):
                            test_count += 1
            except Exception:
                pass

        repos.append(DemoRepoInfo(
            id=rid,
            name=name,
            path=rpath,
            description=desc,
            test_count=max(test_count, len(test_files)),
            modules=modules,
            scenarios=scenarios
        ))

    return repos


def list_repo_source_files(repo_path: str) -> List[str]:
    """Scans and returns all candidate Python source files in repo's src/ directory."""
    src_dir = os.path.join(repo_path, "src")
    if not os.path.isdir(src_dir):
        return []
    files: List[str] = []
    for f in sorted(os.listdir(src_dir)):
        if f.endswith(".py") and f != "__init__.py":
            files.append(f"src/{f}")
    return files


def run_isolated_pytest_command(
    temp_dir: str,
    test_targets: List[str],
    mode_name: str,
    fail_fast: bool = True,
    timeout_seconds: float = 60.0
) -> ModeExecutionResult:
    """
    Safely launches pytest in the isolated temporary directory with monotonic timing plugin.
    Captures exact failure node, monotonic time to first failure, per-test duration, and stdout.
    """
    timing_out_path = os.path.join(temp_dir, f"_timing_{mode_name}.json")
    plugin_path = os.path.join(temp_dir, "_timing_plugin.py")
    if not os.path.exists(plugin_path):
        with open(plugin_path, "w", encoding="utf-8") as f:
            f.write(TIMING_RECORDER_CODE)

    env = os.environ.copy()
    env["PYTHONPATH"] = temp_dir
    env["TESTPRIORITIZE_TIMING_OUT"] = timing_out_path

    ini_path = os.path.join(temp_dir, "pytest.ini")
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        "-c",
        ini_path if os.path.exists(ini_path) else "pytest.ini",
        "-p",
        "_timing_plugin"
    ]
    if fail_fast:
        cmd.append("-x")

    cmd.extend(test_targets)

    t_start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=temp_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False
        )
        wall_duration = time.perf_counter() - t_start
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        wall_duration = time.perf_counter() - t_start
        exit_code = -1
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
    except Exception as exc:
        wall_duration = time.perf_counter() - t_start
        exit_code = -1
        stdout = ""
        stderr = str(exc)

    # Parse timing plugin JSON output
    first_fail_node = None
    first_fail_time = None
    events: List[TestEventRecord] = []
    passed = 0
    failed = 0

    if os.path.exists(timing_out_path) and os.path.getsize(timing_out_path) > 0:
        try:
            with open(timing_out_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            first_fail_node = data.get("first_failure_node")
            first_fail_time = data.get("first_failure_time")
            for idx, ev in enumerate(data.get("events", []), 1):
                outcome = ev.get("outcome", "unknown")
                if outcome == "passed":
                    passed += 1
                elif outcome == "failed":
                    failed += 1
                events.append(TestEventRecord(
                    nodeid=ev.get("nodeid", ""),
                    outcome=outcome,
                    duration_seconds=ev.get("duration", 0.0),
                    elapsed_seconds=ev.get("elapsed", 0.0),
                    sequence_num=idx
                ))
        except Exception:
            pass
        finally:
            try:
                os.remove(timing_out_path)
            except OSError:
                pass

    # Compute failure position and passed-before-failure count
    first_fail_pos = None
    passed_before_fail = 0
    if events:
        for idx, ev in enumerate(events, 1):
            if ev.outcome == "failed":
                first_fail_pos = idx
                break
            elif ev.outcome == "passed":
                passed_before_fail += 1

    return ModeExecutionResult(
        mode_name=mode_name,
        exit_code=exit_code,
        duration_seconds=round(wall_duration, 4),
        total_executed=passed + failed,
        passed_count=passed,
        failed_count=failed,
        first_failing_node=first_fail_node,
        first_failing_position=first_fail_pos,
        tests_passed_before_failure=passed_before_fail,
        time_to_first_failure=first_fail_time,
        ordered_test_targets=test_targets,
        events=events,
        stdout=stdout,
        stderr=stderr
    )


def execute_demo_scenario(
    repo_id: str,
    changed_files: List[str],
    scenario_id: Optional[str] = None,
    mode: str = "benchmark",
    fail_fast: bool = True,
    timeout_seconds: float = 60.0
) -> IsolatedRunReport:
    """
    Executes a demo run in a strictly isolated temporary workspace.
    Guarantees demo_repos/ is completely untouched.
    """
    repo_map = {r.id: r for r in get_all_demo_repos()}
    if repo_id not in repo_map:
        raise ValueError(f"Unknown repository ID '{repo_id}'.")

    target_repo = repo_map[repo_id]
    src_path = target_repo.path

    # Locate scenario metadata if specified
    active_scenario: Optional[Dict[str, Any]] = None
    if scenario_id:
        for sc in target_repo.scenarios:
            if sc.get("id") == scenario_id:
                active_scenario = sc
                break

    is_regression = bool(active_scenario and active_scenario.get("is_regression", False))
    scenario_title = active_scenario.get("title", "Ad-Hoc File Selection") if active_scenario else "Custom Changed File"

    # Step 1: Perform static analysis on selected changed files (Monotonic clock)
    t0 = time.perf_counter()
    mapping_results = map_changed_sources_to_tests(
        changed_files=changed_files,
        repo_path=src_path,
        test_dir="tests"
    )
    ranking_result = rank_tests(mapping_results)
    analysis_overhead = time.perf_counter() - t0

    # Determine execution targets:
    # Ranked candidate test files first
    ranked_targets = [item.test_file for item in ranking_result.ranked_tests]
    # Followed by remaining test files in alphabetical order
    all_discovered = discover_test_files(src_path, "tests")
    remaining_targets = [tf for tf in all_discovered if tf not in ranked_targets]
    prioritized_targets = ranked_targets + remaining_targets

    standard_targets = sorted(list(all_discovered))

    # Step 2: Create isolated temp directory and execute tests
    with tempfile.TemporaryDirectory() as td:
        # Copy repo into temp directory
        shutil.copytree(src_path, td, dirs_exist_ok=True)

        # If a scenario with git revision was selected, check it out ONLY inside td
        if active_scenario and active_scenario.get("target_ref"):
            t_ref = active_scenario["target_ref"]
            subprocess.run(["git", "checkout", t_ref], cwd=td, capture_output=True, check=False)

        std_result: Optional[ModeExecutionResult] = None
        pri_result: Optional[ModeExecutionResult] = None

        if mode in ("standard", "benchmark"):
            std_result = run_isolated_pytest_command(
                temp_dir=td,
                test_targets=standard_targets,
                mode_name="standard",
                fail_fast=fail_fast,
                timeout_seconds=timeout_seconds
            )

        if mode in ("prioritized", "benchmark"):
            pri_result = run_isolated_pytest_command(
                temp_dir=td,
                test_targets=prioritized_targets,
                mode_name="prioritized",
                fail_fast=fail_fast,
                timeout_seconds=timeout_seconds
            )

    # Step 3: Compute honest comparative benchmark metrics
    time_saved: Optional[float] = None
    pct_saved: Optional[float] = None
    tests_moved: Optional[int] = None
    total_diff: Optional[float] = None
    summary_text = ""

    if std_result is not None and pri_result is not None:
        total_diff = round(std_result.duration_seconds - pri_result.duration_seconds, 4)

        # Check if both encountered a failure
        std_failed = (std_result.failed_count > 0 and std_result.first_failing_position is not None)
        pri_failed = (pri_result.failed_count > 0 and pri_result.first_failing_position is not None)

        if std_failed and pri_failed:
            std_pos = std_result.first_failing_position
            pri_pos = pri_result.first_failing_position
            tests_moved = std_pos - pri_pos

            std_t = std_result.time_to_first_failure or std_result.duration_seconds
            pri_t = pri_result.time_to_first_failure or pri_result.duration_seconds
            time_saved = round(std_t - pri_t, 4)

            if std_t > 0:
                pct_saved = round(((std_t - pri_t) / std_t) * 100.0, 1)

            if tests_moved > 0:
                summary_text = (
                    f"Regression surfaced {tests_moved} test(s) earlier in prioritized execution "
                    f"(position #{pri_pos} vs #{std_pos} in standard alphabetical execution). "
                    f"Fail-fast time to first failure saved: {time_saved:.4f}s ({pct_saved}% faster)."
                )
            else:
                summary_text = (
                    f"Regression caught at position #{pri_pos} (prioritized) vs #{std_pos} (standard). "
                    f"Time to failure: {pri_t:.4f}s vs {std_t:.4f}s."
                )
        elif not std_failed and not pri_failed:
            summary_text = (
                f"Healthy run: All tests passed cleanly in both modes. "
                f"Prioritized runtime: {pri_result.duration_seconds:.3f}s; "
                f"Standard runtime: {std_result.duration_seconds:.3f}s."
            )
        else:
            summary_text = "Mode execution discrepancy: One mode passed while the other failed."

    elif pri_result is not None:
        if pri_result.failed_count > 0:
            summary_text = (
                f"Prioritized execution caught failure at position #{pri_result.first_failing_position} "
                f"in {pri_result.time_to_first_failure or pri_result.duration_seconds:.3f}s."
            )
        else:
            summary_text = f"Prioritized execution passed all {pri_result.passed_count} tests in {pri_result.duration_seconds:.3f}s."
    elif std_result is not None:
        if std_result.failed_count > 0:
            summary_text = (
                f"Standard execution caught failure at position #{std_result.first_failing_position} "
                f"in {std_result.time_to_first_failure or std_result.duration_seconds:.3f}s."
            )
        else:
            summary_text = f"Standard execution passed all {std_result.passed_count} tests in {std_result.duration_seconds:.3f}s."

    return IsolatedRunReport(
        repo_id=repo_id,
        repo_name=target_repo.name,
        changed_files=changed_files,
        scenario_id=scenario_id or "adhoc",
        scenario_title=scenario_title,
        is_regression=is_regression,
        mode=mode,
        analysis_overhead_seconds=round(analysis_overhead, 4),
        mapping_results=mapping_results,
        ranking_result=ranking_result,
        standard_run=std_result,
        prioritized_run=pri_result,
        time_saved_seconds=time_saved,
        time_saved_percentage=pct_saved,
        tests_moved_ahead=tests_moved,
        total_runtime_difference=total_diff,
        benchmark_summary=summary_text
    )
