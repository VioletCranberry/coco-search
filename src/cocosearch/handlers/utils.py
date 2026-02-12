"""Shared utilities for language and grammar handlers."""

import re


def strip_leading_comments(
    text: str,
    comment_patterns: list[re.Pattern],
    skip_strings: list[str] | None = None,
) -> str:
    """Strip leading comments, blank lines, and skip strings from chunk text.

    Iterates lines from the start, skipping blank lines, lines matching any
    comment pattern, and lines whose stripped content is in skip_strings.
    Returns from the first non-skipped line onward.

    Args:
        text: The chunk text content.
        comment_patterns: Compiled regex patterns matching comment lines.
        skip_strings: Optional list of exact strings to skip (matched against
            stripped line content, e.g. ``["---"]`` for YAML separators).

    Returns:
        Text from first non-comment, non-blank, non-skipped line onward,
        or empty string if all lines are comments/blank/skipped.
    """
    skip_set = set(skip_strings) if skip_strings else set()
    lines = text.lstrip().split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in skip_set:
            continue
        if any(pat.match(line) for pat in comment_patterns):
            continue
        return "\n".join(lines[i:])
    return ""
