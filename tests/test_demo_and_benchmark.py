"""
tests/test_demo_and_benchmark.py
Part of TestPrioritize AI.

Tests demo repository initialization, scenario definitions,
authentic failing regressions, and benchmark comparison mechanics.
"""

import os
import subprocess
import sys
import unittest.mock as mock
import pytest

from benchmark_runner import (
    BenchmarkComparison,
    SuiteRunResult,
    TestCaseResult,
    run_benchmark_comparison,
    run_pytest_with_junit,
)
from demo_scenarios import (
    DEMO_REPO_PATH,
    checkout_scenario_target,
    ensure_demo_repo_exists,
    get_demo_scenarios,
    get_scenario_diff,
)
from pipeline import run_pipeline


@pytest.fixture(scope="module")
def initialized_demo():
    """Ensures demo repository is initialized for testing."""
    assert ensure_demo_repo_exists(DEMO_REPO_PATH) is True
    return DEMO_REPO_PATH


def test_demo_repo_initialization_and_scenarios(initialized_demo):
    """Verifies demo_repo has valid scenario catalogue with 4 scenarios."""
    scenarios = get_demo_scenarios(initialized_demo)
    assert len(scenarios) == 4

    ids = [s.id for s in scenarios]
    assert "cart_enhancement" in ids
    assert "checkout_regression" in ids
    assert "multi_module_pricing" in ids
    assert "dependency_upgrade" in ids


def test_scenario_valid_git_revisions_and_diff(initialized_demo):
    """Verifies each scenario resolves to valid git revisions and produces real diffs."""
    scenarios = get_demo_scenarios(initialized_demo)
    for s in scenarios:
        diff_text = get_scenario_diff(s.base_ref, s.target_ref, initialized_demo)
        assert len(diff_text) > 0
        for expected_file in s.expected_changed_files:
            assert expected_file in diff_text


def test_scenario_1_cart_enhancement_prioritization(initialized_demo):
    """Verifies Scenario 1 prioritizes test_cart.py to Rank 1 with all tests passing."""
    checkout_scenario_target("cart-enhancement", initialized_demo)
    res = run_pipeline(
        base_ref="base",
        target_ref="cart-enhancement",
        repo_path=initialized_demo,
        execute_tests=True,
        enable_tinyfish=False
    )
    assert res.status == "success"
    assert len(res.ranking_result.ranked_tests) >= 1
    top_test = res.ranking_result.ranked_tests[0]
    assert "test_cart.py" in top_test.test_file
    assert top_test.score >= 50
    assert res.execution_outcome.passed_count > 0
    assert res.execution_outcome.failed_count == 0


def test_scenario_2_authentic_failing_regression(initialized_demo):
    """
    Verifies Scenario 2 authentic failing regression:
    - Checkout introduces truncation bug in src/checkout.py
    - Prioritizes tests/test_checkout.py to Rank 1
    - Pytest genuinely catches the failure in test_apply_tax_fractional_precision.
    """
    checkout_scenario_target("checkout-regression", initialized_demo)
    try:
        res = run_pipeline(
            base_ref="base",
            target_ref="checkout-regression",
            repo_path=initialized_demo,
            execute_tests=True,
            fail_fast=True,
            enable_tinyfish=False
        )
        assert res.status == "test_failure"
        assert len(res.ranking_result.ranked_tests) >= 1
        top_test = res.ranking_result.ranked_tests[0]
        assert "test_checkout.py" in top_test.test_file

        outcome = res.execution_outcome
        assert outcome.executed is True
        assert outcome.failed_count >= 1
        assert "test_apply_tax_fractional_precision" in outcome.stdout
    finally:
        checkout_scenario_target("main", initialized_demo)


def test_scenario_3_multi_module_pricing_corroboration(initialized_demo):
    """Verifies Scenario 3 detects changes across multiple modules (cart + pricing)."""
    checkout_scenario_target("bulk-pricing", initialized_demo)
    try:
        res = run_pipeline(
            base_ref="base",
            target_ref="bulk-pricing",
            repo_path=initialized_demo,
            execute_tests=False,
            enable_tinyfish=False
        )
        assert res.status == "success"
        changed_paths = [cf.path for cf in res.changed_files]
        assert "src/cart.py" in changed_paths
        assert "src/pricing.py" in changed_paths
        ranked_files = [t.test_file for t in res.ranking_result.ranked_tests]
        assert any("test_cart.py" in f for f in ranked_files)
        assert any("test_pricing.py" in f for f in ranked_files)
    finally:
        checkout_scenario_target("main", initialized_demo)


def test_run_pytest_with_junit_structured_results(initialized_demo):
    """Verifies JUnit XML parsing extracts per-test durations, names, and status."""
    checkout_scenario_target("main", initialized_demo)
    suite_res = run_pytest_with_junit(["tests/test_cart.py"], repo_path=initialized_demo)
    assert suite_res.exit_code == 0
    assert suite_res.passed_count > 0
    assert suite_res.failed_count == 0
    assert len(suite_res.test_cases) == suite_res.passed_count

    # Check structure of TestCaseResult
    first_tc = suite_res.test_cases[0]
    assert first_tc.status == "passed"
    assert first_tc.duration_seconds >= 0.0
    assert len(first_tc.name) > 0


def test_run_benchmark_comparison_metrics(initialized_demo):
    """Verifies benchmark runner computes analysis overhead, test counts, and durations."""
    checkout_scenario_target("cart-enhancement", initialized_demo)
    try:
        bench = run_benchmark_comparison(
            repo_path=initialized_demo,
            base_ref="base",
            target_ref="cart-enhancement",
            iterations=1,
            fail_fast=True
        )
        assert bench.analysis_overhead_seconds >= 0.0
        assert bench.change_detection_seconds >= 0.0
        assert bench.test_mapping_seconds >= 0.0
        assert bench.ranking_seconds >= 0.0
        assert bench.prioritized_run.total_executed > 0
        assert bench.full_suite_run.total_executed > bench.prioritized_run.total_executed
        assert bench.tests_skipped_count > 0
        assert "Prioritized testing ran in" in bench.summary
    finally:
        checkout_scenario_target("main", initialized_demo)


def test_benchmark_empty_candidates_handled_gracefully(tmp_path):
    """Verifies benchmark comparison handles empty changed files without crashing."""
    dummy_repo = str(tmp_path)
    subprocess.run(["git", "init", "-b", "main"], cwd=dummy_repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=dummy_repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=dummy_repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=dummy_repo, check=True)

    with open(os.path.join(dummy_repo, "README.md"), "w") as f:
        f.write("# Empty Test Repo")
    subprocess.run(["git", "add", "."], cwd=dummy_repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=dummy_repo, check=True)

    # Identical revision benchmark
    bench = run_benchmark_comparison(
        repo_path=dummy_repo,
        base_ref="HEAD",
        target_ref="HEAD",
        iterations=1
    )
    assert bench.prioritized_run.total_executed == 0
    assert "No candidate tests mapped" in bench.summary
