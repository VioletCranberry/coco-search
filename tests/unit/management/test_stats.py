"""Tests for index statistics module.

Tests format_bytes helper and get_stats function using mock database pool.
"""

from datetime import datetime, timezone
import pytest
from unittest.mock import patch

from cocosearch.management.stats import (
    IndexStats,
    check_staleness,
    collect_warnings,
    format_bytes,
    get_comprehensive_stats,
    get_grammar_failures,
    get_grammar_stats,
    get_parse_failures,
    get_parse_stats,
    get_stats,
    get_symbol_stats,
)


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


class TestIndexStats:
    """Tests for IndexStats dataclass."""

    def test_instantiation_with_all_fields(self):
        """Can create IndexStats with all required fields."""
        now = datetime.now(timezone.utc)
        stats = IndexStats(
            name="test",
            file_count=10,
            chunk_count=50,
            storage_size=1024,
            storage_size_pretty="1.0 KB",
            created_at=now,
            updated_at=now,
            is_stale=False,
            staleness_days=1,
            languages=[{"language": "python", "file_count": 10, "chunk_count": 50}],
            symbols={"function": 25},
            warnings=[],
            parse_stats={},
            source_path="/path/to/project",
            status="indexed",
            indexing_elapsed_seconds=None,
            repo_url=None,
        )
        assert stats.name == "test"
        assert stats.file_count == 10
        assert stats.chunk_count == 50
        assert stats.storage_size == 1024
        assert stats.storage_size_pretty == "1.0 KB"
        assert stats.created_at == now
        assert stats.updated_at == now
        assert stats.is_stale is False
        assert stats.staleness_days == 1
        assert stats.languages == [
            {"language": "python", "file_count": 10, "chunk_count": 50}
        ]
        assert stats.symbols == {"function": 25}
        assert stats.warnings == []
        assert stats.parse_stats == {}
        assert stats.source_path == "/path/to/project"
        assert stats.status == "indexed"

    def test_to_dict_serialization(self):
        """to_dict() returns dictionary suitable for JSON serialization."""
        now = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        stats = IndexStats(
            name="test",
            file_count=10,
            chunk_count=50,
            storage_size=1024,
            storage_size_pretty="1.0 KB",
            created_at=now,
            updated_at=now,
            is_stale=False,
            staleness_days=1,
            languages=[],
            symbols={},
            warnings=[],
            parse_stats={},
            source_path="/path/to/project",
            status="indexed",
            indexing_elapsed_seconds=None,
            repo_url=None,
        )
        result = stats.to_dict()
        assert result["name"] == "test"
        assert result["created_at"] == "2026-01-15T12:00:00+00:00"
        assert result["updated_at"] == "2026-01-15T12:00:00+00:00"
        assert result["source_path"] == "/path/to/project"
        assert result["status"] == "indexed"

    def test_to_dict_with_none_datetimes(self):
        """to_dict() handles None datetime fields."""
        stats = IndexStats(
            name="test",
            file_count=10,
            chunk_count=50,
            storage_size=1024,
            storage_size_pretty="1.0 KB",
            created_at=None,
            updated_at=None,
            is_stale=True,
            staleness_days=-1,
            languages=[],
            symbols={},
            warnings=["No metadata found"],
            parse_stats={},
            source_path=None,
            status=None,
            indexing_elapsed_seconds=None,
            repo_url=None,
        )
        result = stats.to_dict()
        assert result["created_at"] is None
        assert result["updated_at"] is None
        assert result["source_path"] is None
        assert result["status"] is None


