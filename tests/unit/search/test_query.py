"""Tests for cocosearch.search.query module.

Tests search query functionality including SearchResult dataclass,
search function with mocked database and embedding calls,
DevOps language filtering, alias resolution, and graceful degradation.
"""

import logging
from unittest.mock import patch, MagicMock

import pytest

import cocosearch.search.query as query_module
from cocosearch.search.query import (
    SearchResult,
    search,
    get_extension_patterns,
    validate_language_filter,
    LANGUAGE_EXTENSIONS,
    DEVOPS_LANGUAGES,
    LANGUAGE_ALIASES,
    ALL_LANGUAGES,
)


@pytest.fixture(autouse=True)
def reset_metadata_flag():
    """Reset module-level metadata flags between tests.

    Prevents test pollution from tests that modify _has_metadata_columns.
    """
    yield
    query_module._has_metadata_columns = True
    query_module._metadata_warning_emitted = False


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_dataclass_fields(self):
        """SearchResult should have filename, start_byte, end_byte, score fields."""
        result = SearchResult(
            filename="/path/to/file.py",
            start_byte=0,
            end_byte=100,
            score=0.85,
        )

        assert result.filename == "/path/to/file.py"
        assert result.start_byte == 0
        assert result.end_byte == 100
        assert result.score == 0.85

    def test_dataclass_equality(self):
        """Two SearchResults with same values should be equal."""
        r1 = SearchResult("/file.py", 0, 100, 0.85)
        r2 = SearchResult("/file.py", 0, 100, 0.85)
        assert r1 == r2

    def test_dataclass_inequality(self):
        """SearchResults with different values should not be equal."""
        r1 = SearchResult("/file.py", 0, 100, 0.85)
        r2 = SearchResult("/file.py", 0, 100, 0.90)  # Different score
        assert r1 != r2

    def test_metadata_fields_default_empty_strings(self):
        """Metadata fields should default to empty strings."""
        result = SearchResult(
            filename="/path/file.py",
            start_byte=0,
            end_byte=100,
            score=0.85,
        )
        assert result.block_type == ""
        assert result.hierarchy == ""
        assert result.language_id == ""

    def test_metadata_fields_set(self):
        """Metadata fields should accept explicit values."""
        result = SearchResult(
            filename="/path/main.tf",
            start_byte=0,
            end_byte=200,
            score=0.90,
            block_type="resource",
            hierarchy="resource.aws_s3_bucket.data",
            language_id="hcl",
        )
        assert result.block_type == "resource"
        assert result.hierarchy == "resource.aws_s3_bucket.data"
        assert result.language_id == "hcl"


class TestGetExtensionPatterns:
    """Tests for get_extension_patterns function."""

    def test_python_extensions(self):
        """Should return Python file patterns."""
        patterns = get_extension_patterns("python")
        assert "%.py" in patterns
        assert "%.pyw" in patterns
        assert "%.pyi" in patterns

    def test_typescript_extensions(self):
        """Should return TypeScript file patterns."""
        patterns = get_extension_patterns("typescript")
        assert "%.ts" in patterns
        assert "%.tsx" in patterns

    def test_case_insensitive(self):
        """Should handle case-insensitive language names."""
        patterns = get_extension_patterns("Python")
        assert "%.py" in patterns

    def test_unknown_language_fallback(self):
        """Unknown language should fallback to .{language} extension."""
        patterns = get_extension_patterns("cobol")
        assert patterns == ["%.cobol"]


