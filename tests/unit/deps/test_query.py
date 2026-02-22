"""Tests for cocosearch.deps.query module."""

import json
from unittest.mock import patch

from cocosearch.deps.models import DependencyEdge, DepType
from cocosearch.deps.query import (
    _row_to_edge,
    get_dependencies,
    get_dep_stats,
    get_dependents,
)


class TestRowToEdge:
    """Tests for _row_to_edge()."""

    def test_deserializes_full_row(self):
        """Should convert a DB row tuple into a DependencyEdge."""
        row = (
            "src/main.py",
            "main",
            "src/utils.py",
            "helper",
            "import",
            json.dumps({"line": 5}),
        )

        edge = _row_to_edge(row)

        assert edge == DependencyEdge(
            source_file="src/main.py",
            source_symbol="main",
            target_file="src/utils.py",
            target_symbol="helper",
            dep_type="import",
            metadata={"line": 5},
        )

    def test_handles_dict_metadata_from_psycopg(self):
        """Psycopg auto-deserializes JSONB into dicts — should not double-decode."""
        row = (
            "src/main.py",
            None,
            "src/utils.py",
            None,
            "import",
            {"line": 5},  # dict, not JSON string
        )

        edge = _row_to_edge(row)

        assert edge.metadata == {"line": 5}

    def test_handles_none_metadata(self):
        """None metadata_json should produce an empty dict."""
        row = (
            "src/main.py",
            None,
            "src/utils.py",
            None,
            "call",
            None,
        )

        edge = _row_to_edge(row)

        assert edge.metadata == {}

    def test_handles_none_optional_fields(self):
        """None source_symbol and target_file should be preserved."""
        row = (
            "src/main.py",
            None,
            None,
            "os",
            "import",
            json.dumps({}),
        )

        edge = _row_to_edge(row)

        assert edge.source_symbol is None
        assert edge.target_file is None
        assert edge.target_symbol == "os"


class TestGetDependencies:
    """Tests for get_dependencies() — forward lookup."""

    def test_returns_edges_for_file(self, mock_db_pool):
        """Should return deserialized edges for a given source_file."""
        pool, cursor, conn = mock_db_pool(
            results=[
                (
                    "src/main.py",
                    "main",
                    "src/utils.py",
                    "helper",
                    "import",
                    json.dumps({"line": 1}),
                ),
                (
                    "src/main.py",
                    "main",
                    "src/db.py",
                    "connect",
                    "call",
                    json.dumps({"line": 10}),
                ),
            ]
        )

        with patch(
            "cocosearch.deps.query.get_connection_pool", return_value=pool
        ):
            edges = get_dependencies("myindex", "src/main.py")

        assert len(edges) == 2
        assert edges[0].source_file == "src/main.py"
        assert edges[0].target_file == "src/utils.py"
        assert edges[0].dep_type == "import"
        assert edges[0].metadata == {"line": 1}
        assert edges[1].target_file == "src/db.py"
        assert edges[1].dep_type == "call"

        cursor.assert_query_contains("source_file")
        cursor.assert_query_contains("ORDER BY id")
        cursor.assert_called_with_param("src/main.py")

    def test_filters_by_dep_type(self, mock_db_pool):
        """Should add dep_type filter when specified."""
        pool, cursor, conn = mock_db_pool(results=[])

        with patch(
            "cocosearch.deps.query.get_connection_pool", return_value=pool
        ):
            get_dependencies("myindex", "src/main.py", dep_type=DepType.IMPORT)

        cursor.assert_query_contains("dep_type")
        cursor.assert_called_with_param("import")

    def test_filters_by_symbol(self, mock_db_pool):
        """Should add source_symbol filter when specified."""
        pool, cursor, conn = mock_db_pool(results=[])

        with patch(
            "cocosearch.deps.query.get_connection_pool", return_value=pool
        ):
            get_dependencies("myindex", "src/main.py", symbol="main")

        cursor.assert_query_contains("source_symbol")
        cursor.assert_called_with_param("main")

    def test_returns_empty_list(self, mock_db_pool):
        """Should return an empty list when no edges match."""
        pool, cursor, conn = mock_db_pool(results=[])

        with patch(
            "cocosearch.deps.query.get_connection_pool", return_value=pool
        ):
            edges = get_dependencies("myindex", "src/nonexistent.py")

        assert edges == []

    def test_uses_correct_table_name(self, mock_db_pool):
        """Should query the correct deps table."""
        pool, cursor, conn = mock_db_pool(results=[])

        with patch(
            "cocosearch.deps.query.get_connection_pool", return_value=pool
        ):
            get_dependencies("testidx", "src/main.py")

        cursor.assert_query_contains("cocosearch_deps_testidx")


