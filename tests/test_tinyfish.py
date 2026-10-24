"""
tests/test_tinyfish.py
Unit tests for TinyFish client, dependency intelligence, and ranking integration.
All network calls are strictly mocked for offline, deterministic execution.
"""

from unittest.mock import MagicMock, patch
import pytest
import requests

from tinyfish_client import (
    DEFAULT_TINYFISH_ENDPOINT,
    STATUS_HTTP_ERROR,
    STATUS_INVALID_JSON,
    STATUS_MISSING_KEY,
    STATUS_NETWORK_ERROR,
    STATUS_NO_RESULTS,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    SearchResultItem,
    get_api_key,
    is_valid_url,
    search_tinyfish,
)
from dependency_intelligence import (
    CATEGORY_BREAKING,
    CATEGORY_MIGRATION,
    CATEGORY_UNVERIFIED,
    STATUS_EVIDENCE_FOUND,
    STATUS_MANIFEST_UNCHANGED,
    STATUS_NO_RELEVANT_EVIDENCE,
    STATUS_SKIPPED_MISSING_KEY,
    DependencyChange,
    DependencyEvidence,
    DependencyIntelligenceReport,
    analyze_dependency_risks,
    build_search_query,
    compute_dependency_diff,
    parse_requirements_content,
    validate_and_categorize_evidence,
)
from ranking_engine import (
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    SCORE_DEPENDENCY_RISK,
    SCORE_DIRECT_MATCH,
    rank_tests,
)
from test_mapper import MappingMatch


# ============================================================================
# TinyFish Client Tests
# ============================================================================


def test_get_api_key_returns_explicit_or_env(monkeypatch):
    """get_api_key should return explicit key, env var, or None if placeholder/missing."""
    assert get_api_key("explicit_test_key") == "explicit_test_key"

    monkeypatch.setenv("TINYFISH_API_KEY", "env_test_key")
    assert get_api_key() == "env_test_key"

    monkeypatch.setenv("TINYFISH_API_KEY", "your_tinyfish_api_key_here")
    assert get_api_key() is None

    monkeypatch.delenv("TINYFISH_API_KEY", raising=False)
    assert get_api_key() is None


def test_is_valid_url_accepts_http_https_rejects_others():
    """URL validation must verify safe HTTP/HTTPS schemes."""
    assert is_valid_url("https://github.com/stripe/stripe-python/releases") is True
    assert is_valid_url("http://pypi.org/project/pytest") is True
    assert is_valid_url("javascript:alert(1)") is False
    assert is_valid_url("file:///etc/passwd") is False
    assert is_valid_url("not_a_url") is False
    assert is_valid_url("") is False


def test_search_tinyfish_missing_api_key(monkeypatch):
    """search_tinyfish without API key returns STATUS_MISSING_KEY without raising error."""
    monkeypatch.delenv("TINYFISH_API_KEY", raising=False)
    resp = search_tinyfish("stripe upgrade")
    assert resp.status == STATUS_MISSING_KEY
    assert resp.results == []
    assert "TINYFISH_API_KEY" in (resp.error_message or "")


def test_search_tinyfish_empty_query():
    """Empty search query returns STATUS_NO_RESULTS cleanly."""
    resp = search_tinyfish("   ", api_key="dummy_key")
    assert resp.status == STATUS_NO_RESULTS