class TestCheckStaleness:
    """Tests for check_staleness function."""

    def test_returns_stale_for_old_index(self, mock_db_pool):
        """Returns (True, days) for index older than threshold."""
        # 10 days ago
        from datetime import timedelta

        old_date = datetime.now(timezone.utc) - timedelta(days=10)

        pool, cursor, conn = mock_db_pool(results=[(old_date,)])

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            is_stale, days = check_staleness("myproject", threshold_days=7)

        assert is_stale is True
        assert days == 10

    def test_returns_not_stale_for_recent_index(self, mock_db_pool):
        """Returns (False, days) for index updated within threshold."""
        # 2 days ago
        from datetime import timedelta

        recent_date = datetime.now(timezone.utc) - timedelta(days=2)

        pool, cursor, conn = mock_db_pool(results=[(recent_date,)])

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            is_stale, days = check_staleness("myproject", threshold_days=7)

        assert is_stale is False
        assert days == 2

    def test_threshold_boundary(self, mock_db_pool):
        """7 days exactly is considered stale with threshold=7."""
        from datetime import timedelta

        boundary_date = datetime.now(timezone.utc) - timedelta(days=7)

        pool, cursor, conn = mock_db_pool(results=[(boundary_date,)])

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            is_stale, days = check_staleness("myproject", threshold_days=7)

        assert is_stale is True
        assert days == 7

    def test_missing_metadata(self, mock_db_pool):
        """Returns (True, -1) when metadata doesn't exist."""
        pool, cursor, conn = mock_db_pool(results=[None])  # fetchone returns None

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            is_stale, days = check_staleness("myproject")

        assert is_stale is True
        assert days == -1

    def test_null_updated_at(self, mock_db_pool):
        """Returns (True, -1) when updated_at is NULL."""
        pool, cursor, conn = mock_db_pool(results=[(None,)])

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            is_stale, days = check_staleness("myproject")

        assert is_stale is True
        assert days == -1


class TestGetSymbolStats:
    """Tests for get_symbol_stats function."""

    def test_returns_symbol_counts(self, mock_db_pool):
        """Returns dict mapping symbol types to counts."""
        # Results in order:
        # 1. Column check returns symbol_type exists (fetchone)
        # 2-4. Symbol stats query returns counts (fetchall returns remaining results)
        pool, cursor, conn = mock_db_pool(
            results=[
                ("symbol_type",),  # Column exists (consumed by fetchone)
                ("function", 150),  # First symbol count row
                ("class", 25),  # Second symbol count row
                ("method", 80),  # Third symbol count row
            ]
        )

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            with patch(
                "cocosearch.management.stats.get_table_name",
                return_value="codeindex_test__test_chunks",
            ):
                symbols = get_symbol_stats("test")

        assert symbols == {"function": 150, "class": 25, "method": 80}

    def test_graceful_degradation_without_symbol_column(self, mock_db_pool):
        """Returns empty dict when symbol_type column doesn't exist."""
        pool, cursor, conn = mock_db_pool(results=[None])  # Column doesn't exist

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            with patch(
                "cocosearch.management.stats.get_table_name",
                return_value="codeindex_test__test_chunks",
            ):
                symbols = get_symbol_stats("test")

        assert symbols == {}

    def test_empty_result_handling(self, mock_db_pool):
        """Returns empty dict when no symbols exist."""
        pool, cursor, conn = mock_db_pool(
            results=[
                ("symbol_type",),  # Column exists (consumed by fetchone)
                # No more results - fetchall will return empty list
            ]
        )

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            with patch(
                "cocosearch.management.stats.get_table_name",
                return_value="codeindex_test__test_chunks",
            ):
                symbols = get_symbol_stats("test")

        assert symbols == {}


