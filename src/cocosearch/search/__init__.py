"""Search module for cocosearch.

Provides semantic code search functionality using vector similarity
queries against PostgreSQL with pgvector.

Also provides hybrid search combining vector and keyword matching for
improved results on code identifier queries.
"""

from cocosearch.search.query import SearchResult, search
from cocosearch.search.utils import byte_to_line, read_chunk_content

# Note: SearchREPL and run_repl are not exported here to avoid circular imports.
# Import them directly from cocosearch.search.repl when needed.

__all__ = [
    # Core search
    "search",
    "SearchResult",
    # Result utilities
    "byte_to_line",
    "read_chunk_content",
]
