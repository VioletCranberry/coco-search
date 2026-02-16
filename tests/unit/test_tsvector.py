"""Unit tests for tsvector generation module."""

from cocosearch.indexer.tsvector import (
    split_code_identifier,
    extract_filename_tokens,
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


class TestExtractFilenameTokens:
    """Tests for extract_filename_tokens function."""

    def test_github_workflow_path(self):
        """Extracts tokens from GitHub Actions workflow path."""
        result = extract_filename_tokens(".github/workflows/release.yaml")
        assert "github" in result
        assert "workflows" in result
        assert "release" in result
        assert "yaml" in result

    def test_nested_path(self):
        """Extracts tokens from nested source path."""
        result = extract_filename_tokens("src/cocosearch/indexer/flow.py")
        assert "src" in result
        assert "cocosearch" in result
        assert "indexer" in result
        assert "flow" in result
        assert "py" in result

    def test_camel_case_component(self):
        """Splits camelCase path components."""
        result = extract_filename_tokens("src/myModule.js")
        assert "my" in result
        assert "module" in result

    def test_snake_case_component(self):
        """Splits snake_case path components."""
        result = extract_filename_tokens("src/my_module.py")
        assert "my" in result
        assert "module" in result

    def test_kebab_case_component(self):
        """Splits kebab-case path components."""
        result = extract_filename_tokens("src/my-component.tsx")
        assert "my" in result
        assert "component" in result

    def test_empty_filename(self):
        """Returns empty string for empty input."""
        assert extract_filename_tokens("") == ""

    def test_leading_dots_stripped(self):
        """Strips leading dots from path components."""
        result = extract_filename_tokens(".github/workflows/ci.yml")
        assert "github" in result
        # Should not contain a bare dot token
        assert "." not in result.split()

    def test_simple_filename(self):
        """Handles simple filename without path."""
        result = extract_filename_tokens("Dockerfile")
        assert "dockerfile" in result


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

    def test_with_filename_appends_tokens(self):
        """Filename tokens are appended to content tokens."""
        code = "name: Deploy"
        result = text_to_tsvector_sql(code, filename=".github/workflows/release.yaml")
        assert "release" in result
        assert "workflows" in result

    def test_without_filename_unchanged(self):
        """Without filename, output matches content-only preprocessing."""
        code = "def hello(): pass"
        result_no_file = text_to_tsvector_sql(code)
        result_empty = text_to_tsvector_sql(code, filename="")
        assert result_no_file == result_empty
