"""
demo_manager.py
Part of TestPrioritize AI.

Unified manager for demo repositories, interactive file selection,
reproducible regression scenarios, and isolated, non-destructive execution.
Guarantees original demo repositories under demo_repos/ are never mutated.
"""

import ast
import json
import os
import re
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

    # Selection Mode & Granularity
    selection_mode: str = "all"
    selected_count: int = 0
    available_candidates_count: int = 0
    subset_warning: Optional[str] = None


def get_all_demo_repos() -> List[DemoRepoInfo]:
    """
    Discovers all 4 demo repositories under demo_repos/ and returns their descriptors.
    """
    # Auto-initialize demo repos if missing or unpopulated (e.g. fresh cloud deployment)
    needs_setup = not os.path.exists(DEMO_REPOS_ROOT)
    if not needs_setup:
        for rid in ("ecommerce", "auth_service", "payment_gateway", "booking_platform"):
            rpath = os.path.join(DEMO_REPOS_ROOT, rid)
            test_dir = os.path.join(rpath, "tests")
            git_dir = os.path.join(rpath, ".git")
            if not os.path.isdir(rpath) or not os.path.isdir(test_dir) or not os.path.exists(git_dir):
                needs_setup = True
                break

    if needs_setup:
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


def get_modified_functions_from_diff(diff_text: str, source_path: str) -> Set[str]:
    """
    Parses a unified git diff and the target Python source file AST.
    Returns the set of function/method names that contain modified lines in the diff.
    """
    if not os.path.exists(source_path) or not diff_text:
        return set()
    try:
        with open(source_path, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read())
    except Exception:
        return set()

    func_ranges = {node.name: (node.lineno, getattr(node, "end_lineno", node.lineno + 50))
                   for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}

    changed_lines = set()
    hunk_pattern = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
    curr_line = 0
    in_target = False
    source_base = os.path.basename(source_path)

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            in_target = (source_base in line)
            continue
        if not in_target:
            continue
        m = hunk_pattern.match(line)
        if m:
            curr_line = int(m.group(1))
            continue
        if line.startswith("+") and not line.startswith("+++"):
            changed_lines.add(curr_line)
            curr_line += 1
        elif line.startswith("-"):
            pass
        else:
            curr_line += 1

    return {fn for fn, (s, e) in func_ranges.items() if any(s <= l <= e for l in changed_lines)}


def extract_diff_keywords(diff_text: str) -> Set[str]:
    """
    Extracts non-trivial domain and behavioral tokens from added/removed lines in a git diff.
    """
    keywords: Set[str] = set()
    if not diff_text:
        return keywords
    for line in diff_text.splitlines():
        if (line.startswith("+") and not line.startswith("+++")) or (line.startswith("-") and not line.startswith("---")):
            words = re.findall(r"[a-zA-Z_]\w*", line)
            for w in words:
                w_lower = w.lower()
                if len(w) >= 3 and w_lower not in ("def", "return", "self", "none", "true", "false", "int", "float", "str", "list", "dict", "raise"):
                    keywords.add(w_lower)
    return keywords


@dataclass
class TestFunctionInfo:
    test_file: str
    func_name: str
    called_symbols: Set[str]
    docstring_and_body_tokens: Set[str]
    is_direct_file: bool


def extract_test_functions_detailed(test_file: str, full_test_path: str, is_direct_file: bool, file_content: Optional[str] = None) -> List[TestFunctionInfo]:
    """
    Parses a test file with AST and extracts function names, called symbols,
    and lexical/docstring tokens for granular relevance scoring.
    """
    if file_content is None:
        if not os.path.exists(full_test_path):
            return []
        try:
            with open(full_test_path, "r", encoding="utf-8", errors="replace") as f:
                code_text = f.read()
        except Exception:
            return []
    else:
        code_text = file_content

    try:
        tree = ast.parse(code_text)
    except Exception:
        return []

    results = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            called = {sub.func.id if isinstance(sub.func, ast.Name) else sub.func.attr
                      for sub in ast.walk(node) if isinstance(sub, ast.Call) and isinstance(sub.func, (ast.Name, ast.Attribute))}

            # Extract tokens from function name, string literals, and identifier names
            body_tokens = set(re.findall(r"[a-zA-Z_]\w*", node.name.lower()))
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    body_tokens.update(w.lower() for w in re.findall(r"[a-zA-Z_]\w*", sub.value))
                elif isinstance(sub, ast.Name):
                    body_tokens.add(sub.id.lower())

            results.append(TestFunctionInfo(
                test_file=test_file,
                func_name=node.name,
                called_symbols=called,
                docstring_and_body_tokens=body_tokens,
                is_direct_file=is_direct_file
            ))
    return results


