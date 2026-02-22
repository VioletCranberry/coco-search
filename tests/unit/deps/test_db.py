"""Tests for cocosearch.deps.db module."""

import json
from unittest.mock import patch

from cocosearch.deps.db import create_deps_table, drop_deps_table, insert_edges
from cocosearch.deps.models import DependencyEdge, DepType


class TestCreateDepsTable:
    """Tests for create_deps_table()."""

    def test_creates_table_with_correct_columns(self, mock_db_pool):
        """CREATE TABLE should include all required columns."""
        pool, cursor, conn = mock_db_pool()

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            create_deps_table("myindex")

        cursor.assert_query_contains("CREATE TABLE")
        cursor.assert_query_contains("cocosearch_deps_myindex")
        cursor.assert_query_contains("id SERIAL PRIMARY KEY")
        cursor.assert_query_contains("source_file TEXT NOT NULL")
        cursor.assert_query_contains("source_symbol TEXT")
        cursor.assert_query_contains("target_file TEXT")
        cursor.assert_query_contains("target_symbol TEXT")
        cursor.assert_query_contains("dep_type TEXT NOT NULL")
        cursor.assert_query_contains("metadata JSONB")
        cursor.assert_query_contains("created_at TIMESTAMPTZ DEFAULT NOW()")

    def test_creates_indexes(self, mock_db_pool):
        """Should create indexes on key columns."""
        pool, cursor, conn = mock_db_pool()

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            create_deps_table("myindex")

        cursor.assert_query_contains("CREATE INDEX")
        # Index on (source_file, dep_type)
        cursor.assert_query_contains("source_file")
        cursor.assert_query_contains("dep_type")
        # Index on (target_file, target_symbol)
        cursor.assert_query_contains("target_file")
        cursor.assert_query_contains("target_symbol")

    def test_commits_after_creation(self, mock_db_pool):
        """Should commit after creating the table and indexes."""
        pool, cursor, conn = mock_db_pool()

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            create_deps_table("testindex")

        assert conn.committed

    def test_if_not_exists(self, mock_db_pool):
        """CREATE TABLE should use IF NOT EXISTS to be idempotent."""
        pool, cursor, conn = mock_db_pool()

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            create_deps_table("myindex")

        cursor.assert_query_contains("IF NOT EXISTS")


class TestDropDepsTable:
    """Tests for drop_deps_table()."""

    def test_drops_table_if_exists(self, mock_db_pool):
        """Should execute DROP TABLE IF EXISTS."""
        pool, cursor, conn = mock_db_pool()

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            drop_deps_table("myindex")

        cursor.assert_query_contains("DROP TABLE IF EXISTS")
        cursor.assert_query_contains("cocosearch_deps_myindex")

    def test_commits_after_drop(self, mock_db_pool):
        """Should commit after dropping the table."""
        pool, cursor, conn = mock_db_pool()

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            drop_deps_table("myindex")

        assert conn.committed


class TestInsertEdges:
    """Tests for insert_edges()."""

    def test_inserts_edges_with_correct_columns(self, mock_db_pool):
        """INSERT should include all edge columns."""
        pool, cursor, conn = mock_db_pool()
        edges = [
            DependencyEdge(
                source_file="src/main.py",
                source_symbol="main",
                target_file="src/utils.py",
                target_symbol="helper",
                dep_type=DepType.IMPORT,
                metadata={"line": 5},
            ),
        ]

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            insert_edges("myindex", edges)

        cursor.assert_query_contains("INSERT INTO")
        cursor.assert_query_contains("cocosearch_deps_myindex")
        cursor.assert_query_contains("source_file")
        cursor.assert_query_contains("source_symbol")
        cursor.assert_query_contains("target_file")
        cursor.assert_query_contains("target_symbol")
        cursor.assert_query_contains("dep_type")
        cursor.assert_query_contains("metadata")

    def test_inserts_correct_values(self, mock_db_pool):
        """INSERT should pass correct parameter values."""
        pool, cursor, conn = mock_db_pool()
        edges = [
            DependencyEdge(
                source_file="src/main.py",
                source_symbol="main",
                target_file="src/utils.py",
                target_symbol="helper",
                dep_type=DepType.IMPORT,
                metadata={"line": 5},
            ),
        ]

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            insert_edges("myindex", edges)

        # Verify the parameters passed to execute
        assert len(cursor.calls) > 0
        query, params = cursor.calls[0]
        assert params is not None
        assert "src/main.py" in params
        assert "main" in params
        assert "src/utils.py" in params
        assert "helper" in params
        assert "import" in params
        assert json.dumps({"line": 5}) in params

    def test_inserts_multiple_edges(self, mock_db_pool):
        """Should insert each edge individually."""
        pool, cursor, conn = mock_db_pool()
        edges = [
            DependencyEdge(
                source_file="src/a.py",
                source_symbol=None,
                target_file="src/b.py",
                target_symbol=None,
                dep_type=DepType.IMPORT,
            ),
            DependencyEdge(
                source_file="src/b.py",
                source_symbol="func",
                target_file="src/c.py",
                target_symbol="other",
                dep_type=DepType.CALL,
            ),
        ]

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            insert_edges("myindex", edges)

        # Should have two INSERT calls
        insert_calls = [
            (q, p) for q, p in cursor.calls if "INSERT INTO" in q
        ]
        assert len(insert_calls) == 2

    def test_commits_after_insert(self, mock_db_pool):
        """Should commit after inserting edges."""
        pool, cursor, conn = mock_db_pool()
        edges = [
            DependencyEdge(
                source_file="src/main.py",
                source_symbol=None,
                target_file="src/utils.py",
                target_symbol=None,
                dep_type=DepType.IMPORT,
            ),
        ]

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            insert_edges("myindex", edges)

        assert conn.committed

    def test_empty_list_is_noop(self, mock_db_pool):
        """Empty edge list should make no DB calls."""
        pool, cursor, conn = mock_db_pool()

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            insert_edges("myindex", [])

        assert len(cursor.calls) == 0
        assert not conn.committed

    def test_none_values_passed_correctly(self, mock_db_pool):
        """None values for optional fields should be passed as None."""
        pool, cursor, conn = mock_db_pool()
        edges = [
            DependencyEdge(
                source_file="src/main.py",
                source_symbol=None,
                target_file=None,
                target_symbol="os",
                dep_type=DepType.IMPORT,
            ),
        ]

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            insert_edges("myindex", edges)

        assert len(cursor.calls) == 1
        _, params = cursor.calls[0]
        assert params is not None
        # source_symbol and target_file should be None
        assert None in params

    def test_empty_metadata_serialized(self, mock_db_pool):
        """Empty metadata dict should be serialized as JSON '{}'."""
        pool, cursor, conn = mock_db_pool()
        edges = [
            DependencyEdge(
                source_file="src/main.py",
                source_symbol=None,
                target_file=None,
                target_symbol=None,
                dep_type=DepType.IMPORT,
            ),
        ]

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            insert_edges("myindex", edges)

        _, params = cursor.calls[0]
        assert json.dumps({}) in params
