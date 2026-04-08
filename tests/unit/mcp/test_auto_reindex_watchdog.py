"""Unit tests for the MCP server auto-reindex watchdog (Layer 1)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cocosearch.auto_reindex import DriftReport
from cocosearch.mcp import server as srv


@pytest.fixture(autouse=True)
def clear_active_indexing():
    """Ensure the shared _active_indexing dict is empty between tests."""
    srv._active_indexing.clear()
    yield
    srv._active_indexing.clear()


# ---------------------------------------------------------------------------
# _resolve_watchdog_project
# ---------------------------------------------------------------------------


class TestResolveWatchdogProject:
    def test_prefers_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("COCOSEARCH_PROJECT_PATH", str(tmp_path))
        assert srv._resolve_watchdog_project() == tmp_path

    def test_falls_back_to_cwd_when_env_missing(self, monkeypatch):
        monkeypatch.delenv("COCOSEARCH_PROJECT_PATH", raising=False)
        monkeypatch.delenv("COCOSEARCH_PROJECT", raising=False)
        result = srv._resolve_watchdog_project()
        assert result == Path.cwd()

    def test_falls_back_to_cwd_when_env_missing_disk(self, monkeypatch):
        monkeypatch.setenv("COCOSEARCH_PROJECT_PATH", "/does/not/exist/xyz")
        monkeypatch.delenv("COCOSEARCH_PROJECT", raising=False)
        result = srv._resolve_watchdog_project()
        assert result == Path.cwd()


# ---------------------------------------------------------------------------
# _watchdog_tick_once
# ---------------------------------------------------------------------------


class TestWatchdogTickOnce:
    """Single poll of the watchdog — the unit that runs inside the loop."""

    def _no_drift(self) -> DriftReport:
        return DriftReport(
            should_reindex=False,
            reason="in_sync",
            indexed_branch="main",
            indexed_commit="abc1234",
            current_branch="main",
            current_commit="abc1234",
        )

    def _branch_drift(self) -> DriftReport:
        return DriftReport(
            should_reindex=True,
            reason="branch_changed",
            indexed_branch="main",
            indexed_commit="abc1234",
            current_branch="feature",
            current_commit="def5678",
        )

    def test_noop_when_in_sync(self, tmp_path, monkeypatch):
        monkeypatch.setenv("COCOSEARCH_PROJECT_PATH", str(tmp_path))
        (tmp_path / ".git").mkdir()  # make find_project_root resolve here
        with (
            patch(
                "cocosearch.auto_reindex.detect_drift",
                return_value=self._no_drift(),
            ) as mock_detect,
            patch("cocosearch.auto_reindex.trigger_reindex") as mock_trigger,
            patch(
                "cocosearch.management.context.resolve_index_name",
                return_value="my_index",
            ),
        ):
            srv._watchdog_tick_once()

        mock_detect.assert_called_once()
        mock_trigger.assert_not_called()

    def test_triggers_reindex_on_drift(self, tmp_path, monkeypatch):
        monkeypatch.setenv("COCOSEARCH_PROJECT_PATH", str(tmp_path))
        (tmp_path / ".git").mkdir()
        with (
            patch(
                "cocosearch.auto_reindex.detect_drift",
                return_value=self._branch_drift(),
            ),
            patch("cocosearch.auto_reindex.trigger_reindex") as mock_trigger,
            patch(
                "cocosearch.management.context.resolve_index_name",
                return_value="my_index",
            ),
        ):
            srv._watchdog_tick_once()

        mock_trigger.assert_called_once()
        # Passes the shared lock + active registry so /api/reindex coordinates.
        kwargs = mock_trigger.call_args.kwargs
        assert kwargs["lock"] is srv._indexing_lock
        assert kwargs["active_registry"] is srv._active_indexing
        assert kwargs["include_deps"] is True
        assert kwargs["fresh"] is False

    def test_skips_when_indexing_already_active(self, tmp_path, monkeypatch):
        """Concurrent /api/reindex run blocks the watchdog from double-triggering."""
        monkeypatch.setenv("COCOSEARCH_PROJECT_PATH", str(tmp_path))
        (tmp_path / ".git").mkdir()

        fake_thread = MagicMock()
        fake_thread.is_alive.return_value = True
        srv._active_indexing["my_index"] = (fake_thread, MagicMock())

        with (
            patch(
                "cocosearch.auto_reindex.detect_drift",
                return_value=self._branch_drift(),
            ),
            patch("cocosearch.auto_reindex.trigger_reindex") as mock_trigger,
            patch(
                "cocosearch.management.context.resolve_index_name",
                return_value="my_index",
            ),
        ):
            srv._watchdog_tick_once()

        mock_trigger.assert_not_called()

    def test_iterates_linked_indexes(self, tmp_path, monkeypatch):
        """linkedIndexes from cocosearch.yaml are polled in addition to the main index."""
        monkeypatch.setenv("COCOSEARCH_PROJECT_PATH", str(tmp_path))
        (tmp_path / ".git").mkdir()

        # Create a minimal cocosearch.yaml with linkedIndexes
        (tmp_path / "cocosearch.yaml").write_text(
            "indexName: my_index\nlinkedIndexes:\n  - linked_a\n  - linked_b\n"
        )

        calls: list[str] = []

        def _fake_detect(name, path=None):
            calls.append(name)
            return self._no_drift()

        with (
            patch("cocosearch.auto_reindex.detect_drift", side_effect=_fake_detect),
            patch("cocosearch.auto_reindex.trigger_reindex"),
        ):
            srv._watchdog_tick_once()

        # Main index + two linked indexes polled.
        assert calls == ["my_index", "linked_a", "linked_b"]

    def test_trigger_uses_canonical_path_for_linked(self, tmp_path, monkeypatch):
        """For linked indexes, project_path comes from metadata canonical_path."""
        monkeypatch.setenv("COCOSEARCH_PROJECT_PATH", str(tmp_path))
        (tmp_path / ".git").mkdir()
        (tmp_path / "cocosearch.yaml").write_text(
            "indexName: my_index\nlinkedIndexes:\n  - linked_a\n"
        )

        def _fake_detect(name, path=None):
            # Only the linked index drifts.
            if name == "linked_a":
                return self._branch_drift()
            return self._no_drift()

        with (
            patch("cocosearch.auto_reindex.detect_drift", side_effect=_fake_detect),
            patch(
                "cocosearch.mcp.server.get_index_metadata",
                return_value={"canonical_path": "/other/project"},
            ),
            patch("cocosearch.auto_reindex.trigger_reindex") as mock_trigger,
        ):
            srv._watchdog_tick_once()

        assert mock_trigger.call_count == 1
        args, kwargs = mock_trigger.call_args
        assert args[0] == "linked_a"
        assert args[1] == "/other/project"


# ---------------------------------------------------------------------------
# _start_auto_reindex_watchdog
# ---------------------------------------------------------------------------


class TestStartAutoReindexWatchdog:
    def test_returns_daemon_thread(self):
        thread = srv._start_auto_reindex_watchdog(interval_seconds=3600)
        assert thread.daemon is True
        # Daemon thread will clean up when the test process exits; we don't
        # join it (the interval is an hour).
