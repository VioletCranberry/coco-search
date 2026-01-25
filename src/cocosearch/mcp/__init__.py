"""MCP server module for cocosearch.

Provides Model Context Protocol server for LLM integration,
exposing tools for searching and managing code indexes.
"""

from cocosearch.mcp.server import mcp, run_server

__all__ = ["mcp", "run_server"]