class TestCollectWarnings:
    """Tests for collect_warnings function."""

    def test_stale_index_warning(self, mock_db_pool):
        """Generates staleness warning for stale index."""
        pool, cursor, conn = mock_db_pool(results=[(100,), (100,)])  # file counts

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            with patch(
                "cocosearch.management.stats.get_table_name",
                return_value="codeindex_test__test_chunks",
            ):
                warnings = collect_warnings("test", is_stale=True, staleness_days=10)

        assert len(warnings) == 1
        assert "10 days since last update" in warnings[0]

    def test_missing_metadata_warning(self, mock_db_pool):
        """Generates warning when metadata is missing."""
        pool, cursor, conn = mock_db_pool(results=[(100,), (100,)])

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            with patch(
                "cocosearch.management.stats.get_table_name",
                return_value="codeindex_test__test_chunks",
            ):
                warnings = collect_warnings("test", is_stale=True, staleness_days=-1)

        assert len(warnings) == 1
        assert "No metadata found" in warnings[0]

    def test_no_warnings_for_fresh_index(self, mock_db_pool):
        """Returns empty list for fresh index."""
        pool, cursor, conn = mock_db_pool(results=[(100,), (100,)])

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            with patch(
                "cocosearch.management.stats.get_table_name",
                return_value="codeindex_test__test_chunks",
            ):
                warnings = collect_warnings("test", is_stale=False, staleness_days=1)

        assert warnings == []


class TestGetParseStats:
    """Tests for get_parse_stats function."""

    def test_returns_aggregated_stats(self, mock_db_pool):
        """Returns per-language breakdown with correct structure."""
        pool, cursor, conn = mock_db_pool(
            results=[
                (True,),  # Table exists
                ("python", "ok", 100),
                ("python", "partial", 5),
                ("python", "error", 2),
                ("javascript", "ok", 50),
            ]
        )

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            stats = get_parse_stats("test")

        assert "by_language" in stats
        assert "python" in stats["by_language"]
        assert stats["by_language"]["python"]["ok"] == 100
        assert stats["by_language"]["python"]["partial"] == 5
        assert stats["by_language"]["python"]["error"] == 2
        assert stats["by_language"]["javascript"]["ok"] == 50
        assert stats["total_files"] == 157
        assert stats["total_ok"] == 150
        assert stats["parse_health_pct"] == round(150 / 157 * 100, 1)

    def test_returns_empty_for_missing_table(self, mock_db_pool):
        """Returns empty dict when parse_results table doesn't exist."""
        pool, cursor, conn = mock_db_pool(results=[(False,)])  # Table doesn't exist

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            stats = get_parse_stats("old_index")

        assert stats == {}

    def test_returns_100_percent_for_all_ok(self, mock_db_pool):
        """Returns 100% health when all files parse ok."""
        pool, cursor, conn = mock_db_pool(
            results=[
                (True,),  # Table exists
                ("python", "ok", 50),
            ]
        )

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            stats = get_parse_stats("test")

        assert stats["parse_health_pct"] == 100.0

    def test_returns_100_percent_for_empty_table(self, mock_db_pool):
        """Returns 100% health when no files are tracked."""
        pool, cursor, conn = mock_db_pool(
            results=[
                (True,),  # Table exists
                # No rows from aggregation
            ]
        )

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            stats = get_parse_stats("test")

        assert stats["parse_health_pct"] == 100.0
        assert stats["total_files"] == 0


class TestGetParseFailures:
    """Tests for get_parse_failures function."""

    def test_returns_failure_details(self, mock_db_pool):
        """Returns list of failure dicts for non-ok files."""
        pool, cursor, conn = mock_db_pool(
            results=[
                (True,),  # Table exists
                ("src/broken.py", "python", "error", "SyntaxError"),
                ("src/partial.js", "javascript", "partial", "ERROR nodes at lines: 5"),
            ]
        )

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            failures = get_parse_failures("test")

        assert len(failures) == 2
        assert failures[0]["file_path"] == "src/broken.py"
        assert failures[0]["parse_status"] == "error"
        assert failures[1]["parse_status"] == "partial"

    def test_returns_empty_for_missing_table(self, mock_db_pool):
        """Returns empty list when table doesn't exist."""
        pool, cursor, conn = mock_db_pool(results=[(False,)])

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            failures = get_parse_failures("old_index")

        assert failures == []

    def test_excludes_grammar_handled_languages(self, mock_db_pool):
        """Grammar-handled languages (docker-compose, etc.) are filtered out."""
        pool, cursor, conn = mock_db_pool(
            results=[
                (True,),  # Table exists
                ("docker-compose.yml", "docker-compose", "no_grammar", None),
                ("src/broken.py", "python", "error", "SyntaxError"),
            ]
        )

        class MockGrammar:
            GRAMMAR_NAME = "docker-compose"

        with (
            patch(
                "cocosearch.management.stats.get_connection_pool",
                return_value=pool,
            ),
            patch(
                "cocosearch.handlers.get_registered_grammars",
                return_value=[MockGrammar()],
            ),
        ):
            failures = get_parse_failures("test")

        assert len(failures) == 1
        assert failures[0]["file_path"] == "src/broken.py"


