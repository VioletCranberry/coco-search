"""Tests for index discovery module.

Tests list_indexes function using mock database pool.
"""

from unittest.mock import patch

from cocosearch.management.discovery import list_indexes


class TestListIndexes:
    """Tests for list_indexes function."""

    def test_returns_empty_when_no_indexes(self, mock_db_pool):
        """Returns empty list when no tables match pattern."""
        pool, cursor, conn = mock_db_pool(results=[])
        with patch(
            "cocosearch.management.discovery.get_connection_pool", return_value=pool
        ):
            indexes = list_indexes()
        assert indexes == []
        cursor.assert_query_contains("information_schema.tables")

    def test_returns_index_list(self, mock_db_pool):
        """Returns list of dicts with name and table_name."""
        pool, cursor, conn = mock_db_pool(
            results=[
                ("codeindex_myproject__myproject_chunks",),
                ("codeindex_other__other_chunks",),
            ]
        )
        with patch(
            "cocosearch.management.discovery.get_connection_pool", return_value=pool
        ):
            indexes = list_indexes()

        assert len(indexes) == 2
        assert indexes[0]["name"] == "myproject"
        assert indexes[0]["table_name"] == "codeindex_myproject__myproject_chunks"
        assert indexes[1]["name"] == "other"
        assert indexes[1]["table_name"] == "codeindex_other__other_chunks"

    def test_parses_table_name_correctly(self, mock_db_pool):
        """Extracts name from codeindex_X__X_chunks pattern."""
        pool, cursor, conn = mock_db_pool(
            results=[
                ("codeindex_my_app__my_app_chunks",),
            ]
        )
        with patch(
            "cocosearch.management.discovery.get_connection_pool", return_value=pool
        ):
            indexes = list_indexes()

        assert len(indexes) == 1
        # Name should be "my_app" - everything after "codeindex_" and before "__"
        assert indexes[0]["name"] == "my_app"

    def test_handles_complex_names(self, mock_db_pool):
        """Handles index names with underscores."""
        pool, cursor, conn = mock_db_pool(
            results=[
                ("codeindex_my_cool_project__my_cool_project_chunks",),
            ]
        )
        with patch(
            "cocosearch.management.discovery.get_connection_pool", return_value=pool
        ):
            indexes = list_indexes()

        assert len(indexes) == 1
        assert indexes[0]["name"] == "my_cool_project"
