"""Context detection module for cocosearch.

Provides functions to detect project root from any subdirectory,
resolve symlinks to canonical paths, derive index names from paths,
and determine the appropriate index name following the priority chain.
"""

import os
import re
from pathlib import Path


def get_canonical_path(path: str | Path) -> Path:
    """Resolve path to canonical form, following symlinks.

    Args:
        path: Path to resolve (may be relative or symlinked)

    Returns:
        Absolute path with all symlinks resolved
    """
    # strict=False allows resolving paths even if they don't exist yet
    return Path(path).resolve(strict=False)


def derive_index_name(path: str) -> str:
    """Derive an index name from a directory path.

    Converts a path to a sanitized index name by:
    1. Converting to absolute path
    2. Extracting the last directory component
    3. Converting to lowercase
    4. Replacing non-alphanumeric characters with underscores

    Args:
        path: Path to derive name from.

    Returns:
        Sanitized index name suitable for database table names.

    Examples:
        >>> derive_index_name("/home/user/MyProject")
        'myproject'
        >>> derive_index_name("/tmp/test-repo/")
        'test_repo'
    """
    # Convert to absolute and resolve any symlinks
    abs_path = os.path.abspath(path)

    # Remove trailing slashes
    abs_path = abs_path.rstrip(os.sep)

    # Handle root path edge case
    if not abs_path or abs_path == os.sep:
        return "root"

    # Get the last component (directory name)
    name = os.path.basename(abs_path)

    # Lowercase
    name = name.lower()

    # Replace non-alphanumeric with underscore
    name = re.sub(r"[^a-z0-9]", "_", name)

    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name)

    # Remove leading/trailing underscores
    name = name.strip("_")

    # Handle empty result
    if not name:
        return "index"

    return name


def find_project_root(start_path: Path | None = None) -> tuple[Path | None, str | None]:
    """Walk up directory tree to find project root.

    Searches for .git directory first (git repository root), then
    cocosearch.yaml (explicit project configuration).

    Args:
        start_path: Directory to start searching from. Defaults to cwd.

    Returns:
        Tuple of (root_path, detection_method) or (None, None) if not found.
        detection_method is one of: "git", "config", or None
    """
    if start_path is None:
        start_path = Path.cwd()

    # Resolve symlinks to canonical path before walking
    current = get_canonical_path(start_path)

    # Walk up until we hit filesystem root
    while True:
        # Check for .git directory (git repo root)
        if (current / ".git").exists():
            return current, "git"

        # Check for cocosearch.yaml (project with explicit config)
        if (current / "cocosearch.yaml").exists():
            return current, "config"

        # Check if we've reached filesystem root
        parent = current.parent
        if parent == current:
            # We're at the root, no project found
            break
        current = parent

    return None, None


def resolve_index_name(project_root: Path, detection_method: str | None) -> str:
    """Resolve index name following priority chain.

    Priority chain:
    1. cocosearch.yaml indexName field (if config exists)
    2. Directory name (derived from project root)

    Args:
        project_root: Canonical path to project root
        detection_method: One of "git", "config", or None

    Returns:
        Index name derived following priority rules
    """
    # Priority 1: cocosearch.yaml indexName field
    config_path = project_root / "cocosearch.yaml"
    if config_path.exists():
        try:
            from cocosearch.config import load_config
            from cocosearch.config.schema import ConfigError

            config = load_config(config_path)
            if config.indexName:
                return config.indexName
        except (ConfigError, Exception):
            # Config invalid or unreadable, fall back to directory name
            pass

    # Priority 2: Directory name (always available)
    return derive_index_name(str(project_root))
