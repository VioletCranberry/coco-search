"""Unit tests for check_deps_staleness function.

Tests verify that dependency staleness checks return the correct
warning types for various states of the dependency data.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from cocosearch.management.stats import check_deps_staleness


class TestDepsStalenessNoDepsTable:
    """Tests for when deps table doesn't exist."""

    def test_no_deps_table_returns_not_extracted(self, mock_db_pool):
        """Returns deps_not_extracted when deps table doesn't exist."""
        pool, cursor, conn = mock_db_pool(results=[(False,)])

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            warnings = check_deps_staleness("myindex")

        assert len(warnings) == 1
        assert warnings[0]["type"] == "deps_not_extracted"
        assert "not extracted" in warnings[0]["warning"].lower()


class TestDepsStalenessNullTimestamp:
    """Tests for when deps_extracted_at is NULL."""

    def test_null_deps_extracted_at_returns_not_extracted(self, mock_db_pool):
        """Returns deps_not_extracted when timestamp is NULL."""
        # First query: deps table exists
        pool, cursor, conn = mock_db_pool(results=[(True,)])

        metadata = {
            "index_name": "myindex",
            "canonical_path": "/path",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "status": "indexed",
            "branch": None,
            "commit_hash": None,
            "branch_commit_count": None,
            "embedding_provider": None,
            "embedding_model": None,
            "deps_extracted_at": None,
        }

        with (
            patch("cocosearch.management.stats.get_connection_pool", return_value=pool),
            patch(
                "cocosearch.management.stats.get_index_metadata",
                return_value=metadata,
            ),
        ):
            warnings = check_deps_staleness("myindex")

        assert len(warnings) == 1
        assert warnings[0]["type"] == "deps_not_extracted"


class TestDepsStalenessOutdated:
    """Tests for when index was updated after deps extraction."""

    def test_deps_older_than_index_returns_outdated(self, mock_db_pool):
        """Returns deps_outdated when deps_extracted_at < updated_at."""
        pool, cursor, conn = mock_db_pool(results=[(True,)])

        now = datetime.now(timezone.utc)
        metadata = {
            "index_name": "myindex",
            "canonical_path": "/path",
            "created_at": now - timedelta(hours=2),
            "updated_at": now,  # Index updated recently
            "status": "indexed",
            "branch": "main",
            "commit_hash": "abc123",
            "branch_commit_count": None,
            "embedding_provider": None,
            "embedding_model": None,
            "deps_extracted_at": now - timedelta(hours=1),  # Deps older
        }

        with (
            patch("cocosearch.management.stats.get_connection_pool", return_value=pool),
            patch(
                "cocosearch.management.stats.get_index_metadata",
                return_value=metadata,
            ),
            patch(
                "cocosearch.management.stats.check_branch_staleness",
                return_value={
                    "branch_changed": False,
                    "commits_changed": False,
                },
            ),
        ):
            warnings = check_deps_staleness("myindex")

        assert len(warnings) == 1
        assert warnings[0]["type"] == "deps_outdated"
        assert "re-indexed" in warnings[0]["message"].lower()


class TestDepsStalenessFresh:
    """Tests for when deps are fresh."""

    def test_fresh_deps_returns_empty(self, mock_db_pool):
        """Returns empty list when deps are up to date."""
        pool, cursor, conn = mock_db_pool(results=[(True,)])

        now = datetime.now(timezone.utc)
        metadata = {
            "index_name": "myindex",
            "canonical_path": "/path",
            "created_at": now - timedelta(hours=2),
            "updated_at": now - timedelta(hours=1),  # Index older
            "status": "indexed",
            "branch": "main",
            "commit_hash": "abc123",
            "branch_commit_count": None,
            "embedding_provider": None,
            "embedding_model": None,
            "deps_extracted_at": now,  # Deps newer
        }

        with (
            patch("cocosearch.management.stats.get_connection_pool", return_value=pool),
            patch(
                "cocosearch.management.stats.get_index_metadata",
                return_value=metadata,
            ),
            patch(
                "cocosearch.management.stats.check_branch_staleness",
                return_value={
                    "branch_changed": False,
                    "commits_changed": False,
                },
            ),
        ):
            warnings = check_deps_staleness("myindex")

        assert warnings == []


class TestDepsStalenessBranchDrift:
    """Tests for branch/commit drift detection."""

    def test_branch_changed_returns_drift_warning(self, mock_db_pool):
        """Returns deps_branch_drift when branch has changed."""
        pool, cursor, conn = mock_db_pool(results=[(True,)])

        now = datetime.now(timezone.utc)
        metadata = {
            "index_name": "myindex",
            "canonical_path": "/path",
            "created_at": now - timedelta(hours=2),
            "updated_at": now - timedelta(hours=1),
            "status": "indexed",
            "branch": "main",
            "commit_hash": "abc123",
            "branch_commit_count": None,
            "embedding_provider": None,
            "embedding_model": None,
            "deps_extracted_at": now,  # Fresh
        }

        with (
            patch("cocosearch.management.stats.get_connection_pool", return_value=pool),
            patch(
                "cocosearch.management.stats.get_index_metadata",
                return_value=metadata,
            ),
            patch(
                "cocosearch.management.stats.check_branch_staleness",
                return_value={
                    "branch_changed": True,
                    "commits_changed": True,
                },
            ),
        ):
            warnings = check_deps_staleness("myindex")

        assert len(warnings) == 1
        assert warnings[0]["type"] == "deps_branch_drift"


class TestDepsStalenessDbError:
    """Tests for error handling."""

    def test_db_error_returns_empty(self):
        """Returns empty list on database error."""
        with patch(
            "cocosearch.management.stats.get_connection_pool",
            side_effect=Exception("connection failed"),
        ):
            warnings = check_deps_staleness("myindex")

        assert warnings == []

    def test_no_metadata_returns_empty(self, mock_db_pool):
        """Returns empty list when metadata is None (table exists but no row)."""
        pool, cursor, conn = mock_db_pool(results=[(True,)])

        with (
            patch("cocosearch.management.stats.get_connection_pool", return_value=pool),
            patch(
                "cocosearch.management.stats.get_index_metadata",
                return_value=None,
            ),
        ):
            warnings = check_deps_staleness("myindex")

        assert warnings == []
