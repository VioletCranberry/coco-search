"""MCP server for cocosearch.

Provides Model Context Protocol server with tools for:
- Searching indexed code
- Listing available indexes
- Getting index statistics
- Clearing (deleting) indexes
- Indexing codebases
"""

# CRITICAL: Configure logging to stderr immediately before any other imports
# This prevents stdout corruption of the JSON-RPC protocol
import os
import sys
import logging
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

_active_indexing: dict[str, threading.Thread] = {}
_indexing_lock = threading.Lock()
_cocoindex_initialized = False
_cocoindex_init_lock = threading.Lock()

from pathlib import Path  # noqa: E402
from typing import Annotated  # noqa: E402

import cocoindex  # noqa: E402
from mcp.server.fastmcp import Context, FastMCP  # noqa: E402
from pydantic import Field  # noqa: E402
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse  # noqa: E402

from cocosearch.management.context import derive_index_name  # noqa: E402
from cocosearch.dashboard.web import get_dashboard_html  # noqa: E402
from cocosearch.indexer import IndexingConfig, run_index  # noqa: E402
from cocosearch.management import clear_index as mgmt_clear_index  # noqa: E402
from cocosearch.management import list_indexes as mgmt_list_indexes  # noqa: E402
from cocosearch.management import (  # noqa: E402
    resolve_index_name,
    get_index_metadata,
    ensure_metadata_table,
    register_index_path,
    set_index_status,
)
from cocosearch.management.git import get_current_branch, get_commit_hash  # noqa: E402
from cocosearch.mcp.project_detection import (  # noqa: E402
    _detect_project,
    register_roots_notification,
)
from cocosearch.management.stats import (  # noqa: E402
    check_staleness,
    get_comprehensive_stats,
    get_grammar_failures,
    get_parse_failures,
)
from cocosearch.search import byte_to_line, read_chunk_content, search  # noqa: E402
from cocosearch.search.analyze import analyze as run_analyze  # noqa: E402
from cocosearch.search.context_expander import ContextExpander  # noqa: E402


def _ensure_cocoindex_init() -> None:
    """Initialize CocoIndex exactly once, thread-safely.

    cocoindex.init() is synchronous and triggers a RuntimeWarning when called
    inside an async event loop. By calling it once (guarded by a lock) we
    avoid the repeated sync-inside-async warnings from every HTTP/MCP handler.
    """
    global _cocoindex_initialized
    if _cocoindex_initialized:
        return
    with _cocoindex_init_lock:
        if not _cocoindex_initialized:
            cocoindex.init()
            _cocoindex_initialized = True


def _apply_thread_liveness_status(
    index_name: str, result: dict, db_status: str | None
) -> None:
    """Override status from thread liveness if indexing thread is still alive.

    The DB status may lag behind the actual indexing state. This ensures
    the API returns accurate status by checking the in-memory thread registry.

    Args:
        index_name: Index name to check.
        result: Mutable result dict to update.
        db_status: Status from database metadata.
    """
    with _indexing_lock:
        active = _active_indexing.get(index_name)
    if active is not None and active.is_alive():
        result["status"] = "indexing"
        if db_status != "indexing":
            try:
                set_index_status(index_name, "indexing", update_timestamp=False)
            except Exception:
                pass


def _register_with_git(index_name: str, project_path: str) -> None:
    """Register index path with current git branch/commit metadata."""
    from cocosearch.management.git import get_branch_commit_count

    branch = get_current_branch(project_path)
    commit_hash = get_commit_hash(project_path)
    branch_commit_count = get_branch_commit_count(project_path)
    register_index_path(
        index_name,
        project_path,
        branch=branch,
        commit_hash=commit_hash,
        branch_commit_count=branch_commit_count,
    )


def build_all_stats(include_failures: bool = False) -> list[dict]:
    """Build stats for all indexes.

    Shared by MCP API routes and the background DashboardHandler.
    Calls _ensure_cocoindex_init() internally.
    """
    _ensure_cocoindex_init()
    indexes = mgmt_list_indexes()
    all_stats = []
    for idx in indexes:
        try:
            stats = get_comprehensive_stats(idx["name"])
            result = stats.to_dict()
            _apply_thread_liveness_status(idx["name"], result, stats.status)
            if include_failures:
                result["parse_failures"] = get_parse_failures(idx["name"])
                result["grammar_failures"] = get_grammar_failures(idx["name"])
            all_stats.append(result)
        except ValueError:
            continue
    return all_stats


def build_single_stats(index_name: str, include_failures: bool = False) -> dict:
    """Build stats for a single index.

    Shared by MCP API routes and the background DashboardHandler.
    Calls _ensure_cocoindex_init() internally.
    Raises ValueError if the index is not found.
    """
    _ensure_cocoindex_init()
    stats = get_comprehensive_stats(index_name)
    result = stats.to_dict()
    _apply_thread_liveness_status(index_name, result, stats.status)
    if include_failures:
        result["parse_failures"] = get_parse_failures(index_name)
        result["grammar_failures"] = get_grammar_failures(index_name)
    return result


# Create FastMCP server instance
mcp = FastMCP("cocosearch")
register_roots_notification(mcp)


# Health endpoint for Docker/orchestration
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request) -> JSONResponse:
    """Health check endpoint. Also see /dashboard for web UI."""
    return JSONResponse({"status": "ok"})


