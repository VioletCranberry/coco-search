"""MCP server module for cocosearch.

Provides Model Context Protocol server for LLM integration,
exposing tools for searching and managing code indexes.
"""

from cocosearch.mcp.project_detection import (
    _detect_project,
    file_uri_to_path,
    register_roots_notification,
)
from cocosearch.mcp.server import mcp, run_server

__all__ = [
    "mcp",
    "run_server",
    "file_uri_to_path",
    "_detect_project",
    "register_roots_notification",
]