class TestIndexStatsWithParseStats:
    """Tests for IndexStats with parse_stats field."""

    def test_to_dict_includes_parse_stats(self):
        """to_dict() includes parse_stats in output."""
        stats = IndexStats(
            name="test",
            file_count=10,
            chunk_count=50,
            storage_size=1024,
            storage_size_pretty="1.0 KB",
            created_at=None,
            updated_at=None,
            is_stale=False,
            staleness_days=0,
            languages=[],
            symbols={},
            warnings=[],
            parse_stats={
                "by_language": {
                    "python": {
                        "files": 10,
                        "ok": 9,
                        "partial": 1,
                        "error": 0,
                        "no_grammar": 0,
                    }
                },
                "parse_health_pct": 90.0,
                "total_files": 10,
                "total_ok": 9,
            },
            source_path=None,
            status=None,
            indexing_elapsed_seconds=None,
            repo_url=None,
        )
        d = stats.to_dict()
        assert "parse_stats" in d
        assert d["parse_stats"]["parse_health_pct"] == 90.0

    def test_to_dict_with_empty_parse_stats(self):
        """to_dict() handles empty parse_stats (pre-v46 indexes)."""
        stats = IndexStats(
            name="test",
            file_count=10,
            chunk_count=50,
            storage_size=1024,
            storage_size_pretty="1.0 KB",
            created_at=None,
            updated_at=None,
            is_stale=False,
            staleness_days=0,
            languages=[],
            symbols={},
            warnings=[],
            parse_stats={},
            source_path=None,
            status=None,
            indexing_elapsed_seconds=None,
            repo_url=None,
        )
        d = stats.to_dict()
        assert d["parse_stats"] == {}


