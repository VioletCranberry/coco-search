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
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

from typing import Annotated

import cocoindex
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from starlette.responses import JSONResponse

from cocosearch.cli import derive_index_name
from cocosearch.indexer import IndexingConfig, run_index
from cocosearch.management import clear_index as mgmt_clear_index
from cocosearch.management import get_stats, list_indexes as mgmt_list_indexes
from cocosearch.management import (
    find_project_root,
    resolve_index_name,
    get_index_metadata,
    register_index_path,
)
from cocosearch.search import byte_to_line, read_chunk_content, search

# Create FastMCP server instance
mcp = FastMCP("cocosearch")


# Health endpoint for Docker/orchestration
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint for Docker HEALTHCHECK and load balancers."""
    return JSONResponse({"status": "ok"})


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
) -> list[dict]:
    """Search indexed code using natural language.

    Returns code chunks matching the query, ranked by semantic similarity.
    If index_name is not provided, auto-detects from current working directory.
    """
    # Auto-detect index if not provided
    if index_name is None:
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
    results = search(
        query=query,
        index_name=index_name,
        limit=limit,
        language_filter=language,
    )

    # Convert results to dicts with line numbers and content
    output = []
    for r in results:
        start_line = byte_to_line(r.filename, r.start_byte)
        end_line = byte_to_line(r.filename, r.end_byte)
        content = read_chunk_content(r.filename, r.start_byte, r.end_byte)

        output.append(
            {
                "file_path": r.filename,
                "start_line": start_line,
                "end_line": end_line,
                "score": r.score,
                "content": content,
                "block_type": r.block_type,
                "hierarchy": r.hierarchy,
                "language_id": r.language_id,
            }
        )

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
