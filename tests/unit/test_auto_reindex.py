"""Unit tests for cocosearch.auto_reindex shared core."""

import threading
from unittest.mock import MagicMock, patch

import pytest

from cocosearch import auto_reindex
from cocosearch.auto_reindex import (
    detect_drift,
    has_deps_table,
    run_reindex_sync,
    trigger_reindex,
)


# ---------------------------------------------------------------------------
# detect_drift
# ---------------------------------------------------------------------------


class TestDetectDrift:
    """Structured drift detection wrapping check_branch_staleness."""

    def test_in_sync_returns_false(self):
        with patch.object(
            auto_reindex,
            "check_branch_staleness",
            return_value={
                "indexed_branch": "main",
                "indexed_commit": "abc1234",
                "current_branch": "main",
                "current_commit": "abc1234",
                "branch_changed": False,
                "commits_changed": False,
            },
        ):
            report = detect_drift("my_index", "/tmp/proj")
        assert report.should_reindex is False
        assert report.reason == "in_sync"
        assert report.indexed_branch == "main"
        assert report.current_branch == "main"

    def test_branch_switch_detected(self):
        with patch.object(
            auto_reindex,
            "check_branch_staleness",
            return_value={
                "indexed_branch": "main",
                "indexed_commit": "abc1234",
                "current_branch": "feature",
                "current_commit": "def5678",
                "branch_changed": True,
                "commits_changed": True,
            },
        ):
            report = detect_drift("my_index", "/tmp/proj")
        assert report.should_reindex is True
        assert report.reason == "branch_changed"

    def test_new_commit_same_branch_detected(self):
        with patch.object(
            auto_reindex,
            "check_branch_staleness",
            return_value={
                "indexed_branch": "main",
                "indexed_commit": "abc1234",
                "current_branch": "main",
                "current_commit": "def5678",
                "branch_changed": False,
                "commits_changed": True,
            },
        ):
            report = detect_drift("my_index", "/tmp/proj")
        assert report.should_reindex is True
        assert report.reason == "commits_changed"

    def test_no_metadata_does_not_trigger(self):
        """If the index has never been registered, don't auto-create."""
        with patch.object(
            auto_reindex,
            "check_branch_staleness",
            return_value={
                "indexed_branch": None,
                "indexed_commit": None,
                "current_branch": "main",
                "current_commit": "abc1234",
                "branch_changed": False,
                "commits_changed": False,
            },
        ):
            report = detect_drift("my_index", "/tmp/proj")
        assert report.should_reindex is False
        assert report.reason == "no_metadata"


# ---------------------------------------------------------------------------
# has_deps_table
# ---------------------------------------------------------------------------


class TestHasDepsTable:
    """Cheap existence check for cocosearch_deps_{index_name}."""

    def test_returns_true_when_table_exists(self, mock_db_pool):
        pool, cursor, _ = mock_db_pool(results=[(True,)])
        with patch.object(auto_reindex, "get_connection_pool", return_value=pool):
            assert has_deps_table("my_index") is True
        cursor.assert_query_contains("information_schema.tables")
        cursor.assert_called_with_param("cocosearch_deps_my_index")

    def test_returns_false_when_table_missing(self, mock_db_pool):
        pool, _, _ = mock_db_pool(results=[(False,)])
        with patch.object(auto_reindex, "get_connection_pool", return_value=pool):
            assert has_deps_table("my_index") is False

    def test_returns_false_on_db_error(self):
        with patch.object(
            auto_reindex,
            "get_connection_pool",
            side_effect=RuntimeError("no db"),
        ):
            assert has_deps_table("my_index") is False

    def test_rejects_invalid_index_name(self):
        # validate_index_name raises → has_deps_table returns False
        assert has_deps_table("bad;name") is False


# ---------------------------------------------------------------------------
# run_reindex_sync
# ---------------------------------------------------------------------------


