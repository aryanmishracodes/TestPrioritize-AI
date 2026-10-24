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


# ============================================================================
# AST Import Extraction & Analysis Tests
# ============================================================================


def test_extract_ast_imports_direct_and_from_imports(tmp_path):
    """AST import extraction correctly parses direct imports, from imports, and member aliases."""
    from test_mapper import extract_ast_imports

    code = """
import os
import sys
import src.cart as cart_mod
from src.checkout import apply_discount, FREE_SHIPPING_THRESHOLD
from src import pricing
"""
    f_path = tmp_path / "sample.py"
    f_path.write_text(code, encoding="utf-8")

    imports = extract_ast_imports(str(f_path), repo_path=str(tmp_path))
    assert "os" in imports
    assert "sys" in imports
    assert "src.cart" in imports
    assert "cart" in imports  # leaf module
    assert "src.checkout" in imports
    assert "checkout" in imports  # leaf module
    assert "src.checkout.apply_discount" in imports
    assert "src.pricing" in imports
    assert "pricing" in imports


def test_extract_ast_imports_relative_imports(tmp_path):
    """AST import extraction handles relative package imports."""
    from test_mapper import extract_ast_imports

    pkg_dir = tmp_path / "src" / "sub"
    pkg_dir.mkdir(parents=True)
    code = """
from . import helper
from .. import cart
"""
    f_path = pkg_dir / "worker.py"
    f_path.write_text(code, encoding="utf-8")

    imports = extract_ast_imports(str(f_path), repo_path=str(tmp_path))
    assert len(imports) > 0


def test_extract_ast_imports_syntax_error_handled_gracefully(tmp_path):
    """Files with broken syntax must return an empty set without raising exceptions."""
    from test_mapper import extract_ast_imports

    broken_code = "def broken_syntax( { this is invalid python"
    f_path = tmp_path / "broken.py"
    f_path.write_text(broken_code, encoding="utf-8")

    imports = extract_ast_imports(str(f_path), repo_path=str(tmp_path))
    assert imports == set()


def test_extract_ast_imports_missing_file_handled_gracefully(tmp_path):
    """Non-existent file paths return empty sets without crashing."""
    from test_mapper import extract_ast_imports

    missing = str(tmp_path / "non_existent_file.py")
    assert extract_ast_imports(missing) == set()


def test_map_source_to_tests_ast_differently_named_test(tmp_path):
    """
    CRITICAL AST TEST:
    A test file named 'tests/test_billing_workflow.py' does NOT lexically match 'src/checkout.py'.
    However, because it contains 'from src.checkout import apply_discount',
    AST analysis correctly maps 'src/checkout.py' to it with 'direct' confidence!
    """
    repo = tmp_path
    src_dir = repo / "src"
    test_dir = repo / "tests"
    src_dir.mkdir()
    test_dir.mkdir()

    (src_dir / "checkout.py").write_text("def apply_discount(t, p): return t", encoding="utf-8")
    test_file = test_dir / "test_billing_workflow.py"
    test_file.write_text("""
import pytest
from src.checkout import apply_discount

def test_billing():
    assert apply_discount(100, 10) == 100
""", encoding="utf-8")

    result = map_source_to_tests(
        source_file="src/checkout.py",
        candidate_test_files=["tests/test_billing_workflow.py"],
        repo_path=str(repo)
    )

    assert result.has_matches is True
    assert len(result.matches) == 1
    match = result.matches[0]
    assert match.test_file == "tests/test_billing_workflow.py"
    assert match.confidence == "direct"
    assert "AST import match" in match.reason


