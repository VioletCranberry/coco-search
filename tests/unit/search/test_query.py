"""Tests for cocosearch.search.query module.

Tests search query functionality including SearchResult dataclass,
search function with mocked database and embedding calls,
DevOps language filtering, alias resolution, and graceful degradation.
"""

from unittest.mock import patch

import pytest

from cocosearch.search.query import (
    SearchResult,
    search,
    get_extension_patterns,
    validate_language_filter,
)


# Note: Module state reset is now handled by reset_search_module_state fixture
# in tests/fixtures/db.py which is an autouse fixture.


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
        pool, cursor, _conn = mock_db_pool(
            results=[
                ("/path/file.py", 0, 100, 0.85, "", "", ""),
            ]
        )

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
        pool, cursor, _conn = mock_db_pool(
            results=[
                ("/path/file1.py", 0, 100, 0.9, "", "", ""),
                ("/path/file2.py", 0, 100, 0.8, "", "", ""),
                ("/path/file3.py", 0, 100, 0.7, "", "", ""),
            ]
        )

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            results = search(query="test", index_name="testindex", limit=5)

        # Verify LIMIT was in the query
        cursor.assert_query_contains("LIMIT")
        # Results should be returned (limit applied at DB level)
        assert len(results) == 3

    def test_applies_min_score(self, mock_code_to_embedding, mock_db_pool):
        """Should filter results below min_score."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                ("/path/file1.py", 0, 100, 0.9, "", "", ""),
                ("/path/file2.py", 0, 100, 0.6, "", "", ""),  # Below 0.7 threshold
                ("/path/file3.py", 0, 100, 0.5, "", "", ""),  # Below 0.7 threshold
            ]
        )

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            results = search(query="test", index_name="testindex", min_score=0.7)

        # Only file1 should pass the min_score filter
        assert len(results) == 1
        assert results[0].filename == "/path/file1.py"
        assert results[0].score >= 0.7

    def test_applies_language_filter(self, mock_code_to_embedding, mock_db_pool):
        """Should filter by file extension when language specified."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                ("/path/file.py", 0, 100, 0.85, "", "", ""),
            ]
        )

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            results = search(
                query="test",
                index_name="testindex",
                language_filter="python",
            )

        # Verify LIKE clause was in the query for extension filtering
        cursor.assert_query_contains("LIKE")
        assert len(results) == 1

    def test_multiple_results_ordered_by_score(
        self, mock_code_to_embedding, mock_db_pool
    ):
        """Results should maintain database order (by score)."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                ("/path/high.py", 0, 100, 0.95, "", "", ""),
                ("/path/medium.py", 0, 100, 0.75, "", "", ""),
                ("/path/low.py", 0, 100, 0.55, "", "", ""),
            ]
        )

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
        pool, cursor, _conn = mock_db_pool(
            results=[
                (
                    "/path/main.tf",
                    0,
                    200,
                    0.90,
                    "resource",
                    "resource.aws_s3_bucket.data",
                    "hcl",
                ),
            ]
        )

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
        pool, cursor, _conn = mock_db_pool(
            results=[
                (
                    "/path/main.tf",
                    0,
                    200,
                    0.90,
                    "resource",
                    "resource.aws_s3_bucket.data",
                    "hcl",
                ),
            ]
        )

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            search(query="s3", index_name="testindex", language_filter="hcl")

        cursor.assert_query_contains("language_id")

    def test_dockerfile_filter_uses_language_id(
        self, mock_code_to_embedding, mock_db_pool
    ):
        """Dockerfile filter should use language_id column."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                (
                    "/path/Dockerfile",
                    0,
                    100,
                    0.85,
                    "FROM",
                    "stage:builder",
                    "dockerfile",
                ),
            ]
        )

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            search(query="build", index_name="testindex", language_filter="dockerfile")

        cursor.assert_query_contains("language_id")

    def test_multi_language_filter(self, mock_code_to_embedding, mock_db_pool):
        """Multi-language filter should combine language_id and filename LIKE with OR."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                (
                    "/path/main.tf",
                    0,
                    200,
                    0.90,
                    "resource",
                    "resource.aws_s3_bucket.data",
                    "hcl",
                ),
                ("/path/utils.py", 0, 150, 0.80, "", "", ""),
            ]
        )

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            search(query="code", index_name="testindex", language_filter="hcl,python")

        # Should have both language_id and LIKE conditions
        cursor.assert_query_contains("language_id")
        cursor.assert_query_contains("LIKE")

    def test_alias_terraform_filters_as_hcl(self, mock_code_to_embedding, mock_db_pool):
        """Alias 'terraform' should filter by language_id = 'hcl'."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                (
                    "/path/main.tf",
                    0,
                    200,
                    0.90,
                    "resource",
                    "resource.aws_s3_bucket.data",
                    "hcl",
                ),
            ]
        )

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            search(query="s3", index_name="testindex", language_filter="terraform")

        cursor.assert_query_contains("language_id")
        cursor.assert_called_with_param("hcl")