def test_search_tinyfish_successful_mocked_response():
    """Verifies parsing of successful response with title, url, snippet, and position."""
    mock_payload = {
        "query": "stripe upgrade",
        "results": [
            {
                "title": "Stripe Python v8.0.0 Release Notes",
                "url": "https://github.com/stripe/stripe-python/releases/tag/v8.0.0",
                "snippet": "Major breaking changes: removed legacy charges endpoint.",
                "site_name": "GitHub",
                "position": 1
            }
        ],
        "total_results": 1
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    with patch("requests.get", return_value=mock_resp) as mock_get:
        response = search_tinyfish("stripe upgrade", api_key="test_key")

        mock_get.assert_called_once()
        assert response.status == STATUS_SUCCESS
        assert len(response.results) == 1
        item = response.results[0]
        assert item.title == "Stripe Python v8.0.0 Release Notes"
        assert item.url == "https://github.com/stripe/stripe-python/releases/tag/v8.0.0"
        assert "breaking changes" in item.snippet
        assert item.position == 1


def test_search_tinyfish_http_error_handling():
    """Handles non-200 HTTP response codes cleanly."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403

    with patch("requests.get", return_value=mock_resp):
        response = search_tinyfish("query", api_key="test_key")
        assert response.status == STATUS_HTTP_ERROR
        assert "403" in (response.error_message or "")


def test_search_tinyfish_timeout_handling():
    """Handles network timeouts gracefully."""
    with patch("requests.get", side_effect=requests.Timeout("Connection timed out")):
        response = search_tinyfish("query", api_key="test_key")
        assert response.status == STATUS_TIMEOUT
        assert "timed out" in (response.error_message or "")


def test_search_tinyfish_network_error_handling():
    """Handles network request exceptions gracefully."""
    with patch("requests.get", side_effect=requests.ConnectionError("DNS failure")):
        response = search_tinyfish("query", api_key="test_key")
        assert response.status == STATUS_NETWORK_ERROR
        assert "Network error" in (response.error_message or "")


def test_search_tinyfish_invalid_json_handling():
    """Handles malformed JSON payloads from server."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Invalid JSON")

    with patch("requests.get", return_value=mock_resp):
        response = search_tinyfish("query", api_key="test_key")
        assert response.status == STATUS_INVALID_JSON


# ============================================================================
# Dependency Intelligence Tests
# ============================================================================


def test_parse_requirements_content():
    """Parses package names and version specifiers, ignoring comments."""
    content = """
    # Primary dependencies
    stripe==8.0.0
    requests>=2.31.0
    pytest~=7.4.0
    unpinned-package
    """
    parsed = parse_requirements_content(content)
    assert parsed["stripe"] == "8.0.0"
    assert parsed["requests"] == "2.31.0"
    assert parsed["pytest"] == "7.4.0"
    assert parsed["unpinned_package"] == "unpinned"


def test_compute_dependency_diff():
    """Correctly detects added, modified, and removed packages."""
    old_pkgs = {"stripe": "5.4.0", "requests": "2.28.0", "deprecated_lib": "1.0.0"}
    new_pkgs = {"stripe": "8.0.0", "requests": "2.28.0", "new_lib": "2.0.0"}

    diff = compute_dependency_diff(old_pkgs, new_pkgs)
    diff_map = {d.package: d for d in diff}

    assert diff_map["stripe"].change_type == "modified"
    assert diff_map["stripe"].old_version == "5.4.0"
    assert diff_map["stripe"].new_version == "8.0.0"

    assert diff_map["new_lib"].change_type == "added"
    assert diff_map["new_lib"].new_version == "2.0.0"

    assert diff_map["deprecated_lib"].change_type == "removed"
    assert diff_map["deprecated_lib"].old_version == "1.0.0"

    assert "requests" not in diff_map


def test_build_search_query():
    """Builds query targeting release notes and breaking changes."""
    query_pinned = build_search_query("stripe", "5.4.0", "8.0.0")
    assert "stripe 8.0.0 release notes breaking changes migration guide" == query_pinned

    query_unpinned = build_search_query("stripe", None, "unpinned")
    assert "stripe release notes breaking changes" == query_unpinned


def test_validate_and_categorize_evidence():
    """Classifies breaking changes, migration guides, and rejects unrelated results."""
    item_breaking = SearchResultItem(
        title="Stripe Python Upgrade Guide",
        url="https://stripe.com/docs/libraries/python",
        snippet="Warning: this major release includes breaking changes in charge tokens."
    )
    ev_breaking = validate_and_categorize_evidence(item_breaking, "stripe", "8.0.0")
    assert ev_breaking.is_relevant is True
    assert ev_breaking.category == CATEGORY_BREAKING

    # Unrelated package search result
    item_unrelated = SearchResultItem(
        title="Python Recipe Book",
        url="https://example.com/recipes",
        snippet="Delicious strawberry pie recipe with brown sugar."
    )
    ev_unrelated = validate_and_categorize_evidence(item_unrelated, "stripe", "8.0.0")
    assert ev_unrelated.is_relevant is False
    assert ev_unrelated.category == CATEGORY_UNVERIFIED


