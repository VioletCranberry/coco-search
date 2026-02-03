"""Tests for cocosearch.search.filters module.

Tests symbol filter SQL building including glob-to-SQL pattern conversion
and parameterized WHERE clause generation.
"""

import pytest

from cocosearch.search.filters import (
    VALID_SYMBOL_TYPES,
    build_symbol_where_clause,
    glob_to_sql_pattern,
)


class TestGlobToSqlPattern:
    """Tests for glob_to_sql_pattern function."""

    def test_simple_wildcard(self):
        """Simple asterisk should convert to percent."""
        assert glob_to_sql_pattern("get*") == "get%"

    def test_prefix_wildcard(self):
        """Asterisk at start should convert to percent."""
        assert glob_to_sql_pattern("*Handler") == "%Handler"

    def test_middle_wildcard(self):
        """Asterisk in middle should convert to percent."""
        assert glob_to_sql_pattern("User*Service") == "User%Service"

    def test_question_mark(self):
        """Question mark should convert to underscore."""
        assert glob_to_sql_pattern("test?") == "test_"

    def test_escape_underscore(self):
        """Underscore should be escaped before * is converted."""
        # Critical order: _ -> \_, then * -> %
        assert glob_to_sql_pattern("get_*") == "get\\_%"

    def test_escape_percent(self):
        """Percent in input should be escaped."""
        assert glob_to_sql_pattern("find%user") == "find\\%user"

    def test_combined_escaping(self):
        """Multiple SQL special characters should all be escaped."""
        assert glob_to_sql_pattern("get_user*") == "get\\_user%"

    def test_no_wildcards(self):
        """String without wildcards should pass through unchanged."""
        assert glob_to_sql_pattern("exactMatch") == "exactMatch"

    def test_multiple_wildcards(self):
        """Multiple wildcards should all convert."""
        assert glob_to_sql_pattern("*user*service*") == "%user%service%"

    def test_question_and_asterisk(self):
        """Both wildcard types should convert."""
        assert glob_to_sql_pattern("test?_*") == "test_\\_%"

    def test_empty_string(self):
        """Empty string should return empty."""
        assert glob_to_sql_pattern("") == ""


class TestBuildSymbolWhereClause:
    """Tests for build_symbol_where_clause function."""

    def test_single_type(self):
        """Single symbol type should generate equality condition."""
        where, params = build_symbol_where_clause(symbol_type="function")
        assert where == "symbol_type = %s"
        assert params == ["function"]

    def test_multiple_types(self):
        """Multiple symbol types should generate IN condition."""
        where, params = build_symbol_where_clause(symbol_type=["function", "method"])
        assert where == "symbol_type IN (%s, %s)"
        assert params == ["function", "method"]

    def test_name_pattern(self):
        """Symbol name should generate ILIKE condition with glob conversion."""
        where, params = build_symbol_where_clause(symbol_name="get*")
        assert where == "symbol_name ILIKE %s"
        assert params == ["get%"]

    def test_type_and_name(self):
        """Both type and name should combine with AND."""
        where, params = build_symbol_where_clause(
            symbol_type="function",
            symbol_name="get*",
        )
        assert where == "symbol_type = %s AND symbol_name ILIKE %s"
        assert params == ["function", "get%"]

    def test_neither(self):
        """Both None should return empty string and list."""
        where, params = build_symbol_where_clause()
        assert where == ""
        assert params == []

    def test_invalid_type_single(self):
        """Invalid single type should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid symbol type"):
            build_symbol_where_clause(symbol_type="invalid")

    def test_invalid_type_in_list(self):
        """Invalid type in list should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid symbol type"):
            build_symbol_where_clause(symbol_type=["function", "invalid"])

    def test_valid_type_error_message(self):
        """Error message should list valid types."""
        with pytest.raises(ValueError, match="class, function, interface, method"):
            build_symbol_where_clause(symbol_type="bogus")

    def test_all_valid_types(self):
        """All valid types should be accepted."""
        for valid_type in VALID_SYMBOL_TYPES:
            where, params = build_symbol_where_clause(symbol_type=valid_type)
            assert where == "symbol_type = %s"
            assert params == [valid_type]

    def test_name_with_underscore_escaping(self):
        """Symbol name with underscore should be escaped."""
        where, params = build_symbol_where_clause(symbol_name="get_user*")
        assert params == ["get\\_user%"]

    def test_three_types(self):
        """Three symbol types should generate correct IN clause."""
        where, params = build_symbol_where_clause(
            symbol_type=["function", "method", "class"]
        )
        assert where == "symbol_type IN (%s, %s, %s)"
        assert params == ["function", "method", "class"]
