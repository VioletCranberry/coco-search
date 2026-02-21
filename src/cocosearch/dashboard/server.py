"""Background HTTP server for the web dashboard.

Used in stdio MCP transport mode where FastMCP's custom routes are
inaccessible. Starts uvicorn serving the MCP server's sse_app() in a
daemon thread so the dashboard — and all API routes — remain reachable
at http://127.0.0.1:{port}/dashboard.

CRITICAL: All logging goes to stderr — stdout is reserved for JSON-RPC
when running under stdio transport.
"""

import asyncio
import logging
import os
import sys
import threading

logger = logging.getLogger(__name__)


def start_dashboard_server(port: int | None = None) -> str | None:
    """Start the dashboard HTTP server in a daemon thread.

    Runs uvicorn with the MCP server's sse_app(), which includes all
    custom_route endpoints (API, dashboard, health, etc.).

    Args:
        port: Port to bind to. Defaults to COCOSEARCH_DASHBOARD_PORT env
              var or 0 (OS-assigned random port).

    Returns:
        Dashboard URL on success, None if the port is already in use.
    """
    import uvicorn

    from cocosearch.mcp.server import mcp

    if port is None:
        env_port = os.environ.get("COCOSEARCH_DASHBOARD_PORT")
        port = int(env_port) if env_port else 0  # 0 = OS-assigned

    app = mcp.sse_app()

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)

    # Track the actual bound port (resolved after startup when port=0)
    actual_port = port

    def _run():
        nonlocal actual_port
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.serve())
        except Exception as e:
            logger.warning(f"Dashboard server error: {e}")
        finally:
            loop.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    # Wait for server to start (up to 5 seconds)
    for _ in range(50):
        if server.started:
            break
        threading.Event().wait(0.1)

    if not server.started:
        print(
            f"Warning: Dashboard server did not start on port {port}",
            file=sys.stderr,
        )
        return None

    # Extract actual port from bound sockets
    for sock in server.servers:
        actual_port = sock.sockets[0].getsockname()[1]
        break

    url = f"http://127.0.0.1:{actual_port}/dashboard"
    print(f"Dashboard available at {url}", file=sys.stderr)
    return url