# SSE heartbeat endpoint for dashboard disconnect detection
@mcp.custom_route("/api/heartbeat", methods=["GET"])
async def heartbeat(request) -> StreamingResponse:
    """SSE heartbeat stream. Dashboard connects to detect server shutdown."""
    import asyncio

    async def event_stream():
        try:
            while True:
                yield "data: ping\n\n"
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# Dashboard endpoint
@mcp.custom_route("/dashboard", methods=["GET"])
async def serve_dashboard(request) -> HTMLResponse:
    """Serve the web dashboard HTML."""
    html_content = get_dashboard_html()
    return HTMLResponse(content=html_content)


# Stats API endpoints
@mcp.custom_route("/api/stats", methods=["GET"])
async def api_stats(request) -> JSONResponse:
    """Stats API endpoint for web dashboard and programmatic access."""
    index_name = request.query_params.get("index")
    include_failures = (
        request.query_params.get("include_failures", "").lower() == "true"
    )

    try:
        if index_name:
            result = build_single_stats(index_name, include_failures)
            return JSONResponse(
                result, headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
        else:
            all_stats = build_all_stats(include_failures)
            return JSONResponse(
                all_stats,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    except Exception as e:
        logger.warning(f"Stats failed: {e}")
        return JSONResponse(
            {"error": "Database not initialized. Index a codebase first."},
            status_code=503,
        )


@mcp.custom_route("/api/stats/{index_name}", methods=["GET"])
async def api_stats_single(request) -> JSONResponse:
    """Stats for a single index by name."""
    index_name = request.path_params["index_name"]
    include_failures = (
        request.query_params.get("include_failures", "").lower() == "true"
    )
    try:
        result = build_single_stats(index_name, include_failures)
        return JSONResponse(
            result, headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    except Exception as e:
        logger.warning(f"Stats failed: {e}")
        return JSONResponse(
            {"error": "Database not initialized. Index a codebase first."},
            status_code=503,
        )


@mcp.custom_route("/api/reindex", methods=["POST"])
async def api_reindex(request) -> JSONResponse:
    """Trigger reindexing of an existing index in a background thread."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    index_name = body.get("index_name")
    fresh = body.get("fresh", False)

    if not index_name:
        return JSONResponse({"error": "index_name is required"}, status_code=400)

    # Look up source path from metadata, with fallbacks
    metadata = get_index_metadata(index_name)
    source_path = metadata.get("canonical_path") if metadata else None

    if not source_path:
        # Fallback 1: source_path from request body (dashboard sends this)
        source_path = body.get("source_path")

        # Fallback 2: COCOSEARCH_PROJECT_PATH env var
        if not source_path:
            from cocosearch.management.context import find_project_root

            env_path = os.environ.get("COCOSEARCH_PROJECT_PATH")
            if env_path:
                project_root, _ = find_project_root(Path(env_path))
                if project_root:
                    source_path = str(project_root.resolve())

        if not source_path:
            return JSONResponse(
                {"error": f"Index '{index_name}' not found or has no source path"},
                status_code=400,
            )

        # Auto-register metadata so future reindex calls work without fallback
        try:
            ensure_metadata_table()
            _register_with_git(index_name, source_path)
        except Exception as e:
            logger.warning(f"Auto-registration of metadata failed: {e}")

    # Hold lock for entire check-and-start to prevent two threads
    # from both starting indexing for the same index
    with _indexing_lock:
        prev = _active_indexing.get(index_name)
        if prev is not None and prev.is_alive():
            return JSONResponse(
                {"error": "Previous indexing still completing. Try again shortly."},
                status_code=409,
            )

        # Set status to indexing
        try:
            set_index_status(index_name, "indexing")
        except Exception as e:
            logger.warning(f"Failed to set indexing status for '{index_name}': {e}")

        def _run():
            failed = False
            try:
                _ensure_cocoindex_init()
                run_index(
                    index_name=index_name,
                    codebase_path=source_path,
                    config=IndexingConfig(),
                    fresh=fresh,
                )
                _register_with_git(index_name, source_path)
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
        _active_indexing[index_name] = thread
        thread.start()

    action = "Fresh reindex" if fresh else "Reindex"
    return JSONResponse(
        {"success": True, "message": f"{action} started for '{index_name}'"}
    )


@mcp.custom_route("/api/project", methods=["GET"])
async def api_project(request) -> JSONResponse:
    """Return current project context based on COCOSEARCH_PROJECT_PATH."""
    from cocosearch.management.context import find_project_root

    env_path = os.environ.get("COCOSEARCH_PROJECT_PATH")
    if not env_path:
        return JSONResponse({"has_project": False})

    project_root, detection_method = find_project_root(Path(env_path))
    if project_root is None:
        # Env var set but no project root found — use the path directly
        project_root = Path(env_path).resolve()
        detection_method = None

    index_name = resolve_index_name(project_root, detection_method)

    # Check if the index exists
    is_indexed = False
    path_collision = False
    collision_message = None
    try:
        _ensure_cocoindex_init()
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
    except Exception as e:
        logger.warning(f"Failed to check index existence: {e}")

    return JSONResponse(
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


@mcp.custom_route("/api/index", methods=["POST"])
async def api_index(request) -> JSONResponse:
    """Trigger initial indexing of a project from the dashboard."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    project_path = body.get("project_path")
    index_name = body.get("index_name")

    if not project_path:
        return JSONResponse({"error": "project_path is required"}, status_code=400)

    # Derive index name if not provided
    if not index_name:
        index_name = derive_index_name(project_path)

    # Hold lock for entire check-and-start to prevent two threads
    # from both starting indexing for the same index
    with _indexing_lock:
        prev = _active_indexing.get(index_name)
        if prev is not None and prev.is_alive():
            return JSONResponse(
                {"error": "Previous indexing still completing. Try again shortly."},
                status_code=409,
            )

        # Register metadata before starting
        try:
            ensure_metadata_table()
            _register_with_git(index_name, project_path)
            set_index_status(index_name, "indexing")
        except Exception as e:
            logger.warning(f"Metadata registration failed: {e}")

        def _run():
            failed = False
            try:
                _ensure_cocoindex_init()
                run_index(
                    index_name=index_name,
                    codebase_path=project_path,
                    config=IndexingConfig(),
                )
                _register_with_git(index_name, project_path)
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
        _active_indexing[index_name] = thread
        thread.start()

    return JSONResponse(
        {
            "success": True,
            "index_name": index_name,
            "message": f"Indexing started for '{index_name}' from {project_path}",
        }
    )


@mcp.custom_route("/api/stop-indexing", methods=["POST"])
async def api_stop_indexing(request) -> JSONResponse:
    """Stop an in-progress indexing operation."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    index_name = body.get("index_name")
    if not index_name:
        return JSONResponse({"error": "index_name is required"}, status_code=400)

    with _indexing_lock:
        thread = _active_indexing.get(index_name)
    if thread is None or not thread.is_alive():
        return JSONResponse(
            {"error": f"No active indexing found for '{index_name}'"},
            status_code=404,
        )

    try:
        set_index_status(index_name, "indexed")
    except Exception as e:
        return JSONResponse({"error": f"Failed to update status: {e}"}, status_code=500)

    return JSONResponse(
        {"success": True, "message": f"Indexing stopped for '{index_name}'"}
    )


@mcp.custom_route("/api/delete-index", methods=["POST"])
async def api_delete_index(request) -> JSONResponse:
    """Delete an index permanently."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    index_name = body.get("index_name")
    if not index_name:
        return JSONResponse({"error": "index_name is required"}, status_code=400)

    # Reject if indexing is currently active for this index
    with _indexing_lock:
        prev = _active_indexing.get(index_name)
    if prev is not None and prev.is_alive():
        return JSONResponse(
            {
                "error": f"Cannot delete '{index_name}' while indexing is active. Stop indexing first."
            },
            status_code=409,
        )

    try:
        result = mgmt_clear_index(index_name)
        return JSONResponse(result)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": f"Failed to delete index: {e}"}, status_code=500)


@mcp.custom_route("/api/search", methods=["POST"])
async def api_search(request) -> JSONResponse:
    """Search indexed code via the dashboard API."""
    import time

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    query = body.get("query", "").strip()
    index_name = body.get("index_name")

    if not query:
        return JSONResponse({"error": "query is required"}, status_code=400)
    if not index_name:
        return JSONResponse({"error": "index_name is required"}, status_code=400)

    limit = body.get("limit", 10)
    language = body.get("language") or None
    symbol_type = body.get("symbol_type") or None
    symbol_name = body.get("symbol_name") or None
    min_score = body.get("min_score", 0.3)
    use_hybrid = body.get("use_hybrid")

    try:
        _ensure_cocoindex_init()
    except Exception as e:
        logger.warning(f"CocoIndex init failed: {e}")
        return JSONResponse(
            {"error": "Database not initialized. Index a codebase first."},
            status_code=503,
        )

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
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return JSONResponse({"error": f"Search failed: {e}"}, status_code=500)

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

    return JSONResponse(
        {
            "success": True,
            "results": output,
            "query_time_ms": query_time_ms,
            "total": len(output),
        }
    )


@mcp.custom_route("/api/open-in-editor", methods=["POST"])
async def api_open_in_editor(request) -> JSONResponse:
    """Open a file in the user's configured editor with optional line jump."""
    import subprocess

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    file_path = body.get("file_path", "")
    line = body.get("line")

    # Validate path
    path_error = _validate_file_path(file_path)
    if path_error:
        return JSONResponse({"error": path_error}, status_code=400)

    # Resolve editor
    editor = _resolve_editor()
    if not editor:
        return JSONResponse(
            {
                "error": "No editor configured. Set COCOSEARCH_EDITOR, EDITOR, or VISUAL environment variable."
            },
            status_code=400,
        )

    # Build and run command
    try:
        cmd = _build_editor_command(editor, file_path, line)
        subprocess.Popen(cmd)  # noqa: S603 — fire-and-forget, path validated above
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": f"Failed to open editor: {e}"}, status_code=500)


@mcp.custom_route("/api/file-content", methods=["GET"])
async def api_file_content(request) -> JSONResponse:
    """Read a file and return its content with language detection for syntax highlighting."""
    file_path = request.query_params.get("path", "")

    # Validate path
    path_error = _validate_file_path(file_path)
    if path_error:
        return JSONResponse({"error": path_error}, status_code=400)

    max_lines = 50_000
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        truncated = len(lines) > max_lines
        if truncated:
            lines = lines[:max_lines]

        content = "".join(lines)
        language = _get_prism_language(file_path)
        total_lines = len(lines)

        result = {
            "content": content,
            "language": language,
            "lines": total_lines,
        }
        if truncated:
            result["truncated"] = True
            result["message"] = f"File truncated to {max_lines:,} lines"

        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": f"Failed to read file: {e}"}, status_code=500)


def _get_treesitter_language(ext: str) -> str | None:
    """Map file extension to tree-sitter language name."""
    mapping = {
        "py": "python",
        "js": "javascript",
        "jsx": "javascript",
        "mjs": "javascript",
        "cjs": "javascript",
        "ts": "typescript",
        "tsx": "typescript",
        "mts": "typescript",
        "cts": "typescript",
        "go": "go",
        "rs": "rust",
    }
    return mapping.get(ext)


# Extended mapping for Prism.js syntax highlighting (superset of tree-sitter mapping)
_EXT_TO_PRISM_LANGUAGE: dict[str, str] = {
    "py": "python",
    "js": "javascript",
    "jsx": "jsx",
    "mjs": "javascript",
    "cjs": "javascript",
    "ts": "typescript",
    "tsx": "tsx",
    "mts": "typescript",
    "cts": "typescript",
    "go": "go",
    "rs": "rust",
    "rb": "ruby",
    "java": "java",
    "kt": "kotlin",
    "kts": "kotlin",
    "scala": "scala",
    "cs": "csharp",
    "cpp": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "c": "c",
    "h": "c",
    "hpp": "cpp",
    "swift": "swift",
    "php": "php",
    "lua": "lua",
    "r": "r",
    "R": "r",
    "sh": "bash",
    "bash": "bash",
    "zsh": "bash",
    "fish": "bash",
    "ps1": "powershell",
    "sql": "sql",
    "html": "html",
    "htm": "html",
    "css": "css",
    "scss": "scss",
    "sass": "sass",
    "less": "less",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "xml": "xml",
    "md": "markdown",
    "markdown": "markdown",
    "tf": "hcl",
    "hcl": "hcl",
    "dockerfile": "docker",
    "Dockerfile": "docker",
    "proto": "protobuf",
    "graphql": "graphql",
    "gql": "graphql",
    "vim": "vim",
    "el": "lisp",
    "clj": "clojure",
    "ex": "elixir",
    "exs": "elixir",
    "erl": "erlang",
    "hs": "haskell",
    "ml": "ocaml",
    "mli": "ocaml",
    "dart": "dart",
    "groovy": "groovy",
    "gradle": "groovy",
    "pl": "perl",
    "pm": "perl",
    "ini": "ini",
    "cfg": "ini",
    "conf": "ini",
    "diff": "diff",
    "patch": "diff",
    "makefile": "makefile",
    "Makefile": "makefile",
    "cmake": "cmake",
}


def _get_prism_language(file_path: str) -> str:
    """Detect Prism.js language from file path. Returns 'plain' as fallback."""
    name = os.path.basename(file_path)
    # Handle dotfiles/exact names
    lower = name.lower()
    if lower in ("dockerfile", "makefile", "cmakelists.txt"):
        special = {
            "dockerfile": "docker",
            "makefile": "makefile",
            "cmakelists.txt": "cmake",
        }
        return special.get(lower, "plain")
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    return _EXT_TO_PRISM_LANGUAGE.get(ext, "plain")


def _validate_file_path(file_path: str) -> str | None:
    """Validate a file path for security. Returns error message or None if valid."""
    if not file_path:
        return "file_path is required"
    if not os.path.isabs(file_path):
        return "file_path must be absolute"
    if ".." in Path(file_path).parts:
        return "path traversal not allowed"
    if not os.path.isfile(file_path):
        return "file not found"
    return None


def _resolve_editor() -> str | None:
    """Resolve editor from env var chain: COCOSEARCH_EDITOR → EDITOR → VISUAL."""
    return (
        os.environ.get("COCOSEARCH_EDITOR")
        or os.environ.get("EDITOR")
        or os.environ.get("VISUAL")
        or None
    )


def _build_editor_command(editor: str, file_path: str, line: int | None) -> list[str]:
    """Build editor command with line-number flag based on known editor patterns."""
    import shutil

    # Get the base editor name (handle paths like /usr/bin/vim)
    editor_base = os.path.basename(editor).lower()

    # Resolve editor binary path
    editor_path = shutil.which(editor) or editor

    if line is None or line < 1:
        return [editor_path, file_path]

    # VS Code family
    if editor_base in ("code", "code-insiders"):
        return [editor_path, "--goto", f"{file_path}:{line}"]

    # Vim family
    if editor_base in ("vim", "nvim", "vi"):
        return [editor_path, f"+{line}", file_path]

    # Nano
    if editor_base == "nano":
        return [editor_path, f"+{line}", file_path]

    # Emacs family
    if editor_base in ("emacs", "emacsclient"):
        return [editor_path, f"+{line}", file_path]

    # Sublime Text
    if editor_base in ("subl", "sublime", "sublime_text"):
        return [editor_path, f"{file_path}:{line}"]

    # JetBrains family
    if editor_base in (
        "idea",
        "goland",
        "pycharm",
        "webstorm",
        "phpstorm",
        "rubymine",
        "clion",
        "rider",
    ):
        return [editor_path, "--line", str(line), file_path]

    # Unknown editor — no line jump
    return [editor_path, file_path]


# ---------------------------------------------------------------------------
# AI Chat endpoints (optional — requires claude-agent-sdk)
# ---------------------------------------------------------------------------

try:
    from cocosearch.chat import (
        check_cli_available,
        get_session_manager,
        is_chat_available,
    )

    _chat_imported = True
except ImportError:
    _chat_imported = False


@mcp.custom_route("/api/ai-chat/status", methods=["GET"])
async def api_ai_chat_status(request) -> JSONResponse:
    """Check if AI chat feature is available."""
    if not _chat_imported or not is_chat_available():
        return JSONResponse(
            {"available": False, "reason": "claude-agent-sdk not installed"}
        )
    cli_found = check_cli_available()
    if not cli_found:
        return JSONResponse(
            {"available": False, "reason": "claude CLI not found on PATH"}
        )
    return JSONResponse({"available": True, "cli_found": True})


@mcp.custom_route("/api/ai-chat/start", methods=["POST"])
async def api_ai_chat_start(request) -> JSONResponse:
    """Create a new AI chat session."""
    if not _chat_imported or not is_chat_available():
        return JSONResponse({"error": "AI chat not available"}, status_code=503)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    index_name = body.get("index_name")
    project_path = body.get("project_path")
    if not index_name or not project_path:
        return JSONResponse(
            {"error": "index_name and project_path are required"}, status_code=400
        )

    mgr = get_session_manager()
    session = mgr.create_session(index_name, project_path)
    if session is None:
        return JSONResponse(
            {"error": "Maximum concurrent chat sessions reached"}, status_code=503
        )
    return JSONResponse({"session_id": session.session_id})


@mcp.custom_route("/api/ai-chat/stream", methods=["GET"])
async def api_ai_chat_stream(request) -> StreamingResponse:
    """Stream AI chat response as SSE."""
    import asyncio
    import json as _json

    if not _chat_imported or not is_chat_available():

        async def _err():
            yield f"data: {_json.dumps({'type': 'error', 'error': 'AI chat not available'})}\n\n"

        return StreamingResponse(_err(), media_type="text/event-stream")

    session_id = request.query_params.get("session_id", "")
    message = request.query_params.get("message", "")

    mgr = get_session_manager()
    session = mgr.get_session(session_id)

    if session is None:

        async def _err():
            yield f"data: {_json.dumps({'type': 'error', 'error': 'Session not found'})}\n\n"

        return StreamingResponse(_err(), media_type="text/event-stream")

    if not message:

        async def _err():
            yield f"data: {_json.dumps({'type': 'error', 'error': 'message parameter is required'})}\n\n"

        return StreamingResponse(_err(), media_type="text/event-stream")

    import queue as _queue

    response_queue: _queue.Queue = _queue.Queue()
    session.send_message(message, response_queue)

    async def event_stream():
        loop = asyncio.get_event_loop()
        while True:
            try:
                item = await loop.run_in_executor(None, response_queue.get, True, 120)
            except Exception:
                yield f"data: {_json.dumps({'type': 'error', 'error': 'Timeout waiting for response'})}\n\n"
                return

            yield f"data: {_json.dumps(item)}\n\n"
            if item.get("type") in ("done", "error"):
                return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@mcp.custom_route("/api/ai-chat/session", methods=["DELETE"])
async def api_ai_chat_session_delete(request) -> JSONResponse:
    """Close an AI chat session."""
    if not _chat_imported or not is_chat_available():
        return JSONResponse({"error": "AI chat not available"}, status_code=503)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    session_id = body.get("session_id", "")
    mgr = get_session_manager()
    if mgr.close_session(session_id):
        return JSONResponse({"success": True})
    return JSONResponse({"error": "Session not found"}, status_code=404)


@mcp.tool()
async def search_code(
    query: Annotated[str, Field(description="Natural language search query")],
    ctx: Context,
    index_name: Annotated[
        str | None,
        Field(
            description="Name of the index to search. If not provided, auto-detects from current working directory."
        ),
    ] = None,
    limit: Annotated[int, Field(description="Maximum results to return")] = 10,
    language: Annotated[
        str | None,
        Field(
            description="Filter by language (e.g., python, typescript, hcl, dockerfile, bash). "
            "Aliases: terraform=hcl, shell/sh=bash. Comma-separated for multiple."
        ),
    ] = None,
    use_hybrid_search: Annotated[
        bool | None,
        Field(
            description="Enable hybrid search (vector + keyword matching). "
            "None=auto (enabled for identifier patterns like camelCase/snake_case), "
            "True=always use hybrid, False=vector-only"
        ),
    ] = None,
    symbol_type: Annotated[
        str | list[str] | None,
        Field(
            description="Filter by symbol type. "
            "Single: 'function', 'class', 'method', 'interface'. "
            "Array: ['function', 'method'] for OR filtering."
        ),
    ] = None,
    symbol_name: Annotated[
        str | None,
        Field(
            description="Filter by symbol name pattern (glob). "
            "Examples: 'get*', 'User*Service', '*Handler'. "
            "Case-insensitive matching."
        ),
    ] = None,
    context_before: Annotated[
        int | None,
        Field(
            description="Number of lines to show before each match. "
            "Overrides smart context expansion when specified."
        ),
    ] = None,
    context_after: Annotated[
        int | None,
        Field(
            description="Number of lines to show after each match. "
            "Overrides smart context expansion when specified."
        ),
    ] = None,
    smart_context: Annotated[
        bool,
        Field(
            description="Expand context to enclosing function/class boundaries. "
            "Enabled by default. Set to False for exact line counts only."
        ),
    ] = True,
) -> list[dict]:
    """Search indexed code using natural language.

    Returns code chunks matching the query, ranked by semantic similarity.
    By default, context expands to enclosing function/class boundaries.
    Use context_before/context_after to specify exact line counts.
    Set smart_context=False to disable automatic boundary expansion.

    Supports hybrid search combining vector similarity and keyword matching
    for better results when searching for code identifiers.
    If index_name is not provided, auto-detects from current working directory.
    """
    # Track root_path for search header (set during auto-detection)
    root_path: Path | None = None
    auto_detected_source = None  # Track detection source for hint

    # Auto-detect index if not provided
    if index_name is None:
        detected_path, source = await _detect_project(ctx)
        auto_detected_source = source

        root_path = detected_path

        # Use find_project_root to walk up to actual git/config root from detected path
        from cocosearch.management.context import find_project_root

        project_root, detection_method = find_project_root(detected_path)
        if project_root is not None:
            root_path = project_root

        # Resolve index name using priority chain
        index_name = resolve_index_name(
            root_path, detection_method if project_root else None
        )
        logger.info(
            f"Auto-detected index: {index_name} from {root_path} (source: {source})"
        )

        # Check if index exists
        indexes = mgmt_list_indexes()
        index_names = {idx["name"] for idx in indexes}

        if index_name not in index_names:
            # Project detected but not indexed
            return [
                {
                    "error": "Index not found",
                    "message": (
                        f"Project detected at {root_path} but not indexed. "
                        f"Index this project first using:\n"
                        f"  CLI: cocosearch index {root_path}\n"
                        f"  MCP: index_codebase(path='{root_path}')"
                    ),
                    "detected_path": str(root_path),
                    "suggested_index_name": index_name,
                    "results": [],
                }
            ]

        # Check for collision (same index name, different path in metadata)
        metadata = get_index_metadata(index_name)
        if metadata is not None:
            canonical_cwd = str(root_path.resolve())
            stored_path = metadata.get("canonical_path", "")
            if stored_path and stored_path != canonical_cwd:
                # Collision detected
                return [
                    {
                        "error": "Index name collision",
                        "message": (
                            f"Index '{index_name}' is already mapped to a different project:\n"
                            f"  Stored: {stored_path}\n"
                            f"  Current: {canonical_cwd}\n\n"
                            f"To resolve:\n"
                            f"  1. Set explicit indexName in cocosearch.yaml, or\n"
                            f"  2. Specify index_name parameter explicitly"
                        ),
                        "results": [],
                    }
                ]

    # Initialize CocoIndex (required for embedding generation)
    try:
        _ensure_cocoindex_init()
    except Exception as e:
        logger.warning(f"CocoIndex init failed: {e}")
        return [
            {
                "error": "Database not initialized",
                "message": "Index a codebase first using index_codebase(path='.')",
                "results": [],
            }
        ]

    # Execute search
    try:
        results = search(
            query=query,
            index_name=index_name,
            limit=limit,
            language_filter=language,
            use_hybrid=use_hybrid_search,
            symbol_type=symbol_type,
            symbol_name=symbol_name,
        )
    except ValueError as e:
        # Symbol filter errors (invalid type or pre-v1.7 index)
        return [{"error": "Symbol filter error", "message": str(e), "results": []}]

    # Create context expander for file caching
    expander = ContextExpander()

    # Build header with project context when auto-detecting
    output = []
    if root_path is not None:
        search_header = {
            "type": "search_context",
            "searching": str(root_path),
            "index_name": index_name,
        }
        # Include last_indexed_at so LLM clients know when the index was built
        metadata = get_index_metadata(index_name)
        if metadata and metadata.get("updated_at"):
            search_header["last_indexed_at"] = str(metadata["updated_at"])
        output.append(search_header)

    # Convert results to dicts with line numbers, content, and context.
    # Wrap in try/finally to ensure expander cache is always cleared,
    # preventing LRU cache leaks (up to 128 files) on exceptions.
    try:
        for r in results:
            start_line = byte_to_line(r.filename, r.start_byte)
            end_line = byte_to_line(r.filename, r.end_byte)
            content = read_chunk_content(r.filename, r.start_byte, r.end_byte)

            # Get context if requested or smart context enabled
            context_before_text = ""
            context_after_text = ""

            if context_before is not None or context_after is not None or smart_context:
                # Determine language for smart expansion
                ext = os.path.splitext(r.filename)[1].lstrip(".")
                language_name = _get_treesitter_language(ext)

                before_lines, _match_lines, after_lines, _is_bof, _is_eof = (
                    expander.get_context_lines(
                        r.filename,
                        start_line,
                        end_line,
                        context_before=context_before or 0,
                        context_after=context_after or 0,
                        smart=smart_context
                        and (context_before is None and context_after is None),
                        language=language_name,
                    )
                )

                # Format context as strings (newline-separated)
                context_before_text = "\n".join(line for _, line in before_lines)
                context_after_text = "\n".join(line for _, line in after_lines)

            # Build result dict
            result_dict = {
                "file_path": r.filename,
                "start_line": start_line,
                "end_line": end_line,
                "score": r.score,
                "content": content,
                "block_type": r.block_type,
                "hierarchy": r.hierarchy,
                "language_id": r.language_id,
                # Symbol metadata (always included, None if not available)
                "symbol_type": r.symbol_type,
                "symbol_name": r.symbol_name,
                "symbol_signature": r.symbol_signature,
            }

            # Include context fields when context was requested
            if context_before_text or context_after_text:
                result_dict["context_before"] = context_before_text
                result_dict["context_after"] = context_after_text

            # Include hybrid search fields when available
            if r.match_type:
                result_dict["match_type"] = r.match_type
            if r.vector_score is not None:
                result_dict["vector_score"] = r.vector_score
            if r.keyword_score is not None:
                result_dict["keyword_score"] = r.keyword_score

            output.append(result_dict)
    finally:
        expander.clear_cache()

    # Add hint for clients without Roots support
    if auto_detected_source in ("env", "cwd"):
        output.append(
            {
                "type": "hint",
                "message": "Tip: Use Claude Code for automatic project detection via MCP Roots.",
            }
        )

    # Check branch staleness and add warning if needed
    try:
        from cocosearch.management.stats import check_branch_staleness

        branch_staleness = check_branch_staleness(index_name)
        if branch_staleness.get("branch_changed") or branch_staleness.get(
            "commits_changed"
        ):
            indexed_branch = branch_staleness.get("indexed_branch", "unknown")
            indexed_commit = branch_staleness.get("indexed_commit", "")
            current_branch = branch_staleness.get("current_branch", "unknown")
            current_commit = branch_staleness.get("current_commit", "")

            indexed_ref = f"'{indexed_branch}'"
            if indexed_commit:
                indexed_ref += f" ({indexed_commit})"
            current_ref = f"'{current_branch}'"
            if current_commit:
                current_ref += f" ({current_commit})"

            reindex_path = str(root_path) if root_path else "<path-to-project>"
            output.append(
                {
                    "type": "branch_staleness_warning",
                    "warning": "Index built from different branch",
                    "message": (
                        f"Index built from {indexed_ref}, "
                        f"current branch is {current_ref}. "
                        f"Results may be stale. "
                        f"Run `cocosearch index {reindex_path}` to update."
                    ),
                    "indexed_branch": indexed_branch,
                    "current_branch": current_branch,
                }
            )
    except Exception:
        pass  # Best-effort — don't block search on staleness check

    # Check staleness and add footer warning if needed
    try:
        is_stale, staleness_days = check_staleness(index_name, threshold_days=7)
    except Exception:
        # Database not available or other error - skip staleness check
        is_stale, staleness_days = False, -1

    if is_stale and staleness_days > 0:
        # Determine path for reindex command (use root_path if available)
        reindex_path = str(root_path) if root_path else "<path-to-project>"
        output.append(
            {
                "type": "staleness_warning",
                "warning": "Index may be stale",
                "message": (
                    f"Index last updated {staleness_days} days ago. "
                    f"Run `cocosearch index {reindex_path}` to refresh."
                ),
                "staleness_days": staleness_days,
            }
        )

    return output


@mcp.tool()
async def analyze_query(
    query: Annotated[str, Field(description="Search query to analyze")],
    ctx: Context,
    index_name: Annotated[
        str | None,
        Field(
            description="Name of the index to search. If not provided, auto-detects from current working directory."
        ),
    ] = None,
    limit: Annotated[int, Field(description="Maximum results to return")] = 10,
    language: Annotated[
        str | None,
        Field(
            description="Filter by language (e.g., python, typescript, hcl). "
            "Comma-separated for multiple."
        ),
    ] = None,
    use_hybrid_search: Annotated[
        bool | None,
        Field(
            description="Enable hybrid search. "
            "None=auto, True=always hybrid, False=vector-only"
        ),
    ] = None,
    symbol_type: Annotated[
        str | list[str] | None,
        Field(
            description="Filter by symbol type: 'function', 'class', 'method', 'interface'"
        ),
    ] = None,
    symbol_name: Annotated[
        str | None,
        Field(
            description="Filter by symbol name pattern (glob). Examples: 'get*', '*Handler'"
        ),
    ] = None,
) -> dict:
    """Analyze the search pipeline for a query with stage-by-stage diagnostics.

    Runs the same pipeline as search_code but captures diagnostics at each stage:
    query analysis, mode selection, cache status, vector search, keyword search,
    RRF fusion, definition boost, filtering, and per-stage timing breakdown.

    Use this to understand WHY a query returns specific results — which identifiers
    were detected, whether hybrid mode kicked in, how RRF scored results, or
    where time was spent.
    """
    # Auto-detect index if not provided (same logic as search_code)
    if index_name is None:
        detected_path, source = await _detect_project(ctx)
        root_path = detected_path

        from cocosearch.management.context import find_project_root

        project_root, detection_method = find_project_root(detected_path)
        if project_root is not None:
            root_path = project_root

        index_name = resolve_index_name(
            root_path, detection_method if project_root else None
        )

        # Check if index exists
        indexes = mgmt_list_indexes()
        index_names = {idx["name"] for idx in indexes}

        if index_name not in index_names:
            return {
                "error": "Index not found",
                "message": (
                    f"Project detected at {root_path} but not indexed. "
                    f"Index first: index_codebase(path='{root_path}')"
                ),
            }

    # Initialize CocoIndex
    try:
        _ensure_cocoindex_init()
    except Exception as e:
        logger.warning(f"CocoIndex init failed: {e}")
        return {
            "error": "Database not initialized",
            "message": "Index a codebase first using index_codebase(path='.')",
        }

    # Run analysis
    try:
        result = run_analyze(
            query=query,
            index_name=index_name,
            limit=limit,
            language_filter=language,
            use_hybrid=use_hybrid_search,
            symbol_type=symbol_type,
            symbol_name=symbol_name,
            no_cache=True,  # Always bypass cache for analysis
        )
        return result.to_dict()
    except ValueError as e:
        return {"error": "Analysis failed", "message": str(e)}
    except Exception as e:
        logger.error(f"Analyze failed: {e}")
        return {"error": "Analysis failed", "message": str(e)}


@mcp.tool()
def list_indexes() -> list[dict]:
    """List all available code indexes.

    Returns a list of indexes with their names and table names.
    """
    try:
        return mgmt_list_indexes()
    except Exception as e:
        logger.warning(f"Failed to list indexes: {e}")
        return []


@mcp.tool()
def index_stats(
    index_name: Annotated[
        str | None,
        Field(description="Name of the index (omit for all indexes)"),
    ] = None,
    include_failures: Annotated[
        bool,
        Field(
            description="Include individual file parse failure details. "
            "When True, adds a 'parse_failures' list with file paths, languages, statuses, and error messages."
        ),
    ] = False,
) -> dict | list[dict]:
    """Get statistics for code indexes including parse health.

    Returns file count, chunk count, storage size, language distribution,
    symbol counts, and parse failure breakdown per language.
    If index_name is provided, returns stats for that index only.
    Otherwise, returns stats for all indexes.
    """
    try:
        if index_name:
            return build_single_stats(index_name, include_failures)
        else:
            return build_all_stats(include_failures)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.warning(f"CocoIndex init failed (fresh database?): {e}")
        return {
            "success": False,
            "error": "Database not initialized. Index a codebase first: index_codebase(path='.')",
        }


@mcp.tool()
def clear_index(
    index_name: Annotated[str, Field(description="Name of the index to delete")],
) -> dict:
    """Clear (delete) a code index.

    WARNING: This permanently deletes all indexed data for this codebase.
    The operation cannot be undone.
    """
    try:
        # mgmt_clear_index also clears path metadata internally
        result = mgmt_clear_index(index_name)
        return result
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Failed to clear index: {e}"}


@mcp.tool()
def index_codebase(
    path: Annotated[str, Field(description="Path to the codebase directory to index")],
    index_name: Annotated[
        str | None,
        Field(
            description="Name for the index (auto-derived from path if not provided)"
        ),
    ] = None,
) -> dict:
    """Index a codebase directory for semantic search.

    Creates embeddings for all code files and stores them in the database.
    If the index already exists, it will be updated with any changes.
    """
    try:
        _ensure_cocoindex_init()

        # Derive index name if not provided
        if not index_name:
            index_name = derive_index_name(path)

        # Set status to 'indexing' before starting (best-effort)
        try:
            ensure_metadata_table()
            _register_with_git(index_name, path)
            set_index_status(index_name, "indexing")
        except Exception:
            pass  # Best-effort — don't block indexing on metadata failures

        # Run indexing with default config
        indexing_failed = False
        try:
            update_info = run_index(
                index_name=index_name,
                codebase_path=path,
                config=IndexingConfig(),
            )
        except Exception:
            indexing_failed = True
            raise
        finally:
            try:
                set_index_status(index_name, "error" if indexing_failed else "indexed")
            except Exception:
                pass

        # Register path-to-index mapping (enables collision detection)
        try:
            _register_with_git(index_name, path)
        except ValueError as collision_error:
            # Collision during indexing - warn but continue (index was created)
            logger.warning(f"Path registration warning: {collision_error}")

        # Extract stats from update_info
        stats = {
            "files_added": 0,
            "files_removed": 0,
            "files_updated": 0,
        }

        if hasattr(update_info, "stats") and isinstance(update_info.stats, dict):
            file_stats = update_info.stats.get("files", {})
            stats["files_added"] = file_stats.get("num_insertions", 0)
            stats["files_removed"] = file_stats.get("num_deletions", 0)
            stats["files_updated"] = file_stats.get("num_updates", 0)

        return {
            "success": True,
            "index_name": index_name,
            "path": path,
            "stats": stats,
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to index codebase: {e}"}


def _open_browser(url: str, delay: float = 1.5):
    """Open a browser to the given URL after a short delay.

    Uses a daemon timer thread so it doesn't block shutdown.
    """
    import threading
    import webbrowser

    def _open():
        try:
            webbrowser.open(url)
        except Exception:
            logger.debug("Could not open browser", exc_info=True)

    timer = threading.Timer(delay, _open)
    timer.daemon = True
    timer.start()


def run_server(
    transport: str = "stdio",
    host: str = "0.0.0.0",
    port: int = 3000,
):
    """Run the MCP server with specified transport.

    Args:
        transport: Transport protocol - "stdio", "sse", or "http"
        host: Host to bind to (ignored for stdio)
        port: Port to bind to (ignored for stdio)
    """
    # Log startup info (always to stderr)
    logger.info(f"Starting MCP server with transport: {transport}")

    # Dashboard auto-open (opt-out via COCOSEARCH_NO_DASHBOARD=1)
    no_dashboard = os.environ.get("COCOSEARCH_NO_DASHBOARD", "").strip() == "1"

    # Initialize CocoIndex before the event loop starts to avoid
    # "sync API called inside existing event loop" RuntimeWarning
    try:
        _ensure_cocoindex_init()
    except Exception as e:
        logger.warning(f"CocoIndex pre-init failed (will retry on demand): {e}")

    if transport == "stdio":
        if port != 3000:  # Non-default port specified
            logger.warning("--port is ignored with stdio transport")

        # Start background dashboard server for stdio mode
        if not no_dashboard:
            from cocosearch.dashboard.server import start_dashboard_server

            dashboard_url = start_dashboard_server()
            if dashboard_url:
                _open_browser(dashboard_url)

        mcp.run(transport="stdio")
    elif transport == "sse":
        # Suppress verbose per-request access logs from uvicorn
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        # Configure host/port for network transport
        mcp.settings.host = host
        mcp.settings.port = port
        logger.info(f"Connect at http://{host}:{port}/sse")
        logger.info(f"Health check at http://{host}:{port}/health")

        if not no_dashboard:
            dashboard_url = f"http://127.0.0.1:{port}/dashboard"
            _open_browser(dashboard_url)

        mcp.run(transport="sse")
    elif transport == "http":
        # Suppress verbose per-request access logs from uvicorn
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        # Configure host/port for network transport
        mcp.settings.host = host
        mcp.settings.port = port
        logger.info(f"Connect at http://{host}:{port}/mcp")
        logger.info(f"Health check at http://{host}:{port}/health")

        if not no_dashboard:
            dashboard_url = f"http://127.0.0.1:{port}/dashboard"
            _open_browser(dashboard_url)

        mcp.run(transport="streamable-http")
    else:
        # Should not reach here if CLI validates
        raise ValueError(f"Invalid transport: {transport}")
