"""Search module for cocosearch.

Provides semantic code search functionality using vector similarity
queries against PostgreSQL with pgvector.

Also provides hybrid search combining vector and keyword matching for
improved results on code identifier queries.
"""

from cocosearch.search.db import get_connection_pool, get_table_name
from cocosearch.search.filters import build_symbol_where_clause, glob_to_sql_pattern
from cocosearch.search.formatter import format_json, format_pretty
from cocosearch.search.hybrid import (
    HybridSearchResult,
    execute_keyword_search,
    hybrid_search,
    rrf_fusion,
)
from cocosearch.search.query import SearchResult, search
from cocosearch.search.query_analyzer import (
    has_identifier_pattern,
    normalize_query_for_keyword,
)
from cocosearch.search.utils import byte_to_line, get_context_lines, read_chunk_content

# Note: SearchREPL and run_repl are not exported here to avoid circular imports.
# Import them directly from cocosearch.search.repl when needed.

__all__ = [
    # Database utilities
    "get_connection_pool",
    "get_table_name",
    # Core search
    "search",
    "SearchResult",
    # Symbol filters
    "build_symbol_where_clause",
    "glob_to_sql_pattern",
    # Hybrid search
    "hybrid_search",
    "rrf_fusion",
    "execute_keyword_search",
    "HybridSearchResult",
    # Query analysis
    "has_identifier_pattern",
    "normalize_query_for_keyword",
    # Result utilities
    "byte_to_line",
    "read_chunk_content",
    "get_context_lines",
    # Formatters
    "format_json",
    "format_pretty",
]
