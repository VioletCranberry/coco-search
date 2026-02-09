"""Unit tests for query analyzer module."""

from cocosearch.search.query_analyzer import (
    has_identifier_pattern,
    normalize_query_for_keyword,
)


class TestHasIdentifierPattern:
    """Tests for has_identifier_pattern function."""

    def test_detects_camelcase_identifier(self):
        """Test detection of camelCase identifiers."""
        assert has_identifier_pattern("getUserById") is True
        assert has_identifier_pattern("myFunction") is True
        assert has_identifier_pattern("parseHTTPRequest") is True

    def test_detects_pascal_case_identifier(self):
        """Test detection of PascalCase identifiers."""
        assert has_identifier_pattern("UserRepository") is True
        assert has_identifier_pattern("HttpClient") is True
        assert has_identifier_pattern("GetUserById") is True

    def test_detects_snake_case_identifier(self):
        """Test detection of snake_case identifiers."""
        assert has_identifier_pattern("get_user_by_id") is True
        assert has_identifier_pattern("my_function") is True
        assert has_identifier_pattern("parse_http_request") is True

    def test_no_match_for_plain_english(self):
        """Test that plain English queries don't trigger identifier detection."""
        assert has_identifier_pattern("authentication handler") is False
        assert has_identifier_pattern("database connection") is False
        assert has_identifier_pattern("find all users") is False
        assert has_identifier_pattern("search for documents") is False

    def test_no_match_for_single_words(self):
        """Test that single lowercase words don't trigger detection."""
        assert has_identifier_pattern("user") is False
        assert has_identifier_pattern("auth") is False
        assert has_identifier_pattern("function") is False

    def test_no_match_for_acronyms_alone(self):
        """Test that standalone acronyms don't trigger detection."""
        assert has_identifier_pattern("HTTP") is False
        assert has_identifier_pattern("API") is False
        assert has_identifier_pattern("URL") is False

    def test_mixed_query_with_identifier(self):
        """Test queries mixing natural language with identifiers."""
        assert has_identifier_pattern("find getUserById function") is True
        assert has_identifier_pattern("search for get_user_by_id") is True
        assert has_identifier_pattern("where is UserRepository defined") is True

    def test_identifier_at_start(self):
        """Test identifier at the start of query."""
        assert has_identifier_pattern("getUserById in auth module") is True

    def test_identifier_at_end(self):
        """Test identifier at the end of query."""
        assert has_identifier_pattern("find the getUserById") is True

    def test_empty_query(self):
        """Test empty query handling."""
        assert has_identifier_pattern("") is False

    def test_whitespace_only(self):
        """Test whitespace-only query."""
        assert has_identifier_pattern("   ") is False


class TestNormalizeQueryForKeyword:
    """Tests for normalize_query_for_keyword function."""

    def test_normalize_splits_camelcase(self):
        """Test camelCase identifier splitting."""
        result = normalize_query_for_keyword("getUserById")
        assert "getUserById" in result  # Original preserved
        assert "get" in result.lower()
        assert "user" in result.lower()
        assert "by" in result.lower()
        assert "id" in result.lower()

    def test_normalize_splits_snake_case(self):
        """Test snake_case identifier splitting."""
        result = normalize_query_for_keyword("get_user_by_id")
        assert "get_user_by_id" in result  # Original preserved
        assert "get" in result
        assert "user" in result
        assert "by" in result
        assert "id" in result

    def test_normalize_preserves_plain_words(self):
        """Test that plain words are preserved unchanged."""
        result = normalize_query_for_keyword("find user")
        assert "find" in result
        assert "user" in result

    def test_normalize_mixed_query(self):
        """Test normalization of mixed natural language and identifiers."""
        result = normalize_query_for_keyword("find getUserById function")
        assert "find" in result
        assert "function" in result
        assert "getUserById" in result
        assert "get" in result.lower()

    def test_normalize_empty_query(self):
        """Test empty query handling."""
        result = normalize_query_for_keyword("")
        assert result == ""

    def test_normalize_preserves_acronyms(self):
        """Test that acronyms are not split incorrectly."""
        result = normalize_query_for_keyword("HTTP API")
        assert "HTTP" in result
        assert "API" in result

    def test_normalize_pascal_case(self):
        """Test PascalCase identifier splitting."""
        result = normalize_query_for_keyword("UserRepository")
        assert "UserRepository" in result
        assert "User" in result or "user" in result.lower()
        assert "Repository" in result or "repository" in result.lower()

    def test_normalize_multiple_identifiers(self):
        """Test query with multiple identifiers."""
        result = normalize_query_for_keyword("getUserById and set_user_name")
        # Both identifiers should be preserved and split
        assert "getUserById" in result
        assert "set_user_name" in result
        assert "get" in result.lower()
        assert "set" in result.lower()