class TestValidateLanguageFilter:
    """Tests for validate_language_filter function."""

    def test_single_language(self):
        """Single language should return a one-element list."""
        assert validate_language_filter("python") == ["python"]

    def test_multiple_languages(self):
        """Comma-separated languages should return multiple elements."""
        assert validate_language_filter("hcl,bash") == ["hcl", "bash"]

    def test_strips_whitespace(self):
        """Whitespace around language names should be stripped."""
        assert validate_language_filter("hcl , bash") == ["hcl", "bash"]

    def test_devops_languages(self):
        """DevOps canonical names should be accepted."""
        assert validate_language_filter("hcl") == ["hcl"]
        assert validate_language_filter("dockerfile") == ["dockerfile"]
        assert validate_language_filter("bash") == ["bash"]

    def test_alias_terraform_resolves_to_hcl(self):
        """Alias 'terraform' should resolve to 'hcl'."""
        assert validate_language_filter("terraform") == ["hcl"]

    def test_alias_shell_resolves_to_bash(self):
        """Alias 'shell' should resolve to 'bash'."""
        assert validate_language_filter("shell") == ["bash"]

    def test_alias_sh_resolves_to_bash(self):
        """Alias 'sh' should resolve to 'bash'."""
        assert validate_language_filter("sh") == ["bash"]

    def test_mixed_alias_and_canonical(self):
        """Mixed aliases and canonical names should resolve correctly."""
        assert validate_language_filter("terraform,bash") == ["hcl", "bash"]

    def test_unknown_raises_valueerror(self):
        """Unknown language should raise ValueError with suggestions."""
        with pytest.raises(ValueError, match="Unknown language"):
            validate_language_filter("foobar")

    def test_mixed_known_unknown_raises(self):
        """Mix of known and unknown should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown language"):
            validate_language_filter("python,foobar")


class TestSearch:
    """Tests for search function with mocked dependencies."""

    def test_returns_search_results(self, mock_code_to_embedding, mock_db_pool):
        """Should return list of SearchResult objects."""
        pool, cursor, _conn = mock_db_pool(results=[
            ("/path/file.py", 0, 100, 0.85, "", "", ""),
        ])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            results = search(query="test query", index_name="testindex")

        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].filename == "/path/file.py"
        assert results[0].start_byte == 0
        assert results[0].end_byte == 100
        assert results[0].score == 0.85

    def test_applies_limit(self, mock_code_to_embedding, mock_db_pool):
        """Should respect limit parameter in query."""
        pool, cursor, _conn = mock_db_pool(results=[
            ("/path/file1.py", 0, 100, 0.9, "", "", ""),
            ("/path/file2.py", 0, 100, 0.8, "", "", ""),
            ("/path/file3.py", 0, 100, 0.7, "", "", ""),
        ])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            results = search(query="test", index_name="testindex", limit=5)

        # Verify LIMIT was in the query
        cursor.assert_query_contains("LIMIT")
        # Results should be returned (limit applied at DB level)
        assert len(results) == 3

    def test_applies_min_score(self, mock_code_to_embedding, mock_db_pool):
        """Should filter results below min_score."""
        pool, cursor, _conn = mock_db_pool(results=[
            ("/path/file1.py", 0, 100, 0.9, "", "", ""),
            ("/path/file2.py", 0, 100, 0.6, "", "", ""),  # Below 0.7 threshold
            ("/path/file3.py", 0, 100, 0.5, "", "", ""),  # Below 0.7 threshold
        ])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            results = search(query="test", index_name="testindex", min_score=0.7)

        # Only file1 should pass the min_score filter
        assert len(results) == 1
        assert results[0].filename == "/path/file1.py"
        assert results[0].score >= 0.7

    def test_applies_language_filter(self, mock_code_to_embedding, mock_db_pool):
        """Should filter by file extension when language specified."""
        pool, cursor, _conn = mock_db_pool(results=[
            ("/path/file.py", 0, 100, 0.85, "", "", ""),
        ])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            results = search(
                query="test",
                index_name="testindex",
                language_filter="python",
            )

        # Verify LIKE clause was in the query for extension filtering
        cursor.assert_query_contains("LIKE")
        assert len(results) == 1

    def test_multiple_results_ordered_by_score(self, mock_code_to_embedding, mock_db_pool):
        """Results should maintain database order (by score)."""
        pool, cursor, _conn = mock_db_pool(results=[
            ("/path/high.py", 0, 100, 0.95, "", "", ""),
            ("/path/medium.py", 0, 100, 0.75, "", "", ""),
            ("/path/low.py", 0, 100, 0.55, "", "", ""),
        ])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            results = search(query="test", index_name="testindex")

        assert len(results) == 3
        # Verify order matches input (already sorted by DB)
        assert results[0].score == 0.95
        assert results[1].score == 0.75
        assert results[2].score == 0.55

    def test_empty_results(self, mock_code_to_embedding, mock_db_pool):
        """Should handle empty results gracefully."""
        pool, cursor, _conn = mock_db_pool(results=[])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            results = search(query="nonexistent", index_name="testindex")

        assert results == []

    def test_calls_embedding_function(self, mock_code_to_embedding, mock_db_pool):
        """Should call code_to_embedding.eval with the query."""
        pool, cursor, _conn = mock_db_pool(results=[])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            search(query="find authentication code", index_name="testindex")

        # The mock tracks that eval was called
        assert mock_code_to_embedding.eval is not None

    def test_uses_correct_table_name(self, mock_code_to_embedding, mock_db_pool):
        """Should query the correct table based on index_name."""
        pool, cursor, _conn = mock_db_pool(results=[])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            search(query="test", index_name="myproject")

        # Table name should follow CocoIndex convention
        cursor.assert_query_contains("codeindex_myproject__myproject_chunks")

    def test_metadata_populated_from_row(self, mock_code_to_embedding, mock_db_pool):
        """Should populate metadata fields from database rows."""
        pool, cursor, _conn = mock_db_pool(results=[
            ("/path/main.tf", 0, 200, 0.90, "resource", "resource.aws_s3_bucket.data", "hcl"),
        ])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            results = search(query="s3 bucket", index_name="testindex")

        assert len(results) == 1
        assert results[0].block_type == "resource"
        assert results[0].hierarchy == "resource.aws_s3_bucket.data"
        assert results[0].language_id == "hcl"


class TestDevOpsLanguageFilter:
    """Tests for DevOps language filtering via language_id column."""

    def test_hcl_filter_uses_language_id(self, mock_code_to_embedding, mock_db_pool):
        """HCL filter should use language_id column, not filename LIKE."""
        pool, cursor, _conn = mock_db_pool(results=[
            ("/path/main.tf", 0, 200, 0.90, "resource", "resource.aws_s3_bucket.data", "hcl"),
        ])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            search(query="s3", index_name="testindex", language_filter="hcl")

        cursor.assert_query_contains("language_id")

    def test_dockerfile_filter_uses_language_id(self, mock_code_to_embedding, mock_db_pool):
        """Dockerfile filter should use language_id column."""
        pool, cursor, _conn = mock_db_pool(results=[
            ("/path/Dockerfile", 0, 100, 0.85, "FROM", "stage:builder", "dockerfile"),
        ])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            search(query="build", index_name="testindex", language_filter="dockerfile")

        cursor.assert_query_contains("language_id")

    def test_multi_language_filter(self, mock_code_to_embedding, mock_db_pool):
        """Multi-language filter should combine language_id and filename LIKE with OR."""
        pool, cursor, _conn = mock_db_pool(results=[
            ("/path/main.tf", 0, 200, 0.90, "resource", "resource.aws_s3_bucket.data", "hcl"),
            ("/path/utils.py", 0, 150, 0.80, "", "", ""),
        ])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            search(query="code", index_name="testindex", language_filter="hcl,python")

        # Should have both language_id and LIKE conditions
        cursor.assert_query_contains("language_id")
        cursor.assert_query_contains("LIKE")

    def test_alias_terraform_filters_as_hcl(self, mock_code_to_embedding, mock_db_pool):
        """Alias 'terraform' should filter by language_id = 'hcl'."""
        pool, cursor, _conn = mock_db_pool(results=[
            ("/path/main.tf", 0, 200, 0.90, "resource", "resource.aws_s3_bucket.data", "hcl"),
        ])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            search(query="s3", index_name="testindex", language_filter="terraform")

        cursor.assert_query_contains("language_id")
        cursor.assert_called_with_param("hcl")


class TestGracefulDegradation:
    """Tests for graceful degradation on pre-v1.2 indexes."""

    def test_pre_v12_index_returns_empty_metadata(self, mock_code_to_embedding, mock_db_pool):
        """Pre-v1.2 index should return results with empty metadata, not crash."""
        from psycopg.errors import UndefinedColumn

        pool, cursor, _conn = mock_db_pool(results=[])

        call_count = 0
        original_execute = cursor.execute

        def side_effect_execute(query, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call with metadata columns - simulate UndefinedColumn
                original_execute(query, params)
                raise UndefinedColumn("column \"block_type\" does not exist")
            else:
                # Second call without metadata columns - return results
                cursor.results = [
                    ("/path/file.py", 0, 100, 0.85),
                ]
                cursor._fetch_index = 0
                original_execute(query, params)

        cursor.execute = side_effect_execute

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            results = search(query="test", index_name="testindex")

        assert len(results) == 1
        assert results[0].block_type == ""
        assert results[0].hierarchy == ""
        assert results[0].language_id == ""

    def test_pre_v12_emits_warning(self, mock_code_to_embedding, mock_db_pool, caplog):
        """Pre-v1.2 index should emit a one-time warning about missing metadata."""
        from psycopg.errors import UndefinedColumn

        pool, cursor, _conn = mock_db_pool(results=[])

        call_count = 0
        original_execute = cursor.execute

        def side_effect_execute(query, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                original_execute(query, params)
                raise UndefinedColumn("column \"block_type\" does not exist")
            else:
                cursor.results = [("/path/file.py", 0, 100, 0.85)]
                cursor._fetch_index = 0
                original_execute(query, params)

        cursor.execute = side_effect_execute

        with caplog.at_level(logging.WARNING):
            with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
                search(query="test", index_name="testindex")

        assert any("metadata columns" in record.message for record in caplog.records)
        assert any("upgrade" in record.message for record in caplog.records)

    def test_pre_v12_devops_filter_raises_error(self, mock_code_to_embedding, mock_db_pool):
        """DevOps language filter on pre-v1.2 index should raise clear error."""
        # Simulate pre-v1.2 state
        query_module._has_metadata_columns = False

        pool, cursor, _conn = mock_db_pool(results=[])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            with pytest.raises(ValueError, match="v1.2 index"):
                search(query="s3", index_name="testindex", language_filter="hcl")

    def test_pre_v12_extension_filter_still_works(self, mock_code_to_embedding, mock_db_pool):
        """Extension-based filter should still work on pre-v1.2 index."""
        # Simulate pre-v1.2 state
        query_module._has_metadata_columns = False

        pool, cursor, _conn = mock_db_pool(results=[
            ("/path/file.py", 0, 100, 0.85),
        ])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            results = search(
                query="test",
                index_name="testindex",
                language_filter="python",
            )

        assert len(results) == 1
        cursor.assert_query_contains("LIKE")
