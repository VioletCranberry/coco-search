"""Tests for idle watchdog, activity tracking, graceful shutdown, and shutdown endpoint."""

import time as _time
from unittest.mock import MagicMock, patch

import httpx
import pytest
import pytest_asyncio


class TestTouchActivity:
    """Tests for _touch_activity() timestamp tracking."""

    def test_touch_activity_updates_timestamp(self):
        """_touch_activity() advances _last_activity."""
        import cocosearch.mcp.server as srv

        before = srv._last_activity
        _time.sleep(0.01)
        srv._touch_activity()
        assert srv._last_activity > before

    def test_touch_activity_monotonic(self):
        """Multiple calls always advance the timestamp."""
        import cocosearch.mcp.server as srv

        srv._touch_activity()
        t1 = srv._last_activity
        _time.sleep(0.01)
        srv._touch_activity()
        t2 = srv._last_activity
        assert t2 > t1


class TestLogMcpToolTouchesActivity:
    """Verify that the log_mcp_tool decorator calls _touch_activity."""

    def test_sync_wrapper_touches_activity(self):
        """Sync log_mcp_tool wrapper calls _touch_activity."""
        from cocosearch.mcp.server import log_mcp_tool

        with patch("cocosearch.mcp.server._touch_activity") as mock_touch:

            @log_mcp_tool
            def my_tool(ctx=None):
                return "ok"

            my_tool()
            mock_touch.assert_called()

    @pytest.mark.asyncio
    async def test_async_wrapper_touches_activity(self):
        """Async log_mcp_tool wrapper calls _touch_activity."""
        from cocosearch.mcp.server import log_mcp_tool

        with patch("cocosearch.mcp.server._touch_activity") as mock_touch:

            @log_mcp_tool
            async def my_async_tool(ctx=None):
                return "ok"

            await my_async_tool()
            mock_touch.assert_called()


class TestGracefulShutdown:
    """Tests for _graceful_shutdown() cleanup."""

    def test_graceful_shutdown_cancels_indexing(self):
        """_graceful_shutdown sets stop events and calls os._exit."""
        import cocosearch.mcp.server as srv

        stop_event = MagicMock()
        thread = MagicMock()
        srv._active_indexing["test_idx"] = (thread, stop_event)

        try:
            with (
                patch("cocosearch.mcp.server.os._exit") as mock_exit,
                patch(
                    "cocosearch.dashboard.server.stop_dashboard_server"
                ) as mock_stop_dash,
                patch("cocosearch.search.db.close_pool") as mock_close_pool,
            ):
                srv._graceful_shutdown()

                stop_event.set.assert_called_once()
                thread.join.assert_called_once_with(timeout=2.0)
                mock_stop_dash.assert_called_once()
                mock_close_pool.assert_called_once()
                mock_exit.assert_called_once_with(0)
        finally:
            srv._active_indexing.pop("test_idx", None)


@pytest.fixture
def asgi_app():
    """Create the ASGI app from the MCP server."""
    from cocosearch.mcp.server import mcp

    return mcp.sse_app()


@pytest_asyncio.fixture
async def client(asgi_app):
    """Create an httpx AsyncClient wired to the ASGI app."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as c:
        yield c


class TestShutdownEndpoint:
    """Tests for POST /api/shutdown through the ASGI stack."""

    @pytest.mark.asyncio
    async def test_shutdown_returns_200(self, client):
        """POST /api/shutdown returns 200 with shutting_down status."""
        with patch("cocosearch.mcp.server._graceful_shutdown"):
            response = await client.post("/api/shutdown")
            assert response.status_code == 200
            assert response.json()["status"] == "shutting_down"

    @pytest.mark.asyncio
    async def test_shutdown_schedules_graceful_shutdown(self, client):
        """POST /api/shutdown schedules _graceful_shutdown via call_later."""
        with patch("cocosearch.mcp.server._graceful_shutdown") as mock_shutdown:
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value = MagicMock()
                await client.post("/api/shutdown")
                mock_loop.return_value.call_later.assert_called_once()
                args = mock_loop.return_value.call_later.call_args
                assert args[0][0] == 0.5
                assert args[0][1] is mock_shutdown
