"""Integration tests for hybrid search with symbol filters.

Tests the combination of --hybrid with --symbol-type and --symbol-name filters
to ensure filters apply before RRF fusion and results include correct metadata.
"""

import pytest
from unittest.mock import patch, MagicMock
import inspect

from cocosearch.search.query import search
from cocosearch.search.hybrid import (
    hybrid_search,
    execute_vector_search,
    execute_keyword_search,
    HybridSearchResult,
    VectorResult,
)
from cocosearch.search.filters import build_symbol_where_clause


@pytest.mark.unit
class TestHybridWithSymbolFilters:
    """Tests for hybrid search combined with symbol filtering."""

    def test_hybrid_search_accepts_symbol_type_filter(self):
        """Verify hybrid_search function accepts symbol_type parameter."""
        sig = inspect.signature(hybrid_search)
        assert "symbol_type" in sig.parameters
        assert "symbol_name" in sig.parameters

    def test_hybrid_search_accepts_language_filter(self):
        """Verify hybrid_search function accepts language_filter parameter."""
        sig = inspect.signature(hybrid_search)
        assert "language_filter" in sig.parameters

    def test_execute_vector_search_accepts_where_clause(self):
        """Verify execute_vector_search accepts WHERE clause parameters."""
        sig = inspect.signature(execute_vector_search)
        assert "where_clause" in sig.parameters
        assert "where_params" in sig.parameters

    def test_execute_keyword_search_accepts_where_clause(self):
        """Verify execute_keyword_search accepts WHERE clause parameters."""
        sig = inspect.signature(execute_keyword_search)
        assert "where_clause" in sig.parameters
        assert "where_params" in sig.parameters

    def test_execute_vector_search_accepts_include_symbol_columns(self):
        """Verify execute_vector_search accepts include_symbol_columns parameter."""
        sig = inspect.signature(execute_vector_search)
        assert "include_symbol_columns" in sig.parameters

    @patch("cocosearch.search.query.get_connection_pool")
    @patch("cocosearch.search.query.check_symbol_columns_exist")
    @patch("cocosearch.search.query.check_column_exists")
    @patch("cocosearch.search.query.execute_hybrid_search")
    def test_search_uses_hybrid_with_symbol_filter(
        self, mock_hybrid, mock_col_exists, mock_sym_cols, mock_pool
    ):
        """Verify search() calls hybrid_search with symbol filters when both are requested."""
        # Setup mocks
        mock_col_exists.return_value = True  # content_text exists
        mock_sym_cols.return_value = True  # symbol columns exist
        mock_hybrid.return_value = []  # Empty results for simplicity

        # Call search with hybrid + symbol filter
        search(
            query="process data",
            index_name="test",
            use_hybrid=True,
            symbol_type="function",
        )

        # Verify hybrid_search was called with symbol_type
        mock_hybrid.assert_called_once()
        call_kwargs = mock_hybrid.call_args.kwargs
        assert call_kwargs.get("symbol_type") == "function"

    @patch("cocosearch.search.query.get_connection_pool")
    @patch("cocosearch.search.query.check_symbol_columns_exist")
    @patch("cocosearch.search.query.check_column_exists")
    @patch("cocosearch.search.query.execute_hybrid_search")
    def test_search_passes_language_filter_to_hybrid(
        self, mock_hybrid, mock_col_exists, mock_sym_cols, mock_pool
    ):
        """Verify search() passes language_filter to hybrid_search."""
        mock_col_exists.return_value = True
        mock_sym_cols.return_value = False
        mock_hybrid.return_value = []

        search(
            query="process data",
            index_name="test",
            use_hybrid=True,
            language_filter="python",
        )

        mock_hybrid.assert_called_once()
        call_kwargs = mock_hybrid.call_args.kwargs
        assert call_kwargs.get("language_filter") == "python"

    @patch("cocosearch.search.query.get_connection_pool")
    @patch("cocosearch.search.query.check_symbol_columns_exist")
    @patch("cocosearch.search.query.check_column_exists")
    @patch("cocosearch.search.query.execute_hybrid_search")
    def test_search_passes_all_filters_to_hybrid(
        self, mock_hybrid, mock_col_exists, mock_sym_cols, mock_pool
    ):
        """Verify search() passes all filter types to hybrid_search."""
        mock_col_exists.return_value = True
        mock_sym_cols.return_value = True
        mock_hybrid.return_value = []

        search(
            query="process data",
            index_name="test",
            use_hybrid=True,
            symbol_type="function",
            symbol_name="get*",
            language_filter="python,javascript",
        )

        mock_hybrid.assert_called_once()
        call_kwargs = mock_hybrid.call_args.kwargs
        assert call_kwargs.get("symbol_type") == "function"
        assert call_kwargs.get("symbol_name") == "get*"
        assert call_kwargs.get("language_filter") == "python,javascript"


