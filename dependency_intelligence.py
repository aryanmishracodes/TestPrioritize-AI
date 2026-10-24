"""
dependency_intelligence.py
Part of TestPrioritize AI.

Analyzes dependency manifest modifications (e.g. requirements.txt) and
retrieves external release intelligence, breaking change notices, and
migration guides using TinyFish Search.
"""

import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from tinyfish_client import (
    STATUS_HTTP_ERROR,
    STATUS_MISSING_KEY,
    STATUS_NETWORK_ERROR,
    STATUS_NO_RESULTS,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    SearchResultItem,
    search_tinyfish,
)

MANIFEST_REQUIREMENTS = "requirements.txt"

CATEGORY_BREAKING = "breaking_change"
CATEGORY_MIGRATION = "migration_guide"
CATEGORY_RELEASE = "release_notes"
CATEGORY_ADVISORY = "general_advisory"
CATEGORY_UNVERIFIED = "unverified"

STATUS_EVIDENCE_FOUND = "evidence_found"
STATUS_NO_RELEVANT_EVIDENCE = "no_relevant_evidence"
STATUS_MANIFEST_UNCHANGED = "manifest_unchanged"
STATUS_SKIPPED_MISSING_KEY = "skipped_missing_key"
STATUS_LOOKUP_FAILED = "lookup_failed"


@dataclass(frozen=True)
class DependencyChange:
    """
    Represents a single package version delta in a manifest.

    Attributes:
        package: Normalized package name.
        change_type: Nature of change ('added', 'modified', 'removed').
        old_version: Previous version string if available.
        new_version: Updated version string if available.
    """
    package: str
    change_type: str
    old_version: Optional[str] = None
    new_version: Optional[str] = None


@dataclass(frozen=True)
class DependencyEvidence:
    """
    Validated external intelligence item discovered for a dependency.

    Attributes:
        package: Target dependency name.
        title: Title of source document.
        url: Validated URL of the source.
        snippet: Content excerpt.
        category: Classified category (breaking_change, migration_guide, release_notes, etc.).
        is_relevant: Boolean indicating whether package relevance was confirmed.
        explanation: Transparent explanation of the finding.
    """
    package: str
    title: str
    url: str
    snippet: str
    category: str
    is_relevant: bool
    explanation: str


@dataclass(frozen=True)
class DependencyIntelligenceReport:
    """
    Complete structured report returned by the dependency intelligence module.

    Attributes:
        manifest_changed: Whether a dependency manifest was modified.
        dependencies_analyzed: List of package changes identified.
        findings: List of validated DependencyEvidence items.
        status: Overall status code.
        summary: Plain-English summary of the intelligence outcome.
    """
    manifest_changed: bool
    dependencies_analyzed: List[DependencyChange] = field(default_factory=list)
    findings: List[DependencyEvidence] = field(default_factory=list)
    status: str = STATUS_MANIFEST_UNCHANGED
    summary: str = ""

    @property
    def has_breaking_evidence(self) -> bool:
        """Returns True if any verified finding indicates breaking changes."""
        return any(
            f.is_relevant and f.category in (CATEGORY_BREAKING, CATEGORY_MIGRATION)
            for f in self.findings
        )

    @property
    def risky_packages(self) -> Set[str]:
        """Returns set of package names associated with verified breaking/migration evidence."""
        return {
            f.package for f in self.findings
            if f.is_relevant and f.category in (CATEGORY_BREAKING, CATEGORY_MIGRATION)
        }


def parse_requirements_content(content: str) -> Dict[str, str]:
    """
    Parses requirements.txt content into a dictionary of {package_name: version_specifier}.
    Safely ignores comments and empty lines.
    """
    packages: Dict[str, str] = {}
    if not content or not isinstance(content, str):
        return packages

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Strip inline comments
        line = line.split("#")[0].strip()

        # Match package name and version specs (==, >=, <=, ~=, !=)
        match = re.match(r"^([a-zA-Z0-9_\-\.]+)\s*([=><~]=?)\s*([a-zA-Z0-9_\-\.]+)", line)
        if match:
            pkg, _, ver = match.groups()
            norm_pkg = pkg.lower().replace("-", "_")
            packages[norm_pkg] = ver
        else:
            # Package specified without pinned version
            pkg_match = re.match(r"^([a-zA-Z0-9_\-\.]+)", line)
            if pkg_match:
                norm_pkg = pkg_match.group(1).lower().replace("-", "_")
                packages[norm_pkg] = "unpinned"

    return packages


