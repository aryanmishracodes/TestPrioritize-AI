"""
ranking_engine.py
Part of TestPrioritize AI.

Explainable, deterministic test prioritization engine that evaluates
candidate test mappings from test_mapper.py and ranks them based on
transparent, rule-based evidence weights.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union

from test_mapper import MappingMatch, SourceMappingResult, normalize_path

# ============================================================================
# Scoring Constants & Configuration
# ============================================================================

SCORE_MIN: int = 0
SCORE_MAX: int = 100

# Base confidence weights
SCORE_DIRECT_MATCH: int = 50     # Exact module stem match (e.g. cart.py -> test_cart.py)
SCORE_COMPOUND_MATCH: int = 25   # Delimited compound match (e.g. cart.py -> test_cart_integration.py)

# Additional evidence: multiple distinct changed source files pointing to the same test
SCORE_ADDITIONAL_SOURCE: int = 15
MAX_ADDITIONAL_SOURCE_BONUS: int = 30  # At most 2 additional sources grant bonus points

# Priority tier thresholds
THRESHOLD_HIGH: int = 70         # score >= 70
THRESHOLD_MEDIUM: int = 40       # 40 <= score < 70
# score < 40 is categorized as LOW

PRIORITY_HIGH: str = "HIGH"
PRIORITY_MEDIUM: str = "MEDIUM"
PRIORITY_LOW: str = "LOW"


@dataclass(frozen=True)
class RankedItem:
    """
    Represents an individual test file ranked with a transparent score,
    priority level, and contributing evidence.

    Attributes:
        test_file: Normalized relative path to the test file.
        score: Clamped integer score from 0 to 100.
        priority: Human-readable priority tier ('HIGH', 'MEDIUM', 'LOW').
        contributing_sources: Distinct changed source files mapped to this test.
        explanation: Comprehensive plain-English breakdown of the score.
        reasons: Individual contributing signal lines.
    """
    test_file: str
    score: int
    priority: str
    contributing_sources: List[str] = field(default_factory=list)
    explanation: str = ""
    reasons: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RankingResult:
    """
    Represents the complete output of the ranking engine.

    Attributes:
        ranked_tests: Deterministically ordered list of RankedItem objects.
        total_candidates: Number of unique candidate test files ranked.
        summary: Overview summary of the ranking operation.
    """
    ranked_tests: List[RankedItem] = field(default_factory=list)
    total_candidates: int = 0
    summary: str = ""

    @property
    def test_paths(self) -> List[str]:
        """Returns ordered list of candidate test file path strings."""
        return [item.test_file for item in self.ranked_tests]


def determine_priority_label(score: int) -> str:
    """Assigns priority tier label based on documented score thresholds."""
    if score >= THRESHOLD_HIGH:
        return PRIORITY_HIGH
    elif score >= THRESHOLD_MEDIUM:
        return PRIORITY_MEDIUM
    return PRIORITY_LOW


def _extract_all_matches(
    mapping_inputs: Union[List[SourceMappingResult], List[MappingMatch]]
) -> List[MappingMatch]:
    """
    Extracts a flat list of MappingMatch objects from either a list of
    SourceMappingResult objects or a direct list of MappingMatch objects.
    """
    matches: List[MappingMatch] = []
    for item in mapping_inputs:
        if isinstance(item, SourceMappingResult):
            matches.extend(item.matches)
        elif isinstance(item, MappingMatch):
            matches.append(item)
        else:
            raise TypeError(
                f"Unsupported input type in mapping_inputs: {type(item).__name__}. "
                "Expected SourceMappingResult or MappingMatch."
            )
    return matches


def rank_tests(
    mapping_results: Union[List[SourceMappingResult], List[MappingMatch]]
) -> RankingResult:
    """
    Ranks candidate test files based on evidence provided by test_mapper.

    Scoring Logic:
    1. Base Score:
       - Direct lexical match ('direct'): +50 points.
       - Compound delimited match ('compound'): +25 points.
       - Unsupported or unrecognized confidence: +0 points.
       If multiple matches map to the same test, the highest base score is used.
    2. Multi-Source Bonus:
       - If multiple distinct changed source files map to the same test, each
         additional source adds +15 points (capped at +30 points).
    3. Clamping & Priority Tier:
       - Final score clamped to [0, 100].
       - HIGH: score >= 70
       - MEDIUM: 40 <= score < 70
       - LOW: score < 40
    4. Deterministic Tie-Breaking:
       - Sorted by score DESCENDING, then by test_file ASCENDING (alphabetical).

    Args:
        mapping_results: List of SourceMappingResult or MappingMatch objects.

    Returns:
        RankingResult containing deterministically ordered RankedItem entries.

    Raises:
        TypeError: If mapping_results is not a list.
    """
    if not isinstance(mapping_results, list):
        raise TypeError(
            f"mapping_results must be a list, got {type(mapping_results).__name__}."
        )

    all_matches = _extract_all_matches(mapping_results)

    if not all_matches:
        return RankingResult(
            ranked_tests=[],
            total_candidates=0,
            summary="No candidate test mappings found to rank."
        )

    # Group matches by normalized test file path
    # test_file -> set of (source_file, confidence, match_reason)
    grouped_tests: Dict[str, List[MappingMatch]] = {}
    seen_pairs: Set[str] = set()

    for match in all_matches:
        if not match.test_file or not isinstance(match.test_file, str) or not match.test_file.strip():
            continue

        norm_test = normalize_path(match.test_file)
        norm_source = normalize_path(match.source_file) if match.source_file else "unknown_source"

        # Deduplicate exact duplicate mapping records
        pair_key = f"{norm_source}::{norm_test}::{match.confidence}"
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        # Normalize the match object
        clean_match = MappingMatch(
            source_file=norm_source,
            test_file=norm_test,
            reason=match.reason,
            confidence=match.confidence
        )

        if norm_test not in grouped_tests:
            grouped_tests[norm_test] = []
        grouped_tests[norm_test].append(clean_match)

    if not grouped_tests:
        return RankingResult(
            ranked_tests=[],
            total_candidates=0,
            summary="No valid candidate test files after normalizing inputs."
        )

    ranked_items: List[RankedItem] = []

    for test_path, matches in grouped_tests.items():
        reasons: List[str] = []
        distinct_sources = sorted(list({m.source_file for m in matches}))

        # Evaluate base score from highest confidence match
        has_direct = any(m.confidence == "direct" for m in matches)
        has_compound = any(m.confidence == "compound" for m in matches)

        if has_direct:
            base_score = SCORE_DIRECT_MATCH
            direct_sources = [m.source_file for m in matches if m.confidence == "direct"]
            reasons.append(
                f"Direct match from source: {', '.join(direct_sources)} (+{SCORE_DIRECT_MATCH} pts)"
            )
        elif has_compound:
            base_score = SCORE_COMPOUND_MATCH
            compound_sources = [m.source_file for m in matches if m.confidence == "compound"]
            reasons.append(
                f"Compound match from source: {', '.join(compound_sources)} (+{SCORE_COMPOUND_MATCH} pts)"
            )
        else:
            base_score = 0
            unsupported = [m.confidence for m in matches]
            reasons.append(
                f"Unsupported confidence value(s) {unsupported} received (+0 pts)"
            )

        # Evaluate multi-source corroborating evidence bonus
        additional_source_count = max(0, len(distinct_sources) - 1)
        raw_bonus = additional_source_count * SCORE_ADDITIONAL_SOURCE
        source_bonus = min(raw_bonus, MAX_ADDITIONAL_SOURCE_BONUS)

        if additional_source_count > 0:
            if raw_bonus > MAX_ADDITIONAL_SOURCE_BONUS:
                reasons.append(
                    f"Multi-source bonus: {additional_source_count} additional changed sources mapped "
                    f"(+{source_bonus} pts, capped at max {MAX_ADDITIONAL_SOURCE_BONUS})"
                )
            else:
                reasons.append(
                    f"Multi-source bonus: {additional_source_count} additional changed source(s) mapped "
                    f"(+{source_bonus} pts)"
                )

        raw_score = base_score + source_bonus
        final_score = max(SCORE_MIN, min(SCORE_MAX, raw_score))
        priority = determine_priority_label(final_score)

        explanation = (
            f"Score: {final_score}/100 [{priority}]. "
            + "; ".join(reasons)
        )

        ranked_items.append(
            RankedItem(
                test_file=test_path,
                score=final_score,
                priority=priority,
                contributing_sources=distinct_sources,
                explanation=explanation,
                reasons=reasons
            )
        )

    # Deterministic sorting: score DESCENDING, then test_file ASCENDING (alphabetical tie-breaker)
    ranked_items.sort(key=lambda item: (-item.score, item.test_file))

    summary = (
        f"Prioritized {len(ranked_items)} candidate test file(s) across "
        f"{len(seen_pairs)} mapping relationship(s)."
    )

    return RankingResult(
        ranked_tests=ranked_items,
        total_candidates=len(ranked_items),
        summary=summary
    )
