"""
tests/test_ranking_engine.py
Automated tests for ranking_engine.py.
Verifies scoring weights, priority tiers, multi-source bonuses,
deterministic tie-breaking, deduplication, and edge case handling.
"""

import pytest
from test_mapper import MappingMatch, SourceMappingResult
from ranking_engine import (
    MAX_ADDITIONAL_SOURCE_BONUS,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    SCORE_ADDITIONAL_SOURCE,
    SCORE_COMPOUND_MATCH,
    SCORE_DIRECT_MATCH,
    RankedItem,
    RankingResult,
    determine_priority_label,
    rank_tests,
)


def test_direct_match_ranks_above_compound_match_all_else_equal():
    """A direct match (+50) must strictly rank above a compound match (+25)."""
    match_direct = MappingMatch(
        source_file="src/cart.py",
        test_file="tests/test_cart.py",
        reason="exact match",
        confidence="direct"
    )
    match_compound = MappingMatch(
        source_file="src/checkout.py",
        test_file="tests/test_checkout_flows.py",
        reason="compound match",
        confidence="compound"
    )

    result = rank_tests([match_compound, match_direct])
    assert len(result.ranked_tests) == 2

    # Direct match should be first
    assert result.ranked_tests[0].test_file == "tests/test_cart.py"
    assert result.ranked_tests[0].score == SCORE_DIRECT_MATCH
    assert result.ranked_tests[0].priority == PRIORITY_MEDIUM

    # Compound match should be second
    assert result.ranked_tests[1].test_file == "tests/test_checkout_flows.py"
    assert result.ranked_tests[1].score == SCORE_COMPOUND_MATCH
    assert result.ranked_tests[1].priority == PRIORITY_LOW


def test_multiple_changed_sources_increase_score_without_exceeding_cap():
    """Each additional mapped source grants +15 points, capped at +30 points bonus."""
    # 1 source: 50 pts
    match_1 = MappingMatch(
        source_file="src/module_a.py",
        test_file="tests/test_multi.py",
        reason="direct",
        confidence="direct"
    )
    res_1 = rank_tests([match_1])
    assert res_1.ranked_tests[0].score == 50

    # 2 sources: 50 + 15 = 65 pts
    match_2 = MappingMatch(
        source_file="src/module_b.py",
        test_file="tests/test_multi.py",
        reason="direct",
        confidence="direct"
    )
    res_2 = rank_tests([match_1, match_2])
    assert res_2.ranked_tests[0].score == 65
    assert res_2.ranked_tests[0].priority == PRIORITY_MEDIUM

    # 3 sources: 50 + 30 = 80 pts
    match_3 = MappingMatch(
        source_file="src/module_c.py",
        test_file="tests/test_multi.py",
        reason="compound",
        confidence="compound"
    )
    res_3 = rank_tests([match_1, match_2, match_3])
    assert res_3.ranked_tests[0].score == 80
    assert res_3.ranked_tests[0].priority == PRIORITY_HIGH

    # 4 sources: still capped at +30 -> 80 pts (cap message appears)
    match_4 = MappingMatch(
        source_file="src/module_d.py",
        test_file="tests/test_multi.py",
        reason="compound",
        confidence="compound"
    )
    res_4 = rank_tests([match_1, match_2, match_3, match_4])
    assert res_4.ranked_tests[0].score == 80
    assert len(res_4.ranked_tests[0].contributing_sources) == 4
    assert "capped at max 30" in res_4.ranked_tests[0].explanation


def test_duplicate_mapping_records_are_deduplicated():
    """Identical (source, test, confidence) records must not inflate score or appear twice."""
    match = MappingMatch(
        source_file="src/cart.py",
        test_file="tests/test_cart.py",
        reason="direct",
        confidence="direct"
    )
    # Passed 3 times
    result = rank_tests([match, match, match])
    assert len(result.ranked_tests) == 1
    item = result.ranked_tests[0]
    assert item.score == SCORE_DIRECT_MATCH
    assert item.contributing_sources == ["src/cart.py"]


