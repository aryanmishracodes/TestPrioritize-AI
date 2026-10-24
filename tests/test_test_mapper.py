"""
tests/test_test_mapper.py
Unit tests for test discovery and lexical source-to-test mapping in test_mapper.py.
"""

import os
import pytest
from test_mapper import (
    MappingMatch,
    SourceMappingResult,
    discover_test_files,
    extract_module_stem,
    extract_test_core_name,
    is_test_file,
    map_changed_sources_to_tests,
    map_source_to_tests,
    normalize_path,
)


# ============================================================================
# Path & Utility Normalization Tests
# ============================================================================


def test_normalize_path_handles_windows_and_posix_separators():
    """Paths with Windows backslashes and redundant relative dots must normalize to POSIX forward slashes."""
    assert normalize_path(r"src\cart.py") == "src/cart.py"
    assert normalize_path(r".\src\checkout.py") == "src/checkout.py"
    assert normalize_path("src/cart.py") == "src/cart.py"
    assert normalize_path("./tests/test_cart.py") == "tests/test_cart.py"


def test_normalize_path_invalid_type_raises_type_error():
    """Non-string inputs to normalize_path must raise TypeError."""
    with pytest.raises(TypeError, match="must be a string"):
        normalize_path(123)  # type: ignore


def test_is_test_file_identifies_test_naming_conventions():
    """Standard pytest conventions and test directory placements must be recognized."""
    assert is_test_file("tests/test_cart.py") is True
    assert is_test_file("tests/cart_test.py") is True
    assert is_test_file("tests/conftest.py") is True
    assert is_test_file(r"tests\unit\test_helpers.py") is True
    assert is_test_file("src/cart.py") is False
    assert is_test_file("README.md") is False


def test_extract_module_stem():
    """extract_module_stem should extract the stem and ignore __init__.py or non-python files."""
    assert extract_module_stem("src/checkout.py") == "checkout"
    assert extract_module_stem(r"src\cart.py") == "cart"
    assert extract_module_stem("src/__init__.py") is None
    assert extract_module_stem("requirements.txt") is None


def test_extract_test_core_name():
    """extract_test_core_name should strip test_ prefix or _test suffix."""
    assert extract_test_core_name("tests/test_checkout.py") == "checkout"
    assert extract_test_core_name("tests/checkout_test.py") == "checkout"
    assert extract_test_core_name("tests/test_cart_integration.py") == "cart_integration"
    assert extract_test_core_name("tests/README.md") is None


# ============================================================================
# Test Discovery Tests
# ============================================================================


def test_discover_test_files_in_temp_directory(tmp_path):
    """Test discovery in an isolated directory structure."""
    test_dir = tmp_path / "custom_tests"
    test_dir.mkdir()

    # Create dummy test files and non-test files
    (test_dir / "test_alpha.py").write_text("# test", encoding="utf-8")
    (test_dir / "beta_test.py").write_text("# test", encoding="utf-8")
    (test_dir / "__init__.py").write_text("", encoding="utf-8")
    (test_dir / "helper.txt").write_text("not a test", encoding="utf-8")

    # Nested test file
    sub_dir = test_dir / "unit"
    sub_dir.mkdir()
    (sub_dir / "test_gamma.py").write_text("# test", encoding="utf-8")

    discovered = discover_test_files(repo_path=str(tmp_path), test_dir="custom_tests")
    expected = [
        "custom_tests/beta_test.py",
        "custom_tests/test_alpha.py",
        "custom_tests/unit/test_gamma.py",
    ]
    assert discovered == expected


def test_discover_test_files_missing_directory_returns_empty_list(tmp_path):
    """Discovering tests in a non-existent directory must return an empty list without error."""
    discovered = discover_test_files(repo_path=str(tmp_path), test_dir="non_existent_dir")
    assert discovered == []


def test_discover_test_files_invalid_arguments_raise_value_error():
    """Empty or whitespace directory parameters must raise ValueError."""
    with pytest.raises(ValueError, match="repo_path must be a non-empty string"):
        discover_test_files(repo_path="")

    with pytest.raises(ValueError, match="test_dir must be a non-empty string"):
        discover_test_files(test_dir="   ")