def compute_dependency_diff(
    old_packages: Dict[str, str],
    new_packages: Dict[str, str]
) -> List[DependencyChange]:
    """
    Computes added, modified, and removed packages between two parsed package dictionaries.
    """
    changes: List[DependencyChange] = []

    # Check for added or modified
    for pkg, new_ver in new_packages.items():
        if pkg not in old_packages:
            changes.append(
                DependencyChange(package=pkg, change_type="added", new_version=new_ver)
            )
        elif old_packages[pkg] != new_ver:
            changes.append(
                DependencyChange(
                    package=pkg,
                    change_type="modified",
                    old_version=old_packages[pkg],
                    new_version=new_ver
                )
            )

    # Check for removed
    for pkg, old_ver in old_packages.items():
        if pkg not in new_packages:
            changes.append(
                DependencyChange(package=pkg, change_type="removed", old_version=old_ver)
            )

    changes.sort(key=lambda c: c.package)
    return changes


def build_search_query(
    package: str,
    old_version: Optional[str] = None,
    new_version: Optional[str] = None
) -> str:
    """
    Constructs a targeted search query for TinyFish.
    Focuses on official release notes, breaking changes, and migration guides.
    """
    clean_pkg = package.replace("_", "-")
    if new_version and new_version != "unpinned":
        return f"{clean_pkg} {new_version} release notes breaking changes migration guide"
    return f"{clean_pkg} release notes breaking changes"


def validate_and_categorize_evidence(
    item: SearchResultItem,
    package: str,
    new_version: Optional[str] = None
) -> DependencyEvidence:
    """
    Validates that a search result is genuinely relevant to the target package
    and categorizes the nature of the evidence.
    """
    norm_pkg = package.lower().replace("-", "_")
    pkg_alt = package.lower().replace("_", "-")

    text_to_check = f"{item.title} {item.snippet} {item.url}".lower()

    # Rule 1: Package name must appear in title, snippet, or URL
    has_package = norm_pkg in text_to_check or pkg_alt in text_to_check
    if not has_package:
        return DependencyEvidence(
            package=package,
            title=item.title,
            url=item.url,
            snippet=item.snippet,
            category=CATEGORY_UNVERIFIED,
            is_relevant=False,
            explanation=f"Result discarded: Package '{package}' was not found in document text."
        )

    # Rule 2: Categorization based on explicit keywords
    is_breaking = any(kw in text_to_check for kw in [
        "breaking change", "breaking changes", "incompatible", "deprecated in", "removed in"
    ])
    is_migration = any(kw in text_to_check for kw in [
        "migration guide", "migrating from", "upgrade guide", "how to upgrade"
    ])
    is_release = any(kw in text_to_check for kw in [
        "release notes", "changelog", "what's new", "whats new"
    ])

    if is_breaking:
        category = CATEGORY_BREAKING
        explanation = f"Potential breaking changes or deprecations reported for '{package}'."
    elif is_migration:
        category = CATEGORY_MIGRATION
        explanation = f"Migration instructions or upgrade guidelines identified for '{package}'."
    elif is_release:
        category = CATEGORY_RELEASE
        explanation = f"Official release documentation or changelog noted for '{package}'."
    else:
        category = CATEGORY_ADVISORY
        explanation = f"General external documentation matching package '{package}'."

    return DependencyEvidence(
        package=package,
        title=item.title,
        url=item.url,
        snippet=item.snippet,
        category=category,
        is_relevant=True,
        explanation=explanation
    )


def read_git_file_content(ref: str, file_path: str, repo_path: str) -> Optional[str]:
    """Safely retrieves file content at a given Git revision."""
    cmd = ["git", "-C", repo_path, "show", f"{ref}:{file_path}"]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            check=False
        )
        if res.returncode == 0:
            return res.stdout
    except Exception:
        pass
    return None