class TestGetGrammarStats:
    """Tests for get_grammar_stats function."""

    def _make_mock_grammar(self, name, base):
        """Create a mock grammar handler object."""

        class MockGrammar:
            GRAMMAR_NAME = name
            BASE_LANGUAGE = base

        return MockGrammar()

    def test_returns_grammar_stats(self, mock_db_pool):
        """Returns per-grammar stats with recognition percentage."""
        pool, cursor, conn = mock_db_pool(
            results=[
                ("docker-compose", 5, 20, 18, 2),
                ("github-actions", 3, 12, 10, 2),
            ]
        )

        grammars = [
            self._make_mock_grammar("docker-compose", "yaml"),
            self._make_mock_grammar("github-actions", "yaml"),
        ]

        with (
            patch(
                "cocosearch.management.stats.get_connection_pool",
                return_value=pool,
            ),
            patch(
                "cocosearch.management.stats.get_table_name",
                return_value="codeindex_test__test_chunks",
            ),
            patch(
                "cocosearch.handlers.get_registered_grammars",
                return_value=grammars,
            ),
        ):
            result = get_grammar_stats("test")

        assert len(result) == 2
        assert result[0]["grammar_name"] == "docker-compose"
        assert result[0]["base_language"] == "yaml"
        assert result[0]["file_count"] == 5
        assert result[0]["chunk_count"] == 20
        assert result[0]["recognized_chunks"] == 18
        assert result[0]["unrecognized_chunks"] == 2
        assert result[0]["recognition_pct"] == 90.0

    def test_returns_empty_for_no_grammars(self):
        """Returns empty list when no grammar handlers are registered."""
        with patch(
            "cocosearch.handlers.get_registered_grammars",
            return_value=[],
        ):
            result = get_grammar_stats("test")

        assert result == []

    def test_handles_zero_chunks(self, mock_db_pool):
        """Handles grammar with zero chunks (recognition_pct = 0.0)."""
        pool, cursor, conn = mock_db_pool(
            results=[
                ("docker-compose", 1, 0, 0, 0),
            ]
        )

        grammars = [self._make_mock_grammar("docker-compose", "yaml")]

        with (
            patch(
                "cocosearch.management.stats.get_connection_pool",
                return_value=pool,
            ),
            patch(
                "cocosearch.management.stats.get_table_name",
                return_value="codeindex_test__test_chunks",
            ),
            patch(
                "cocosearch.handlers.get_registered_grammars",
                return_value=grammars,
            ),
        ):
            result = get_grammar_stats("test")

        assert len(result) == 1
        assert result[0]["recognition_pct"] == 0.0

    def test_calculates_recognition_pct(self, mock_db_pool):
        """Correctly calculates recognition percentage."""
        pool, cursor, conn = mock_db_pool(
            results=[
                ("github-actions", 2, 10, 7, 3),
            ]
        )

        grammars = [self._make_mock_grammar("github-actions", "yaml")]

        with (
            patch(
                "cocosearch.management.stats.get_connection_pool",
                return_value=pool,
            ),
            patch(
                "cocosearch.management.stats.get_table_name",
                return_value="codeindex_test__test_chunks",
            ),
            patch(
                "cocosearch.handlers.get_registered_grammars",
                return_value=grammars,
            ),
        ):
            result = get_grammar_stats("test")

        assert result[0]["recognition_pct"] == 70.0


class TestGetGrammarFailures:
    """Tests for get_grammar_failures function."""

    def _make_mock_grammar(self, name, base):
        """Create a mock grammar handler object."""

        class MockGrammar:
            GRAMMAR_NAME = name
            BASE_LANGUAGE = base

        return MockGrammar()

    def test_returns_failures_grouped_by_grammar(self, mock_db_pool):
        """Returns per-file failure data grouped by grammar name."""
        pool, cursor, conn = mock_db_pool(
            results=[
                ("docker-compose", "docker-compose.yml", 5, 2),
                ("docker-compose", "docker-compose.prod.yml", 3, 1),
                ("github-actions", ".github/workflows/ci.yml", 8, 3),
            ]
        )

        grammars = [
            self._make_mock_grammar("docker-compose", "yaml"),
            self._make_mock_grammar("github-actions", "yaml"),
        ]

        with (
            patch(
                "cocosearch.management.stats.get_connection_pool",
                return_value=pool,
            ),
            patch(
                "cocosearch.management.stats.get_table_name",
                return_value="codeindex_test__test_chunks",
            ),
            patch(
                "cocosearch.handlers.get_registered_grammars",
                return_value=grammars,
            ),
        ):
            result = get_grammar_failures("test")

        assert len(result) == 3
        assert result[0]["grammar_name"] == "docker-compose"
        assert result[0]["file_path"] == "docker-compose.yml"
        assert result[0]["total_chunks"] == 5
        assert result[0]["unrecognized_chunks"] == 2
        assert result[2]["grammar_name"] == "github-actions"
        assert result[2]["file_path"] == ".github/workflows/ci.yml"

    def test_returns_empty_for_no_grammars(self):
        """Returns empty list when no grammar handlers are registered."""
        with patch(
            "cocosearch.handlers.get_registered_grammars",
            return_value=[],
        ):
            result = get_grammar_failures("test")

        assert result == []

    def test_returns_empty_when_no_failures(self, mock_db_pool):
        """Returns empty list when query returns no rows."""
        pool, cursor, conn = mock_db_pool(
            results=[]  # No rows — all files fully recognized
        )

        grammars = [self._make_mock_grammar("docker-compose", "yaml")]

        with (
            patch(
                "cocosearch.management.stats.get_connection_pool",
                return_value=pool,
            ),
            patch(
                "cocosearch.management.stats.get_table_name",
                return_value="codeindex_test__test_chunks",
            ),
            patch(
                "cocosearch.handlers.get_registered_grammars",
                return_value=grammars,
            ),
        ):
            result = get_grammar_failures("test")

        assert result == []


