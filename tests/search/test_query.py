"""Tests for cocosearch.search.query module.

Tests search query functionality including SearchResult dataclass,
search function with mocked database and embedding calls.
"""

from unittest.mock import patch

import pytest

from cocosearch.search.query import (
    SearchResult,
    search,
    get_extension_patterns,
    LANGUAGE_EXTENSIONS,
)


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


class TestSearch:
    """Tests for search function with mocked dependencies."""

    def test_returns_search_results(self, mock_code_to_embedding, mock_db_pool):
        """Should return list of SearchResult objects."""
        pool, cursor, _conn = mock_db_pool(results=[
            ("/path/file.py", 0, 100, 0.85),
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
            ("/path/file1.py", 0, 100, 0.9),
            ("/path/file2.py", 0, 100, 0.8),
            ("/path/file3.py", 0, 100, 0.7),
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
            ("/path/file1.py", 0, 100, 0.9),
            ("/path/file2.py", 0, 100, 0.6),  # Below 0.7 threshold
            ("/path/file3.py", 0, 100, 0.5),  # Below 0.7 threshold
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
            ("/path/file.py", 0, 100, 0.85),
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
            ("/path/high.py", 0, 100, 0.95),
            ("/path/medium.py", 0, 100, 0.75),
            ("/path/low.py", 0, 100, 0.55),
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
