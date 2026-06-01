"""Git integration module for cocosearch.

Provides functions to detect git repository root and derive
index names from git repositories.
"""

import subprocess
from pathlib import Path


def is_worktree(path: str | Path | None = None) -> bool:
    """Check if the given path is inside a git worktree (not the main checkout).

    Worktrees have a .git *file* (pointing to the main repo's .git/worktrees/<name>),
    while the main checkout has a .git *directory*.

    Args:
        path: Directory to check. Defaults to current directory.

    Returns:
        True if the path is a git worktree, False otherwise.
    """
    git_path = (Path(path) if path else Path.cwd()) / ".git"
    return git_path.is_file()


def get_main_repo_root(path: str | Path | None = None) -> Path | None:
    """Get the root of the main git working tree.

    For worktrees, follows --git-common-dir to find the main repo's .git directory,
    then returns its parent. For main checkouts, returns the same as get_git_root().

    Args:
        path: Directory to check. Defaults to current directory.

    Returns:
        Path to the main repo root, or None if not in a git repository.
    """
    cmd = ["git", "rev-parse", "--git-common-dir"]
    if path:
        cmd = ["git", "-C", str(path)] + cmd[1:]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        git_common_dir = Path(result.stdout.strip())
        if not git_common_dir.is_absolute():
            # --git-common-dir can return a relative path from the worktree
            base = Path(path) if path else Path.cwd()
            git_common_dir = (base / git_common_dir).resolve()
        return git_common_dir.parent
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_git_root() -> Path | None:
    """Get the root directory of the current git repository.

    Uses `git rev-parse --show-toplevel` to find the repository root.

    Returns:
        Path to git root directory, or None if not in a git repository.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return None


def get_repo_url(path: str | Path | None = None) -> str | None:
    """Get a browsable HTTPS URL for the git remote origin.

    Handles both SSH (git@github.com:user/repo.git) and HTTPS URLs,
    stripping the .git suffix.

    Args:
        path: Directory to check. Defaults to current directory.

    Returns:
        HTTPS URL (e.g., "https://github.com/user/repo"), or None
        if not a git repo or no origin remote.
    """
    cmd = ["git", "remote", "get-url", "origin"]
    if path:
        cmd = ["git", "-C", str(path), "remote", "get-url", "origin"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        url = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    if not url:
        return None

    # Convert SSH/git protocol URLs to HTTPS
    if url.startswith("ssh://git@"):
        url = url.replace("ssh://git@", "https://", 1)
    elif url.startswith("ssh://"):
        url = url.replace("ssh://", "https://", 1)
    elif url.startswith("git://"):
        url = url.replace("git://", "https://", 1)
    elif url.startswith("git@"):
        # git@github.com:user/repo.git -> https://github.com/user/repo
        url = url.replace(":", "/", 1).replace("git@", "https://", 1)

    # Strip .git suffix
    if url.endswith(".git"):
        url = url[:-4]

    return url


def get_current_branch(path: str | Path | None = None) -> str | None:
    """Get the current git branch name.

    Args:
        path: Directory to check. Defaults to current directory.

    Returns:
        Branch name (e.g., "main"), or None for detached HEAD or non-git dirs.
    """
    cmd = ["git", "rev-parse", "--abbrev-ref", "HEAD"]
    if path:
        cmd = ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        branch = result.stdout.strip()
        # "HEAD" means detached HEAD state
        if branch == "HEAD":
            return None
        return branch
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_commit_hash(path: str | Path | None = None, short: bool = True) -> str | None:
    """Get the current commit hash.

    Args:
        path: Directory to check. Defaults to current directory.
        short: If True, return abbreviated hash (default 7 chars).

    Returns:
        Commit hash string, or None if not in a git repo.
    """
    cmd = ["git", "rev-parse"]
    if short:
        cmd.append("--short")
    cmd.append("HEAD")
    if path:
        cmd = ["git", "-C", str(path)] + cmd[1:]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_commits_behind(
    path: str | Path | None = None, from_commit: str = "HEAD"
) -> int | None:
    """Get the number of commits between a given commit and current HEAD.

    Runs `git rev-list <from_commit>..HEAD --count` to determine how many
    commits HEAD is ahead of from_commit.

    Args:
        path: Directory to check. Defaults to current directory.
        from_commit: The commit hash to measure from (typically the indexed commit).

    Returns:
        Number of commits behind, or None if not in a git repo or if
        from_commit is invalid.
    """
    cmd = ["git"]
    if path:
        cmd += ["-C", str(path)]
    cmd += ["rev-list", f"{from_commit}..HEAD", "--count"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None


def get_branch_commit_count(path: str | Path | None = None) -> int | None:
    """Get the total number of commits in the current branch.

    Runs `git rev-list --count HEAD` to count all reachable commits.

    Args:
        path: Directory to check. Defaults to current directory.

    Returns:
        Total commit count, or None if not in a git repo.
    """
    cmd = ["git"]
    if path:
        cmd += ["-C", str(path)]
    cmd += ["rev-list", "--count", "HEAD"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None


def derive_index_from_git(path: str | Path | None = None) -> str | None:
    """Derive an index name from a git repository.

    Uses the main repo root (not the worktree root) so that all worktrees
    of the same repository derive the same index name.

    Args:
        path: Directory to resolve the git repo from. Defaults to the current
            directory.

    Returns:
        Index name derived from git root directory, or None if not in a git repo.
    """
    repo_root = get_main_repo_root(path)
    if repo_root is None:
        return None

    from cocosearch.management.context import derive_index_name

    return derive_index_name(str(repo_root))
