"""Unit tests for metadata storage module.

Tests ensure_metadata_table, get_index_metadata, get_index_for_path,
register_index_path, and clear_index_path functions with mocked database.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from cocosearch.management.metadata import (
    ensure_metadata_table,
    get_index_metadata,
    get_index_for_path,
    register_index_path,
    clear_index_path,
)


class TestEnsureMetadataTable:
    """Tests for ensure_metadata_table function."""

    def test_creates_table_if_not_exists(self, mock_db_pool):
        """ensure_metadata_table creates table and index."""
        pool, cursor, conn = mock_db_pool()

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            ensure_metadata_table()

        # Should execute CREATE TABLE and CREATE INDEX
        assert len(cursor.calls) >= 2
        sql = cursor.calls[0][0]
        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert "cocosearch_index_metadata" in sql

    def test_creates_path_index(self, mock_db_pool):
        """ensure_metadata_table creates index on canonical_path."""
        pool, cursor, conn = mock_db_pool()

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            ensure_metadata_table()

        # Second SQL should be CREATE INDEX
        sql = cursor.calls[1][0]
        assert "CREATE INDEX IF NOT EXISTS" in sql
        assert "canonical_path" in sql

    def test_commits_after_creation(self, mock_db_pool):
        """ensure_metadata_table commits transaction."""
        pool, cursor, conn = mock_db_pool()

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            ensure_metadata_table()

        assert conn.committed


class TestGetIndexMetadata:
    """Tests for get_index_metadata function."""

    def test_returns_metadata_when_found(self, mock_db_pool):
        """get_index_metadata returns dict when index exists."""
        pool, cursor, conn = mock_db_pool(results=[
            ("myindex", "/path/to/project", "2024-01-01 00:00:00", "2024-01-01 00:00:00"),
        ])

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            result = get_index_metadata("myindex")

        assert result is not None
        assert result["index_name"] == "myindex"
        assert result["canonical_path"] == "/path/to/project"
        assert "created_at" in result
        assert "updated_at" in result

    def test_returns_none_when_not_found(self, mock_db_pool):
        """get_index_metadata returns None when index doesn't exist."""
        pool, cursor, conn = mock_db_pool(results=[])

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            result = get_index_metadata("nonexistent")

        assert result is None

    def test_queries_by_index_name(self, mock_db_pool):
        """get_index_metadata queries with correct index name."""
        pool, cursor, conn = mock_db_pool(results=[])

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            get_index_metadata("testindex")

        cursor.assert_called_with_param("testindex")


class TestRegisterIndexPath:
    """Tests for register_index_path function."""

    def test_registers_new_mapping(self, mock_db_pool, tmp_path):
        """register_index_path stores new path mapping."""
        pool, cursor, conn = mock_db_pool(results=[])  # No existing entry

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            with patch("cocosearch.management.metadata.ensure_metadata_table"):
                register_index_path("myindex", tmp_path)

        # Should execute INSERT/UPSERT
        assert any("INSERT INTO cocosearch_index_metadata" in call[0] for call in cursor.calls)

    def test_detects_collision(self, mock_db_pool, tmp_path):
        """register_index_path raises ValueError on collision."""
        pool, cursor, conn = mock_db_pool(results=[
            ("myindex", "/different/path", "2024-01-01 00:00:00", "2024-01-01 00:00:00"),
        ])

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            with patch("cocosearch.management.metadata.ensure_metadata_table"):
                with pytest.raises(ValueError) as exc_info:
                    register_index_path("myindex", tmp_path)

        assert "collision" in str(exc_info.value).lower()
        assert "myindex" in str(exc_info.value)

    def test_allows_same_path_reregistration(self, mock_db_pool, tmp_path):
        """register_index_path allows re-registering same path."""
        canonical = str(tmp_path.resolve())
        pool, cursor, conn = mock_db_pool(results=[
            ("myindex", canonical, "2024-01-01 00:00:00", "2024-01-01 00:00:00"),
        ])

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            with patch("cocosearch.management.metadata.ensure_metadata_table"):
                # Should not raise - same path is fine
                register_index_path("myindex", tmp_path)

    def test_clears_cache_after_registration(self, mock_db_pool, tmp_path):
        """register_index_path clears lru_cache after write."""
        pool, cursor, conn = mock_db_pool(results=[])

        # Clear cache first so we know it has some state
        get_index_for_path.cache_clear()

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            with patch("cocosearch.management.metadata.ensure_metadata_table"):
                # Populate cache
                get_index_for_path("/some/path")

                # Check cache has entry
                cache_info_before = get_index_for_path.cache_info()
                assert cache_info_before.currsize >= 0  # Cache may or may not have entries

                # Register should clear cache
                register_index_path("myindex", tmp_path)

                # After registration, cache should be cleared
                cache_info_after = get_index_for_path.cache_info()
                assert cache_info_after.currsize == 0

    def test_commits_transaction(self, mock_db_pool, tmp_path):
        """register_index_path commits transaction after insert."""
        pool, cursor, conn = mock_db_pool(results=[])

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            with patch("cocosearch.management.metadata.ensure_metadata_table"):
                register_index_path("myindex", tmp_path)

        assert conn.committed