class TestGetDependents:
    """Tests for get_dependents() — reverse lookup."""

    def test_returns_dependents_for_file(self, mock_db_pool):
        """Should return edges where the file is the target."""
        pool, cursor, conn = mock_db_pool(
            results=[
                (
                    "src/api.py",
                    "handler",
                    "src/utils.py",
                    "helper",
                    "call",
                    json.dumps({"line": 20}),
                ),
            ]
        )

        with patch(
            "cocosearch.deps.query.get_connection_pool", return_value=pool
        ):
            edges = get_dependents("myindex", "src/utils.py")

        assert len(edges) == 1
        assert edges[0].source_file == "src/api.py"
        assert edges[0].target_file == "src/utils.py"
        assert edges[0].dep_type == "call"

        cursor.assert_query_contains("target_file")
        cursor.assert_query_contains("ORDER BY id")
        cursor.assert_called_with_param("src/utils.py")

    def test_filters_by_symbol(self, mock_db_pool):
        """Should add target_symbol filter when specified."""
        pool, cursor, conn = mock_db_pool(results=[])

        with patch(
            "cocosearch.deps.query.get_connection_pool", return_value=pool
        ):
            get_dependents("myindex", "src/utils.py", symbol="helper")

        cursor.assert_query_contains("target_symbol")
        cursor.assert_called_with_param("helper")

    def test_filters_by_dep_type(self, mock_db_pool):
        """Should add dep_type filter when specified."""
        pool, cursor, conn = mock_db_pool(results=[])

        with patch(
            "cocosearch.deps.query.get_connection_pool", return_value=pool
        ):
            get_dependents("myindex", "src/utils.py", dep_type=DepType.CALL)

        cursor.assert_query_contains("dep_type")
        cursor.assert_called_with_param("call")

    def test_returns_empty_list(self, mock_db_pool):
        """Should return an empty list when no dependents exist."""
        pool, cursor, conn = mock_db_pool(results=[])

        with patch(
            "cocosearch.deps.query.get_connection_pool", return_value=pool
        ):
            edges = get_dependents("myindex", "src/orphan.py")

        assert edges == []

    def test_uses_correct_table_name(self, mock_db_pool):
        """Should query the correct deps table."""
        pool, cursor, conn = mock_db_pool(results=[])

        with patch(
            "cocosearch.deps.query.get_connection_pool", return_value=pool
        ):
            get_dependents("testidx", "src/utils.py")

        cursor.assert_query_contains("cocosearch_deps_testidx")


class TestGetDepStats:
    """Tests for get_dep_stats()."""

    def test_returns_total_edges_count(self, mock_db_pool):
        """Should return dict with total_edges from COUNT(*)."""
        pool, cursor, conn = mock_db_pool(results=[(42,)])

        with patch(
            "cocosearch.deps.query.get_connection_pool", return_value=pool
        ):
            stats = get_dep_stats("myindex")

        assert stats == {"total_edges": 42}
        cursor.assert_query_contains("COUNT(*)")
        cursor.assert_query_contains("cocosearch_deps_myindex")

    def test_returns_zero_for_empty_table(self, mock_db_pool):
        """Should return total_edges=0 when table is empty."""
        pool, cursor, conn = mock_db_pool(results=[(0,)])

        with patch(
            "cocosearch.deps.query.get_connection_pool", return_value=pool
        ):
            stats = get_dep_stats("myindex")

        assert stats == {"total_edges": 0}
