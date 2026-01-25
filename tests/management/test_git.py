"""Tests for git integration module.

Tests get_git_root and derive_index_from_git functions
using pytest-subprocess for git command mocking.
"""

from pathlib import Path
from unittest.mock import patch

from cocosearch.management.git import get_git_root, derive_index_from_git


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
