"""
tests/test_test_selection.py
Comprehensive automated test suite for User-Controlled Test Selection in TestPrioritize AI:
1. Top-N selects precisely the top N ranked candidates.
2. Manual mode runs exactly the selected candidates.
3. Empty manual selection is handled correctly.
4. Standard and prioritized modes respect the same selected set.
5. Prioritized mode follows ranked order for the selected candidates.
6. Standard mode follows standard order for the selected candidates.
7. Fail-fast works correctly on a subset.
8. Healthy and regression scenarios remain valid.
9. Switching repositories or scenarios does not reuse invalid selections.
10. TinyFish integration and fallback behavior remain intact.
11. Existing tests continue to pass.
"""

import os
import pytest
from demo_manager import (
    get_all_demo_repos,
    get_available_test_candidates,
    execute_demo_scenario,
    IsolatedRunReport,
)
from pipeline import run_pipeline, STATUS_NO_CANDIDATE_TESTS
from tinyfish_client import search_tinyfish, get_api_key, STATUS_MISSING_KEY


def test_1_top_n_selects_precisely_top_n_candidates():
    """Verify Top-N selection mode selects and executes precisely the top N candidates."""
    candidates = get_available_test_candidates("ecommerce", ["src/checkout.py"], "checkout_regression")
    assert len(candidates) >= 10, f"Expected at least 10 candidates, found {len(candidates)}"

    top_n = 4
    expected_top_n_ids = [c.node_id for c in candidates[:top_n]]

    report = execute_demo_scenario(
        repo_id="ecommerce",
        changed_files=["src/checkout.py"],
        scenario_id="checkout_regression",
        mode="prioritized",
        fail_fast=False,
        selection_mode="top_n",
        top_n=top_n
    )

    assert report.selection_mode == "top_n"
    assert report.selected_count == top_n
    assert report.available_candidates_count == len(candidates)
    assert report.subset_warning is not None
    assert f"Top-{top_n} Subset Active" in report.subset_warning

    pri_res = report.prioritized_run
    assert pri_res is not None
    assert pri_res.total_executed == top_n
    executed_ids = [ev.nodeid for ev in pri_res.events]
    assert executed_ids == expected_top_n_ids


def test_2_manual_mode_runs_exactly_selected():
    """Verify manual mode executes only the user-selected candidates without running others."""
    candidates = get_available_test_candidates("ecommerce", ["src/cart.py"], "cart_enhancement")
    assert len(candidates) >= 5

    # Select candidate #2 and candidate #4 specifically
    selected = [candidates[1].node_id, candidates[3].node_id]

    report = execute_demo_scenario(
        repo_id="ecommerce",
        changed_files=["src/cart.py"],
        scenario_id="cart_enhancement",
        mode="prioritized",
        fail_fast=False,
        selection_mode="manual",
        selected_test_ids=selected
    )

    assert report.selection_mode == "manual"
    assert report.selected_count == 2
    assert report.subset_warning is not None
    assert "Manual Subset Active" in report.subset_warning

    pri_res = report.prioritized_run
    assert pri_res is not None
    assert pri_res.total_executed == 2
    executed_ids = [ev.nodeid for ev in pri_res.events]
    assert set(executed_ids) == set(selected)


def test_3_empty_manual_selection_handled_correctly():
    """Verify empty manual selection raises a descriptive ValueError and does not execute."""
    with pytest.raises(ValueError, match="Empty test selection"):
        execute_demo_scenario(
            repo_id="ecommerce",
            changed_files=["src/cart.py"],
            scenario_id="cart_enhancement",
            mode="prioritized",
            selection_mode="manual",
            selected_test_ids=[]
        )

    # Also verify custom pipeline handles empty selection
    res = run_pipeline(
        base_ref="main",
        target_ref="feature/cart-enhancement",
        repo_path="demo_repos/ecommerce",
        execute_tests=True,
        selection_mode="manual",
        selected_test_ids=[]
    )
    assert res.status == STATUS_NO_CANDIDATE_TESTS
    assert "Empty test selection" in res.summary


def test_4_standard_and_prioritized_modes_respect_same_selected_set():
    """Verify benchmark mode applies the identical selected candidate subset to both standard and prioritized runs."""
    candidates = get_available_test_candidates("ecommerce", ["src/cart.py"], "cart_enhancement")
    selected = [candidates[0].node_id, candidates[2].node_id, candidates[4].node_id]

    report = execute_demo_scenario(
        repo_id="ecommerce",
        changed_files=["src/cart.py"],
        scenario_id="cart_enhancement",
        mode="benchmark",
        fail_fast=False,
        selection_mode="manual",
        selected_test_ids=selected
    )

    assert report.standard_run is not None
    assert report.prioritized_run is not None
    assert report.standard_run.total_executed == 3
    assert report.prioritized_run.total_executed == 3

    std_executed = {ev.nodeid for ev in report.standard_run.events}
    pri_executed = {ev.nodeid for ev in report.prioritized_run.events}

    assert std_executed == set(selected)
    assert pri_executed == set(selected)


