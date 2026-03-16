"""Search module for cocosearch.

Provides semantic code search functionality using vector similarity
queries against PostgreSQL with pgvector.

Also provides hybrid search combining vector and keyword matching for
improved results on code identifier queries.
"""

from cocosearch.search.analyze import AnalysisResult, MultiAnalysisResult, analyze, multi_analyze
from cocosearch.search.multi import multi_search
from cocosearch.search.query import SearchResult, search
from cocosearch.search.utils import byte_to_line, read_chunk_content

# Note: SearchREPL and run_repl are not exported here to avoid circular imports.
# Import them directly from cocosearch.search.repl when needed.

__all__ = [
    # Core search
    "search",
    "multi_search",
    "SearchResult",
    # Pipeline analysis
    "analyze",
    "multi_analyze",
    "AnalysisResult",
    "MultiAnalysisResult",
    # Result utilities
    "byte_to_line",
    "read_chunk_content",
]
