"""tsvector generation for hybrid search.

Converts code content to PostgreSQL tsvector format for full-text search.
Includes code-aware tokenization that handles:
- camelCase splitting: getUserById -> get user by id
- snake_case splitting: get_user_by_id -> get user by id
- Original identifiers preserved for exact match

Uses PostgreSQL 'simple' text search config (no stemming) because:
- Code identifiers shouldn't be stemmed (running != run in code)
- Case is preserved in original but lowercased tokens also added
"""

import re

import cocoindex


def split_code_identifier(identifier: str) -> list[str]:
    """Split a code identifier into searchable tokens.

    Handles camelCase, PascalCase, snake_case, and kebab-case.

    Args:
        identifier: Code identifier (e.g., "getUserById", "get_user_by_id")

    Returns:
        List of tokens including original and split parts.

    Examples:
        >>> split_code_identifier("getUserById")
        ['getUserById', 'get', 'User', 'By', 'Id']
        >>> split_code_identifier("get_user_by_id")
        ['get_user_by_id', 'get', 'user', 'by', 'id']
    """
    tokens = [identifier]  # Always include original

    # Split camelCase/PascalCase
    camel_parts = re.findall(
        r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", identifier
    )
    if camel_parts and len(camel_parts) > 1:
        tokens.extend(camel_parts)

    # Split snake_case/kebab-case
    if "_" in identifier or "-" in identifier:
        snake_parts = re.split(r"[_-]", identifier)
        snake_parts = [p for p in snake_parts if p]
        if len(snake_parts) > 1:
            tokens.extend(snake_parts)

    return tokens


def extract_filename_tokens(filename: str) -> str:
    """Extract searchable tokens from a file path.

    Splits path components on /, ., _, - and applies camelCase splitting.
    Leading dots are stripped from components.

    Args:
        filename: File path (e.g., ".github/workflows/release.yaml")

    Returns:
        Space-separated tokens (e.g., "github workflows release yaml")
    """
    if not filename:
        return ""

    # Split on path separator
    parts = filename.split("/")

    all_tokens = []
    for part in parts:
        # Strip leading dots (e.g., .github -> github)
        part = part.lstrip(".")
        if not part:
            continue

        # Split on . _ - to get sub-components
        sub_parts = re.split(r"[._\-]", part)
        for sub in sub_parts:
            if not sub:
                continue
            # Apply camelCase splitting to each sub-component
            tokens = split_code_identifier(sub)
            all_tokens.extend(t.lower() for t in tokens)

    return " ".join(all_tokens)


def preprocess_code_for_tsvector(content: str) -> str:
    """Preprocess code content for tsvector generation.

    Extracts identifiers and splits them for better keyword matching.
    The result is a space-separated string suitable for to_tsvector().

    Args:
        content: Raw code content (chunk text)

    Returns:
        Preprocessed text with split identifiers, ready for to_tsvector().
    """
    # Extract potential identifiers (alphanumeric sequences with underscores)
    # This pattern matches: variable_name, functionName, ClassName, etc.
    identifier_pattern = r"\b[a-zA-Z_][a-zA-Z0-9_]*\b"
    identifiers = re.findall(identifier_pattern, content)

    # Split each identifier and collect all tokens
    all_tokens = []
    for ident in identifiers:
        if len(ident) >= 2:  # Skip single-char identifiers
            tokens = split_code_identifier(ident)
            all_tokens.extend(tokens)

    # Also include raw words for natural language in comments
    # (to_tsvector will handle deduplication)
    words = re.findall(r"\b\w+\b", content.lower())
    all_tokens.extend(words)

    # Join with spaces for to_tsvector input
    return " ".join(all_tokens)


@cocoindex.op.function(behavior_version=2)
def text_to_tsvector_sql(content: str, filename: str = "") -> str:
    """Generate SQL expression for creating tsvector from content.

    Returns the preprocessed text that should be passed to PostgreSQL's
    to_tsvector('simple', ...) function.

    Note: The actual to_tsvector() call happens in PostgreSQL, not Python.
    This function prepares the input text.

    Args:
        content: Raw code content (chunk text)
        filename: Optional file path to extract additional tokens from

    Returns:
        Preprocessed text ready for to_tsvector('simple', ...)
    """
    result = preprocess_code_for_tsvector(content)
    if filename:
        filename_tokens = extract_filename_tokens(filename)
        if filename_tokens:
            result = f"{result} {filename_tokens}"
    return result