def test_map_source_to_tests_unrelated_modules_not_matched(tmp_path):
    """A test importing unrelated libraries (pytest, requests, cart) must NOT match checkout.py."""
    repo = tmp_path
    src_dir = repo / "src"
    test_dir = repo / "tests"
    src_dir.mkdir()
    test_dir.mkdir()

    (src_dir / "checkout.py").write_text("def checkout(): pass", encoding="utf-8")
    (src_dir / "cart.py").write_text("def cart(): pass", encoding="utf-8")
    test_file = test_dir / "test_unrelated.py"
    test_file.write_text("""
import pytest
import os
from src.cart import cart
""", encoding="utf-8")

    result = map_source_to_tests(
        source_file="src/checkout.py",
        candidate_test_files=["tests/test_unrelated.py"],
        repo_path=str(repo)
    )

    assert result.has_matches is False
    assert result.matches == []


def test_map_source_to_tests_lexical_fallback_when_syntax_error(tmp_path):
    """When a test file has a syntax error, lexical matching serves as the robust fallback."""
    repo = tmp_path
    test_dir = repo / "tests"
    test_dir.mkdir()

    # Syntax error in test file
    (test_dir / "test_cart.py").write_text("def syntax_error( {", encoding="utf-8")

    result = map_source_to_tests(
        source_file="src/cart.py",
        candidate_test_files=["tests/test_cart.py"],
        repo_path=str(repo)
    )

    # Lexical fallback succeeds even though AST parsing failed
    assert result.has_matches is True
    assert result.matches[0].test_file == "tests/test_cart.py"
    assert result.matches[0].confidence == "direct"
    assert "Exact module stem match" in result.matches[0].reason


def test_transitive_ast_dependency_mapping(tmp_path):
    """
    When src/payment.py imports src/checkout.py, and src/checkout.py changes:
    test_payment.py is discovered as a candidate test via transitive AST dependency.
    """
    repo = tmp_path
    src_dir = repo / "src"
    test_dir = repo / "tests"
    src_dir.mkdir()
    test_dir.mkdir()

    (src_dir / "checkout.py").write_text("def process(): pass", encoding="utf-8")
    (src_dir / "payment.py").write_text("""
from src.checkout import process
def pay(): process()
""", encoding="utf-8")

    (test_dir / "test_payment.py").write_text("""
from src.payment import pay
def test_pay(): pay()
""", encoding="utf-8")

    result = map_source_to_tests(
        source_file="src/checkout.py",
        candidate_test_files=["tests/test_payment.py"],
        repo_path=str(repo)
    )

    assert result.has_matches is True
    match = result.matches[0]
    assert match.test_file == "tests/test_payment.py"
    assert match.confidence == "compound"
    assert "AST dependency match" in match.reason


# ============================================================================
# Upstream & Bidirectional Dependency-Aware Mapping Tests
# ============================================================================


def test_judge_scenario_upstream_dependency_mapping(tmp_path):
    """
    Exact judge scenario:
    src/checkout.py imports src.cart.calculate_total.
    tests/test_checkout.py imports checkout.
    tests/test_cart.py imports cart.
    When only src/checkout.py changes:
    Both tests/test_checkout.py and tests/test_cart.py must be candidates.
    test_checkout.py has direct confidence; test_cart.py has dependency match evidence.
    """
    from test_mapper import find_imported_source_files
    from ranking_engine import rank_tests

    src = tmp_path / "src"
    tests = tmp_path / "tests"
    src.mkdir()
    tests.mkdir()

    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "checkout.py").write_text("""
from src.cart import calculate_total

def checkout(items):
    return calculate_total(items)
""", encoding="utf-8")

    (src / "cart.py").write_text("""
def calculate_total(items):
    return sum(items)
""", encoding="utf-8")

    (tests / "test_checkout.py").write_text("""
from src.checkout import checkout

def test_checkout():
    assert checkout([10, 20]) == 30
""", encoding="utf-8")

    (tests / "test_cart.py").write_text("""
from src.cart import calculate_total

def test_cart():
    assert calculate_total([10, 20]) == 30
""", encoding="utf-8")

    # 1. find_imported_source_files directly
    imported = find_imported_source_files("src/checkout.py", repo_path=str(tmp_path))
    assert "src/cart.py" in imported

    # 2. map_changed_sources_to_tests
    results = map_changed_sources_to_tests(["src/checkout.py"], repo_path=str(tmp_path), test_dir="tests")
    assert len(results) == 1
    mapping_res = results[0]
    assert mapping_res.has_matches is True

    matched_tests = [m.test_file for m in mapping_res.matches]
    assert "tests/test_checkout.py" in matched_tests
    assert "tests/test_cart.py" in matched_tests

    # Verify checkout match details
    checkout_match = next(m for m in mapping_res.matches if m.test_file == "tests/test_checkout.py")
    assert checkout_match.confidence == "direct"
    assert "checkout" in checkout_match.reason

    # Verify cart match details
    cart_match = next(m for m in mapping_res.matches if m.test_file == "tests/test_cart.py")
    assert cart_match.confidence == "compound"
    assert "Dependency match: changed source 'src/checkout.py' imports 'src/cart.py'" in cart_match.reason
    assert "test imports 'src/cart.py'" in cart_match.reason

    # 3. Ranking evaluation
    ranking = rank_tests(results)
    assert ranking.total_candidates == 2
    top = ranking.ranked_tests[0]
    second = ranking.ranked_tests[1]

    assert top.test_file == "tests/test_checkout.py"
    assert top.score == 50
    assert top.priority == "MEDIUM"

    assert second.test_file == "tests/test_cart.py"
    assert second.score == 25
    assert second.priority == "LOW"


