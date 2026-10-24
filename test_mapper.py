"""
test_mapper.py
Part of TestPrioritize AI.

Discovers test files and maps changed Python application source files
to candidate test files using deterministic lexical rules.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass(frozen=True)
class MappingMatch:
    """
    Represents a candidate test file mapped to a source file.

    Attributes:
        source_file: Normalized relative path of the changed source file.
        test_file: Normalized relative path of the mapped test file.
        reason: Plain-English explanation of why the match was made.
        confidence: Match confidence level ('direct' or 'compound').
    """
    source_file: str
    test_file: str
    reason: str
    confidence: str = "direct"


@dataclass(frozen=True)
class SourceMappingResult:
    """
    Structured mapping result for a single source file.

    Attributes:
        source_file: Normalized relative path of the source file.
        matches: List of MappingMatch candidate test files.
    """
    source_file: str
    matches: List[MappingMatch] = field(default_factory=list)

    @property
    def has_matches(self) -> bool:
        """Returns True if at least one candidate test file was matched."""
        return len(self.matches) > 0

    @property
    def matched_test_files(self) -> List[str]:
        """Convenience property returning just the matched test file paths."""
        return [m.test_file for m in self.matches]


def normalize_path(path: str) -> str:
    """
    Normalizes file path strings:
    - Converts Windows backslashes '\\' to POSIX forward slashes '/'.
    - Strips leading './' or redundant slashes.
    """
    if not isinstance(path, str):
        raise TypeError(f"Path must be a string, got {type(path).__name__}.")
    clean = path.strip().replace("\\", "/")
    while clean.startswith("./"):
        clean = clean[2:]
    return clean


def is_test_file(path: str) -> bool:
    """
    Determines if a given path represents a test file based on standard
    pytest naming conventions ('test_*.py' or '*_test.py') or location in a test directory.
    """
    norm = normalize_path(path)
    base = os.path.basename(norm)

    if not base.endswith(".py"):
        return False

    if base.startswith("test_") or base.endswith("_test.py"):
        return True

    # Check if the file is inside a test directory
    parts = norm.split("/")
    if any(p in ("tests", "test") for p in parts[:-1]):
        return True

    return False


def extract_module_stem(path: str) -> Optional[str]:
    """
    Extracts the base Python module stem from a file path.
    Example: 'src/checkout.py' -> 'checkout'
    Returns None if the file is not a Python source file or is __init__.py.
    """
    norm = normalize_path(path)
    base = os.path.basename(norm)
    if not base.endswith(".py") or base == "__init__.py":
        return None
    return base[:-3]


def extract_test_core_name(test_path: str) -> Optional[str]:
    """
    Extracts the core module name targeted by a test file.
    Examples:
      'tests/test_checkout.py' -> 'checkout'
      'tests/checkout_test.py' -> 'checkout'
    """
    norm = normalize_path(test_path)
    base = os.path.basename(norm)
    if not base.endswith(".py") or base == "__init__.py":
        return None

    stem = base[:-3]
    if stem.startswith("test_"):
        return stem[5:]
    elif stem.endswith("_test"):
        return stem[:-5]
    return stem


def discover_test_files(
    repo_path: str = ".",
    test_dir: str = "tests"
) -> List[str]:
    """
    Recursively discovers all test files in the specified test directory.

    Args:
        repo_path: Root directory of the repository (default: current directory).
        test_dir: Relative path to the test directory (default: 'tests').

    Returns:
        List of normalized relative paths to discovered test files, sorted alphabetically.
        If test_dir does not exist or is empty, returns an empty list.
    """
    if not isinstance(repo_path, str) or not repo_path.strip():
        raise ValueError("repo_path must be a non-empty string.")
    if not isinstance(test_dir, str) or not test_dir.strip():
        raise ValueError("test_dir must be a non-empty string.")

    norm_repo = os.path.abspath(repo_path)
    target_dir = os.path.join(norm_repo, test_dir)

    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        return []

    discovered: List[str] = []

    for root, _, files in os.walk(target_dir):
        for file in files:
            if not file.endswith(".py") or file == "__init__.py":
                continue

            if file.startswith("test_") or file.endswith("_test.py"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, norm_repo)
                discovered.append(normalize_path(rel_path))

    discovered.sort()
    return discovered


def map_source_to_tests(
    source_file: str,
    candidate_test_files: List[str]
) -> SourceMappingResult:
    """
    Maps a single source file to candidate test files using deterministic lexical rules.

    Rules applied:
    1. If source_file is a test file itself, it is NOT treated as an application source file (returns empty matches).
    2. If source_file is not a Python file, returns empty matches.
    3. Direct Match (Highest Confidence):
       Test core name exactly matches source module stem.
       e.g., 'src/cart.py' (stem 'cart') -> 'tests/test_cart.py' (core 'cart').
    4. Compound Delimited Match (Secondary Confidence):
       Test core name contains the source stem bounded by underscores.
       e.g., 'src/cart.py' -> 'tests/test_cart_integration.py'.
       (Note: Substrings without boundary delimiters like 'art.py' matching 'test_cart.py' are rejected).

    Args:
        source_file: Path to the source file.
        candidate_test_files: List of discovered test files to match against.

    Returns:
        SourceMappingResult with matched candidate test files and match reasons.
    """
    norm_source = normalize_path(source_file)

    # Rule 1: A test file is not an application source file
    if is_test_file(norm_source):
        return SourceMappingResult(source_file=norm_source, matches=[])

    # Rule 2: Must be a Python source module
    stem = extract_module_stem(norm_source)
    if not stem:
        return SourceMappingResult(source_file=norm_source, matches=[])

    matches: List[MappingMatch] = []

    for test_path in candidate_test_files:
        norm_test = normalize_path(test_path)
        core_test_name = extract_test_core_name(norm_test)
        if not core_test_name:
            continue

        # Rule 3: Exact stem match
        if core_test_name == stem:
            matches.append(
                MappingMatch(
                    source_file=norm_source,
                    test_file=norm_test,
                    reason=f"Exact module stem match: '{stem}' -> '{os.path.basename(norm_test)}'",
                    confidence="direct"
                )
            )
            continue

        # Rule 4: Compound match with underscore delimiter
        # e.g., 'cart' matches 'cart_checkout' or 'integration_cart'
        # but 'art' does NOT match 'cart'
        if core_test_name.startswith(f"{stem}_") or core_test_name.endswith(f"_{stem}") or f"_{stem}_" in core_test_name:
            matches.append(
                MappingMatch(
                    source_file=norm_source,
                    test_file=norm_test,
                    reason=f"Compound delimited module match: '{stem}' in '{os.path.basename(norm_test)}'",
                    confidence="compound"
                )
            )

    # Sort matches: 'direct' confidence first, then alphabetically by test path
    matches.sort(key=lambda m: (0 if m.confidence == "direct" else 1, m.test_file))
    return SourceMappingResult(source_file=norm_source, matches=matches)


def map_changed_sources_to_tests(
    changed_files: List[str],
    repo_path: str = ".",
    test_dir: str = "tests"
) -> List[SourceMappingResult]:
    """
    Convenience orchestrator that discovers test files in repo_path and
    maps each changed file to candidate test files.

    Args:
        changed_files: List of file paths that were modified, added, or deleted.
        repo_path: Repository root directory.
        test_dir: Subdirectory containing test files.

    Returns:
        List of SourceMappingResult objects for each input changed file.
    """
    if not isinstance(changed_files, list):
        raise TypeError("changed_files must be a list of file path strings.")

    available_tests = discover_test_files(repo_path=repo_path, test_dir=test_dir)

    results: List[SourceMappingResult] = []
    for file_path in changed_files:
        results.append(map_source_to_tests(file_path, available_tests))

    return results