def test_analyze_dependency_risks_when_manifest_unchanged():
    """When requirements.txt is not in changed files, intelligence is skipped."""
    report = analyze_dependency_risks(changed_files=["src/cart.py"])
    assert report.manifest_changed is False
    assert report.status == STATUS_MANIFEST_UNCHANGED
    assert report.findings == []


def test_analyze_dependency_risks_when_key_missing(monkeypatch):
    """When requirements.txt changed but API key is missing, reports skipped_missing_key."""
    monkeypatch.delenv("TINYFISH_API_KEY", raising=False)
    report = analyze_dependency_risks(changed_files=["requirements.txt"])
    assert report.manifest_changed is True
    assert report.status == STATUS_SKIPPED_MISSING_KEY


# ============================================================================
# Ranking Integration Tests
# ============================================================================


def test_ranking_incorporates_external_dependency_risk_when_test_connects():
    """
    When TinyFish reports breaking changes for a package and a test maps to that package,
    the test receives +20 points (SCORE_DEPENDENCY_RISK).
    """
    match_stripe = MappingMatch(
        source_file="src/stripe_checkout.py",
        test_file="tests/test_stripe.py",
        reason="exact match",
        confidence="direct"
    )
    match_cart = MappingMatch(
        source_file="src/cart.py",
        test_file="tests/test_cart.py",
        reason="exact match",
        confidence="direct"
    )

    finding = DependencyEvidence(
        package="stripe",
        title="Stripe v8 Changelog",
        url="https://stripe.com/docs/v8",
        snippet="Breaking changes in charges endpoint.",
        category=CATEGORY_BREAKING,
        is_relevant=True,
        explanation="Breaking changes detected."
    )
    dep_report = DependencyIntelligenceReport(
        manifest_changed=True,
        dependencies_analyzed=[DependencyChange(package="stripe", change_type="modified")],
        findings=[finding],
        status=STATUS_EVIDENCE_FOUND,
        summary="Found 1 breaking change."
    )

    result = rank_tests([match_stripe, match_cart], dependency_report=dep_report)
    assert len(result.ranked_tests) == 2

    # test_stripe gets: base direct (50) + dependency risk (20) = 70 [HIGH]
    item_stripe = result.ranked_tests[0]
    assert item_stripe.test_file == "tests/test_stripe.py"
    assert item_stripe.score == 70
    assert item_stripe.priority == PRIORITY_HIGH
    assert "External dependency risk: verified breaking changes" in item_stripe.explanation

    # test_cart has no connection to stripe: remains base direct (50) [MEDIUM]
    item_cart = result.ranked_tests[1]
    assert item_cart.test_file == "tests/test_cart.py"
    assert item_cart.score == 50
    assert item_cart.priority == PRIORITY_MEDIUM


def test_ranking_remains_unchanged_without_dependency_report():
    """Existing ranking scores remain 100% identical when dependency_report is None."""
    match = MappingMatch(
        source_file="src/cart.py",
        test_file="tests/test_cart.py",
        reason="exact match",
        confidence="direct"
    )
    res_without = rank_tests([match])
    assert res_without.ranked_tests[0].score == SCORE_DIRECT_MATCH


def test_unverified_external_evidence_gives_no_ranking_bonus():
    """Unverified findings (e.g. package not mentioned) do not boost test score."""
    match = MappingMatch(
        source_file="src/stripe.py",
        test_file="tests/test_stripe.py",
        reason="exact",
        confidence="direct"
    )
    unverified_finding = DependencyEvidence(
        package="stripe",
        title="Unrelated doc",
        url="https://example.com",
        snippet="nothing",
        category=CATEGORY_UNVERIFIED,
        is_relevant=False,
        explanation="Not relevant"
    )
    dep_report = DependencyIntelligenceReport(
        manifest_changed=True,
        dependencies_analyzed=[],
        findings=[unverified_finding],
        status=STATUS_NO_RELEVANT_EVIDENCE,
        summary="No relevant evidence"
    )
    result = rank_tests([match], dependency_report=dep_report)
    # Stays at base 50, does NOT get 70
    assert result.ranked_tests[0].score == SCORE_DIRECT_MATCH