def test_reverse_direction_downstream_dependency_mapping(tmp_path):
    """
    Reverse direction:
    src/cart.py changes. src/checkout.py imports src/cart.py.
    tests/test_cart.py (direct) and tests/test_checkout.py (downstream dependency) are candidates.
    """
    from ranking_engine import rank_tests

    src = tmp_path / "src"
    tests = tmp_path / "tests"
    src.mkdir()
    tests.mkdir()

    (src / "cart.py").write_text("def calc(): pass", encoding="utf-8")
    (src / "checkout.py").write_text("from src.cart import calc\ndef checkout(): calc()", encoding="utf-8")

    (tests / "test_cart.py").write_text("from src.cart import calc\ndef test_cart(): pass", encoding="utf-8")
    (tests / "test_checkout.py").write_text("from src.checkout import checkout\ndef test_checkout(): pass", encoding="utf-8")

    results = map_changed_sources_to_tests(["src/cart.py"], repo_path=str(tmp_path), test_dir="tests")
    mapping_res = results[0]
    matched_tests = [m.test_file for m in mapping_res.matches]

    assert "tests/test_cart.py" in matched_tests
    assert "tests/test_checkout.py" in matched_tests

    ranking = rank_tests(results)
    assert ranking.ranked_tests[0].test_file == "tests/test_cart.py"
    assert ranking.ranked_tests[0].score == 50
    assert ranking.ranked_tests[1].test_file == "tests/test_checkout.py"
    assert ranking.ranked_tests[1].score == 25


def test_no_duplicate_candidate_paths(tmp_path):
    """
    A test file that qualifies through both direct stem and import or dependency
    is deduplicated and retains its direct match confidence.
    """
    src = tmp_path / "src"
    tests = tmp_path / "tests"
    src.mkdir()
    tests.mkdir()

    (src / "cart.py").write_text("def calc(): pass", encoding="utf-8")
    (tests / "test_cart.py").write_text("from src.cart import calc\ndef test_cart(): pass", encoding="utf-8")

    results = map_changed_sources_to_tests(["src/cart.py"], repo_path=str(tmp_path), test_dir="tests")
    matches = results[0].matches

    # Exactly 1 match for test_cart.py
    cart_matches = [m for m in matches if m.test_file == "tests/test_cart.py"]
    assert len(cart_matches) == 1
    assert cart_matches[0].confidence == "direct"