@pytest.mark.unit
class TestWhereClauseIntegration:
    """Tests for WHERE clause building and application."""

    def test_symbol_where_clause_single_type(self):
        """Verify symbol filter WHERE clause for single type."""
        where, params = build_symbol_where_clause(symbol_type="function")
        assert where == "symbol_type = %s"
        assert params == ["function"]

    def test_symbol_where_clause_multiple_types(self):
        """Verify multiple symbol types use IN clause."""
        where, params = build_symbol_where_clause(symbol_type=["function", "method"])
        assert "IN" in where
        assert params == ["function", "method"]

    def test_symbol_where_clause_name_filter(self):
        """Verify symbol name filter uses ILIKE."""
        where, params = build_symbol_where_clause(symbol_name="get*")
        assert "ILIKE" in where
        assert params == ["get%"]

    def test_symbol_where_clause_combined(self):
        """Verify combined symbol_type and symbol_name."""
        where, params = build_symbol_where_clause(
            symbol_type="function", symbol_name="process*"
        )
        assert "symbol_type = %s" in where
        assert "AND" in where
        assert "ILIKE" in where
        assert params == ["function", "process%"]


@pytest.mark.unit
class TestHybridSearchResultWithSymbols:
    """Tests for HybridSearchResult with symbol fields."""

    def test_hybrid_result_has_symbol_fields(self):
        """Verify HybridSearchResult has symbol_type, symbol_name, symbol_signature fields."""
        result = HybridSearchResult(
            filename="/path/file.py",
            start_byte=0,
            end_byte=100,
            combined_score=0.5,
            match_type="both",
            vector_score=0.9,
            keyword_score=0.4,
            symbol_type="function",
            symbol_name="process_data",
            symbol_signature="def process_data(items: list)",
        )

        assert result.symbol_type == "function"
        assert result.symbol_name == "process_data"
        assert result.symbol_signature == "def process_data(items: list)"

    def test_hybrid_result_symbol_fields_default_none(self):
        """Verify symbol fields default to None."""
        result = HybridSearchResult(
            filename="/path/file.py",
            start_byte=0,
            end_byte=100,
            combined_score=0.5,
            match_type="semantic",
            vector_score=0.9,
            keyword_score=None,
        )

        assert result.symbol_type is None
        assert result.symbol_name is None
        assert result.symbol_signature is None


@pytest.mark.unit
class TestVectorResultWithSymbols:
    """Tests for VectorResult with symbol fields."""

    def test_vector_result_has_symbol_fields(self):
        """Verify VectorResult has symbol_type, symbol_name, symbol_signature fields."""
        result = VectorResult(
            filename="/path/file.py",
            start_byte=0,
            end_byte=100,
            score=0.9,
            symbol_type="method",
            symbol_name="UserService.get_user",
            symbol_signature="def get_user(self, id: int) -> User",
        )

        assert result.symbol_type == "method"
        assert result.symbol_name == "UserService.get_user"
        assert result.symbol_signature == "def get_user(self, id: int) -> User"

    def test_vector_result_symbol_fields_default_none(self):
        """Verify symbol fields default to None."""
        result = VectorResult(
            filename="/path/file.py",
            start_byte=0,
            end_byte=100,
            score=0.9,
        )

        assert result.symbol_type is None
        assert result.symbol_name is None
        assert result.symbol_signature is None


@pytest.mark.unit
class TestSearchResultWithHybridSymbols:
    """Tests for SearchResult with hybrid+symbol data."""

    @patch("cocosearch.search.query.get_connection_pool")
    @patch("cocosearch.search.query.check_symbol_columns_exist")
    @patch("cocosearch.search.query.check_column_exists")
    @patch("cocosearch.search.query.execute_hybrid_search")
    def test_search_result_includes_symbol_fields_from_hybrid(
        self, mock_hybrid, mock_col_exists, mock_sym_cols, mock_pool
    ):
        """Verify SearchResult includes symbol fields from HybridSearchResult."""
        mock_col_exists.return_value = True
        mock_sym_cols.return_value = True
        mock_hybrid.return_value = [
            HybridSearchResult(
                filename="/path/file.py",
                start_byte=0,
                end_byte=100,
                combined_score=0.8,
                match_type="both",
                vector_score=0.9,
                keyword_score=0.4,
                symbol_type="function",
                symbol_name="process_data",
                symbol_signature="def process_data(items: list)",
            )
        ]

        results = search(
            query="process data",
            index_name="test",
            use_hybrid=True,
            symbol_type="function",
        )

        assert len(results) == 1
        assert results[0].symbol_type == "function"
        assert results[0].symbol_name == "process_data"
        assert results[0].symbol_signature == "def process_data(items: list)"
        assert results[0].match_type == "both"
