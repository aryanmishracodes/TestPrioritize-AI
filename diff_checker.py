"""
diff_checker.py
Part of TestPrioritize AI.

Safely detects changed, added, deleted, and renamed files between two
Git revisions using Python's subprocess module (without executing shell commands).
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional


class GitDiffError(Exception):
    """Base exception for all Git change detection errors."""
    pass


class NotAGitRepositoryError(GitDiffError):
    """Raised when the specified directory is not a valid Git repository."""
    pass


class GitRevisionError(GitDiffError):
    """Raised when a specified Git revision (commit/branch/tag) cannot be found."""
    pass


class GitCommandError(GitDiffError):
    """Raised when an underlying Git command fails unexpectedly."""
    pass


@dataclass(frozen=True)
class FileChange:
    """
    Represents a single changed file between two Git revisions.
    
    Attributes:
        path: Relative path to the changed file (using forward slashes).
        change_type: Nature of change ('added', 'modified', 'deleted', 'renamed').
        old_path: Original path if the file was renamed, otherwise None.
    """
    path: str
    change_type: str
    old_path: Optional[str] = None


def _check_git_installed() -> None:
    """Verifies that git executable is available on the system PATH."""
    if shutil.which("git") is None:
        raise GitCommandError(
            "Git executable not found. Please ensure Git is installed and added to PATH."
        )


def _run_git_command(args: List[str], repo_path: str) -> subprocess.CompletedProcess:
    """
    Safely runs a Git command with shell=False and returns the CompletedProcess.
    """
    _check_git_installed()
    
    cmd = ["git", "-C", repo_path] + args
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            check=False,
        )
        return result
    except OSError as err:
        raise GitCommandError(f"Failed to execute Git command: {err}") from err


def _verify_git_repo(repo_path: str) -> None:
    """Verifies that the provided path exists and is inside a Git repository."""
    if not os.path.exists(repo_path):
        raise NotAGitRepositoryError(f"Directory does not exist: {repo_path}")

    if not os.path.isdir(repo_path):
        raise NotAGitRepositoryError(f"Path is not a directory: {repo_path}")

    res = _run_git_command(["rev-parse", "--is-inside-work-tree"], repo_path)
    if res.returncode != 0 or res.stdout.strip() != "true":
        raise NotAGitRepositoryError(
            f"The directory '{os.path.abspath(repo_path)}' is not a Git repository."
        )


def _verify_revision(ref: str, repo_path: str) -> None:
    """Verifies that a Git revision (branch, tag, or commit hash) can be resolved."""
    res = _run_git_command(["rev-parse", "--verify", ref], repo_path)
    if res.returncode != 0:
        err_msg = res.stderr.strip() or f"Revision '{ref}' not found."
        raise GitRevisionError(
            f"Invalid or unresolved Git revision '{ref}' in '{repo_path}': {err_msg}"
        )


def _parse_name_status_line(line: str) -> Optional[FileChange]:
    """
    Parses a single line of `git diff --name-status` output.
    Format examples:
      M    src/checkout.py
      A    src/new_module.py
      D    src/deprecated.py
      R100 old_name.py    new_name.py
    """
    parts = line.split("\t")
    if not parts or not parts[0].strip():
        return None

    status_code = parts[0].strip()
    status_char = status_code[0].upper()

    if status_char == "M":
        return FileChange(path=parts[1].strip().replace("\\", "/"), change_type="modified")
    elif status_char == "A":
        return FileChange(path=parts[1].strip().replace("\\", "/"), change_type="added")
    elif status_char == "D":
        return FileChange(path=parts[1].strip().replace("\\", "/"), change_type="deleted")
    elif status_char == "R":
        # Rename lines have 3 tab-separated tokens: status, old_path, new_path
        old_path = parts[1].strip().replace("\\", "/") if len(parts) > 1 else None
        new_path = parts[2].strip().replace("\\", "/") if len(parts) > 2 else parts[1].strip()
        return FileChange(path=new_path, change_type="renamed", old_path=old_path)
    elif status_char == "C":
        # Copied file
        new_path = parts[2].strip().replace("\\", "/") if len(parts) > 2 else parts[1].strip()
        return FileChange(path=new_path, change_type="added")
    else:
        # Fallback for other status types (e.g. Type changed 'T')
        path = parts[1].strip().replace("\\", "/") if len(parts) > 1 else parts[0].strip()
        return FileChange(path=path, change_type="modified")


def get_changed_files(
    base_ref: str,
    target_ref: str,
    repo_path: str = "."
) -> List[FileChange]:
    """
    Discovers all changed files between two Git revisions.

    Args:
        base_ref: Starting commit, branch, or tag (e.g. 'main', 'HEAD~1').
        target_ref: Target commit, branch, or tag (e.g. 'feature-branch', 'HEAD').
        repo_path: Path to the target Git repository (default: current directory).

    Returns:
        List of FileChange objects containing the path, change type, and optional old_path.

    Raises:
        ValueError: If base_ref or target_ref is empty.
        NotAGitRepositoryError: If repo_path is not a Git repository.
        GitRevisionError: If base_ref or target_ref cannot be resolved.
        GitCommandError: If the Git diff execution fails.
    """
    if not isinstance(base_ref, str) or not base_ref.strip():
        raise ValueError("base_ref must be a non-empty string.")
    if not isinstance(target_ref, str) or not target_ref.strip():
        raise ValueError("target_ref must be a non-empty string.")

    norm_repo = os.path.abspath(repo_path)
    _verify_git_repo(norm_repo)
    _verify_revision(base_ref.strip(), norm_repo)
    _verify_revision(target_ref.strip(), norm_repo)

    # If revisions are identical, no files changed
    if base_ref.strip() == target_ref.strip():
        return []

    # Run git diff with rename detection enabled
    res = _run_git_command(
        ["diff", "--name-status", "-M", base_ref.strip(), target_ref.strip()],
        norm_repo,
    )
    if res.returncode != 0:
        raise GitCommandError(f"git diff failed: {res.stderr.strip()}")

    changes: List[FileChange] = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        change = _parse_name_status_line(line)
        if change:
            changes.append(change)

    # Sort deterministically by file path
    changes.sort(key=lambda c: c.path)
    return changes


def get_changed_file_paths(
    base_ref: str,
    target_ref: str,
    repo_path: str = "."
) -> List[str]:
    """
    Convenience helper returning just the sorted list of changed file path strings.
    """
    return [change.path for change in get_changed_files(base_ref, target_ref, repo_path)]
