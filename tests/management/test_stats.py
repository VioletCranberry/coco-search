"""Tests for index statistics module.

Tests format_bytes helper and get_stats function using mock database pool.
"""

import pytest
from unittest.mock import patch

from cocosearch.management.stats import format_bytes, get_stats


class TestFormatBytes:
    """Tests for format_bytes helper function."""

    def test_formats_bytes(self):
        """Small values show 'X B' format."""
        assert format_bytes(0) == "0 B"
        assert format_bytes(512) == "512 B"
        assert format_bytes(1023) == "1023 B"

    def test_formats_kilobytes(self):
        """Values 1024 to 1MB show 'X.X KB' format."""
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(2048) == "2.0 KB"
        assert format_bytes(1536) == "1.5 KB"
        assert format_bytes(1024 * 500) == "500.0 KB"

    def test_formats_megabytes(self):
        """Values 1MB to 1GB show 'X.X MB' format."""
        assert format_bytes(1024 * 1024) == "1.0 MB"
        assert format_bytes(1024 * 1024 * 2) == "2.0 MB"
        assert format_bytes(1024 * 1024 * 1.5) == "1.5 MB"
        assert format_bytes(1024 * 1024 * 500) == "500.0 MB"

    def test_formats_gigabytes(self):
        """Values 1GB+ show 'X.X GB' format."""
        assert format_bytes(1024 * 1024 * 1024) == "1.0 GB"
        assert format_bytes(1024 * 1024 * 1024 * 2) == "2.0 GB"
        assert format_bytes(1024 * 1024 * 1024 * 1.5) == "1.5 GB"
        assert format_bytes(1024 * 1024 * 1024 * 100) == "100.0 GB"


class TestGetStats:
    """Tests for get_stats function with mocked database."""

    def test_returns_stats_dict(self, mock_db_pool):
        """Returns dict with name, file_count, chunk_count, storage_size."""
        # Results in order:
        # 1. EXISTS check returns True
        # 2. COUNT query returns file_count, chunk_count
        # 3. pg_table_size returns storage_size
        pool, cursor, conn = mock_db_pool(
            results=[
                (True,),  # EXISTS check
                (10, 50),  # file_count, chunk_count
                (1024 * 1024,),  # storage_size (1 MB)
            ]
        )

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            stats = get_stats("myproject")

        assert stats["name"] == "myproject"
        assert stats["file_count"] == 10
        assert stats["chunk_count"] == 50
        assert stats["storage_size"] == 1024 * 1024

    def test_raises_for_nonexistent(self, mock_db_pool):
        """Raises ValueError when index doesn't exist."""
        pool, cursor, conn = mock_db_pool(results=[(False,)])

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            with pytest.raises(ValueError, match="not found"):
                get_stats("nonexistent")

    def test_includes_pretty_size(self, mock_db_pool):
        """Returns storage_size_pretty formatted string."""
        pool, cursor, conn = mock_db_pool(
            results=[
                (True,),
                (5, 25),
                (1024 * 1024 * 2,),  # 2 MB
            ]
        )

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            stats = get_stats("myproject")

        assert "storage_size_pretty" in stats
        assert stats["storage_size_pretty"] == "2.0 MB"

    def test_uses_correct_table_name(self, mock_db_pool):
        """Uses get_table_name to derive table name."""
        pool, cursor, conn = mock_db_pool(
            results=[
                (True,),
                (1, 1),
                (1024,),
            ]
        )

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            with patch(
                "cocosearch.management.stats.get_table_name",
                return_value="codeindex_test__test_chunks",
            ) as mock_table_name:
                get_stats("test")
                mock_table_name.assert_called_once_with("test")

    def test_executes_three_queries(self, mock_db_pool):
        """Executes EXISTS, COUNT, and pg_table_size queries."""
        pool, cursor, conn = mock_db_pool(
            results=[
                (True,),
                (3, 15),
                (2048,),
            ]
        )

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            get_stats("myproject")

        # Should have executed 3 queries
        assert len(cursor.calls) == 3
        cursor.assert_query_contains("EXISTS")
        cursor.assert_query_contains("COUNT")
        cursor.assert_query_contains("pg_table_size")

    def test_handles_zero_files_and_chunks(self, mock_db_pool):
        """Handles empty index with zero counts."""
        pool, cursor, conn = mock_db_pool(
            results=[
                (True,),
                (0, 0),  # Empty index
                (0,),  # Zero bytes
            ]
        )

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            stats = get_stats("emptyindex")

        assert stats["file_count"] == 0
        assert stats["chunk_count"] == 0
        assert stats["storage_size"] == 0
        assert stats["storage_size_pretty"] == "0 B"

    def test_handles_large_storage_sizes(self, mock_db_pool):
        """Formats large storage sizes correctly."""
        pool, cursor, conn = mock_db_pool(
            results=[
                (True,),
                (1000, 50000),
                (1024 * 1024 * 1024 * 5,),  # 5 GB
            ]
        )

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            stats = get_stats("largeindex")

        assert stats["storage_size_pretty"] == "5.0 GB"
