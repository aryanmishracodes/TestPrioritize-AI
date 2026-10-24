"""
tests/test_diff_checker.py
Automated tests for Git change detection in diff_checker.py.
Uses isolated temporary Git repositories to verify added, modified,
deleted, renamed files, and error handling.
"""

import subprocess
import pytest
from diff_checker import (
    FileChange,
    GitCommandError,
    GitRevisionError,
    NotAGitRepositoryError,
    get_changed_file_paths,
    get_changed_files,
)


def _init_test_git_repo(repo_dir) -> str:
    """Helper to initialize an isolated git repository with test author config."""
    repo_path = str(repo_dir)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo_path, check=True, capture_output=True)
    return repo_path


def _commit_all(repo_path: str, message: str) -> str:
    """Helper to stage all files, commit, and return commit hash."""
    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo_path, check=True, capture_output=True)
    res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_path, check=True, capture_output=True, text=True)
    return res.stdout.strip()


def test_non_git_directory_raises_not_a_git_repository_error(tmp_path):
    """Calling get_changed_files on a non-git directory must raise NotAGitRepositoryError."""
    with pytest.raises(NotAGitRepositoryError, match="not a Git repository"):
        get_changed_files("HEAD~1", "HEAD", repo_path=str(tmp_path))


def test_non_existent_directory_raises_not_a_git_repository_error(tmp_path):
    """Calling get_changed_files on a missing directory must raise NotAGitRepositoryError."""
    missing = tmp_path / "does_not_exist"
    with pytest.raises(NotAGitRepositoryError, match="does not exist"):
        get_changed_files("HEAD~1", "HEAD", repo_path=str(missing))


def test_invalid_revision_raises_git_revision_error(tmp_path):
    """Providing a non-existent commit or branch name must raise GitRevisionError."""
    repo = _init_test_git_repo(tmp_path)
    (tmp_path / "file.txt").write_text("initial", encoding="utf-8")
    _commit_all(repo, "initial commit")

    with pytest.raises(GitRevisionError, match="Invalid or unresolved Git revision"):
        get_changed_files("non_existent_branch_123", "HEAD", repo_path=repo)


def test_empty_revision_arguments_raise_value_error(tmp_path):
    """Passing empty or whitespace-only revision strings must raise ValueError."""
    repo = _init_test_git_repo(tmp_path)
    with pytest.raises(ValueError, match="base_ref must be a non-empty string"):
        get_changed_files("", "HEAD", repo_path=repo)

    with pytest.raises(ValueError, match="target_ref must be a non-empty string"):
        get_changed_files("HEAD", "   ", repo_path=repo)


def test_identical_revisions_return_empty_list(tmp_path):
    """Comparing a revision with itself must return an empty list without running diff."""
    repo = _init_test_git_repo(tmp_path)
    (tmp_path / "file.txt").write_text("initial", encoding="utf-8")
    commit_1 = _commit_all(repo, "initial commit")

    changes = get_changed_files(commit_1, commit_1, repo_path=repo)
    assert changes == []


def test_detect_added_file(tmp_path):
    """An added file must be detected with change_type='added'."""
    repo = _init_test_git_repo(tmp_path)
    (tmp_path / "initial.txt").write_text("hello", encoding="utf-8")
    commit_1 = _commit_all(repo, "initial commit")

    # Add a new file in a subdirectory
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "checkout.py").write_text("def checkout(): pass\n", encoding="utf-8")
    commit_2 = _commit_all(repo, "add checkout module")

    changes = get_changed_files(commit_1, commit_2, repo_path=repo)
    assert len(changes) == 1
    assert changes[0].path == "src/checkout.py"
    assert changes[0].change_type == "added"
    assert changes[0].old_path is None


def test_detect_modified_file(tmp_path):
    """Modifying existing file contents must be detected with change_type='modified'."""
    repo = _init_test_git_repo(tmp_path)
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    target_file = src_dir / "cart.py"
    target_file.write_text("version = 1\n", encoding="utf-8")
    commit_1 = _commit_all(repo, "commit 1")

    target_file.write_text("version = 2\n", encoding="utf-8")
    commit_2 = _commit_all(repo, "commit 2")

    changes = get_changed_files(commit_1, commit_2, repo_path=repo)
    assert len(changes) == 1
    assert changes[0].path == "src/cart.py"
    assert changes[0].change_type == "modified"


def test_detect_deleted_file(tmp_path):
    """Deleting a file must be detected with change_type='deleted'."""
    repo = _init_test_git_repo(tmp_path)
    old_file = tmp_path / "obsolete.txt"
    old_file.write_text("to be deleted\n", encoding="utf-8")
    commit_1 = _commit_all(repo, "commit 1")

    old_file.unlink()
    commit_2 = _commit_all(repo, "delete file")

    changes = get_changed_files(commit_1, commit_2, repo_path=repo)
    assert len(changes) == 1
    assert changes[0].path == "obsolete.txt"
    assert changes[0].change_type == "deleted"


def test_detect_renamed_file(tmp_path):
    """Renaming a file must be detected with change_type='renamed' and old_path populated."""
    repo = _init_test_git_repo(tmp_path)
    old_file = tmp_path / "original_name.py"
    old_file.write_text("def stable_code():\n    return 42\n", encoding="utf-8")
    commit_1 = _commit_all(repo, "commit 1")

    # Rename using git mv
    subprocess.run(
        ["git", "mv", "original_name.py", "renamed_name.py"],
        cwd=repo,
        check=True,
        capture_output=True
    )
    commit_2 = _commit_all(repo, "rename file")

    changes = get_changed_files(commit_1, commit_2, repo_path=repo)
    assert len(changes) == 1
    assert changes[0].change_type == "renamed"
    assert changes[0].path == "renamed_name.py"
    assert changes[0].old_path == "original_name.py"


def test_detect_multiple_mixed_changes_sorted_deterministically(tmp_path):
    """Multiple mixed changes should be detected and sorted alphabetically by path."""
    repo = _init_test_git_repo(tmp_path)
    (tmp_path / "file_a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "file_b.txt").write_text("b", encoding="utf-8")
    commit_1 = _commit_all(repo, "commit 1")

    # Modify file_a, delete file_b, add file_c
    (tmp_path / "file_a.txt").write_text("a updated", encoding="utf-8")
    (tmp_path / "file_b.txt").unlink()
    (tmp_path / "file_c.txt").write_text("c", encoding="utf-8")
    commit_2 = _commit_all(repo, "commit 2")

    changes = get_changed_files(commit_1, commit_2, repo_path=repo)
    paths = [c.path for c in changes]
    assert paths == ["file_a.txt", "file_b.txt", "file_c.txt"]

    change_map = {c.path: c.change_type for c in changes}
    assert change_map["file_a.txt"] == "modified"
    assert change_map["file_b.txt"] == "deleted"
    assert change_map["file_c.txt"] == "added"


def test_get_changed_file_paths_convenience_helper(tmp_path):
    """get_changed_file_paths should return just the list of path strings."""
    repo = _init_test_git_repo(tmp_path)
    (tmp_path / "sample.py").write_text("x = 1\n", encoding="utf-8")
    commit_1 = _commit_all(repo, "commit 1")

    (tmp_path / "sample.py").write_text("x = 2\n", encoding="utf-8")
    commit_2 = _commit_all(repo, "commit 2")

    paths = get_changed_file_paths(commit_1, commit_2, repo_path=repo)
    assert paths == ["sample.py"]
