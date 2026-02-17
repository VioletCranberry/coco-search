"""Query analyzer for hybrid search auto-detection.

Analyzes search queries to determine if they contain code identifiers
(camelCase, snake_case, PascalCase) that would benefit from hybrid search
combining both semantic and keyword matching.

This module helps auto-detect when to trigger hybrid search mode:
- Plain English queries -> semantic search only
- Queries with code identifiers -> hybrid search
"""

import re

from cocosearch.indexer.tsvector import split_code_identifier


def has_identifier_pattern(query: str) -> bool:
    """Detect if query contains code identifier patterns.

    Returns True if query contains:
    - camelCase: getUserById, myFunction (must start lowercase, 6+ chars)
    - PascalCase: UserRepository, HttpClient (8+ chars)
    - snake_case: get_user_by_id, my_function (any length)

    Returns False for:
    - Plain English: "authentication handler", "database connection"
    - Single words: "user", "auth"
    - Acronyms alone: "HTTP", "API"
    - Proper nouns with mixed case: "PyPi", "GitHub", "FastAPI", "macOS"

    Works on individual words to avoid false positives from proper nouns
    that resemble code identifiers.

    Args:
        query: Search query string

    Returns:
        True if query contains identifier patterns that would benefit from
        keyword search, False otherwise.

    Examples:
        >>> has_identifier_pattern("getUserById")
        True
        >>> has_identifier_pattern("get_user_by_id")
        True
        >>> has_identifier_pattern("find database connection")
        False
        >>> has_identifier_pattern("find getUserById function")
        True
        >>> has_identifier_pattern("How do I publish to PyPi?")
        False
    """
    # Pattern for camelCase: must start with lowercase AND contain
    # a lowercase-to-uppercase transition AND be 6+ chars.
    # Filters out proper nouns like PyPi, macOS that start uppercase.
    camel_case_pattern = re.compile(r"[a-z][A-Z]")

    # Pattern for PascalCase: uppercase followed by lowercase, then another
    # uppercase (e.g., UserRepository). Word must be 8+ chars to filter
    # short proper nouns like PyPi (4), GitHub (6), FastAPI (7).
    pascal_case_pattern = re.compile(r"[A-Z][a-z]+[A-Z]")

    # Pattern for snake_case: word characters separated by underscore.
    # Any length — underscores are a strong code signal.
    snake_case_pattern = re.compile(r"[a-zA-Z0-9]+_[a-zA-Z0-9]+")

    # Extract words (sequences of word characters) and check each individually
    word_pattern = re.compile(r"[a-zA-Z0-9_]+")

    for match in word_pattern.finditer(query):
        word = match.group()

        # snake_case: any word with underscore between alphanumeric parts
        if snake_case_pattern.search(word):
            return True

        # camelCase: word starts lowercase, has lc→UC transition, 6+ chars
        if len(word) >= 6 and word[0].islower() and camel_case_pattern.search(word):
            return True

        # PascalCase: has UC→lc→UC pattern, 8+ chars
        if len(word) >= 8 and pascal_case_pattern.search(word):
            return True

    return False


def normalize_query_for_keyword(query: str) -> str:
    """Normalize query for keyword search by splitting identifiers.

    Expands camelCase and snake_case identifiers into searchable tokens
    while preserving the original term for exact matching.

    Uses the same splitting logic as tsvector.py to ensure consistency
    between indexing and querying.

    Args:
        query: Search query string

    Returns:
        Normalized query with split identifier tokens appended.

    Examples:
        >>> normalize_query_for_keyword("getUserById")
        'getUserById get User By Id'
        >>> normalize_query_for_keyword("find get_user_by_id function")
        'find get_user_by_id get user by id function'
    """
    # Find potential identifiers in the query
    # Matches: variable_name, functionName, ClassName, etc.
    identifier_pattern = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b")

    # Collect all tokens (original + split)
    all_tokens = []

    # Track position for non-identifier text
    last_end = 0

    for match in identifier_pattern.finditer(query):
        # Add any text before this identifier
        if match.start() > last_end:
            prefix = query[last_end : match.start()].strip()
            if prefix:
                all_tokens.append(prefix)

        identifier = match.group()
        last_end = match.end()

        # Check if this identifier should be split
        if _should_split_identifier(identifier):
            # Use tsvector's split logic for consistency
            tokens = split_code_identifier(identifier)
            all_tokens.extend(tokens)
        else:
            # Keep as-is (simple word or acronym)
            all_tokens.append(identifier)

    # Add any remaining text after last identifier
    if last_end < len(query):
        suffix = query[last_end:].strip()
        if suffix:
            all_tokens.append(suffix)

    return " ".join(all_tokens)


def _should_split_identifier(identifier: str) -> bool:
    """Determine if an identifier should be split into tokens.

    Args:
        identifier: Single identifier string

    Returns:
        True if identifier has camelCase, PascalCase, or snake_case pattern.
    """
    # Skip single characters
    if len(identifier) <= 1:
        return False

    # Skip pure acronyms (all uppercase)
    if identifier.isupper():
        return False

    # Skip pure lowercase single words (no underscore)
    if identifier.islower() and "_" not in identifier:
        return False

    # Check for camelCase transition
    if re.search(r"[a-z][A-Z]", identifier):
        return True

    # Check for PascalCase (uppercase followed by lowercase, with another capital)
    if re.search(r"[A-Z][a-z]+[A-Z]", identifier):
        return True

    # Check for snake_case
    if "_" in identifier:
        return True

    return False
