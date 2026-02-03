"""Symbol filter SQL builder module for cocosearch.

Provides functions for building parameterized SQL WHERE clauses
for filtering search results by symbol type and name.
"""

# Valid symbol types (matches tree-sitter extraction in symbols.py)
VALID_SYMBOL_TYPES = {"function", "class", "method", "interface"}


def glob_to_sql_pattern(glob_pattern: str) -> str:
    """Convert shell-style glob pattern to SQL ILIKE pattern.

    Handles the conversion in correct order:
    1. First escape SQL special characters (%, _)
    2. Then convert glob wildcards (*, ?)

    CRITICAL: Order matters! Escape first, then convert.
    Otherwise "get_*" incorrectly becomes "get\\_%" instead of "get\\_%".

    Args:
        glob_pattern: Shell-style glob pattern (supports * and ?).

    Returns:
        SQL ILIKE pattern with proper escaping.

    Examples:
        >>> glob_to_sql_pattern("get*")
        'get%'
        >>> glob_to_sql_pattern("User*Service")
        'User%Service'
        >>> glob_to_sql_pattern("*Handler")
        '%Handler'
        >>> glob_to_sql_pattern("get_*")
        'get\\_%'
        >>> glob_to_sql_pattern("find%user")
        'find\\%user'
    """
    # Step 1: Escape SQL special characters
    # % -> \%
    # _ -> \_
    result = glob_pattern.replace("%", "\\%")
    result = result.replace("_", "\\_")

    # Step 2: Convert glob wildcards
    # * -> %
    # ? -> _
    result = result.replace("*", "%")
    result = result.replace("?", "_")

    return result


def build_symbol_where_clause(
    symbol_type: str | list[str] | None = None,
    symbol_name: str | None = None,
) -> tuple[str, list]:
    """Build parameterized SQL WHERE clause for symbol filtering.

    Generates SQL conditions for filtering by symbol type and/or name.
    Returns a tuple of (where_clause, params) for use with parameterized queries.

    Args:
        symbol_type: Single type string, list of types, or None.
            Valid types: "function", "class", "method", "interface"
        symbol_name: Glob pattern for symbol name, or None.
            Supports * (any chars) and ? (single char) wildcards.

    Returns:
        Tuple of (where_clause, params):
        - where_clause: SQL condition string (without "WHERE") or empty string
        - params: List of parameter values for the placeholders

    Raises:
        ValueError: If symbol_type contains invalid type names.

    Examples:
        >>> build_symbol_where_clause(symbol_type="function")
        ('symbol_type = %s', ['function'])

        >>> build_symbol_where_clause(symbol_type=["function", "method"])
        ('symbol_type IN (%s, %s)', ['function', 'method'])

        >>> build_symbol_where_clause(symbol_name="get*")
        ('symbol_name ILIKE %s', ['get%'])

        >>> build_symbol_where_clause(symbol_type="function", symbol_name="get*")
        ('symbol_type = %s AND symbol_name ILIKE %s', ['function', 'get%'])

        >>> build_symbol_where_clause()
        ('', [])
    """
    conditions = []
    params = []

    # Handle symbol_type filter
    if symbol_type is not None:
        # Normalize to list
        types = [symbol_type] if isinstance(symbol_type, str) else list(symbol_type)

        # Validate all types
        invalid_types = [t for t in types if t not in VALID_SYMBOL_TYPES]
        if invalid_types:
            valid_list = ", ".join(sorted(VALID_SYMBOL_TYPES))
            raise ValueError(
                f"Invalid symbol type(s): {', '.join(invalid_types)}. "
                f"Valid types: {valid_list}"
            )

        if len(types) == 1:
            conditions.append("symbol_type = %s")
            params.append(types[0])
        else:
            placeholders = ", ".join(["%s"] * len(types))
            conditions.append(f"symbol_type IN ({placeholders})")
            params.extend(types)

    # Handle symbol_name filter
    if symbol_name is not None:
        sql_pattern = glob_to_sql_pattern(symbol_name)
        conditions.append("symbol_name ILIKE %s")
        params.append(sql_pattern)

    # Combine conditions with AND
    where_clause = " AND ".join(conditions)
    return where_clause, params
