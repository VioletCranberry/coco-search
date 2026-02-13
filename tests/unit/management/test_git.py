"""Tests for git integration module.

Tests get_git_root, derive_index_from_git, get_current_branch, and
get_commit_hash functions using pytest-subprocess for git command mocking.
"""

from pathlib import Path

from cocosearch.management.git import (
    get_git_root,
    derive_index_from_git,
    get_current_branch,
    get_commit_hash,
)


class TestGetGitRoot:
    """Tests for get_git_root function."""

    def test_returns_path_in_git_repo(self, fp):
        """Returns Path when git rev-parse succeeds."""
        fp.register(
            ["git", "rev-parse", "--show-toplevel"],
            stdout="/home/user/myproject\n",
        )
        result = get_git_root()
        assert result == Path("/home/user/myproject")
        assert isinstance(result, Path)

    def test_returns_none_outside_repo(self, fp):
        """Returns None when git rev-parse fails with returncode 128."""
        fp.register(
            ["git", "rev-parse", "--show-toplevel"],
            returncode=128,
            stderr="fatal: not a git repository",
        )
        result = get_git_root()
        assert result is None

    def test_strips_trailing_whitespace(self, fp):
        """Strips trailing newlines from git output."""
        fp.register(
            ["git", "rev-parse", "--show-toplevel"],
            stdout="/path/to/repo\n\n",
        )
        result = get_git_root()
        assert result == Path("/path/to/repo")
        assert str(result) == "/path/to/repo"


class TestDeriveIndexFromGit:
    """Tests for derive_index_from_git function."""

    def test_returns_index_name_in_repo(self, fp):
        """Returns sanitized directory name when in git repo."""
        fp.register(
            ["git", "rev-parse", "--show-toplevel"],
            stdout="/home/user/my-project\n",
        )
        result = derive_index_from_git()
        # derive_index_name sanitizes hyphens to underscores
        assert result == "my_project"

    def test_returns_none_outside_repo(self, fp):
        """Returns None when not in git repository."""
        fp.register(
            ["git", "rev-parse", "--show-toplevel"],
            returncode=128,
            stderr="fatal: not a git repository",
        )
        result = derive_index_from_git()
        assert result is None

    def test_uses_directory_name_not_full_path(self, fp):
        """Uses only the last directory component for index name."""
        fp.register(
            ["git", "rev-parse", "--show-toplevel"],
            stdout="/very/deep/nested/path/to/coolproject\n",
        )
        result = derive_index_from_git()
        assert result == "coolproject"


class TestGetCurrentBranch:
    """Tests for get_current_branch function."""

    def test_returns_branch_name(self, fp):
        """Returns branch name when on a branch."""
        fp.register(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stdout="main\n",
        )
        result = get_current_branch()
        assert result == "main"

    def test_returns_none_for_detached_head(self, fp):
        """Returns None when in detached HEAD state."""
        fp.register(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stdout="HEAD\n",
        )
        result = get_current_branch()
        assert result is None

    def test_returns_none_outside_repo(self, fp):
        """Returns None when not in a git repo."""
        fp.register(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            returncode=128,
            stderr="fatal: not a git repository",
        )
        result = get_current_branch()
        assert result is None

    def test_with_path_argument(self, fp):
        """Uses -C flag when path is provided."""
        fp.register(
            ["git", "-C", "/my/project", "rev-parse", "--abbrev-ref", "HEAD"],
            stdout="feature-branch\n",
        )
        result = get_current_branch("/my/project")
        assert result == "feature-branch"

    def test_strips_whitespace(self, fp):
        """Strips trailing whitespace from output."""
        fp.register(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stdout="develop\n\n",
        )
        result = get_current_branch()
        assert result == "develop"


class TestGetCommitHash:
    """Tests for get_commit_hash function."""

    def test_returns_short_hash(self, fp):
        """Returns short commit hash by default."""
        fp.register(
            ["git", "rev-parse", "--short", "HEAD"],
            stdout="abc1234\n",
        )
        result = get_commit_hash()
        assert result == "abc1234"

    def test_returns_full_hash(self, fp):
        """Returns full hash when short=False."""
        full_hash = "abc1234def5678901234567890abcdef12345678"
        fp.register(
            ["git", "rev-parse", "HEAD"],
            stdout=f"{full_hash}\n",
        )
        result = get_commit_hash(short=False)
        assert result == full_hash

    def test_returns_none_outside_repo(self, fp):
        """Returns None when not in a git repo."""
        fp.register(
            ["git", "rev-parse", "--short", "HEAD"],
            returncode=128,
            stderr="fatal: not a git repository",
        )
        result = get_commit_hash()
        assert result is None

    def test_with_path_argument(self, fp):
        """Uses -C flag when path is provided."""
        fp.register(
            ["git", "-C", "/my/project", "rev-parse", "--short", "HEAD"],
            stdout="def5678\n",
        )
        result = get_commit_hash("/my/project")
        assert result == "def5678"

    def test_strips_whitespace(self, fp):
        """Strips trailing whitespace from output."""
        fp.register(
            ["git", "rev-parse", "--short", "HEAD"],
            stdout="abc1234\n\n",
        )
        result = get_commit_hash()
        assert result == "abc1234"