def analyze_dependency_risks(
    changed_files: List[str],
    repo_path: str = ".",
    base_ref: Optional[str] = None,
    target_ref: Optional[str] = None,
    api_key: Optional[str] = None
) -> DependencyIntelligenceReport:
    """
    Orchestrates dependency intelligence gathering:
    1. Checks if requirements.txt was modified.
    2. Identifies changed dependencies between base and target revisions if provided.
    3. Queries TinyFish Search for relevant package updates.
    4. Validates and categorizes findings.
    """
    norm_repo = os.path.abspath(repo_path)
    clean_changed = [f.replace("\\", "/").strip() for f in changed_files]

    # Step 1: Check manifest presence in changed files
    manifest_touched = any(
        f == MANIFEST_REQUIREMENTS or f.endswith(f"/{MANIFEST_REQUIREMENTS}")
        for f in clean_changed
    )

    if not manifest_touched:
        return DependencyIntelligenceReport(
            manifest_changed=False,
            dependencies_analyzed=[],
            findings=[],
            status=STATUS_MANIFEST_UNCHANGED,
            summary="No dependency manifest files were modified in this change."
        )

    # Step 2: Extract dependency changes
    old_content = ""
    new_content = ""

    if base_ref and target_ref:
        old_content = read_git_file_content(base_ref, MANIFEST_REQUIREMENTS, norm_repo) or ""
        new_content = read_git_file_content(target_ref, MANIFEST_REQUIREMENTS, norm_repo) or ""

    if not new_content:
        # Fall back to reading workspace file if target_ref reading wasn't applicable
        local_path = os.path.join(norm_repo, MANIFEST_REQUIREMENTS)
        if os.path.exists(local_path):
            try:
                with open(local_path, "r", encoding="utf-8", errors="replace") as f:
                    new_content = f.read()
            except Exception:
                pass

    old_pkgs = parse_requirements_content(old_content)
    new_pkgs = parse_requirements_content(new_content)
    dep_changes = compute_dependency_diff(old_pkgs, new_pkgs)

    # If diff yielded no changes but manifest was marked touched, analyze all new pkgs as fallback
    if not dep_changes and new_pkgs:
        dep_changes = [
            DependencyChange(package=pkg, change_type="modified", new_version=ver)
            for pkg, ver in new_pkgs.items()
        ]

    if not dep_changes:
        return DependencyIntelligenceReport(
            manifest_changed=True,
            dependencies_analyzed=[],
            findings=[],
            status=STATUS_NO_RELEVANT_EVIDENCE,
            summary="requirements.txt was touched, but no package version deltas could be established."
        )

    # Step 3: Query TinyFish for modified or added packages
    target_changes = [c for c in dep_changes if c.change_type in ("modified", "added")]
    if not target_changes:
        return DependencyIntelligenceReport(
            manifest_changed=True,
            dependencies_analyzed=dep_changes,
            findings=[],
            status=STATUS_NO_RELEVANT_EVIDENCE,
            summary="Only removed dependencies detected; no new release intelligence needed."
        )

    all_findings: List[DependencyEvidence] = []
    lookup_statuses: List[str] = []

    for change in target_changes:
        query = build_search_query(change.package, change.old_version, change.new_version)
        response = search_tinyfish(query=query, api_key=api_key)
        lookup_statuses.append(response.status)

        if response.status == STATUS_SUCCESS:
            for item in response.results:
                evidence = validate_and_categorize_evidence(item, change.package, change.new_version)
                if evidence.is_relevant:
                    all_findings.append(evidence)

    # Step 4: Determine overall status
    if any(s == STATUS_MISSING_KEY for s in lookup_statuses):
        final_status = STATUS_SKIPPED_MISSING_KEY
        summary = (
            f"Detected {len(target_changes)} dependency change(s), but TINYFISH_API_KEY was not "
            "available. External intelligence skipped; local test ranking preserved."
        )
    elif all(s in (STATUS_TIMEOUT, STATUS_NETWORK_ERROR, STATUS_HTTP_ERROR) for s in lookup_statuses):
        final_status = STATUS_LOOKUP_FAILED
        summary = "External intelligence lookup failed due to network/API error. Local ranking preserved."
    elif all_findings:
        final_status = STATUS_EVIDENCE_FOUND
        breaking_count = sum(1 for f in all_findings if f.category in (CATEGORY_BREAKING, CATEGORY_MIGRATION))
        summary = (
            f"Gathered {len(all_findings)} external finding(s) across {len(target_changes)} package(s). "
            f"{breaking_count} indicate potential breaking changes or migration notices."
        )
    else:
        final_status = STATUS_NO_RELEVANT_EVIDENCE
        summary = f"TinyFish search completed for {len(target_changes)} package(s), but returned no relevant documentation."

    return DependencyIntelligenceReport(
        manifest_changed=True,
        dependencies_analyzed=dep_changes,
        findings=all_findings,
        status=final_status,
        summary=summary
    )