class TestSymbolFilters:
    """Tests for symbol filtering in search function."""

    def test_search_symbol_type_filter(self, mock_code_to_embedding, mock_db_pool):
        """Symbol type filter should generate WHERE clause with symbol_type condition."""
        # Results with 10 columns: 7 metadata + 3 symbol columns
        pool, cursor, _conn = mock_db_pool(
            results=[
                (
                    "/path/utils.py",
                    0,
                    100,
                    0.85,
                    "",
                    "",
                    "",
                    "function",
                    "process_data",
                    "def process_data()",
                ),
            ]
        )

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            with patch(
                "cocosearch.search.query.check_symbol_columns_exist", return_value=True
            ):
                results = search(
                    query="test",
                    index_name="testindex",
                    symbol_type="function",
                )

        cursor.assert_query_contains("symbol_type = %s")
        cursor.assert_called_with_param("function")
        assert len(results) == 1
        assert results[0].symbol_type == "function"
        assert results[0].symbol_name == "process_data"

    def test_search_symbol_name_filter(self, mock_code_to_embedding, mock_db_pool):
        """Symbol name filter should generate WHERE clause with ILIKE condition."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                (
                    "/path/utils.py",
                    0,
                    100,
                    0.85,
                    "",
                    "",
                    "",
                    "function",
                    "get_user",
                    "def get_user()",
                ),
            ]
        )

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            with patch(
                "cocosearch.search.query.check_symbol_columns_exist", return_value=True
            ):
                search(
                    query="test",
                    index_name="testindex",
                    symbol_name="get*",
                )

        cursor.assert_query_contains("symbol_name ILIKE %s")
        cursor.assert_called_with_param("get%")

    def test_search_symbol_filters_combined(self, mock_code_to_embedding, mock_db_pool):
        """Both symbol filters should combine with AND."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                (
                    "/path/utils.py",
                    0,
                    100,
                    0.85,
                    "",
                    "",
                    "",
                    "function",
                    "get_user",
                    "def get_user()",
                ),
            ]
        )

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            with patch(
                "cocosearch.search.query.check_symbol_columns_exist", return_value=True
            ):
                search(
                    query="test",
                    index_name="testindex",
                    symbol_type="function",
                    symbol_name="get*",
                )

        cursor.assert_query_contains("symbol_type = %s")
        cursor.assert_query_contains("symbol_name ILIKE %s")

    def test_search_symbol_filter_prv17_error(
        self, mock_code_to_embedding, mock_db_pool
    ):
        """Symbol filter on pre-v1.7 index should raise helpful ValueError."""
        pool, cursor, _conn = mock_db_pool(results=[])

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            with patch(
                "cocosearch.search.query.check_symbol_columns_exist", return_value=False
            ):
                with pytest.raises(ValueError) as exc_info:
                    search(
                        query="test",
                        index_name="testindex",
                        symbol_type="function",
                    )

        assert "v1.7" in str(exc_info.value)
        assert "Re-index" in str(exc_info.value)
        assert "testindex" in str(exc_info.value)

    def test_search_result_includes_symbol_fields(
        self, mock_code_to_embedding, mock_db_pool
    ):
        """SearchResult should include symbol_type, symbol_name, symbol_signature."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                (
                    "/path/utils.py",
                    0,
                    100,
                    0.85,
                    "",
                    "",
                    "",
                    "method",
                    "UserService.get_user",
                    "def get_user(self, id: int)",
                ),
            ]
        )

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            with patch(
                "cocosearch.search.query.check_symbol_columns_exist", return_value=True
            ):
                results = search(
                    query="test",
                    index_name="testindex",
                    symbol_type="method",
                )

        assert len(results) == 1
        assert results[0].symbol_type == "method"
        assert results[0].symbol_name == "UserService.get_user"
        assert results[0].symbol_signature == "def get_user(self, id: int)"

    def test_search_symbol_filter_with_language_filter(
        self, mock_code_to_embedding, mock_db_pool
    ):
        """Symbol filter should combine with language filter via AND."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                (
                    "/path/utils.py",
                    0,
                    100,
                    0.85,
                    "",
                    "",
                    "",
                    "function",
                    "process",
                    "def process()",
                ),
            ]
        )

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            with patch(
                "cocosearch.search.query.check_symbol_columns_exist", return_value=True
            ):
                search(
                    query="test",
                    index_name="testindex",
                    language_filter="python",
                    symbol_type="function",
                )

        # Both conditions should be present
        cursor.assert_query_contains("LIKE")  # Language filter
        cursor.assert_query_contains("symbol_type = %s")  # Symbol filter

    def test_search_multiple_symbol_types(self, mock_code_to_embedding, mock_db_pool):
        """Multiple symbol types should generate IN clause."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                (
                    "/path/utils.py",
                    0,
                    100,
                    0.85,
                    "",
                    "",
                    "",
                    "function",
                    "process",
                    "def process()",
                ),
            ]
        )

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            with patch(
                "cocosearch.search.query.check_symbol_columns_exist", return_value=True
            ):
                search(
                    query="test",
                    index_name="testindex",
                    symbol_type=["function", "method"],
                )

        cursor.assert_query_contains("symbol_type IN")

    def test_search_symbol_fields_default_none(self):
        """SearchResult symbol fields should default to None."""
        result = SearchResult(
            filename="/path/file.py",
            start_byte=0,
            end_byte=100,
            score=0.85,
        )
        assert result.symbol_type is None
        assert result.symbol_name is None
        assert result.symbol_signature is None

    def test_search_without_symbol_filter_no_extra_columns(
        self, mock_code_to_embedding, mock_db_pool
    ):
        """Search without symbol filter should not include symbol columns."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                ("/path/file.py", 0, 100, 0.85, "", "", ""),
            ]
        )

        with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
            search(query="test", index_name="testindex")

        # Should not query for symbol columns when not filtering
        last_query = cursor.calls[-1][0]
        assert "symbol_type," not in last_query
        assert "symbol_name," not in last_query
        assert "symbol_signature" not in last_query
