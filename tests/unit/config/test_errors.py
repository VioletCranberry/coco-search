"""Unit tests for configuration error formatting."""

from pathlib import Path

from pydantic import ValidationError

from cocosearch.config.errors import format_validation_errors, suggest_field_name
from cocosearch.config.schema import CocoSearchConfig


class TestSuggestFieldName:
    """Tests for suggest_field_name function."""

    def test_suggest_field_name_finds_close_match_root(self):
        """Test that close matches are found for root fields."""
        assert suggest_field_name("indxName") == "indexName"
        assert suggest_field_name("indexng") == "indexing"
        assert suggest_field_name("serch") == "search"
        assert suggest_field_name("embeding") == "embedding"

    def test_suggest_field_name_finds_close_match_indexing(self):
        """Test that close matches are found for indexing section fields."""
        assert suggest_field_name("chunkSze", "indexing") == "chunkSize"
        assert suggest_field_name("chunkOverlap", "indexing") == "chunkOverlap"
        assert suggest_field_name("includePattern", "indexing") == "includePatterns"
        assert suggest_field_name("excludePattern", "indexing") == "excludePatterns"

    def test_suggest_field_name_finds_close_match_search(self):
        """Test that close matches are found for search section fields."""
        assert suggest_field_name("resultLimt", "search") == "resultLimit"
        assert suggest_field_name("minScre", "search") == "minScore"

    def test_suggest_field_name_finds_close_match_embedding(self):
        """Test that close matches are found for embedding section fields."""
        assert suggest_field_name("mdel", "embedding") == "model"
        assert suggest_field_name("modle", "embedding") == "model"

    def test_suggest_field_name_returns_none_for_no_match(self):
        """Test that None is returned when no close match exists."""
        assert suggest_field_name("xyzabc123") is None
        assert suggest_field_name("completelywrongfield") is None
        assert suggest_field_name("randomstring") is None

    def test_suggest_field_name_uses_correct_section(self):
        """Test that suggestions are section-specific."""
        # "mdel" should match "model" in embedding section
        assert suggest_field_name("mdel", "embedding") == "model"

        # "mdel" should not match anything in root section
        assert suggest_field_name("mdel", "root") is None

        # "chunkSze" should match in indexing but not in root
        assert suggest_field_name("chunkSze", "indexing") == "chunkSize"
        assert suggest_field_name("chunkSze", "root") is None


class TestFormatValidationErrors:
    """Tests for format_validation_errors function."""

    def test_format_validation_errors_unknown_field_with_suggestion_root(self):
        """Test that unknown root fields get suggestions."""
        try:
            CocoSearchConfig.model_validate({"indxName": "test"})
        except ValidationError as e:
            result = format_validation_errors(e)
            assert "indxName: Unknown field" in result
            assert "Did you mean 'indexName'?" in result

    def test_format_validation_errors_unknown_field_with_suggestion_nested(self):
        """Test that unknown nested fields get suggestions."""
        try:
            CocoSearchConfig.model_validate({"indexing": {"chunkSze": 100}})
        except ValidationError as e:
            result = format_validation_errors(e)
            assert "indexing.chunkSze: Unknown field" in result
            assert "Did you mean 'chunkSize'?" in result

    def test_format_validation_errors_unknown_field_no_suggestion(self):
        """Test that unknown fields without close matches don't suggest."""
        try:
            CocoSearchConfig.model_validate({"xyzabc": "test"})
        except ValidationError as e:
            result = format_validation_errors(e)
            assert "xyzabc: Unknown field" in result
            assert "Did you mean" not in result

    def test_format_validation_errors_type_error(self):
        """Test that type errors are properly formatted."""
        try:
            CocoSearchConfig.model_validate({"indexing": {"chunkSize": "not a number"}})
        except ValidationError as e:
            result = format_validation_errors(e)
            assert "indexing.chunkSize" in result
            # Should mention it's a type error
            assert "Type error" in result or "int" in result.lower()

    def test_format_validation_errors_multiple_errors(self):
        """Test that all validation errors are reported at once."""
        try:
            CocoSearchConfig.model_validate(
                {
                    "indxName": "test",  # Unknown field
                    "indexing": {
                        "chunkSze": 100,  # Unknown field
                        "chunkSize": "invalid",  # Type error
                    },
                }
            )
        except ValidationError as e:
            result = format_validation_errors(e)

            # All three errors should be present
            assert "indxName" in result
            assert "chunkSze" in result
            assert "chunkSize" in result

            # Count number of error lines (lines starting with "  - ")
            error_lines = [
                line for line in result.split("\n") if line.startswith("  - ")
            ]
            assert len(error_lines) >= 3

    def test_format_validation_errors_nested_path(self):
        """Test that nested field paths are properly formatted."""
        try:
            CocoSearchConfig.model_validate({"search": {"minScore": 2.5}})
        except ValidationError as e:
            result = format_validation_errors(e)
            # Should show the full path
            assert "search.minScore" in result

    def test_format_validation_errors_includes_config_path(self):
        """Test that config path is included in the header when provided."""
        try:
            CocoSearchConfig.model_validate({"indxName": "test"})
        except ValidationError as e:
            config_path = Path("/path/to/config.yaml")
            result = format_validation_errors(e, config_path)
            assert str(config_path) in result
            assert "Configuration errors in" in result

    def test_format_validation_errors_no_config_path(self):
        """Test that formatting works without config path."""
        try:
            CocoSearchConfig.model_validate({"indxName": "test"})
        except ValidationError as e:
            result = format_validation_errors(e)
            assert "Configuration errors:" in result
            # Should not have "in" since no path provided
            assert result.startswith("Configuration errors:")

    def test_format_validation_errors_constraint_violation(self):
        """Test that constraint violations are properly formatted."""
        try:
            CocoSearchConfig.model_validate({"indexing": {"chunkSize": -1}})
        except ValidationError as e:
            result = format_validation_errors(e)
            assert "indexing.chunkSize" in result
            # Should mention the constraint violation
            assert (
                "greater than 0" in result.lower()
                or "Input should be greater than 0" in result
            )
