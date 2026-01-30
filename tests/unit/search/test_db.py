"""Tests for cocosearch.search.db module.

Tests database connection pool creation and table name generation
using mocked environments to avoid real database dependencies.
"""

import os
from unittest.mock import patch

import pytest

import cocosearch.search.db as db_module
from cocosearch.search.db import get_connection_pool, get_table_name


class TestGetConnectionPool:
    """Tests for get_connection_pool function."""

    def test_raises_without_env_var(self):
        """Should raise ValueError when COCOINDEX_DATABASE_URL not set."""
        # Reset pool singleton to force new pool creation
        db_module._pool = None

        # Clear environment and verify error
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                get_connection_pool()

            assert "COCOINDEX_DATABASE_URL" in str(exc_info.value)
            assert "not set" in str(exc_info.value)


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
