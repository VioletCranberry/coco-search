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

# Track active indexing threads (mirrors mcp/server.py's _active_indexing)
_active_indexing: dict[str, threading.Thread] = {}
_indexing_lock = threading.Lock()


class DashboardHandler(BaseHTTPRequestHandler):
    """Serves dashboard HTML and stats API."""

    def do_GET(self):  # noqa: N802
        if self.path == "/dashboard":
            self._serve_dashboard()
        elif self.path == "/health":
            self._json_response({"status": "ok"})
        elif self.path == "/api/project":
            self._serve_project_context()
        elif self.path == "/api/stats" or self.path.startswith("/api/stats?"):
            self._serve_all_stats()
        elif self.path.startswith("/api/stats/"):
            index_name = self.path.split("/api/stats/", 1)[1].split("?")[0]
            self._serve_single_stats(index_name)
        else:
            self.send_error(404)

    def do_POST(self):  # noqa: N802
        if self.path == "/api/reindex":
            self._handle_reindex()
        elif self.path == "/api/index":
            self._handle_index()
        elif self.path == "/api/stop-indexing":
            self._handle_stop_indexing()
        elif self.path == "/api/delete-index":
            self._handle_delete_index()
        elif self.path == "/api/search":
            self._handle_search()
        else:
            self.send_error(404)

    def _read_json_body(self) -> dict | None:
        """Read and parse JSON body from request. Returns None on error (response already sent)."""
        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length) if content_length else b""
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            self._json_response({"error": "Invalid JSON body"}, status=400)
            return None

    def _handle_search(self):
        import time
        import cocoindex
        from cocosearch.search import byte_to_line, read_chunk_content, search

        body = self._read_json_body()
        if body is None:
            return

        query = (body.get("query") or "").strip()
        index_name = body.get("index_name")

        if not query:
            self._json_response({"error": "query is required"}, status=400)
            return
        if not index_name:
            self._json_response({"error": "index_name is required"}, status=400)
            return

        limit = body.get("limit", 10)
        language = body.get("language") or None
        symbol_type = body.get("symbol_type") or None
        symbol_name = body.get("symbol_name") or None
        min_score = body.get("min_score", 0.3)
        use_hybrid = body.get("use_hybrid")

        try:
            cocoindex.init()
        except Exception:
            self._json_response(
                {"error": "Database not initialized. Index a codebase first."},
                status=503,
            )
            return

        start_time = time.monotonic()
        try:
            results = search(
                query=query,
                index_name=index_name,
                limit=limit,
                min_score=min_score,
                language_filter=language,
                use_hybrid=use_hybrid,
                symbol_type=symbol_type,
                symbol_name=symbol_name,
            )
        except ValueError as e:
            self._json_response({"error": str(e)}, status=400)
            return
        except Exception as e:
            logger.error(f"Search failed: {e}")
            self._json_response({"error": f"Search failed: {e}"}, status=500)
            return

        query_time_ms = round((time.monotonic() - start_time) * 1000)

        output = []
        for r in results:
            start_line = byte_to_line(r.filename, r.start_byte)
            end_line = byte_to_line(r.filename, r.end_byte)
            content = read_chunk_content(r.filename, r.start_byte, r.end_byte)

            result_dict = {
                "file_path": r.filename,
                "start_line": start_line,
                "end_line": end_line,
                "score": r.score,
                "content": content,
                "block_type": r.block_type,
                "hierarchy": r.hierarchy,
                "language_id": r.language_id,
                "symbol_type": r.symbol_type,
                "symbol_name": r.symbol_name,
                "symbol_signature": r.symbol_signature,
            }

            if r.match_type:
                result_dict["match_type"] = r.match_type
            if r.vector_score is not None:
                result_dict["vector_score"] = r.vector_score
            if r.keyword_score is not None:
                result_dict["keyword_score"] = r.keyword_score

            output.append(result_dict)

        self._json_response(
            {
                "success": True,
                "results": output,
                "query_time_ms": query_time_ms,
                "total": len(output),
            }
        )

    def _handle_reindex(self):
        import cocoindex
        from cocosearch.indexer import IndexingConfig, run_index
        from cocosearch.management import (
            get_index_metadata,
            set_index_status,
            register_index_path,
        )

        body = self._read_json_body()
        if body is None:
            return

        index_name = body.get("index_name")
        fresh = body.get("fresh", False)

        if not index_name:
            self._json_response({"error": "index_name is required"}, status=400)
            return

        metadata = get_index_metadata(index_name)
        if not metadata or not metadata.get("canonical_path"):
            self._json_response(
                {"error": f"Index '{index_name}' not found or has no source path"},
                status=400,
            )
            return

        source_path = metadata["canonical_path"]

        # Reject if a previous indexing thread is still alive
        with _indexing_lock:
            prev = _active_indexing.get(index_name)
        if prev is not None and prev.is_alive():
            self._json_response(
                {"error": "Previous indexing still completing. Try again shortly."},
                status=409,
            )
            return

        # Set status to indexing
        try:
            set_index_status(index_name, "indexing")
        except Exception as e:
            logger.warning(f"Failed to set indexing status for '{index_name}': {e}")

        def _run():
            failed = False
            try:
                cocoindex.init()
                run_index(
                    index_name=index_name,
                    codebase_path=source_path,
                    config=IndexingConfig(),
                    fresh=fresh,
                )
                register_index_path(index_name, source_path)
            except Exception as exc:
                failed = True
                logger.error(f"Background reindex failed: {exc}")
            finally:
                try:
                    current = get_index_metadata(index_name)
                    if current and current.get("status") == "indexing":
                        set_index_status(index_name, "error" if failed else "indexed")
                except Exception as e:
                    logger.warning(f"Failed to update status for '{index_name}': {e}")
                with _indexing_lock:
                    _active_indexing.pop(index_name, None)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        with _indexing_lock:
            _active_indexing[index_name] = thread

        action = "Fresh reindex" if fresh else "Reindex"
        self._json_response(
            {"success": True, "message": f"{action} started for '{index_name}'"}
        )

    def _handle_index(self):
        import cocoindex
        from cocosearch.cli import derive_index_name
        from cocosearch.indexer import IndexingConfig, run_index
        from cocosearch.management import (
            ensure_metadata_table,
            register_index_path,
            set_index_status,
            get_index_metadata,
        )

        body = self._read_json_body()
        if body is None:
            return

        project_path = body.get("project_path")
        index_name = body.get("index_name")

        if not project_path:
            self._json_response({"error": "project_path is required"}, status=400)
            return

        if not index_name:
            index_name = derive_index_name(project_path)

        # Reject if a previous indexing thread is still alive
        with _indexing_lock:
            prev = _active_indexing.get(index_name)
        if prev is not None and prev.is_alive():
            self._json_response(
                {"error": "Previous indexing still completing. Try again shortly."},
                status=409,
            )
            return

        # Register metadata before starting
        try:
            ensure_metadata_table()
            register_index_path(index_name, project_path)
            set_index_status(index_name, "indexing")
        except Exception as e:
            logger.warning(f"Metadata registration failed: {e}")

        def _run():
            failed = False
            try:
                cocoindex.init()
                run_index(
                    index_name=index_name,
                    codebase_path=project_path,
                    config=IndexingConfig(),
                )
                register_index_path(index_name, project_path)
            except Exception as exc:
                failed = True
                logger.error(f"Background indexing failed: {exc}")
            finally:
                try:
                    current = get_index_metadata(index_name)
                    if current and current.get("status") == "indexing":
                        set_index_status(index_name, "error" if failed else "indexed")
                except Exception as e:
                    logger.warning(f"Failed to update status for '{index_name}': {e}")
                with _indexing_lock:
                    _active_indexing.pop(index_name, None)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        with _indexing_lock:
            _active_indexing[index_name] = thread

        self._json_response(
            {
                "success": True,
                "index_name": index_name,
                "message": f"Indexing started for '{index_name}' from {project_path}",
            }
        )

    def _handle_stop_indexing(self):
        from cocosearch.management import set_index_status

        body = self._read_json_body()
        if body is None:
            return

        index_name = body.get("index_name")
        if not index_name:
            self._json_response({"error": "index_name is required"}, status=400)
            return

        with _indexing_lock:
            thread = _active_indexing.get(index_name)
        if thread is None or not thread.is_alive():
            self._json_response(
                {"error": f"No active indexing found for '{index_name}'"},
                status=404,
            )
            return

        try:
            set_index_status(index_name, "indexed")
        except Exception as e:
            self._json_response({"error": f"Failed to update status: {e}"}, status=500)
            return

        self._json_response(
            {"success": True, "message": f"Indexing stopped for '{index_name}'"}
        )

    def _handle_delete_index(self):
        from cocosearch.management import clear_index as mgmt_clear_index

        body = self._read_json_body()
        if body is None:
            return

        index_name = body.get("index_name")
        if not index_name:
            self._json_response({"error": "index_name is required"}, status=400)
            return

        # Reject if indexing is currently active for this index
        with _indexing_lock:
            prev = _active_indexing.get(index_name)
        if prev is not None and prev.is_alive():
            self._json_response(
                {
                    "error": f"Cannot delete '{index_name}' while indexing is active. Stop indexing first."
                },
                status=409,
            )
            return

        try:
            result = mgmt_clear_index(index_name)
            self._json_response(result)
        except ValueError as e:
            self._json_response({"error": str(e)}, status=404)
        except Exception as e:
            self._json_response({"error": f"Failed to delete index: {e}"}, status=500)

    def _serve_project_context(self):
        import cocoindex
        from pathlib import Path
        from cocosearch.management import (
            resolve_index_name,
            get_index_metadata,
        )
        from cocosearch.management import list_indexes as mgmt_list_indexes
        from cocosearch.management.context import find_project_root

        env_path = os.environ.get("COCOSEARCH_PROJECT_PATH")
        if not env_path:
            self._json_response({"has_project": False})
            return

        project_root, detection_method = find_project_root(Path(env_path))
        if project_root is None:
            project_root = Path(env_path).resolve()
            detection_method = None

        index_name = resolve_index_name(project_root, detection_method)

        is_indexed = False
        path_collision = False
        collision_message = None
        try:
            cocoindex.init()
            indexes = mgmt_list_indexes()
            index_names = {idx["name"] for idx in indexes}
            is_indexed = index_name in index_names

            if is_indexed:
                metadata = get_index_metadata(index_name)
                if metadata and metadata.get("canonical_path"):
                    canonical_cwd = str(project_root.resolve())
                    stored_path = metadata["canonical_path"]
                    if stored_path != canonical_cwd:
                        path_collision = True
                        collision_message = (
                            f"Index '{index_name}' is mapped to {stored_path}, "
                            f"but current project is at {canonical_cwd}"
                        )
        except Exception:
            pass

        self._json_response(
            {
                "has_project": True,
                "project_path": str(project_root),
                "index_name": index_name,
                "is_indexed": is_indexed,
                "detection_method": detection_method,
                "path_collision": path_collision,
                "collision_message": collision_message,
            }
        )

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
        from cocosearch.management import (
            get_comprehensive_stats,
            get_grammar_failures,
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
                # Override status from thread liveness — the DB status may
                # lag behind the actual indexing state due to race conditions.
                with _indexing_lock:
                    active = _active_indexing.get(idx["name"])
                if active is not None and active.is_alive():
                    result["status"] = "indexing"
                if include_failures:
                    result["parse_failures"] = get_parse_failures(idx["name"])
                    result["grammar_failures"] = get_grammar_failures(idx["name"])
                all_stats.append(result)
            except ValueError:
                continue
        self._json_response(all_stats)

    def _serve_single_stats(self, index_name: str):
        import cocoindex
        from cocosearch.management import (
            get_comprehensive_stats,
            get_grammar_failures,
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
            # Override status from thread liveness
            with _indexing_lock:
                active = _active_indexing.get(index_name)
            if active is not None and active.is_alive():
                result["status"] = "indexing"
            if include_failures:
                result["parse_failures"] = get_parse_failures(index_name)
                result["grammar_failures"] = get_grammar_failures(index_name)
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
