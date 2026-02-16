"""MCP server module for cocosearch.

Provides Model Context Protocol server for LLM integration,
exposing tools for searching and managing code indexes.
"""

from cocosearch.mcp.server import run_server

__all__ = [
    "run_server",
]
