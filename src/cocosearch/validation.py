"""Input validation for cocosearch.

Provides validation functions for user-supplied inputs like index names
and search queries. These guards prevent SQL injection via dynamic table
names and protect against resource exhaustion from oversized inputs.
"""

import re

from cocosearch.exceptions import IndexValidationError

# Pattern for valid index names: alphanumeric and underscores only
_INDEX_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]+$")

# Input length limits
MAX_INDEX_NAME_LENGTH = 255
MAX_QUERY_LENGTH = 10_000


def validate_index_name(index_name: str) -> str:
    """Validate an index name for safe use in SQL identifiers.

    Index names are used to construct PostgreSQL table names via f-strings.
    This function ensures only safe characters are allowed.

    Args:
        index_name: The index name to validate.

    Returns:
        The validated index name (unchanged).

    Raises:
        IndexValidationError: If the index name is empty, too long, or contains
            characters outside [a-zA-Z0-9_]. Inherits from ValueError for
            backward compatibility.
    """
    if not index_name:
        raise IndexValidationError("Index name cannot be empty")

    if len(index_name) > MAX_INDEX_NAME_LENGTH:
        raise IndexValidationError(
            f"Index name too long ({len(index_name)} chars, max {MAX_INDEX_NAME_LENGTH})"
        )

    if not _INDEX_NAME_PATTERN.match(index_name):
        raise IndexValidationError(
            f"Invalid index name '{index_name}': "
            "must contain only letters, digits, and underscores"
        )

    return index_name


def validate_query(query: str) -> str:
    """Validate a search query string.

    Ensures the query is not empty/whitespace and within size limits
    to prevent resource exhaustion during embedding.

    Args:
        query: The search query to validate.

    Returns:
        The stripped query string.

    Raises:
        ValueError: If the query is empty, whitespace-only, or too long.
    """
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty")

    stripped = query.strip()

    if len(stripped) > MAX_QUERY_LENGTH:
        raise ValueError(
            f"Search query too long ({len(stripped)} chars, max {MAX_QUERY_LENGTH})"
        )

    return stripped
