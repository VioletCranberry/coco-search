"""Unit tests for tsvector generation module."""

from cocosearch.indexer.tsvector import (
    split_code_identifier,
    preprocess_code_for_tsvector,
    text_to_tsvector_sql,
)


class TestSplitCodeIdentifier:
    """Tests for split_code_identifier function."""

    def test_camel_case_splitting(self):
        """Test camelCase identifier splitting."""
        result = split_code_identifier("getUserById")
        assert "getUserById" in result  # Original preserved
        assert "get" in result
        assert "User" in result
        assert "By" in result
        assert "Id" in result

    def test_pascal_case_splitting(self):
        """Test PascalCase identifier splitting."""
        result = split_code_identifier("UserRepository")
        assert "UserRepository" in result
        assert "User" in result
        assert "Repository" in result

    def test_snake_case_splitting(self):
        """Test snake_case identifier splitting."""
        result = split_code_identifier("get_user_by_id")
        assert "get_user_by_id" in result
        assert "get" in result
        assert "user" in result
        assert "by" in result
        assert "id" in result

    def test_kebab_case_splitting(self):
        """Test kebab-case identifier splitting."""
        result = split_code_identifier("get-user-by-id")
        assert "get-user-by-id" in result
        assert "get" in result
        assert "user" in result

    def test_simple_identifier_preserved(self):
        """Test that simple identifiers are preserved."""
        result = split_code_identifier("user")
        assert "user" in result

    def test_mixed_case_with_numbers(self):
        """Test identifiers with numbers."""
        result = split_code_identifier("user2")
        assert "user2" in result

    def test_uppercase_acronym(self):
        """Test identifiers with uppercase acronyms."""
        result = split_code_identifier("parseHTTPRequest")
        assert "parseHTTPRequest" in result
        assert "parse" in result
        assert "HTTP" in result or "Request" in result


class TestPreprocessCodeForTsvector:
    """Tests for preprocess_code_for_tsvector function."""

    def test_extracts_function_definition(self):
        """Test extraction from function definition."""
        code = "def getUserById(user_id):\n    return db.query(user_id)"
        result = preprocess_code_for_tsvector(code)

        # Should contain split tokens
        assert "get" in result.lower()
        assert "user" in result.lower()

    def test_includes_comments(self):
        """Test that comment text is included."""
        code = "# This function retrieves a user from the database\ndef get_user():"
        result = preprocess_code_for_tsvector(code)

        # Comment words should be present
        assert "retrieves" in result.lower() or "user" in result.lower()

    def test_handles_empty_string(self):
        """Test handling of empty input."""
        result = preprocess_code_for_tsvector("")
        assert result == "" or result.strip() == ""

    def test_handles_symbols_only(self):
        """Test handling of code with only symbols."""
        code = "{ } ( ) [ ] ; : , ."
        result = preprocess_code_for_tsvector(code)
        # Should handle gracefully, may be empty or have minimal tokens
        assert isinstance(result, str)


class TestTextToTsvectorSql:
    """Tests for text_to_tsvector_sql function."""

    def test_returns_preprocessed_string(self):
        """Test that function returns a string suitable for to_tsvector."""
        code = "def hello_world():\n    print('Hello')"
        result = text_to_tsvector_sql(code)

        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain searchable tokens
        assert "hello" in result.lower() or "world" in result.lower()
