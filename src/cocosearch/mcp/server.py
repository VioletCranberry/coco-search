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

from pathlib import Path  # noqa: E402
from typing import Annotated  # noqa: E402

import cocoindex  # noqa: E402
from mcp.server.fastmcp import Context, FastMCP  # noqa: E402
from pydantic import Field  # noqa: E402
from starlette.responses import HTMLResponse, JSONResponse  # noqa: E402

from cocosearch.cli import derive_index_name  # noqa: E402
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
from cocosearch.mcp.project_detection import (  # noqa: E402
    _detect_project,
    register_roots_notification,
)
from cocosearch.management.stats import (  # noqa: E402
    check_staleness,
    get_comprehensive_stats,
    get_parse_failures,
)
from cocosearch.search import byte_to_line, read_chunk_content, search  # noqa: E402
from cocosearch.search.context_expander import ContextExpander  # noqa: E402

# Create FastMCP server instance
mcp = FastMCP("cocosearch")
register_roots_notification(mcp)


# Health endpoint for Docker/orchestration
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint. Also see /dashboard for web UI."""
    return JSONResponse({"status": "ok"})


# Dashboard endpoint
@mcp.custom_route("/dashboard", methods=["GET"])
async def serve_dashboard(request):
    """Serve the web dashboard HTML."""
    html_content = get_dashboard_html()
    return HTMLResponse(content=html_content)


# Stats API endpoints
@mcp.custom_route("/api/stats", methods=["GET"])
async def api_stats(request):
    """Stats API endpoint for web dashboard and programmatic access."""
    # Initialize CocoIndex (required for database connection)
    try:
        cocoindex.init()
    except Exception as e:
        logger.warning(f"CocoIndex init failed: {e}")
        return JSONResponse(
            {"error": "Database not initialized. Index a codebase first."},
            status_code=503,
        )

    index_name = request.query_params.get("index")

    include_failures = (
        request.query_params.get("include_failures", "").lower() == "true"
    )

    if index_name:
        # Single index stats
        try:
            stats = get_comprehensive_stats(index_name)
            result = stats.to_dict()
            if include_failures:
                result["parse_failures"] = get_parse_failures(index_name)
            return JSONResponse(
                result, headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=404)
    else:
        # All indexes stats
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
        return JSONResponse(
            all_stats, headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )


@mcp.custom_route("/api/stats/{index_name}", methods=["GET"])
async def api_stats_single(request):
    """Stats for a single index by name."""
    # Initialize CocoIndex (required for database connection)
    try:
        cocoindex.init()
    except Exception as e:
        logger.warning(f"CocoIndex init failed: {e}")
        return JSONResponse(
            {"error": "Database not initialized. Index a codebase first."},
            status_code=503,
        )

    index_name = request.path_params["index_name"]
    include_failures = (
        request.query_params.get("include_failures", "").lower() == "true"
    )
    try:
        stats = get_comprehensive_stats(index_name)
        result = stats.to_dict()
        if include_failures:
            result["parse_failures"] = get_parse_failures(index_name)
        return JSONResponse(
            result, headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)


@mcp.custom_route("/api/reindex", methods=["POST"])
async def api_reindex(request):
    """Trigger reindexing of an existing index in a background thread."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    index_name = body.get("index_name")
    fresh = body.get("fresh", False)

    if not index_name:
        return JSONResponse({"error": "index_name is required"}, status_code=400)

    # Look up source path from metadata
    metadata = get_index_metadata(index_name)
    if not metadata or not metadata.get("canonical_path"):
        return JSONResponse(
            {"error": f"Index '{index_name}' not found or has no source path"},
            status_code=400,
        )

    source_path = metadata["canonical_path"]

    # Reject if a previous indexing thread is still alive
    prev = _active_indexing.get(index_name)
    if prev is not None and prev.is_alive():
        return JSONResponse(
            {"error": "Previous indexing still completing. Try again shortly."},
            status_code=409,
        )

    # Set status to indexing
    try:
        set_index_status(index_name, "indexing")
    except Exception:
        pass

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
            except Exception:
                pass
            _active_indexing.pop(index_name, None)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    _active_indexing[index_name] = thread

    action = "Fresh reindex" if fresh else "Reindex"
    return JSONResponse(
        {"success": True, "message": f"{action} started for '{index_name}'"}
    )


@mcp.custom_route("/api/project", methods=["GET"])
async def api_project(request):
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
async def api_index(request):
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

    # Reject if a previous indexing thread is still alive
    prev = _active_indexing.get(index_name)
    if prev is not None and prev.is_alive():
        return JSONResponse(
            {"error": "Previous indexing still completing. Try again shortly."},
            status_code=409,
        )

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
            except Exception:
                pass
            _active_indexing.pop(index_name, None)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    _active_indexing[index_name] = thread

    return JSONResponse(
        {
            "success": True,
            "index_name": index_name,
            "message": f"Indexing started for '{index_name}' from {project_path}",
        }
    )


@mcp.custom_route("/api/stop-indexing", methods=["POST"])
async def api_stop_indexing(request):
    """Stop an in-progress indexing operation."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    index_name = body.get("index_name")
    if not index_name:
        return JSONResponse({"error": "index_name is required"}, status_code=400)

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
async def api_delete_index(request):
    """Delete an index permanently."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    index_name = body.get("index_name")
    if not index_name:
        return JSONResponse({"error": "index_name is required"}, status_code=400)

    # Reject if indexing is currently active for this index
    prev = _active_indexing.get(index_name)
    if prev is not None and prev.is_alive():
        return JSONResponse(
            {"error": f"Cannot delete '{index_name}' while indexing is active. Stop indexing first."},
            status_code=409,
        )

    try:
        result = mgmt_clear_index(index_name)
        return JSONResponse(result)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": f"Failed to delete index: {e}"}, status_code=500)


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
        cocoindex.init()
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
        output.append(search_header)

    # Convert results to dicts with line numbers, content, and context
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

    # Clear cache after processing
    expander.clear_cache()

    # Add hint for clients without Roots support
    if auto_detected_source in ("env", "cwd"):
        output.append(
            {
                "type": "hint",
                "message": "Tip: Use Claude Code for automatic project detection via MCP Roots.",
            }
        )

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
    # Initialize CocoIndex (required for database connection)
    try:
        cocoindex.init()
    except Exception as e:
        logger.warning(f"CocoIndex init failed (fresh database?): {e}")
        return {
            "success": False,
            "error": "Database not initialized. Index a codebase first: index_codebase(path='.')",
        }

    try:
        if index_name:
            stats = get_comprehensive_stats(index_name)
            result = stats.to_dict()
            if include_failures:
                result["parse_failures"] = get_parse_failures(index_name)
            return result
        else:
            # Get stats for all indexes
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
                    pass
            return all_stats
    except ValueError as e:
        return {"success": False, "error": str(e)}


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
        # Initialize CocoIndex
        cocoindex.init()

        # Derive index name if not provided
        if not index_name:
            index_name = derive_index_name(path)

        # Set status to 'indexing' before starting (best-effort)
        try:
            ensure_metadata_table()
            register_index_path(index_name, path)
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
            register_index_path(index_name, path)
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
