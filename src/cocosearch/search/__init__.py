"""Search module for cocosearch.

Provides semantic code search functionality using vector similarity
queries against PostgreSQL with pgvector.
"""

from cocosearch.search.db import get_connection_pool, get_table_name
from cocosearch.search.formatter import format_json, format_pretty
from cocosearch.search.query import SearchResult, search
from cocosearch.search.utils import byte_to_line, get_context_lines, read_chunk_content

__all__ = [
    "get_connection_pool",
    "get_table_name",
    "search",
    "SearchResult",
    "byte_to_line",
    "read_chunk_content",
    "get_context_lines",
    "format_json",
    "format_pretty",
]
