"""Tests for index clearing module.

Tests clear_index function using mock database pool.
"""

import pytest
from unittest.mock import patch

from cocosearch.management.clear import check_linked_index_references, clear_index


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


class TestCheckLinkedIndexReferences:
    """Tests for check_linked_index_references function."""

    def test_index_in_linked_returns_warning(self):
        mock_cfg = type("Cfg", (), {"linkedIndexes": ["shared_lib"]})()
        with (
            patch(
                "cocosearch.config.find_config_file",
                return_value="/fake/cocosearch.yaml",
            ),
            patch("cocosearch.config.load_config", return_value=mock_cfg),
        ):
            warnings = check_linked_index_references(["shared_lib"])
            assert len(warnings) == 1
            assert "shared_lib" in warnings[0]
            assert "linkedIndexes" in warnings[0]

    def test_index_not_in_linked_returns_empty(self):
        mock_cfg = type("Cfg", (), {"linkedIndexes": ["shared_lib"]})()
        with (
            patch(
                "cocosearch.config.find_config_file",
                return_value="/fake/cocosearch.yaml",
            ),
            patch("cocosearch.config.load_config", return_value=mock_cfg),
        ):
            assert check_linked_index_references(["other_index"]) == []

    def test_no_config_returns_empty(self):
        with patch("cocosearch.config.find_config_file", return_value=None):
            assert check_linked_index_references(["anything"]) == []

    def test_empty_linked_indexes_returns_empty(self):
        mock_cfg = type("Cfg", (), {"linkedIndexes": []})()
        with (
            patch(
                "cocosearch.config.find_config_file",
                return_value="/fake/cocosearch.yaml",
            ),
            patch("cocosearch.config.load_config", return_value=mock_cfg),
        ):
            assert check_linked_index_references(["shared_lib"]) == []

    def test_multiple_indexes_some_referenced(self):
        mock_cfg = type("Cfg", (), {"linkedIndexes": ["lib_a", "lib_b"]})()
        with (
            patch(
                "cocosearch.config.find_config_file",
                return_value="/fake/cocosearch.yaml",
            ),
            patch("cocosearch.config.load_config", return_value=mock_cfg),
        ):
            warnings = check_linked_index_references(["lib_a", "unrelated", "lib_b"])
            assert len(warnings) == 2
            assert "lib_a" in warnings[0]
            assert "lib_b" in warnings[1]

    def test_exception_returns_empty(self):
        with patch(
            "cocosearch.config.find_config_file",
            side_effect=RuntimeError("boom"),
        ):
            assert check_linked_index_references(["anything"]) == []
