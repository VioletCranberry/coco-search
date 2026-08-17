"""Tests that shutdown never leaves an index stuck in 'indexing' status.

The background indexing workers deliberately skip their own status write when
their cancel event is set, so that a user-initiated /api/stop-indexing owns the
final status. Every shutdown path reuses that same cancel event, so each one
must release the status itself — otherwise the metadata row stays 'indexing'
until the 1-hour auto-recovery in ``management.metadata``.
"""

import threading
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def registered_index():
    """Register a fake active-indexing entry and clean it up afterwards."""
    import cocosearch.mcp.server as srv

    name = "shutdown_idx"
    stop_event = MagicMock()
    thread = MagicMock()
    with srv._indexing_lock:
        srv._active_indexing[name] = (thread, stop_event)
    try:
        yield name, thread, stop_event
    finally:
        with srv._indexing_lock:
            srv._active_indexing.pop(name, None)


@pytest.fixture
def shutdown_patches():
    """Patch the process-level side effects of _graceful_shutdown()."""
    with (
        patch("cocosearch.mcp.server.os._exit"),
        patch("cocosearch.dashboard.server.stop_dashboard_server"),
        patch("cocosearch.search.db.close_pool"),
    ):
        yield


class TestGracefulShutdownReleasesStatus:
    """_graceful_shutdown() must not leave a stuck 'indexing' row behind."""

    def test_resets_status_of_interrupted_index(
        self, registered_index, shutdown_patches
    ):
        """A row still at 'indexing' is flipped to 'indexed' on shutdown."""
        import cocosearch.mcp.server as srv

        name, _thread, _stop_event = registered_index

        with (
            patch(
                "cocosearch.mcp.server.get_index_metadata",
                return_value={"status": "indexing"},
            ),
            patch("cocosearch.mcp.server.set_index_status") as mock_set,
        ):
            srv._graceful_shutdown()

        mock_set.assert_called_once_with(name, "indexed", update_timestamp=False)

    def test_preserves_timestamp_for_staleness_checks(
        self, registered_index, shutdown_patches
    ):
        """The reset must not touch updated_at — the data is still old."""
        import cocosearch.mcp.server as srv

        with (
            patch(
                "cocosearch.mcp.server.get_index_metadata",
                return_value={"status": "indexing"},
            ),
            patch("cocosearch.mcp.server.set_index_status") as mock_set,
        ):
            srv._graceful_shutdown()

        assert mock_set.call_args.kwargs["update_timestamp"] is False

    def test_leaves_finished_index_alone(self, registered_index, shutdown_patches):
        """A worker that already wrote its own status is not overwritten."""
        import cocosearch.mcp.server as srv

        with (
            patch(
                "cocosearch.mcp.server.get_index_metadata",
                return_value={"status": "error"},
            ),
            patch("cocosearch.mcp.server.set_index_status") as mock_set,
        ):
            srv._graceful_shutdown()

        mock_set.assert_not_called()

    def test_survives_metadata_failure(self, registered_index, shutdown_patches):
        """A dead database must not stop the process from exiting."""
        import cocosearch.mcp.server as srv

        with (
            patch(
                "cocosearch.mcp.server.get_index_metadata",
                side_effect=RuntimeError("db gone"),
            ),
            patch("cocosearch.mcp.server.set_index_status"),
        ):
            srv._graceful_shutdown()  # must not raise

    def test_joins_workers_outside_the_indexing_lock(self, shutdown_patches):
        """A worker's finally block pops itself under _indexing_lock.

        If shutdown holds that lock while joining, the worker deadlocks until
        the join times out and never gets to clean up after itself.
        """
        import cocosearch.mcp.server as srv

        name = "deadlock_idx"
        stop_event = threading.Event()
        started = threading.Event()
        completed = threading.Event()

        def _worker():
            started.set()
            stop_event.wait(2.0)
            with srv._indexing_lock:
                srv._active_indexing.pop(name, None)
            completed.set()

        thread = threading.Thread(target=_worker, daemon=True)
        with srv._indexing_lock:
            srv._active_indexing[name] = (thread, stop_event)
        thread.start()
        assert started.wait(2.0)

        try:
            with (
                patch("cocosearch.mcp.server.get_index_metadata", return_value=None),
                patch("cocosearch.mcp.server.set_index_status"),
            ):
                srv._graceful_shutdown()

            assert completed.is_set(), "worker never finished deregistering itself"
        finally:
            stop_event.set()
            thread.join(timeout=2.0)
            with srv._indexing_lock:
                srv._active_indexing.pop(name, None)


class TestLifespanTeardownReleasesStatus:
    """The MCP lifespan teardown is the path taken when the client closes."""

    @pytest.mark.asyncio
    async def test_resets_status_of_interrupted_index(self, registered_index):
        """Client disconnect resets a row still at 'indexing'."""
        import cocosearch.mcp.server as srv

        name, _thread, _stop_event = registered_index

        with (
            patch("cocosearch.search.db.close_pool"),
            patch(
                "cocosearch.mcp.server.get_index_metadata",
                return_value={"status": "indexing"},
            ),
            patch("cocosearch.mcp.server.set_index_status") as mock_set,
        ):
            async with srv._server_lifespan(MagicMock()):
                pass

        mock_set.assert_called_once_with(name, "indexed", update_timestamp=False)


class TestSigtermReleasesStatus:
    """SIGTERM is how Claude Code stops the stdio server."""

    def test_sigterm_handler_runs_graceful_shutdown(self):
        """The handler must go through the shared shutdown path."""
        import cocosearch.mcp.server as srv

        with patch("cocosearch.mcp.server._graceful_shutdown") as mock_shutdown:
            srv._sigterm_handler(15, None)

        mock_shutdown.assert_called_once()
