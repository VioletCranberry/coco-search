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
