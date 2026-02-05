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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

from pathlib import Path
from typing import Annotated

import cocoindex
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from starlette.responses import HTMLResponse, JSONResponse

from cocosearch.cli import derive_index_name
from cocosearch.dashboard.web import get_dashboard_html
from cocosearch.indexer import IndexingConfig, run_index
from cocosearch.management import clear_index as mgmt_clear_index
from cocosearch.management import get_stats, list_indexes as mgmt_list_indexes
from cocosearch.management import (
    find_project_root,
    resolve_index_name,
    get_index_metadata,
    register_index_path,
)
from cocosearch.management.stats import check_staleness, get_comprehensive_stats
from cocosearch.search import byte_to_line, read_chunk_content, search
from cocosearch.search.context_expander import ContextExpander

# Create FastMCP server instance
mcp = FastMCP("cocosearch")


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
    cocoindex.init()

    index_name = request.query_params.get("index")

    if index_name:
        # Single index stats
        try:
            stats = get_comprehensive_stats(index_name)
            return JSONResponse(
                stats.to_dict(),
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
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
                all_stats.append(stats.to_dict())
            except ValueError:
                continue
        return JSONResponse(
            all_stats,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )


@mcp.custom_route("/api/stats/{index_name}", methods=["GET"])
async def api_stats_single(request):
    """Stats for a single index by name."""
    # Initialize CocoIndex (required for database connection)
    cocoindex.init()

    index_name = request.path_params["index_name"]
    try:
        stats = get_comprehensive_stats(index_name)
        return JSONResponse(
            stats.to_dict(),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)


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
def search_code(
    query: Annotated[str, Field(description="Natural language search query")],
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

    # Check for explicit project path from --project-from-cwd flag
    project_path_env = os.environ.get("COCOSEARCH_PROJECT_PATH")

    # Auto-detect index if not provided
    if index_name is None:
        if project_path_env:
            # Use explicit path from --project-from-cwd flag
            start_path = Path(project_path_env)
            root_path, detection_method = find_project_root(start_path)
        else:
            root_path, detection_method = find_project_root()

        if root_path is None:
            # Not in a project directory
            return [{
                "error": "No project detected",
                "message": (
                    "Not in a git repository or directory with cocosearch.yaml. "
                    "Either navigate to your project directory, or specify index_name parameter explicitly."
                ),
                "results": []
            }]

        # Resolve index name using priority chain
        index_name = resolve_index_name(root_path, detection_method)
        logger.info(f"Auto-detected index: {index_name} from {root_path}")

        # Check if index exists
        indexes = mgmt_list_indexes()
        index_names = {idx["name"] for idx in indexes}

        if index_name not in index_names:
            # Project detected but not indexed
            return [{
                "error": "Index not found",
                "message": (
                    f"Project detected at {root_path} but not indexed. "
                    f"Index this project first using:\n"
                    f"  CLI: cocosearch index {root_path}\n"
                    f"  MCP: index_codebase(path='{root_path}')"
                ),
                "detected_path": str(root_path),
                "suggested_index_name": index_name,
                "results": []
            }]

        # Check for collision (same index name, different path in metadata)
        metadata = get_index_metadata(index_name)
        if metadata is not None:
            canonical_cwd = str(root_path.resolve())
            stored_path = metadata.get("canonical_path", "")
            if stored_path and stored_path != canonical_cwd:
                # Collision detected
                return [{
                    "error": "Index name collision",
                    "message": (
                        f"Index '{index_name}' is already mapped to a different project:\n"
                        f"  Stored: {stored_path}\n"
                        f"  Current: {canonical_cwd}\n\n"
                        f"To resolve:\n"
                        f"  1. Set explicit indexName in cocosearch.yaml, or\n"
                        f"  2. Specify index_name parameter explicitly"
                    ),
                    "results": []
                }]

    # Initialize CocoIndex (required for embedding generation)
    cocoindex.init()

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
        return [{
            "error": "Symbol filter error",
            "message": str(e),
            "results": []
        }]

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

            before_lines, _match_lines, after_lines, _is_bof, _is_eof = expander.get_context_lines(
                r.filename,
                start_line,
                end_line,
                context_before=context_before or 0,
                context_after=context_after or 0,
                smart=smart_context and (context_before is None and context_after is None),
                language=language_name,
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

    # Check staleness and add footer warning if needed
    try:
        is_stale, staleness_days = check_staleness(index_name, threshold_days=7)
    except Exception:
        # Database not available or other error - skip staleness check
        is_stale, staleness_days = False, -1

    if is_stale and staleness_days > 0:
        # Determine path for reindex command (use root_path if available)
        reindex_path = str(root_path) if root_path else f"<path-to-project>"
        output.append({
            "type": "staleness_warning",
            "warning": "Index may be stale",
            "message": (
                f"Index last updated {staleness_days} days ago. "
                f"Run `cocosearch index {reindex_path}` to refresh."
            ),
            "staleness_days": staleness_days,
        })

    return output


@mcp.tool()
def list_indexes() -> list[dict]:
    """List all available code indexes.

    Returns a list of indexes with their names and table names.
    """
    return mgmt_list_indexes()


@mcp.tool()
def index_stats(
    index_name: Annotated[
        str | None,
        Field(description="Name of the index (omit for all indexes)"),
    ] = None,
) -> dict | list[dict]:
    """Get statistics for code indexes.

    Returns file count, chunk count, and storage size.
    If index_name is provided, returns stats for that index only.
    Otherwise, returns stats for all indexes.
    """
    try:
        if index_name:
            return get_stats(index_name)
        else:
            # Get stats for all indexes
            indexes = mgmt_list_indexes()
            stats = []
            for idx in indexes:
                try:
                    idx_stats = get_stats(idx["name"])
                    stats.append(idx_stats)
                except ValueError:
                    # Skip indexes that fail (shouldn't happen normally)
                    pass
            return stats
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
        Field(description="Name for the index (auto-derived from path if not provided)"),
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

        # Run indexing with default config
        update_info = run_index(
            index_name=index_name,
            codebase_path=path,
            config=IndexingConfig(),
        )

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

    if transport == "stdio":
        if port != 3000:  # Non-default port specified
            logger.warning("--port is ignored with stdio transport")
        mcp.run(transport="stdio")
    elif transport == "sse":
        # Configure host/port for network transport
        mcp.settings.host = host
        mcp.settings.port = port
        logger.info(f"Connect at http://{host}:{port}/sse")
        logger.info(f"Health check at http://{host}:{port}/health")
        mcp.run(transport="sse")
    elif transport == "http":
        # Configure host/port for network transport
        mcp.settings.host = host
        mcp.settings.port = port
        logger.info(f"Connect at http://{host}:{port}/mcp")
        logger.info(f"Health check at http://{host}:{port}/health")
        mcp.run(transport="streamable-http")
    else:
        # Should not reach here if CLI validates
        raise ValueError(f"Invalid transport: {transport}")
