"""
tests/test_pipeline.py
Unit tests for end-to-end pipeline orchestration in pipeline.py.
Verifies module coordination, failure fallbacks, safe subprocess test execution,
and result packaging with mocked external boundaries.
"""

import subprocess
from unittest.mock import MagicMock, patch
import pytest

from diff_checker import FileChange, GitRevisionError
from pipeline import (
    STATUS_ERROR,
    STATUS_GIT_ERROR,
    STATUS_NO_CANDIDATE_TESTS,
    STATUS_NO_CHANGES,
    STATUS_SUCCESS,
    STATUS_TEST_FAILURE,
    STATUS_TIMEOUT,
    PipelineResult,
    TestExecutionOutcome,
    execute_prioritized_tests,
    parse_pytest_counts,
    run_pipeline,
)
from test_mapper import MappingMatch, SourceMappingResult
from dependency_intelligence import (
    CATEGORY_BREAKING,
    DependencyEvidence,
    DependencyIntelligenceReport,
)


# ============================================================================
# Pytest Output Parsing Tests
# ============================================================================


def test_parse_pytest_counts_success_and_failure():
    """Parses various pytest stdout summary line patterns accurately."""
    stdout_pass = "=== 31 passed in 0.12s ==="
    counts_pass = parse_pytest_counts(stdout_pass)
    assert counts_pass["passed"] == 31
    assert counts_pass["failed"] == 0
    assert counts_pass["total"] == 31

    stdout_fail = "=== 2 failed, 15 passed in 0.45s ==="
    counts_fail = parse_pytest_counts(stdout_fail)
    assert counts_fail["passed"] == 15
    assert counts_fail["failed"] == 2
    assert counts_fail["total"] == 17

    assert parse_pytest_counts("") == {"passed": 0, "failed": 0, "total": 0}


# ============================================================================
# Safe Test Execution Tests
# ============================================================================


def test_execute_prioritized_tests_empty_list():
    """Empty test path list returns unexecuted outcome without error."""
    outcome = execute_prioritized_tests([])
    assert outcome.executed is False
    assert outcome.exit_code == 0
    assert outcome.mode == "none"


def test_execute_prioritized_tests_missing_files_on_disk(tmp_path):
    """Paths that do not exist on disk are rejected with clear error."""
    outcome = execute_prioritized_tests(["tests/does_not_exist.py"], repo_path=str(tmp_path))
    assert outcome.executed is False
    assert outcome.exit_code == 1
    assert "None of the specified test paths exist" in (outcome.error_message or "")


def test_execute_prioritized_tests_timeout_handling(tmp_path):
    """Subprocess timeout is trapped and returned as a structured outcome."""
    # Create a dummy test file
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    (test_dir / "test_dummy.py").write_text("# dummy", encoding="utf-8")

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["pytest"], timeout=5.0)):
        outcome = execute_prioritized_tests(["tests/test_dummy.py"], repo_path=str(tmp_path), timeout_seconds=5.0)
        assert outcome.executed is True
        assert outcome.exit_code == -1
        assert "timed out after 5.0 seconds" in (outcome.error_message or "")


# ============================================================================
# End-to-End Pipeline Orchestration Tests
# ============================================================================


@patch("pipeline.get_changed_files")
@patch("pipeline.map_changed_sources_to_tests")
@patch("pipeline.analyze_dependency_risks")
@patch("pipeline.execute_prioritized_tests")
def test_successful_end_to_end_orchestration(
    mock_execute,
    mock_dep_intel,
    mock_map,
    mock_diff
):
    """Verifies complete data flow and execution when changes are detected and mapped."""
    # Mock Git diff: 1 changed file
    mock_diff.return_value = [FileChange(path="src/cart.py", change_type="modified")]

    # Mock Mapper: maps src/cart.py to tests/test_cart.py
    match = MappingMatch(
        source_file="src/cart.py",
        test_file="tests/test_cart.py",
        reason="exact match",
        confidence="direct"
    )
    mock_map.return_value = [SourceMappingResult(source_file="src/cart.py", matches=[match])]

    # Mock Dependency Intelligence: unchanged
    mock_dep_intel.return_value = DependencyIntelligenceReport(
        manifest_changed=False,
        dependencies_analyzed=[],
        findings=[],
        summary="No manifest changed"
    )

    # Mock Test Execution: 13 passed
    mock_execute.return_value = TestExecutionOutcome(
        executed=True,
        command=["pytest", "tests/test_cart.py"],
        exit_code=0,
        stdout="=== 13 passed in 0.10s ===",
        stderr="",
        duration_seconds=0.10,
        passed_count=13,
        failed_count=0,
        total_executed=13,
        mode="prioritized_subset"
    )

    result = run_pipeline("main~1", "main", enable_tinyfish=True, execute_tests=True)

    assert result.status == STATUS_SUCCESS
    assert len(result.changed_files) == 1
    assert result.ranking_result is not None
    assert result.ranking_result.test_paths == ["tests/test_cart.py"]
    assert result.execution_outcome is not None
    assert result.execution_outcome.passed_count == 13
    assert result.duration_seconds >= 0.0


