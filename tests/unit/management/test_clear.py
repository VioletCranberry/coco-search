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
            with patch(
                "cocosearch.management.clear.get_table_name",
                return_value="codeindex_test__test_chunks",
            ) as mock_table_name:
                clear_index("test")
                mock_table_name.assert_called_once_with("test")

    def test_drop_table_uses_table_name(self, mock_db_pool):
        """DROP TABLE queries include the correct table names."""
        pool, cursor, conn = mock_db_pool(results=[(True,)])
        with patch(
            "cocosearch.management.clear.get_connection_pool", return_value=pool
        ):
            clear_index("myproject")

        drop_queries = [q for q, _ in cursor.calls if "DROP TABLE" in q]
        assert len(drop_queries) == 6
        assert "codeindex_" in drop_queries[0] or "myproject" in drop_queries[0]
        assert "cocosearch_parse_results_myproject" in drop_queries[1]
        assert "cocosearch_deps_myproject" in drop_queries[2]
        assert "cocosearch_deps_tracking_myproject" in drop_queries[3]
        assert "codeindex_myproject__cocoindex_tracking" in drop_queries[4]
        assert "cocosearch_index_tracking_myproject" in drop_queries[5]

    def test_cleans_cocoindex_metadata(self, mock_db_pool):
        """Cleans legacy CocoIndex setup metadata."""
        pool, cursor, conn = mock_db_pool(results=[(True,)])
        with patch(
            "cocosearch.management.clear.get_connection_pool", return_value=pool
        ):
            clear_index("myproject")

        delete_queries = [
            (q, args)
            for q, args in cursor.calls
            if "DELETE FROM cocoindex_setup_metadata" in q
        ]
        assert len(delete_queries) == 1
        assert delete_queries[0][1] == ("CodeIndex_myproject",)