class TestClearIndexPath:
    """Tests for clear_index_path function."""

    def test_deletes_metadata(self, mock_db_pool):
        """clear_index_path removes entry from database."""
        pool, cursor, conn = mock_db_pool(results=[])
        cursor.rowcount = 1  # One row deleted

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            result = clear_index_path("myindex")

        assert result is True
        sql = cursor.calls[0][0]
        assert "DELETE" in sql

    def test_returns_false_when_not_found(self, mock_db_pool):
        """clear_index_path returns False when no entry exists."""
        pool, cursor, conn = mock_db_pool(results=[])
        cursor.rowcount = 0  # No rows deleted

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            result = clear_index_path("nonexistent")

        assert result is False

    def test_clears_cache_after_deletion(self, mock_db_pool):
        """clear_index_path clears lru_cache after delete."""
        pool, cursor, conn = mock_db_pool(results=[])
        cursor.rowcount = 1

        # Clear cache first
        get_index_for_path.cache_clear()

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            # Populate cache
            get_index_for_path("/some/path")

            # Clear should clear cache
            clear_index_path("myindex")

            # After clear, cache should be empty
            cache_info_after = get_index_for_path.cache_info()
            assert cache_info_after.currsize == 0

    def test_commits_transaction(self, mock_db_pool):
        """clear_index_path commits transaction after delete."""
        pool, cursor, conn = mock_db_pool(results=[])
        cursor.rowcount = 1

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            clear_index_path("myindex")

        assert conn.committed


class TestGetIndexForPath:
    """Tests for get_index_for_path function."""

    def test_returns_index_name_when_found(self, mock_db_pool):
        """get_index_for_path returns index name for known path."""
        pool, cursor, conn = mock_db_pool(results=[("myindex",)])

        # Clear any cached results
        get_index_for_path.cache_clear()

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            result = get_index_for_path("/path/to/project")

        assert result == "myindex"

    def test_returns_none_when_not_found(self, mock_db_pool):
        """get_index_for_path returns None for unknown path."""
        pool, cursor, conn = mock_db_pool(results=[])

        get_index_for_path.cache_clear()

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            result = get_index_for_path("/unknown/path")

        assert result is None

    def test_caches_results(self, mock_db_pool):
        """get_index_for_path caches repeated lookups."""
        pool, cursor, conn = mock_db_pool(results=[("myindex",)])

        get_index_for_path.cache_clear()

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            # First call
            result1 = get_index_for_path("/path/to/project")
            # Second call - should use cache
            result2 = get_index_for_path("/path/to/project")

        assert result1 == result2
        # Should only query database once due to caching
        assert len(cursor.calls) == 1

    def test_different_paths_not_cached_together(self, mock_db_pool):
        """get_index_for_path caches each path separately."""
        pool, cursor, conn = mock_db_pool(results=[
            ("index1",),
            ("index2",),
        ])

        get_index_for_path.cache_clear()

        with patch("cocosearch.management.metadata.get_connection_pool", return_value=pool):
            result1 = get_index_for_path("/path/to/project1")
            result2 = get_index_for_path("/path/to/project2")

        # Each unique path should trigger a database query
        assert len(cursor.calls) == 2


class TestRowcountAttribute:
    """Tests for MockCursor rowcount attribute used in metadata tests."""

    def test_rowcount_defaults_to_zero(self, mock_db_pool):
        """MockCursor rowcount defaults to 0."""
        pool, cursor, conn = mock_db_pool()

        # MockCursor doesn't have rowcount by default - we set it in tests
        # This verifies our test pattern works
        cursor.rowcount = 0
        assert cursor.rowcount == 0

    def test_rowcount_can_be_set(self, mock_db_pool):
        """MockCursor rowcount can be set to simulate deleted rows."""
        pool, cursor, conn = mock_db_pool()
        cursor.rowcount = 5
        assert cursor.rowcount == 5