def test_unrelated_tests_are_not_included(tmp_path):
    """Unrelated test files are not added to candidate list when no dependency exists."""
    src = tmp_path / "src"
    tests = tmp_path / "tests"
    src.mkdir()
    tests.mkdir()

    (src / "checkout.py").write_text("def checkout(): pass", encoding="utf-8")
    (src / "users.py").write_text("def get_user(): pass", encoding="utf-8")

    (tests / "test_checkout.py").write_text("from src.checkout import checkout\ndef test_co(): pass", encoding="utf-8")
    (tests / "test_users.py").write_text("from src.users import get_user\ndef test_u(): pass", encoding="utf-8")

    results = map_changed_sources_to_tests(["src/checkout.py"], repo_path=str(tmp_path), test_dir="tests")
    matched_tests = [m.test_file for m in results[0].matches]

    assert "tests/test_checkout.py" in matched_tests
    assert "tests/test_users.py" not in matched_tests


def test_circular_imports_handled_safely(tmp_path):
    """Circular imports between source files do not cause infinite recursion."""
    from test_mapper import find_imported_source_files

    src = tmp_path / "src"
    tests = tmp_path / "tests"
    src.mkdir()
    tests.mkdir()

    # checkout imports cart, cart imports checkout
    (src / "checkout.py").write_text("from src.cart import get_cart\ndef checkout(): pass", encoding="utf-8")
    (src / "cart.py").write_text("from src.checkout import checkout\ndef get_cart(): pass", encoding="utf-8")

    (tests / "test_checkout.py").write_text("from src.checkout import checkout\ndef test_checkout(): pass", encoding="utf-8")
    (tests / "test_cart.py").write_text("from src.cart import get_cart\ndef test_cart(): pass", encoding="utf-8")

    imported = find_imported_source_files("src/checkout.py", repo_path=str(tmp_path))
    assert "src/cart.py" in imported
    assert "src/checkout.py" not in imported

    results = map_changed_sources_to_tests(["src/checkout.py"], repo_path=str(tmp_path), test_dir="tests")
    assert len(results[0].matches) == 2


def test_relative_package_imports(tmp_path):
    """Relative imports within subpackages resolve properly to upstream dependencies."""
    from test_mapper import find_imported_source_files

    pkg = tmp_path / "pkg"
    tests = tmp_path / "tests"
    pkg.mkdir()
    tests.mkdir()

    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "core.py").write_text("def core_fn(): pass", encoding="utf-8")
    (pkg / "utils.py").write_text("from .core import core_fn\ndef util(): core_fn()", encoding="utf-8")

    (tests / "test_utils.py").write_text("from pkg.utils import util\ndef test_utils(): pass", encoding="utf-8")
    (tests / "test_core.py").write_text("from pkg.core import core_fn\ndef test_core(): pass", encoding="utf-8")

    imported = find_imported_source_files("pkg/utils.py", repo_path=str(tmp_path))
    assert "pkg/core.py" in imported

    results = map_changed_sources_to_tests(["pkg/utils.py"], repo_path=str(tmp_path), test_dir="tests")
    matched = [m.test_file for m in results[0].matches]
    assert "tests/test_utils.py" in matched
    assert "tests/test_core.py" in matched


def test_malformed_syntax_and_missing_imports_handled_gracefully(tmp_path):
    """Files with broken syntax or unresolvable imports do not crash discovery or mapping."""
    from test_mapper import find_imported_source_files

    src = tmp_path / "src"
    tests = tmp_path / "tests"
    src.mkdir()
    tests.mkdir()

    # Syntax error in changed source
    (src / "broken.py").write_text("def broken(: syntax error", encoding="utf-8")
    # File importing non-existent module
    (src / "missing.py").write_text("import nonexistent_library_xyz\nfrom non_existent_pkg import foo", encoding="utf-8")

    assert find_imported_source_files("src/broken.py", repo_path=str(tmp_path)) == set()
    assert find_imported_source_files("src/missing.py", repo_path=str(tmp_path)) == set()
    assert find_imported_source_files("src/does_not_exist.py", repo_path=str(tmp_path)) == set()

    results = map_changed_sources_to_tests(["src/broken.py", "src/missing.py"], repo_path=str(tmp_path), test_dir="tests")
    assert len(results) == 2
    assert results[0].matches == []
    assert results[1].matches == []