def build_prioritized_test_targets(
    repo_path: str,
    ranking_result: RankingResult,
    changed_files: List[str],
    diff_text: str = ""
) -> List[str]:
    """
    Builds an execution target list where candidate tests are scored and ordered
    based on AST call relevance and diff behavioral keyword overlap.

    If no diff is provided, preserves candidate file paths in ranked order.
    If diff is provided:
    1. Identifies modified functions and diff behavioral tokens.
    2. Scores individual test functions across direct and dependency-related files.
    3. Prioritizes test functions directly exercising modified behavior ahead of unrelated tests.
    """
    if not diff_text or not ranking_result.ranked_tests:
        all_discovered = set(discover_test_files(repo_path, "tests"))
        seen_files = set()
        ordered_targets = []
        for item in ranking_result.ranked_tests:
            ordered_targets.append(item.test_file)
            seen_files.add(item.test_file)
        for tf in sorted(list(all_discovered)):
            if tf not in seen_files:
                ordered_targets.append(tf)
        return ordered_targets

    # 1. Identify modified functions in changed source files
    modified_symbols: Set[str] = set()
    for cf in changed_files:
        full_src = os.path.join(repo_path, cf)
        mod_fn = get_modified_functions_from_diff(diff_text, full_src)
        modified_symbols.update(mod_fn)

    diff_keywords = extract_diff_keywords(diff_text)

    # 2. Extract detailed metadata for tests in candidate files
    candidate_files = {item.test_file: item for item in ranking_result.ranked_tests}
    direct_files = {item.test_file for item in ranking_result.ranked_tests if item.priority == "HIGH" or item.score >= 50}

    all_test_funcs: List[TestFunctionInfo] = []
    processed_files: Set[str] = set()

    for item in ranking_result.ranked_tests:
        tf = item.test_file
        processed_files.add(tf)
        full_tf = os.path.join(repo_path, tf)
        funcs = extract_test_functions_detailed(
            test_file=tf,
            full_test_path=full_tf,
            is_direct_file=(tf in direct_files)
        )
        all_test_funcs.extend(funcs)

    # 3. Score each test function based on AST call connection and diff overlap
    scored_tests: List[Tuple[float, str]] = []
    for tf_info in all_test_funcs:
        node_id = f"{tf_info.test_file}::{tf_info.func_name}"
        score = 0.0

        # Direct call to modified function (+100)
        has_call = bool(tf_info.called_symbols & modified_symbols)
        if has_call:
            score += 100.0

        # Diff token overlap (+10 per matching behavioral keyword)
        overlap = len(tf_info.docstring_and_body_tokens & diff_keywords)
        score += min(overlap * 10.0, 50.0)

        # Direct file bonus (+20)
        if tf_info.is_direct_file:
            score += 20.0

        scored_tests.append((score, node_id))

    # Sort scored tests descending by score
    scored_tests.sort(key=lambda x: x[0], reverse=True)

    ordered_targets: List[str] = [node_id for score, node_id in scored_tests]

    # Append remaining test files not in candidate rankings
    all_discovered = sorted(list(discover_test_files(repo_path, "tests")))
    for tf in all_discovered:
        if tf not in processed_files:
            ordered_targets.append(tf)

    return ordered_targets


