"""Search module for cocosearch.

Provides semantic code search functionality using vector similarity
queries against PostgreSQL with pgvector.
"""

from cocosearch.search.db import get_connection_pool, get_table_name
from cocosearch.search.query import SearchResult, search

__all__ = ["get_connection_pool", "get_table_name", "search", "SearchResult"]