# ============================================================================
# Source-to-Test Mapping Rules Tests
# ============================================================================


def test_map_source_to_tests_direct_exact_match():
    """An exact module stem match between source and test file must map with 'direct' confidence."""
    candidates = ["tests/test_cart.py", "tests/test_checkout.py"]
    result = map_source_to_tests("src/cart.py", candidates)

    assert result.has_matches is True
    assert len(result.matches) == 1
    match = result.matches[0]
    assert match.source_file == "src/cart.py"
    assert match.test_file == "tests/test_cart.py"
    assert match.confidence == "direct"
    assert "Exact module stem match" in match.reason


def test_map_source_to_tests_multiple_candidates():
    """A source file can map to multiple candidate tests (e.g., unit and compound integration tests)."""
    candidates = [
        "tests/test_cart.py",
        "tests/test_checkout.py",
        "tests/test_cart_integration.py",
        "tests/unit/test_cart.py",
    ]
    result = map_source_to_tests("src/cart.py", candidates)

    assert result.has_matches is True
    assert len(result.matches) == 3

    # 'direct' matches must precede 'compound' matches
    assert result.matches[0].confidence == "direct"
    assert result.matches[1].confidence == "direct"
    assert result.matches[2].confidence == "compound"
    assert result.matches[2].test_file == "tests/test_cart_integration.py"


def test_map_source_to_tests_no_match():
    """Source files with no corresponding tests must return empty matches."""
    candidates = ["tests/test_cart.py", "tests/test_checkout.py"]
    result = map_source_to_tests("src/notifications.py", candidates)

    assert result.has_matches is False
    assert result.matches == []
    assert result.matched_test_files == []


def test_map_source_to_tests_unrelated_substring_is_rejected():
    """
    Substrings that share letters but are unrelated words must NOT match.
    e.g., 'art.py' shares letters with 'cart' in 'test_cart.py', but must not match.
    """
    candidates = ["tests/test_cart.py"]
    result = map_source_to_tests("src/art.py", candidates)

    assert result.has_matches is False
    assert result.matches == []


def test_map_source_to_tests_does_not_treat_test_file_as_source():
    """Test files passed as source files must not be mapped to other test files."""
    candidates = ["tests/test_cart.py", "tests/test_checkout.py"]
    result = map_source_to_tests("tests/test_cart.py", candidates)

    assert result.has_matches is False
    assert result.matches == []


def test_map_source_to_tests_non_python_file_returns_no_matches():
    """Non-python changed files (e.g. README.md or requirements.txt) must return empty matches."""
    candidates = ["tests/test_cart.py"]
    result_readme = map_source_to_tests("README.md", candidates)
    result_reqs = map_source_to_tests("requirements.txt", candidates)

    assert result_readme.has_matches is False
    assert result_reqs.has_matches is False


def test_map_changed_sources_to_tests_orchestrator(tmp_path):
    """High-level map_changed_sources_to_tests properly handles a list of varied changed files."""
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    (test_dir / "test_cart.py").write_text("# test", encoding="utf-8")
    (test_dir / "test_checkout.py").write_text("# test", encoding="utf-8")

    changed = [
        r"src\cart.py",
        "README.md",
        "tests/test_checkout.py",
        "src/unknown_module.py"
    ]

    results = map_changed_sources_to_tests(changed, repo_path=str(tmp_path), test_dir="tests")
    assert len(results) == 4

    # src/cart.py should have matched tests/test_cart.py
    cart_res = results[0]
    assert cart_res.source_file == "src/cart.py"
    assert cart_res.has_matches is True
    assert cart_res.matched_test_files == ["tests/test_cart.py"]

    # README.md should have no matches
    assert results[1].has_matches is False

    # tests/test_checkout.py should not be mapped as a source
    assert results[2].has_matches is False

    # unknown_module.py has no corresponding test
    assert results[3].has_matches is False