class TestIndexStatsGrammarsField:
    """Tests for IndexStats grammars field."""

    def test_default_grammars_is_empty_list(self):
        """grammars field defaults to empty list."""
        stats = IndexStats(
            name="test",
            file_count=10,
            chunk_count=50,
            storage_size=1024,
            storage_size_pretty="1.0 KB",
            created_at=None,
            updated_at=None,
            is_stale=False,
            staleness_days=0,
            languages=[],
            symbols={},
            warnings=[],
            parse_stats={},
            source_path=None,
            status=None,
            indexing_elapsed_seconds=None,
            repo_url=None,
        )
        assert stats.grammars == []

    def test_to_dict_includes_grammars(self):
        """to_dict() includes grammars in output."""
        grammar_data = [
            {
                "grammar_name": "docker-compose",
                "base_language": "yaml",
                "file_count": 3,
                "chunk_count": 15,
                "recognized_chunks": 12,
                "unrecognized_chunks": 3,
                "recognition_pct": 80.0,
            }
        ]
        stats = IndexStats(
            name="test",
            file_count=10,
            chunk_count=50,
            storage_size=1024,
            storage_size_pretty="1.0 KB",
            created_at=None,
            updated_at=None,
            is_stale=False,
            staleness_days=0,
            languages=[],
            symbols={},
            warnings=[],
            parse_stats={},
            source_path=None,
            status=None,
            indexing_elapsed_seconds=None,
            repo_url=None,
            grammars=grammar_data,
        )
        d = stats.to_dict()
        assert d["grammars"] == grammar_data


class TestComprehensiveStatsAutoRecovery:
    """Tests that get_comprehensive_stats triggers auto-recovery of stale indexing."""

    def test_calls_auto_recover_before_reading_metadata(self):
        """get_comprehensive_stats calls auto_recover_stale_indexing."""
        with (
            patch("cocosearch.management.stats.get_stats") as mock_stats,
            patch("cocosearch.management.stats.get_language_stats", return_value=[]),
            patch("cocosearch.management.stats.get_symbol_stats", return_value={}),
            patch("cocosearch.management.stats.get_parse_stats", return_value={}),
            patch("cocosearch.management.stats.get_grammar_stats", return_value=[]),
            patch(
                "cocosearch.management.stats.check_staleness", return_value=(False, 0)
            ),
            patch(
                "cocosearch.management.stats.get_index_metadata",
                return_value={
                    "index_name": "test",
                    "canonical_path": "/path",
                    "created_at": None,
                    "updated_at": None,
                    "status": "indexed",
                },
            ),
            patch(
                "cocosearch.management.stats.auto_recover_stale_indexing"
            ) as mock_recover,
            patch("cocosearch.management.stats.collect_warnings", return_value=[]),
            patch("cocosearch.management.git.get_repo_url", return_value=None),
        ):
            mock_stats.return_value = {
                "name": "test",
                "file_count": 10,
                "chunk_count": 50,
                "storage_size": 1024,
                "storage_size_pretty": "1.0 KB",
            }
            result = get_comprehensive_stats("test")

        mock_recover.assert_called_once_with("test")
        assert result.status == "indexed"
