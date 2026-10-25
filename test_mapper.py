"""
test_mapper.py
Part of TestPrioritize AI.

Discovers test files and maps changed Python application source files
to candidate test files using:
1. AST-based static import analysis (resolves direct and transitive dependencies).
2. Deterministic lexical matching (exact module stem and compound delimited naming).
3. Graceful fallback on syntax errors, missing files, or non-Python assets.
"""

import ast
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ast_bfs import bfs_walk, collect_nodes_bfs


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


# ============================================================================
# AST Import Extraction & Analysis
# ============================================================================

def extract_ast_imports(file_path: str, repo_path: str = ".") -> Set[str]:
    """
    Safely parses a Python source or test file using the built-in ast module
    and extracts all imported module names, package paths, and imported members.

    Handles:
    - import x, import x.y as z
    - from x import y
    - from x.y import z
    - relative imports (from . import x, from ..x import y)
    - SyntaxError, UnicodeDecodeError, and missing files gracefully.

    Returns:
        Set of normalized module and sub-package import strings.
    """
    norm_repo = os.path.abspath(repo_path)
    full_path = file_path if os.path.isabs(file_path) else os.path.join(norm_repo, file_path)

    if not os.path.isfile(full_path):
        return set()

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        tree = ast.parse(content, filename=full_path)
    except (SyntaxError, UnicodeDecodeError, OSError, ValueError):
        # Gracefully handle unparseable files or syntax errors
        return set()

    imported: Set[str] = set()
    rel_file = normalize_path(file_path)
    file_dir = os.path.dirname(rel_file)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                imported.add(name)
                # If hierarchical (e.g. src.cart), also index leaf module
                if "." in name:
                    imported.add(name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            # Handle relative imports
            if node.level > 0:
                parts = file_dir.split("/") if file_dir else []
                # Pop (level - 1) components for relative directory resolution
                base_parts = parts[:max(0, len(parts) - (node.level - 1))]
                if mod:
                    resolved_mod = ".".join(base_parts + [mod])
                else:
                    resolved_mod = ".".join(base_parts)
                if resolved_mod:
                    imported.add(resolved_mod)
                    imported.add(resolved_mod.split(".")[-1])
            elif mod:
                imported.add(mod)
                if "." in mod:
                    imported.add(mod.split(".")[-1])

            # Also index imported members
            for alias in node.names:
                if mod:
                    imported.add(f"{mod}.{alias.name}")
                    # If imported from top-level package like 'src', index the member (e.g. from src import cart)
                    if mod == "src":
                        imported.add(alias.name)
                else:
                    imported.add(alias.name)

    return imported


def does_test_import_source(
    test_file: str,
    source_file: str,
    repo_path: str = "."
) -> bool:
    """
    Determines if test_file statically imports source_file using AST analysis.
    Checks:
    - Direct module stem (e.g. 'cart')
    - Full module dotted path (e.g. 'src.cart')
    - Dotted prefixes (e.g. 'src.cart.calculate_total')
    """
    stem = extract_module_stem(source_file)
    if not stem:
        return False

    norm_source = normalize_path(source_file)
    source_no_ext = norm_source[:-3] if norm_source.endswith(".py") else norm_source
    dotted_module = source_no_ext.replace("/", ".")

    test_imports = extract_ast_imports(test_file, repo_path=repo_path)
    if not test_imports:
        return False

    # Check for exact matches
    if stem in test_imports or dotted_module in test_imports:
        return True

    # Check for prefix matches (e.g. src.cart.calculate_cart_total)
    stem_prefix = f"{stem}."
    mod_prefix = f"{dotted_module}."
    for imp in test_imports:
        if imp.startswith(stem_prefix) or imp.startswith(mod_prefix):
            return True

    return False


def find_dependent_source_files(
    target_source: str,
    repo_path: str = "."
) -> Set[str]:
    """
    Finds other project source files that import target_source.
    Example: if src/checkout.py imports src/cart.py, and src/cart.py changed,
    src/checkout.py is returned as a dependent source.
    """
    norm_repo = os.path.abspath(repo_path)
    norm_target = normalize_path(target_source)
    stem = extract_module_stem(norm_target)
    if not stem:
        return set()

    source_no_ext = norm_target[:-3] if norm_target.endswith(".py") else norm_target
    dotted_module = source_no_ext.replace("/", ".")

    dependents: Set[str] = set()

    # Search common source locations
    search_dirs = [os.path.join(norm_repo, "src"), norm_repo]
    scanned_files: Set[str] = set()

    for s_dir in search_dirs:
        if not os.path.isdir(s_dir):
            continue
        for root, _, files in os.walk(s_dir):
            # Avoid test directories and caches
            rel_dir = normalize_path(os.path.relpath(root, norm_repo))
            if any(p in ("tests", "test", ".venv", "venv", ".git", "build", "dist", "demo_repo", "demo_repos") for p in rel_dir.split("/")):
                continue

            for file in files:
                if not file.endswith(".py") or file == "__init__.py":
                    continue
                full_path = os.path.join(root, file)
                rel_path = normalize_path(os.path.relpath(full_path, norm_repo))

                if rel_path == norm_target or rel_path in scanned_files or is_test_file(rel_path):
                    continue
                scanned_files.add(rel_path)

                imports = extract_ast_imports(rel_path, repo_path=norm_repo)
                if stem in imports or dotted_module in imports or any(imp.startswith(f"{dotted_module}.") for imp in imports):
                    dependents.add(rel_path)

    return dependents


def find_imported_source_files(
    source_file: str,
    repo_path: str = "."
) -> Set[str]:
    """
    Parses a source file with AST and identifies local project source files
    that are statically imported by it (upstream dependencies).

    Handles:
    - import module
    - from module import member (member can be a submodule or an exported function/class)
    - relative imports (from . import module, from .module import member)
    - package-qualified imports (from src.cart import calculate_total)

    Ignores:
    - Standard library and third-party packages not in repo_path
    - Unparseable files or syntax errors
    - Test files
    - The source file itself (self-imports or circular references)

    Returns:
        Set of normalized relative paths to discovered local source files.
    """
    norm_repo = os.path.abspath(repo_path)
    norm_source = normalize_path(source_file)
    full_source_path = norm_source if os.path.isabs(norm_source) else os.path.join(norm_repo, norm_source)

    if not os.path.isfile(full_source_path):
        return set()

    try:
        with open(full_source_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        tree = ast.parse(content, filename=full_source_path)
    except (SyntaxError, UnicodeDecodeError, OSError, ValueError):
        return set()

    source_dir = os.path.dirname(norm_source)
    imported_sources: Set[str] = set()

    def resolve_candidate(cand_mod: str, base_dir: str = "") -> Optional[str]:
        if not cand_mod:
            return None
        cand_rel = cand_mod.replace(".", "/")
        
        locations_to_check: List[str] = []
        if base_dir:
            locations_to_check.append(normalize_path(os.path.join(base_dir, cand_rel)))
        locations_to_check.append(normalize_path(cand_rel))
        if not cand_rel.startswith("src/") and not base_dir.startswith("src"):
            locations_to_check.append(normalize_path(os.path.join("src", cand_rel)))

        for loc in locations_to_check:
            # Check loc as a .py file
            py_file = loc + ".py"
            full_py = os.path.abspath(os.path.join(norm_repo, py_file))
            if full_py.startswith(norm_repo) and os.path.isfile(full_py):
                rel = normalize_path(os.path.relpath(full_py, norm_repo))
                if not is_test_file(rel) and rel != norm_source and os.path.basename(rel) != "__init__.py":
                    return rel

            # Check loc as a package directory with __init__.py
            init_file = loc + "/__init__.py"
            full_init = os.path.abspath(os.path.join(norm_repo, init_file))
            if full_init.startswith(norm_repo) and os.path.isfile(full_init):
                rel = normalize_path(os.path.relpath(full_init, norm_repo))
                if not is_test_file(rel) and rel != norm_source and os.path.basename(rel) != "__init__.py":
                    return rel

        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                resolved = resolve_candidate(name, source_dir)
                if resolved:
                    imported_sources.add(resolved)
                else:
                    parts = name.split(".")
                    while len(parts) > 1:
                        parts.pop()
                        resolved = resolve_candidate(".".join(parts), source_dir)
                        if resolved:
                            imported_sources.add(resolved)
                            break

        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            level = node.level

            curr_dir = source_dir
            if level > 0:
                parts = source_dir.split("/") if source_dir else []
                pop_count = level - 1
                if pop_count > 0:
                    parts = parts[:max(0, len(parts) - pop_count)]
                curr_dir = "/".join(parts)

            if mod:
                resolved = resolve_candidate(mod, curr_dir)
                if resolved:
                    imported_sources.add(resolved)
                else:
                    parts = mod.split(".")
                    while len(parts) > 1:
                        parts.pop()
                        resolved = resolve_candidate(".".join(parts), curr_dir)
                        if resolved:
                            imported_sources.add(resolved)
                            break

            for alias in node.names:
                combined = f"{mod}.{alias.name}" if mod else alias.name
                resolved = resolve_candidate(combined, curr_dir)
                if resolved:
                    imported_sources.add(resolved)

    return imported_sources


# ============================================================================
# Test Discovery & Mapping Orchestration
# ============================================================================

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
    candidate_test_files: List[str],
    repo_path: str = "."
) -> SourceMappingResult:
    """
    Maps a single source file to candidate test files using AST import analysis
    with deterministic lexical rules as a fallback.

    Rules applied:
    1. If source_file is a test file itself, it is NOT treated as an application source file.
    2. If source_file is not a Python source file, returns empty matches.
    3. Direct Match (Highest Confidence - direct):
       a. Test file statically imports source module (verified via AST).
       b. Test core name exactly matches source module stem (e.g. src/cart.py -> tests/test_cart.py).
    4. Compound Delimited Match (Secondary Confidence - compound):
       a. Test core name contains source stem bounded by underscores (e.g. tests/test_cart_integration.py).
       b. Transitive downstream dependency: another source file imports source_file, and test imports that source file.
       c. Transitive upstream dependency: source_file imports another local source file, and test imports or targets that dependency.

    Args:
        source_file: Path to the source file.
        candidate_test_files: List of discovered test files to match against.
        repo_path: Root directory of the repository (for AST file resolution).

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
    matched_test_paths: Set[str] = set()

    # Precompute transitive dependent source files (downstream: who imports source_file)
    dependent_sources = find_dependent_source_files(norm_source, repo_path=repo_path)
    # Precompute upstream imported source files (upstream: what source_file imports)
    imported_sources = find_imported_source_files(norm_source, repo_path=repo_path)

    for test_path in candidate_test_files:
        norm_test = normalize_path(test_path)
        if norm_test in matched_test_paths:
            continue

        core_test_name = extract_test_core_name(norm_test)
        imports_source = does_test_import_source(norm_test, norm_source, repo_path=repo_path)
        is_exact_stem = (core_test_name == stem) if core_test_name else False
        is_compound = False
        if core_test_name:
            is_compound = (
                core_test_name.startswith(f"{stem}_") or
                core_test_name.endswith(f"_{stem}") or
                f"_{stem}_" in core_test_name
            )

        # 1. Exact Stem Match (preserves canonical exact lexical reason)
        if is_exact_stem:
            matches.append(
                MappingMatch(
                    source_file=norm_source,
                    test_file=norm_test,
                    reason=f"Exact module stem match: '{stem}' -> '{os.path.basename(norm_test)}'",
                    confidence="direct"
                )
            )
            matched_test_paths.add(norm_test)
            continue

        # 2. AST Direct Import Match (test imports source under different test name)
        if imports_source:
            matches.append(
                MappingMatch(
                    source_file=norm_source,
                    test_file=norm_test,
                    reason=f"AST import match: '{os.path.basename(norm_test)}' directly imports '{stem}' from '{norm_source}'",
                    confidence="direct"
                )
            )
            matched_test_paths.add(norm_test)
            continue

        # 3. Compound Delimited Match (lexical fallback)
        if is_compound:
            matches.append(
                MappingMatch(
                    source_file=norm_source,
                    test_file=norm_test,
                    reason=f"Compound delimited module match: '{stem}' in '{os.path.basename(norm_test)}'",
                    confidence="compound"
                )
            )
            matched_test_paths.add(norm_test)
            continue

        # 4. Transitive AST Downstream Dependency Match
        if dependent_sources:
            for dep_src in sorted(list(dependent_sources)):
                if does_test_import_source(norm_test, dep_src, repo_path=repo_path):
                    dep_stem = extract_module_stem(dep_src) or os.path.basename(dep_src)
                    matches.append(
                        MappingMatch(
                            source_file=norm_source,
                            test_file=norm_test,
                            reason=f"AST dependency match: '{dep_stem}' imports '{stem}', and '{os.path.basename(norm_test)}' imports '{dep_stem}'",
                            confidence="compound"
                        )
                    )
                    matched_test_paths.add(norm_test)
                    break

        # 5. Upstream AST Dependency Match (changed source imports local module, test tests that module)
        if norm_test not in matched_test_paths and imported_sources:
            for imp_src in sorted(list(imported_sources)):
                imp_stem = extract_module_stem(imp_src)
                test_imports_imp = does_test_import_source(norm_test, imp_src, repo_path=repo_path)
                test_stem_matches_imp = (core_test_name == imp_stem) if (core_test_name and imp_stem) else False
                test_compound_matches_imp = False
                if core_test_name and imp_stem:
                    test_compound_matches_imp = (
                        core_test_name.startswith(f"{imp_stem}_") or
                        core_test_name.endswith(f"_{imp_stem}") or
                        f"_{imp_stem}_" in core_test_name
                    )

                if test_imports_imp or test_stem_matches_imp or test_compound_matches_imp:
                    if test_imports_imp:
                        reason = f"Dependency match: changed source '{norm_source}' imports '{imp_src}'; test imports '{imp_src}'."
                    else:
                        reason = f"Dependency match: changed source '{norm_source}' imports '{imp_src}'; test matches '{imp_src}'."
                    matches.append(
                        MappingMatch(
                            source_file=norm_source,
                            test_file=norm_test,
                            reason=reason,
                            confidence="compound"
                        )
                    )
                    matched_test_paths.add(norm_test)
                    break

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
    maps each changed file to candidate test files using AST and lexical rules.

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
        results.append(map_source_to_tests(file_path, available_tests, repo_path=repo_path))

    return results