@dataclass(frozen=True)
class TestCandidateItem:
    """
    Represents an individual selectable test candidate (node ID or test file)
    with score, priority tier, and explainable rationale.
    """
    node_id: str
    test_file: str
    func_name: Optional[str]
    score: int
    priority: str
    explanation: str
    is_node: bool = True


def get_available_test_candidates(
    repo_id: str,
    changed_files: List[str],
    scenario_id: Optional[str] = None,
    repo_path_override: Optional[str] = None
) -> List[TestCandidateItem]:
    """
    Returns the deterministic, ordered list of candidate test items (pytest node IDs
    or test files) available for the current repository and changed files.
    Each item contains transparent score, priority tier, and plain-English explanation.
    Used by Streamlit UI and automated tests for Top-N and Manual test selection modes.
    """
    repos = {r.id: r for r in get_all_demo_repos()}
    if repo_id not in repos:
        return []

    target_repo = repos[repo_id]
    src_path = repo_path_override or target_repo.path

    active_scenario = None
    if scenario_id:
        for sc in target_repo.scenarios:
            if sc.get("id") == scenario_id:
                active_scenario = sc
                break

    effective_changed_files = (active_scenario.get("expected_changed_files") if active_scenario else None) or changed_files
    if not effective_changed_files:
        effective_changed_files = changed_files

    diff_text = ""
    if active_scenario and active_scenario.get("base_ref") and active_scenario.get("target_ref"):
        b_ref = active_scenario["base_ref"]
        t_ref = active_scenario["target_ref"]
        res_d = subprocess.run(["git", "diff", f"{b_ref}..{t_ref}"], cwd=src_path, capture_output=True, text=True)
        if res_d.returncode == 0:
            diff_text = res_d.stdout

    mapping_results = map_changed_sources_to_tests(
        changed_files=effective_changed_files,
        repo_path=src_path,
        test_dir="tests"
    )
    ranking_result = rank_tests(mapping_results)

    # 1. Identify modified functions in changed source files
    modified_symbols: Set[str] = set()
    for cf in effective_changed_files:
        full_src = os.path.join(src_path, cf)
        if diff_text:
            mod_fn = get_modified_functions_from_diff(diff_text, full_src)
            modified_symbols.update(mod_fn)
        elif os.path.exists(full_src):
            try:
                with open(full_src, "r", encoding="utf-8", errors="replace") as f:
                    t = ast.parse(f.read())
                for node in t.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        modified_symbols.add(node.name)
            except Exception:
                pass

    diff_keywords = extract_diff_keywords(diff_text)
    candidate_file_map = {item.test_file: item for item in ranking_result.ranked_tests}
    direct_files = {item.test_file for item in ranking_result.ranked_tests if item.priority == "HIGH" or item.score >= 50}

    target_branch = active_scenario.get("target_ref") if (active_scenario and not repo_path_override) else None

    candidates: List[TestCandidateItem] = []
    processed_files: Set[str] = set()

    for item in ranking_result.ranked_tests:
        tf = item.test_file
        processed_files.add(tf)
        full_tf = os.path.join(src_path, tf)
        file_content = None
        if target_branch:
            r_show = subprocess.run(["git", "show", f"{target_branch}:{tf}"], cwd=src_path, capture_output=True, text=True)
            if r_show.returncode == 0:
                file_content = r_show.stdout

        funcs = extract_test_functions_detailed(
            test_file=tf,
            full_test_path=full_tf,
            is_direct_file=(tf in direct_files),
            file_content=file_content
        )

        for tf_info in funcs:
            node_id = f"{tf_info.test_file}::{tf_info.func_name}"
            has_call = bool(tf_info.called_symbols & modified_symbols)
            overlap = len(tf_info.docstring_and_body_tokens & diff_keywords) if diff_keywords else 0

            # Score calculation
            if has_call and overlap > 0:
                raw_score = 95 + min(overlap * 2, 5)
                priority = "HIGH"
                exp = f"High AST relevance: Directly exercises modified behavior ({', '.join(sorted(list(tf_info.called_symbols & modified_symbols)))}) with matching behavioral parameters."
            elif has_call:
                raw_score = 85
                priority = "HIGH"
                exp = f"Direct AST call to modified function: {', '.join(sorted(list(tf_info.called_symbols & modified_symbols)))}."
            elif tf_info.is_direct_file:
                raw_score = item.score
                priority = item.priority
                exp = f"Direct module candidate: {item.explanation}"
            else:
                raw_score = item.score
                priority = item.priority
                exp = f"Dependency candidate: {item.explanation}"

            candidates.append(TestCandidateItem(
                node_id=node_id,
                test_file=tf,
                func_name=tf_info.func_name,
                score=raw_score,
                priority=priority,
                explanation=exp,
                is_node=True
            ))

    # Append tests from remaining unranked test files
    all_discovered = sorted(list(discover_test_files(src_path, "tests")))
    for tf in all_discovered:
        if tf not in processed_files:
            full_tf = os.path.join(src_path, tf)
            file_content = None
            if target_branch:
                r_show = subprocess.run(["git", "show", f"{target_branch}:{tf}"], cwd=src_path, capture_output=True, text=True)
                if r_show.returncode == 0:
                    file_content = r_show.stdout
            funcs = extract_test_functions_detailed(
                test_file=tf,
                full_test_path=full_tf,
                is_direct_file=False,
                file_content=file_content
            )
            for tf_info in funcs:
                node_id = f"{tf_info.test_file}::{tf_info.func_name}"
                candidates.append(TestCandidateItem(
                    node_id=node_id,
                    test_file=tf,
                    func_name=tf_info.func_name,
                    score=10,
                    priority="LOW",
                    explanation=f"Unrelated suite test in {tf}.",
                    is_node=True
                ))

    # Sort descending by score, tiebreak by node_id
    candidates.sort(key=lambda c: (-c.score, c.node_id))
    return candidates