@patch("pipeline.get_changed_files")
def test_pipeline_no_changed_files(mock_diff):
    """When Git diff detects 0 changes, returns STATUS_NO_CHANGES immediately."""
    mock_diff.return_value = []
    result = run_pipeline("main", "main")
    assert result.status == STATUS_NO_CHANGES
    assert result.changed_files == []
    assert "No changed files detected" in result.summary


@patch("pipeline.get_changed_files")
def test_pipeline_invalid_git_revision(mock_diff):
    """Invalid Git revision raises GitRevisionError, caught safely as STATUS_GIT_ERROR."""
    mock_diff.side_effect = GitRevisionError("Invalid revision: 'nonexistent_branch'")
    result = run_pipeline("nonexistent_branch", "main")
    assert result.status == STATUS_GIT_ERROR
    assert "Invalid revision" in (result.error_message or "")


@patch("pipeline.get_changed_files")
@patch("pipeline.map_changed_sources_to_tests")
def test_pipeline_no_candidate_tests(mock_map, mock_diff):
    """When files changed but none map to any tests, returns STATUS_NO_CANDIDATE_TESTS."""
    mock_diff.return_value = [FileChange(path="README.md", change_type="modified")]
    mock_map.return_value = [SourceMappingResult(source_file="README.md", matches=[])]

    result = run_pipeline("main~1", "main")
    assert result.status == STATUS_NO_CANDIDATE_TESTS
    assert result.execution_outcome is None
    assert "no candidate test mappings were found" in result.summary


@patch("pipeline.get_changed_files")
@patch("pipeline.map_changed_sources_to_tests")
@patch("pipeline.analyze_dependency_risks")
def test_pipeline_tinyfish_disabled(mock_dep_intel, mock_map, mock_diff):
    """When enable_tinyfish=False, dependency intelligence is completely skipped."""
    mock_diff.return_value = [FileChange(path="src/cart.py", change_type="modified")]
    match = MappingMatch(source_file="src/cart.py", test_file="tests/test_cart.py", reason="exact", confidence="direct")
    mock_map.return_value = [SourceMappingResult(source_file="src/cart.py", matches=[match])]

    result = run_pipeline("main~1", "main", enable_tinyfish=False, execute_tests=False)
    assert result.status == STATUS_SUCCESS
    assert result.dependency_report is None
    mock_dep_intel.assert_not_called()


@patch("pipeline.get_changed_files")
@patch("pipeline.map_changed_sources_to_tests")
@patch("pipeline.analyze_dependency_risks")
@patch("pipeline.execute_prioritized_tests")
def test_pipeline_test_failure_captured_without_crashing(
    mock_execute,
    mock_dep_intel,
    mock_map,
    mock_diff
):
    """When prioritized tests fail, status is STATUS_TEST_FAILURE and error is preserved."""
    mock_diff.return_value = [FileChange(path="src/checkout.py", change_type="modified")]
    match = MappingMatch(source_file="src/checkout.py", test_file="tests/test_checkout.py", reason="exact", confidence="direct")
    mock_map.return_value = [SourceMappingResult(source_file="src/checkout.py", matches=[match])]
    mock_dep_intel.return_value = None

    # Simulate 1 failed test
    mock_execute.return_value = TestExecutionOutcome(
        executed=True,
        command=["pytest", "tests/test_checkout.py"],
        exit_code=1,
        stdout="=== 1 failed, 17 passed in 0.15s ===",
        stderr="",
        duration_seconds=0.15,
        passed_count=17,
        failed_count=1,
        total_executed=18,
        mode="prioritized_subset",
        error_message="pytest exited with code 1"
    )

    result = run_pipeline("main~1", "main", execute_tests=True)
    assert result.status == STATUS_TEST_FAILURE
    assert result.execution_outcome.failed_count == 1
    assert "Prioritized test execution caught failure" in result.summary


@patch("pipeline.get_changed_files")
@patch("pipeline.map_changed_sources_to_tests")
@patch("pipeline.analyze_dependency_risks")
def test_pipeline_passes_external_evidence_into_ranking(mock_dep_intel, mock_map, mock_diff):
    """Verified TinyFish breaking evidence is passed through to ranking_engine."""
    mock_diff.return_value = [
        FileChange(path="requirements.txt", change_type="modified"),
        FileChange(path="src/stripe.py", change_type="modified"),
    ]
    match = MappingMatch(source_file="src/stripe.py", test_file="tests/test_stripe.py", reason="exact", confidence="direct")
    mock_map.return_value = [SourceMappingResult(source_file="src/stripe.py", matches=[match])]

    finding = DependencyEvidence(
        package="stripe",
        title="Stripe v8 Release",
        url="https://stripe.com",
        snippet="Breaking changes",
        category=CATEGORY_BREAKING,
        is_relevant=True,
        explanation="Breaking change"
    )
    mock_dep_intel.return_value = DependencyIntelligenceReport(
        manifest_changed=True,
        dependencies_analyzed=[],
        findings=[finding],
        status="evidence_found",
        summary="Breaking evidence found"
    )

    result = run_pipeline("main~1", "main", enable_tinyfish=True, execute_tests=False)
    assert result.status == STATUS_SUCCESS
    ranked = result.ranking_result.ranked_tests[0]
    # Direct match (50) + Dependency risk (20) = 70
    assert ranked.score == 70
    assert "External dependency risk" in ranked.explanation
