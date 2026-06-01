"""Tests for git integration module.

Tests get_git_root, derive_index_from_git, get_current_branch,
get_commit_hash, is_worktree, and get_main_repo_root functions
using pytest-subprocess for git command mocking.
"""

from pathlib import Path

from cocosearch.management.git import (
    get_git_root,
    derive_index_from_git,
    get_current_branch,
    get_commit_hash,
    get_commits_behind,
    get_branch_commit_count,
    is_worktree,
    get_main_repo_root,
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
            ["git", "rev-parse", "--git-common-dir"],
            stdout="/home/user/my-project/.git\n",
        )
        result = derive_index_from_git()
        # derive_index_name sanitizes hyphens to underscores
        assert result == "my_project"

    def test_returns_none_outside_repo(self, fp):
        """Returns None when not in git repository."""
        fp.register(
            ["git", "rev-parse", "--git-common-dir"],
            returncode=128,
            stderr="fatal: not a git repository",
        )
        result = derive_index_from_git()
        assert result is None

    def test_passes_path_to_git(self, fp):
        """A path argument is forwarded to git via -C (resolve from target)."""
        fp.register(
            ["git", "-C", "/other/repo", "rev-parse", "--git-common-dir"],
            stdout="/other/repo/.git\n",
        )
        result = derive_index_from_git("/other/repo")
        assert result == "repo"

    def test_uses_directory_name_not_full_path(self, fp):
        """Uses only the last directory component for index name."""
        fp.register(
            ["git", "rev-parse", "--git-common-dir"],
            stdout="/very/deep/nested/path/to/coolproject/.git\n",
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


class TestGetCommitsBehind:
    """Tests for get_commits_behind function."""

    def test_returns_count(self, fp):
        """Returns integer count of commits behind."""
        fp.register(
            ["git", "rev-list", "abc1234..HEAD", "--count"],
            stdout="5\n",
        )
        result = get_commits_behind(from_commit="abc1234")
        assert result == 5

    def test_returns_zero_when_up_to_date(self, fp):
        """Returns 0 when from_commit matches HEAD."""
        fp.register(
            ["git", "rev-list", "abc1234..HEAD", "--count"],
            stdout="0\n",
        )
        result = get_commits_behind(from_commit="abc1234")
        assert result == 0

    def test_returns_none_outside_repo(self, fp):
        """Returns None when not in a git repo."""
        fp.register(
            ["git", "rev-list", "abc1234..HEAD", "--count"],
            returncode=128,
            stderr="fatal: not a git repository",
        )
        result = get_commits_behind(from_commit="abc1234")
        assert result is None

    def test_uses_c_flag_with_path(self, fp):
        """Uses -C flag when path is provided."""
        fp.register(
            ["git", "-C", "/my/project", "rev-list", "abc1234..HEAD", "--count"],
            stdout="3\n",
        )
        result = get_commits_behind("/my/project", from_commit="abc1234")
        assert result == 3

    def test_returns_none_for_invalid_commit(self, fp):
        """Returns None when from_commit is invalid (e.g., rebased away)."""
        fp.register(
            ["git", "rev-list", "deadbeef..HEAD", "--count"],
            returncode=128,
            stderr="fatal: bad revision 'deadbeef..HEAD'",
        )
        result = get_commits_behind(from_commit="deadbeef")
        assert result is None


class TestGetBranchCommitCount:
    """Tests for get_branch_commit_count function."""

    def test_returns_count(self, fp):
        """Returns total commit count for branch."""
        fp.register(
            ["git", "rev-list", "--count", "HEAD"],
            stdout="1234\n",
        )
        result = get_branch_commit_count()
        assert result == 1234

    def test_returns_none_outside_repo(self, fp):
        """Returns None when not in a git repo."""
        fp.register(
            ["git", "rev-list", "--count", "HEAD"],
            returncode=128,
            stderr="fatal: not a git repository",
        )
        result = get_branch_commit_count()
        assert result is None

    def test_uses_c_flag_with_path(self, fp):
        """Uses -C flag when path is provided."""
        fp.register(
            ["git", "-C", "/my/project", "rev-list", "--count", "HEAD"],
            stdout="567\n",
        )
        result = get_branch_commit_count("/my/project")
        assert result == 567

    def test_strips_whitespace(self, fp):
        """Strips trailing whitespace from output."""
        fp.register(
            ["git", "rev-list", "--count", "HEAD"],
            stdout="42\n\n",
        )
        result = get_branch_commit_count()
        assert result == 42


class TestIsWorktree:
    """Tests for is_worktree function."""

    def test_returns_true_for_worktree(self, tmp_path):
        """Returns True when .git is a file (worktree indicator)."""
        # Worktrees have a .git *file* pointing to the main repo
        (tmp_path / ".git").write_text("gitdir: /main/repo/.git/worktrees/feat-x\n")
        assert is_worktree(tmp_path) is True

    def test_returns_false_for_main_checkout(self, tmp_path):
        """Returns False when .git is a directory (main checkout)."""
        (tmp_path / ".git").mkdir()
        assert is_worktree(tmp_path) is False

    def test_returns_false_when_no_git(self, tmp_path):
        """Returns False when there is no .git at all."""
        assert is_worktree(tmp_path) is False


class TestGetMainRepoRoot:
    """Tests for get_main_repo_root function."""

    def test_returns_main_repo_root_from_worktree(self, fp):
        """Returns parent of --git-common-dir for worktrees."""
        fp.register(
            ["git", "rev-parse", "--git-common-dir"],
            stdout="/home/user/myproject/.git\n",
        )
        result = get_main_repo_root()
        assert result == Path("/home/user/myproject")

    def test_returns_main_repo_root_from_main_checkout(self, fp):
        """Returns same as get_git_root for main checkouts."""
        # For main checkouts, --git-common-dir returns .git (the same dir)
        fp.register(
            ["git", "rev-parse", "--git-common-dir"],
            stdout="/home/user/myproject/.git\n",
        )
        result = get_main_repo_root()
        assert result == Path("/home/user/myproject")

    def test_handles_relative_git_common_dir(self, fp, tmp_path):
        """Resolves relative --git-common-dir paths against the given path."""
        # git can return relative paths like "../../.git" from worktrees
        fp.register(
            ["git", "-C", str(tmp_path), "rev-parse", "--git-common-dir"],
            stdout=".git\n",
        )
        result = get_main_repo_root(tmp_path)
        # .git relative to tmp_path → resolve → parent = tmp_path
        assert result == tmp_path.resolve()

    def test_returns_none_outside_repo(self, fp):
        """Returns None when not in a git repository."""
        fp.register(
            ["git", "rev-parse", "--git-common-dir"],
            returncode=128,
            stderr="fatal: not a git repository",
        )
        result = get_main_repo_root()
        assert result is None

    def test_with_path_argument(self, fp):
        """Uses -C flag when path is provided."""
        fp.register(
            ["git", "-C", "/my/worktree", "rev-parse", "--git-common-dir"],
            stdout="/my/mainrepo/.git\n",
        )
        result = get_main_repo_root("/my/worktree")
        assert result == Path("/my/mainrepo")

    def test_strips_whitespace(self, fp):
        """Strips trailing whitespace from git output."""
        fp.register(
            ["git", "rev-parse", "--git-common-dir"],
            stdout="/home/user/repo/.git\n\n",
        )
        result = get_main_repo_root()
        assert result == Path("/home/user/repo")


class TestDeriveIndexFromGitWorktree:
    """Tests that derive_index_from_git uses main repo root."""

    def test_worktree_derives_same_name_as_main(self, fp):
        """Worktree derives index from main repo name, not worktree dir name."""
        # Simulate being in a worktree — --git-common-dir points to main repo
        fp.register(
            ["git", "rev-parse", "--git-common-dir"],
            stdout="/home/user/my-project/.git\n",
        )
        result = derive_index_from_git()
        assert result == "my_project"

    def test_main_checkout_still_works(self, fp):
        """Main checkout derives same name via get_main_repo_root."""
        fp.register(
            ["git", "rev-parse", "--git-common-dir"],
            stdout="/home/user/coolproject/.git\n",
        )
        result = derive_index_from_git()
        assert result == "coolproject"