def test_5_prioritized_mode_follows_ranked_order_for_selected():
    """Verify prioritized mode executes the selected subset strictly in descending rank order."""
    candidates = get_available_test_candidates("ecommerce", ["src/checkout.py"], "checkout_regression")
    # Take candidates 0, 3, 5 which are already sorted descending by score
    selected_in_arbitrary_order = [candidates[5].node_id, candidates[0].node_id, candidates[3].node_id]

    report = execute_demo_scenario(
        repo_id="ecommerce",
        changed_files=["src/checkout.py"],
        scenario_id="checkout_regression",
        mode="prioritized",
        fail_fast=False,
        selection_mode="manual",
        selected_test_ids=selected_in_arbitrary_order
    )

    expected_pri_order = [candidates[0].node_id, candidates[3].node_id, candidates[5].node_id]
    actual_pri_order = [ev.nodeid for ev in report.prioritized_run.events]
    assert actual_pri_order == expected_pri_order


def test_6_standard_mode_follows_standard_order_for_selected():
    """Verify standard mode executes the exact same selected subset in standard alphabetical order."""
    candidates = get_available_test_candidates("ecommerce", ["src/checkout.py"], "checkout_regression")
    selected = [candidates[5].node_id, candidates[0].node_id, candidates[3].node_id]

    report = execute_demo_scenario(
        repo_id="ecommerce",
        changed_files=["src/checkout.py"],
        scenario_id="checkout_regression",
        mode="standard",
        fail_fast=False,
        selection_mode="manual",
        selected_test_ids=selected
    )

    expected_std_order = sorted(selected)
    actual_std_order = [ev.nodeid for ev in report.standard_run.events]
    assert actual_std_order == expected_std_order


def test_7_fail_fast_works_correctly_on_subset():
    """Verify fail-fast stops immediately at the first failure on a selected subset."""
    candidates = get_available_test_candidates("ecommerce", ["src/checkout.py"], "checkout_regression")
    # Candidate #0 is test_apply_tax_fractional_precision which is the bug that fails
    assert "test_apply_tax_fractional_precision" in candidates[0].node_id

    report = execute_demo_scenario(
        repo_id="ecommerce",
        changed_files=["src/checkout.py"],
        scenario_id="checkout_regression",
        mode="prioritized",
        fail_fast=True,
        selection_mode="top_n",
        top_n=5
    )

    pri_res = report.prioritized_run
    assert pri_res is not None
    # With fail-fast, candidate #0 fails on test #1, so execution terminates immediately after 1 test
    assert pri_res.total_executed == 1
    assert pri_res.failed_count == 1
    assert pri_res.first_failing_position == 1


def test_8_healthy_and_regression_scenarios_remain_valid():
    """Verify both healthy and regression scenarios maintain their validity under test selection."""
    # Healthy scenario
    report_healthy = execute_demo_scenario(
        repo_id="ecommerce",
        changed_files=["src/cart.py"],
        scenario_id="cart_enhancement",
        mode="benchmark",
        fail_fast=True,
        selection_mode="top_n",
        top_n=6
    )
    assert report_healthy.prioritized_run.failed_count == 0
    assert report_healthy.prioritized_run.passed_count == 6
    assert report_healthy.standard_run.failed_count == 0
    assert report_healthy.standard_run.passed_count == 6

    # Regression scenario
    report_reg = execute_demo_scenario(
        repo_id="ecommerce",
        changed_files=["src/cart.py"],
        scenario_id="cart_limit_regression",
        mode="benchmark",
        fail_fast=True,
        selection_mode="top_n",
        top_n=6
    )
    # Prioritized runs failing test at position #1
    assert report_reg.prioritized_run.first_failing_position == 1
    assert report_reg.prioritized_run.failed_count == 1


def test_9_switching_repositories_does_not_reuse_invalid_selections():
    """Verify candidates from repository A are rejected as invalid when executing repository B."""
    ecom_candidates = get_available_test_candidates("ecommerce", ["src/checkout.py"])
    auth_candidates = get_available_test_candidates("auth_service", ["src/token_service.py"])

    ecom_ids = {c.node_id for c in ecom_candidates}
    auth_ids = {c.node_id for c in auth_candidates}

    # Verify candidate sets are completely distinct
    assert ecom_ids.isdisjoint(auth_ids)

    # Attempting to execute auth_service repository with ecommerce test IDs must raise ValueError
    with pytest.raises(ValueError, match="None of the selected test IDs match available candidates"):
        execute_demo_scenario(
            repo_id="auth_service",
            changed_files=["src/token_service.py"],
            mode="prioritized",
            selection_mode="manual",
            selected_test_ids=[list(ecom_ids)[0]]
        )


def test_10_tinyfish_integration_and_fallback_intact(monkeypatch):
    """Verify TinyFish external intelligence gracefully returns fallback data when unconfigured."""
    monkeypatch.delenv("TINYFISH_API_KEY", raising=False)
    resp = search_tinyfish("pytest breaking changes", api_key=None)
    assert resp.status == STATUS_MISSING_KEY
    assert resp.results == []
    assert resp.error_message is not None


def test_11_subset_warning_message_integrity():
    """Verify subset warning explicitly states that unselected tests were not run."""
    report = execute_demo_scenario(
        repo_id="ecommerce",
        changed_files=["src/checkout.py"],
        scenario_id="checkout_regression",
        mode="prioritized",
        fail_fast=False,
        selection_mode="top_n",
        top_n=3
    )
    assert report.subset_warning is not None
    assert "Unselected tests were not executed" in report.subset_warning
    assert "does not verify the entire application" in report.subset_warning
