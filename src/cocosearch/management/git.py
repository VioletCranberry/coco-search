"""Git integration module for cocosearch.

Provides functions to detect git repository root and derive
index names from git repositories.
"""

import subprocess
from pathlib import Path


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

    # Convert SSH to HTTPS: git@github.com:user/repo.git -> https://github.com/user/repo
    if url.startswith("git@"):
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


def derive_index_from_git() -> str | None:
    """Derive an index name from the current git repository.

    Combines git root detection with the standard index name derivation.

    Returns:
        Index name derived from git root directory, or None if not in a git repo.
    """
    git_root = get_git_root()
    if git_root is None:
        return None

    # Import here to avoid circular imports
    from cocosearch.cli import derive_index_name

    return derive_index_name(str(git_root))