class TestRunReindexSync:
    """Synchronous in-process reindex used by the watchdog and watch command."""

    def _patch_metadata_refresh(self):
        """Context manager factory patching all post-reindex metadata helpers."""
        # Imports inside run_reindex_sync are lazy, so patch at source modules.
        return (
            patch(
                "cocosearch.management.metadata.ensure_metadata_table",
                return_value=None,
            ),
            patch(
                "cocosearch.management.metadata.register_index_path",
                return_value=None,
            ),
            patch("cocosearch.management.git.get_current_branch", return_value="main"),
            patch("cocosearch.management.git.get_commit_hash", return_value="abc1234"),
            patch("cocosearch.management.git.get_branch_commit_count", return_value=10),
        )

    def test_success_without_deps(self):
        patches = self._patch_metadata_refresh()
        with (
            patch.object(
                auto_reindex, "run_index", return_value=MagicMock()
            ) as mock_run,
            patch.object(auto_reindex, "has_deps_table", return_value=False),
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
        ):
            result = run_reindex_sync("my_index", "/tmp/proj", include_deps=True)
        assert result["success"] is True
        assert result["deps_extracted"] is False
        assert result["error"] is None
        mock_run.assert_called_once()

    def test_success_with_deps(self):
        patches = self._patch_metadata_refresh()
        mock_extract = MagicMock()
        with (
            patch.object(auto_reindex, "run_index", return_value=MagicMock()),
            patch.object(auto_reindex, "has_deps_table", return_value=True),
            patch("cocosearch.deps.extractor.extract_dependencies", mock_extract),
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
        ):
            result = run_reindex_sync("my_index", "/tmp/proj", include_deps=True)
        assert result["success"] is True
        assert result["deps_extracted"] is True
        mock_extract.assert_called_once_with("my_index", "/tmp/proj")

    def test_include_deps_false_skips_extraction(self):
        patches = self._patch_metadata_refresh()
        mock_extract = MagicMock()
        with (
            patch.object(auto_reindex, "run_index", return_value=MagicMock()),
            patch.object(auto_reindex, "has_deps_table", return_value=True),
            patch("cocosearch.deps.extractor.extract_dependencies", mock_extract),
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
        ):
            result = run_reindex_sync("my_index", "/tmp/proj", include_deps=False)
        assert result["success"] is True
        assert result["deps_extracted"] is False
        mock_extract.assert_not_called()

    def test_deps_failure_does_not_fail_reindex(self):
        patches = self._patch_metadata_refresh()
        with (
            patch.object(auto_reindex, "run_index", return_value=MagicMock()),
            patch.object(auto_reindex, "has_deps_table", return_value=True),
            patch(
                "cocosearch.deps.extractor.extract_dependencies",
                side_effect=RuntimeError("deps boom"),
            ),
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
        ):
            result = run_reindex_sync("my_index", "/tmp/proj", include_deps=True)
        # run_index succeeded → success is True, but deps_extracted is False
        assert result["success"] is True
        assert result["deps_extracted"] is False

    def test_run_index_failure_reported(self):
        with patch.object(
            auto_reindex, "run_index", side_effect=RuntimeError("indexing boom")
        ):
            result = run_reindex_sync("my_index", "/tmp/proj")
        assert result["success"] is False
        assert "indexing boom" in result["error"]


# ---------------------------------------------------------------------------
# trigger_reindex
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_module_registry():
    """Ensure trigger_reindex module-level registry is clean between tests."""
    auto_reindex._module_active.clear()
    yield
    auto_reindex._module_active.clear()


class TestTriggerReindex:
    """Threaded trigger with pluggable lock + registry."""

    def _stub_run_reindex_sync(self, started: threading.Event, finish: threading.Event):
        """Returns a stub that blocks until ``finish`` is set."""

        def _stub(index_name, project_path, *, fresh=False, include_deps=True):
            started.set()
            finish.wait(timeout=2.0)
            return {"success": True, "deps_extracted": False, "error": None}

        return _stub

    def test_spawns_daemon_thread(self):
        started = threading.Event()
        finish = threading.Event()
        finish.set()  # let it complete immediately

        with (
            patch.object(
                auto_reindex,
                "run_reindex_sync",
                side_effect=self._stub_run_reindex_sync(started, finish),
            ),
            patch("cocoindex.init", return_value=None),
        ):
            thread = trigger_reindex("my_index", "/tmp/proj")
            assert thread is not None
            assert thread.daemon is True
            thread.join(timeout=2.0)
            assert not thread.is_alive()

    def test_concurrent_trigger_defers(self):
        """Second call while first is running returns None."""
        started = threading.Event()
        finish = threading.Event()

        with (
            patch.object(
                auto_reindex,
                "run_reindex_sync",
                side_effect=self._stub_run_reindex_sync(started, finish),
            ),
            patch("cocoindex.init", return_value=None),
        ):
            first = trigger_reindex("my_index", "/tmp/proj")
            assert first is not None
            assert started.wait(timeout=2.0)

            # First is still running — second call should return None.
            second = trigger_reindex("my_index", "/tmp/proj")
            assert second is None

            finish.set()
            first.join(timeout=2.0)

    def test_uses_custom_lock_and_registry(self):
        """Caller-supplied lock + registry are honored (MCP integration path)."""
        lock = threading.Lock()
        registry: dict = {}
        finish = threading.Event()
        finish.set()

        with (
            patch.object(
                auto_reindex,
                "run_reindex_sync",
                return_value={
                    "success": True,
                    "deps_extracted": False,
                    "error": None,
                },
            ),
            patch("cocoindex.init", return_value=None),
        ):
            thread = trigger_reindex(
                "my_index",
                "/tmp/proj",
                lock=lock,
                active_registry=registry,
            )
            assert thread is not None
            # Registry was populated
            assert "my_index" in registry
            thread.join(timeout=2.0)
            # Cleanup happened
            assert "my_index" not in registry

    def test_on_complete_callback_invoked(self):
        finish = threading.Event()
        finish.set()
        callback_result: list = []

        def _on_complete(result: dict) -> None:
            callback_result.append(result)

        with (
            patch.object(
                auto_reindex,
                "run_reindex_sync",
                return_value={
                    "success": True,
                    "deps_extracted": True,
                    "error": None,
                },
            ),
            patch("cocoindex.init", return_value=None),
        ):
            thread = trigger_reindex(
                "my_index",
                "/tmp/proj",
                on_complete=_on_complete,
            )
            assert thread is not None
            thread.join(timeout=2.0)
        assert len(callback_result) == 1
        assert callback_result[0]["deps_extracted"] is True