def test_stable_deterministic_tie_breaking():
    """When scores are equal, ties must break alphabetically by normalized test_file path."""
    match_z = MappingMatch(
        source_file="src/z.py",
        test_file="tests/test_zebra.py",
        reason="direct",
        confidence="direct"
    )
    match_a = MappingMatch(
        source_file="src/a.py",
        test_file="tests/test_apple.py",
        reason="direct",
        confidence="direct"
    )
    match_m = MappingMatch(
        source_file="src/m.py",
        test_file="tests/test_mango.py",
        reason="direct",
        confidence="direct"
    )

    # Input in random order: zebra, mango, apple
    result = rank_tests([match_z, match_m, match_a])
    paths = result.test_paths
    assert paths == [
        "tests/test_apple.py",
        "tests/test_mango.py",
        "tests/test_zebra.py"
    ]


def test_empty_mapping_produces_explicit_empty_result():
    """Empty mapping inputs must return a valid RankingResult with 0 candidates."""
    result = rank_tests([])
    assert result.ranked_tests == []
    assert result.total_candidates == 0
    assert "No candidate test mappings found" in result.summary


def test_source_mapping_results_with_no_matches_produces_empty_result():
    """SourceMappingResult objects having empty matches list produce an empty result."""
    empty_res = SourceMappingResult(source_file="README.md", matches=[])
    result = rank_tests([empty_res])
    assert result.ranked_tests == []
    assert result.total_candidates == 0


def test_unsupported_confidence_values_handled_safely():
    """Unknown or malformed confidence values receive 0 base points and do not crash."""
    weird_match = MappingMatch(
        source_file="src/experimental.py",
        test_file="tests/test_exp.py",
        reason="speculative",
        confidence="speculative_ai_guess"
    )
    result = rank_tests([weird_match])
    assert len(result.ranked_tests) == 1
    item = result.ranked_tests[0]
    assert item.score == 0
    assert item.priority == PRIORITY_LOW
    assert "Unsupported confidence value(s)" in item.explanation


def test_invalid_or_empty_paths_handled_safely():
    """Matches with empty or blank test_file paths are skipped."""
    blank_match = MappingMatch(
        source_file="src/empty.py",
        test_file="   ",
        reason="invalid",
        confidence="direct"
    )
    result = rank_tests([blank_match])
    assert result.ranked_tests == []
    assert result.total_candidates == 0


def test_windows_and_posix_paths_merged_properly():
    """Same test file mapped with Windows backslashes and POSIX slashes merges into one."""
    match_posix = MappingMatch(
        source_file="src/cart.py",
        test_file="tests/test_cart.py",
        reason="exact",
        confidence="direct"
    )
    match_windows = MappingMatch(
        source_file="src/checkout.py",
        test_file=r"tests\test_cart.py",
        reason="compound",
        confidence="compound"
    )
    result = rank_tests([match_posix, match_windows])
    assert len(result.ranked_tests) == 1
    item = result.ranked_tests[0]
    assert item.test_file == "tests/test_cart.py"
    # Base 50 + 1 additional source (15) = 65
    assert item.score == 65
    assert sorted(item.contributing_sources) == ["src/cart.py", "src/checkout.py"]


def test_explanation_matches_signals_that_contributed():
    """Explanation string must accurately reflect the specific signals that contributed."""
    match = MappingMatch(
        source_file="src/cart.py",
        test_file="tests/test_cart.py",
        reason="exact match",
        confidence="direct"
    )
    result = rank_tests([match])
    explanation = result.ranked_tests[0].explanation
    assert "Score: 50/100 [MEDIUM]" in explanation
    assert "Direct match from source: src/cart.py (+50 pts)" in explanation


def test_invalid_input_type_raises_type_error():
    """Passing non-list input to rank_tests must raise TypeError."""
    with pytest.raises(TypeError, match="must be a list"):
        rank_tests("invalid_string_argument")  # type: ignore

    with pytest.raises(TypeError, match="Unsupported input type"):
        rank_tests(["not_a_mapping_object"])  # type: ignore


def test_priority_label_thresholds():
    """Verify priority tier assignment boundaries."""
    assert determine_priority_label(100) == PRIORITY_HIGH
    assert determine_priority_label(70) == PRIORITY_HIGH
    assert determine_priority_label(69) == PRIORITY_MEDIUM
    assert determine_priority_label(40) == PRIORITY_MEDIUM
    assert determine_priority_label(39) == PRIORITY_LOW
    assert determine_priority_label(0) == PRIORITY_LOW
