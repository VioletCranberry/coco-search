"""Tests for cocosearch.search.db module.

Tests database connection pool creation and table name generation
using mocked environments to avoid real database dependencies.
"""

import os
from unittest.mock import patch, MagicMock

import pytest

import cocosearch.search.db as db_module
from cocosearch.search.db import get_connection_pool, get_table_name


class TestGetConnectionPool:
    """Tests for get_connection_pool function."""

    def test_uses_default_when_env_var_not_set(self):
        """Should use default DATABASE_URL when COCOSEARCH_DATABASE_URL not set."""
        db_module._pool = None

        with patch.dict(os.environ, {}, clear=True):
            with patch("cocosearch.search.db.ConnectionPool") as mock_pool_cls:
                mock_pool_cls.return_value = MagicMock()
                pool = get_connection_pool()

        # Verify ConnectionPool was called with the default URL
        mock_pool_cls.assert_called_once()
        call_kwargs = mock_pool_cls.call_args
        assert "cocosearch:cocosearch" in call_kwargs.kwargs.get("conninfo", call_kwargs.args[0] if call_kwargs.args else "")


class TestGetTableName:
    """Tests for get_table_name function."""

    def test_generates_correct_name(self):
        """Should generate correct table name for simple index name."""
        # Pattern: codeindex_{index}__{index}_chunks
        result = get_table_name("myproject")
        assert result == "codeindex_myproject__myproject_chunks"

    def test_handles_underscores(self):
        """Should handle index names with underscores correctly."""
        result = get_table_name("my_project")
        assert result == "codeindex_my_project__my_project_chunks"

    def test_preserves_case(self):
        """Should preserve case of input in table name."""
        # Note: CocoIndex lowercases flow names but the input case is preserved
        # in the function output (actual lowercasing happens at CocoIndex level)
        result = get_table_name("MyProject")
        assert result == "codeindex_MyProject__MyProject_chunks"

    def test_handles_numbers(self):
        """Should handle index names with numbers."""
        result = get_table_name("project123")
        assert result == "codeindex_project123__project123_chunks"


@pytest.mark.unit
class TestCheckSymbolColumnsExist:
    """Tests for symbol column existence checking."""

    def setup_method(self):
        """Reset module state before each test."""
        db_module.reset_symbol_columns_cache()

    def test_check_symbol_columns_exist_all_present(self):
        """Should return True when all three symbol columns exist."""
        # Mock connection pool and database response
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Mock that all three columns exist
        mock_cursor.fetchall.return_value = [
            ("symbol_type",),
            ("symbol_name",),
            ("symbol_signature",),
        ]

        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.connection.return_value.__enter__.return_value = mock_conn

        with patch.object(db_module, "get_connection_pool", return_value=mock_pool):
            result = db_module.check_symbol_columns_exist("test_table")

        assert result is True

    def test_check_symbol_columns_exist_missing(self):
        """Should return False when symbol columns are missing (pre-v1.7)."""
        # Mock connection pool and database response
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Mock empty result (no columns found)
        mock_cursor.fetchall.return_value = []

        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.connection.return_value.__enter__.return_value = mock_conn

        with patch.object(db_module, "get_connection_pool", return_value=mock_pool):
            result = db_module.check_symbol_columns_exist("test_table")

        assert result is False

    def test_check_symbol_columns_exist_partial(self):
        """Should return False when only some symbol columns exist."""
        # Mock connection pool and database response
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Mock partial columns (only 2 out of 3)
        mock_cursor.fetchall.return_value = [
            ("symbol_type",),
            ("symbol_name",),
        ]

        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.connection.return_value.__enter__.return_value = mock_conn

        with patch.object(db_module, "get_connection_pool", return_value=mock_pool):
            result = db_module.check_symbol_columns_exist("test_table")

        assert result is False

    def test_check_symbol_columns_exist_cached(self):
        """Should use cache on repeated calls to avoid database queries."""
        # Mock connection pool and database response
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Mock that all three columns exist
        mock_cursor.fetchall.return_value = [
            ("symbol_type",),
            ("symbol_name",),
            ("symbol_signature",),
        ]

        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.connection.return_value.__enter__.return_value = mock_conn

        with patch.object(db_module, "get_connection_pool", return_value=mock_pool):
            # First call should query database
            result1 = db_module.check_symbol_columns_exist("test_table")
            # Second call should use cache
            result2 = db_module.check_symbol_columns_exist("test_table")

        assert result1 is True
        assert result2 is True

        # Verify database was only queried once
        assert mock_cursor.execute.call_count == 1

    def test_reset_symbol_columns_cache(self):
        """Should clear the cache when reset function is called."""
        # Populate cache
        db_module._symbol_columns_available["test_table"] = True

        # Verify cache has data
        assert "test_table" in db_module._symbol_columns_available

        # Reset cache
        db_module.reset_symbol_columns_cache()

        # Verify cache is empty
        assert "test_table" not in db_module._symbol_columns_available
        assert len(db_module._symbol_columns_available) == 0
