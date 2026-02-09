"""Background HTTP server for the web dashboard.

Used in stdio MCP transport mode where FastMCP's custom routes are
inaccessible. Starts a lightweight stdlib HTTP server in a daemon thread
so the dashboard remains reachable at http://127.0.0.1:{port}/dashboard.

CRITICAL: All logging goes to stderr — stdout is reserved for JSON-RPC
when running under stdio transport.
"""

import json
import logging
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger(__name__)


class DashboardHandler(BaseHTTPRequestHandler):
    """Serves dashboard HTML and stats API."""

    def do_GET(self):  # noqa: N802
        if self.path == "/dashboard":
            self._serve_dashboard()
        elif self.path == "/health":
            self._json_response({"status": "ok"})
        elif self.path == "/api/stats" or self.path.startswith("/api/stats?"):
            self._serve_all_stats()
        elif self.path.startswith("/api/stats/"):
            index_name = self.path.split("/api/stats/", 1)[1].split("?")[0]
            self._serve_single_stats(index_name)
        else:
            self.send_error(404)

    def _serve_dashboard(self):
        from cocosearch.dashboard.web import get_dashboard_html

        html = get_dashboard_html()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def _serve_all_stats(self):
        import cocoindex
        from cocosearch.management import list_indexes as mgmt_list_indexes
        from cocosearch.management.stats import (
            get_comprehensive_stats,
            get_parse_failures,
        )

        try:
            cocoindex.init()
        except Exception:
            pass

        include_failures = "include_failures=true" in self.path.lower()
        indexes = mgmt_list_indexes()
        all_stats = []
        for idx in indexes:
            try:
                stats = get_comprehensive_stats(idx["name"])
                result = stats.to_dict()
                if include_failures:
                    result["parse_failures"] = get_parse_failures(idx["name"])
                all_stats.append(result)
            except ValueError:
                continue
        self._json_response(all_stats)

    def _serve_single_stats(self, index_name: str):
        import cocoindex
        from cocosearch.management.stats import (
            get_comprehensive_stats,
            get_parse_failures,
        )

        try:
            cocoindex.init()
        except Exception:
            pass

        include_failures = "include_failures=true" in self.path.lower()
        try:
            stats = get_comprehensive_stats(index_name)
            result = stats.to_dict()
            if include_failures:
                result["parse_failures"] = get_parse_failures(index_name)
            self._json_response(result)
        except ValueError as e:
            self._json_response({"error": str(e)}, status=404)

    def _json_response(self, data, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        """Redirect request logs to stderr (never stdout)."""
        logger.debug(format, *args)


def start_dashboard_server(port: int | None = None) -> str | None:
    """Start the dashboard HTTP server in a daemon thread.

    Args:
        port: Port to bind to. Defaults to COCOSEARCH_DASHBOARD_PORT env
              var or 0 (OS-assigned random port).

    Returns:
        Dashboard URL on success, None if the port is already in use.
    """
    if port is None:
        env_port = os.environ.get("COCOSEARCH_DASHBOARD_PORT")
        port = int(env_port) if env_port else 0  # 0 = OS-assigned

    try:
        server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    except OSError as e:
        print(
            f"Warning: Could not start dashboard server on port {port}: {e}",
            file=sys.stderr,
        )
        return None

    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{actual_port}/dashboard"
    print(f"Dashboard available at {url}", file=sys.stderr)
    return url