def execute_demo_scenario(
    repo_id: str,
    changed_files: List[str],
    scenario_id: Optional[str] = None,
    mode: str = "benchmark",
    fail_fast: bool = True,
    timeout_seconds: float = 60.0,
    selection_mode: str = "all",
    top_n: Optional[int] = None,
    selected_test_ids: Optional[List[str]] = None
) -> IsolatedRunReport:
    """
    Executes a demo run in a strictly isolated temporary workspace with optional
    user-controlled test selection (Top-N or Manual selection).

    Guarantees:
    - Never mutates the original demo repository.
    - Each benchmark mode runs in an independent, pristine temporary clone so neither
      run mutates state that affects the other.
    - Captures high-resolution monotonic timestamps for all test lifecycle events.
    - Selected test subset is applied consistently to both standard and prioritized runs.
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

    # Effective changed files
    if active_scenario and active_scenario.get("expected_changed_files"):
        effective_changed_files = active_scenario["expected_changed_files"]
    else:
        effective_changed_files = changed_files

    # Extract git diff text if scenario has revisions
    diff_text = ""
    if active_scenario and active_scenario.get("base_ref") and active_scenario.get("target_ref"):
        b_ref = active_scenario["base_ref"]
        t_ref = active_scenario["target_ref"]
        res_d = subprocess.run(["git", "diff", f"{b_ref}..{t_ref}"], cwd=src_path, capture_output=True, text=True)
        if res_d.returncode == 0:
            diff_text = res_d.stdout

    # Step 1: Perform static analysis on effective changed files (Monotonic clock)
    t0 = time.perf_counter()
    mapping_results = map_changed_sources_to_tests(
        changed_files=effective_changed_files,
        repo_path=src_path,
        test_dir="tests"
    )
    ranking_result = rank_tests(mapping_results)
    analysis_overhead = time.perf_counter() - t0

    # Retrieve all available candidate items
    available_candidates = get_available_test_candidates(
        repo_id=repo_id,
        changed_files=effective_changed_files,
        scenario_id=scenario_id
    )
    total_candidates_count = len(available_candidates)

    # Apply user-controlled test selection
    subset_warning: Optional[str] = None
    if selection_mode == "top_n":
        if top_n is None or top_n < 1:
            raise ValueError(f"Top-N selection mode requires integer N >= 1, got {top_n}.")
        effective_n = min(top_n, total_candidates_count)
        selected_candidates = available_candidates[:effective_n]
        pri_targets = [c.node_id for c in selected_candidates]
        std_targets = sorted(list(pri_targets))
        selected_count = len(pri_targets)
        subset_warning = (
            f"Top-{selected_count} Subset Active: Executing {selected_count} of {total_candidates_count} available candidates. "
            f"Unselected tests were not executed; this run does not verify the entire application."
        )
    elif selection_mode == "manual":
        if not selected_test_ids:
            raise ValueError("Empty test selection. Please select at least one test candidate to execute.")
        selected_set = set(selected_test_ids)
        # Preserve prioritized ranking order for the selected subset
        selected_candidates = [c for c in available_candidates if c.node_id in selected_set or c.test_file in selected_set]
        if not selected_candidates:
            raise ValueError("None of the selected test IDs match available candidates in this repository.")
        pri_targets = [c.node_id for c in selected_candidates]
        std_targets = sorted(list(pri_targets))
        selected_count = len(pri_targets)
        subset_warning = (
            f"Manual Subset Active: Executing {selected_count} of {total_candidates_count} available candidates. "
            f"Unselected tests were not executed; this run does not verify the entire application."
        )
    else:
        # Default: all relevant candidates
        if scenario_id is None and not diff_text:
            ordered_ranked_files = [item.test_file for item in ranking_result.ranked_tests]
            all_discovered_files = sorted(list(discover_test_files(src_path, "tests")))
            pri_targets = ordered_ranked_files + [f for f in all_discovered_files if f not in set(ordered_ranked_files)]
            std_targets = all_discovered_files
        else:
            pri_targets = [c.node_id for c in available_candidates]
            std_targets = sorted(list(discover_test_files(src_path, "tests")))
        selected_count = len(pri_targets)
        subset_warning = None

    # Step 2: Create isolated temp directories and execute tests
    # Use distinct fresh clones for standard and prioritized runs to guarantee neither
    # run can poison or mutate state for the other.
    std_result: Optional[ModeExecutionResult] = None
    pri_result: Optional[ModeExecutionResult] = None

    if mode in ("standard", "benchmark"):
        with tempfile.TemporaryDirectory() as td_std:
            shutil.copytree(src_path, td_std, dirs_exist_ok=True)
            if active_scenario and active_scenario.get("target_ref"):
                t_ref = active_scenario["target_ref"]
                subprocess.run(["git", "checkout", t_ref], cwd=td_std, capture_output=True, check=False)
            std_result = run_isolated_pytest_command(
                temp_dir=td_std,
                test_targets=std_targets,
                mode_name="standard",
                fail_fast=fail_fast,
                timeout_seconds=timeout_seconds
            )

    if mode in ("prioritized", "benchmark"):
        with tempfile.TemporaryDirectory() as td_pri:
            shutil.copytree(src_path, td_pri, dirs_exist_ok=True)
            if active_scenario and active_scenario.get("target_ref"):
                t_ref = active_scenario["target_ref"]
                subprocess.run(["git", "checkout", t_ref], cwd=td_pri, capture_output=True, check=False)

            # If running all candidates in a scenario, resolve dynamic targets from branch
            if selection_mode == "all" and active_scenario and active_scenario.get("target_ref"):
                branch_candidates = get_available_test_candidates(
                    repo_id=repo_id,
                    changed_files=effective_changed_files,
                    scenario_id=scenario_id,
                    repo_path_override=td_pri
                )
                actual_pri_targets = [c.node_id for c in branch_candidates]
            else:
                actual_pri_targets = pri_targets

            pri_result = run_isolated_pytest_command(
                temp_dir=td_pri,
                test_targets=actual_pri_targets,
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
        benchmark_summary=summary_text,
        selection_mode=selection_mode,
        selected_count=selected_count,
        available_candidates_count=total_candidates_count,
        subset_warning=subset_warning
    )
