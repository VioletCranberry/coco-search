"""File filtering module for cocosearch indexer."""

from pathlib import Path

# Default exclusion patterns for common generated/vendored directories.
# Note: include_patterns already restricts indexed files by extension,
# so dotfiles like .gitlab-ci.yml or .github/workflows/*.yml are only
# indexed if they match an include pattern (e.g., *.yml).
DEFAULT_EXCLUDES: list[str] = [
    "**/.git",
    "**/.svn",
    "**/.hg",
    "**/.venv",
    "**/.tox",
    "**/.mypy_cache",
    "**/.ruff_cache",
    "**/.pytest_cache",
    "**/.idea",
    "**/.vscode",
    "**/node_modules",
    "**/__pycache__",
    "**/target",  # Rust
    "**/vendor",  # Go, PHP
    "**/*.min.js",
    "**/*.min.css",
    "**/dist",
    "**/build",
]


def load_gitignore_patterns(codebase_path: str) -> list[str]:
    """Load patterns from .gitignore file if it exists.

    Args:
        codebase_path: Path to the codebase root directory.

    Returns:
        List of gitignore pattern lines (stripped, non-empty, non-comment).
    """
    gitignore_path = Path(codebase_path) / ".gitignore"

    if not gitignore_path.exists():
        return []

    try:
        with open(gitignore_path, "r") as f:
            lines = f.readlines()

        patterns = []
        for line in lines:
            stripped = line.strip()
            # Skip empty lines and comments
            if stripped and not stripped.startswith("#"):
                patterns.append(stripped)

        return patterns
    except (OSError, IOError):
        return []


def build_exclude_patterns(
    codebase_path: str,
    user_excludes: list[str] | None = None,
    respect_gitignore: bool = True,
) -> list[str]:
    """Build combined exclusion pattern list.

    Combines default excludes, .gitignore patterns, and user-specified excludes.

    Args:
        codebase_path: Path to the codebase root directory.
        user_excludes: Optional list of user-specified exclude patterns.
        respect_gitignore: Whether to include .gitignore patterns.

    Returns:
        Combined list of exclusion patterns.
    """
    patterns = list(DEFAULT_EXCLUDES)

    if respect_gitignore:
        gitignore_patterns = load_gitignore_patterns(codebase_path)
        patterns.extend(gitignore_patterns)

    if user_excludes:
        patterns.extend(user_excludes)

    # Filter out empty strings and comment lines
    filtered = [p for p in patterns if p and not p.startswith("#")]

    return filtered
