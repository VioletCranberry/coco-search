"""Tests for index clearing module.

Tests clear_index function using mock database pool.
"""

import pytest
from unittest.mock import patch

from cocosearch.management.clear import clear_index


class TestClearIndex:
    """Tests for clear_index function."""

    def test_deletes_existing_index(self, mock_db_pool):
        """Returns success=True for existing index."""
        # First query: EXISTS check returns True
        # Second query: DROP TABLE (no result needed)
        pool, cursor, conn = mock_db_pool(results=[(True,)])
        with patch(
            "cocosearch.management.clear.get_connection_pool", return_value=pool
        ):
            result = clear_index("myproject")

        assert result["success"] is True
        assert "myproject" in result["message"]
        assert "deleted" in result["message"]
        cursor.assert_query_contains("DROP TABLE")

    def test_raises_for_nonexistent(self, mock_db_pool):
        """Raises ValueError for missing index."""
        # EXISTS check returns False
        pool, cursor, conn = mock_db_pool(results=[(False,)])
        with patch(
            "cocosearch.management.clear.get_connection_pool", return_value=pool
        ):
            with pytest.raises(ValueError, match="not found"):
                clear_index("nonexistent")

    def test_commits_transaction(self, mock_db_pool):
        """Verifies commit is called after DROP."""
        pool, cursor, conn = mock_db_pool(results=[(True,)])
        with patch(
            "cocosearch.management.clear.get_connection_pool", return_value=pool
        ):
            clear_index("myproject")

        assert conn.committed is True

    def test_uses_correct_table_name(self, mock_db_pool):
        """Uses get_table_name to derive table name."""
        pool, cursor, conn = mock_db_pool(results=[(True,)])
        with patch(
            "cocosearch.management.clear.get_connection_pool", return_value=pool
        ):
            # Mock get_table_name to verify it's called
            with patch(
                "cocosearch.management.clear.get_table_name",
                return_value="codeindex_test__test_chunks",
            ) as mock_table_name:
                clear_index("test")
                mock_table_name.assert_called_once_with("test")

    def test_drop_table_uses_table_name(self, mock_db_pool):
        """DROP TABLE query includes the correct table name."""
        pool, cursor, conn = mock_db_pool(results=[(True,)])
        with patch(
            "cocosearch.management.clear.get_connection_pool", return_value=pool
        ):
            clear_index("myproject")

        # Find the DROP TABLE queries and verify table names are included
        drop_queries = [q for q, _ in cursor.calls if "DROP TABLE" in q]
        assert len(drop_queries) == 2
        # Chunks table drop
        assert "codeindex_" in drop_queries[0] or "myproject" in drop_queries[0]
        # Parse results table drop
        assert "cocosearch_parse_results_myproject" in drop_queries[1]
