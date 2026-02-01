"""Database connection module for cocosearch search.

Provides connection pool management and table name resolution for
querying CocoIndex-created vector tables in PostgreSQL.
"""

import os

from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def get_connection_pool() -> ConnectionPool:
    """Get or create the database connection pool.

    Creates a singleton connection pool with pgvector type registration.
    The pool reads the database URL from COCOSEARCH_DATABASE_URL environment
    variable.

    Returns:
        ConnectionPool configured with pgvector support.

    Raises:
        ValueError: If COCOSEARCH_DATABASE_URL is not set.
    """
    global _pool
    if _pool is None:
        conninfo = os.getenv("COCOSEARCH_DATABASE_URL")
        if not conninfo:
            raise ValueError("Missing COCOSEARCH_DATABASE_URL. See .env.example for format.")

        def configure(conn):
            register_vector(conn)

        _pool = ConnectionPool(
            conninfo=conninfo,
            configure=configure,
        )
    return _pool


def get_table_name(index_name: str) -> str:
    """Get the PostgreSQL table name for an index.

    CocoIndex naming convention: {flow_name}__{target_name}
    Flow name: CodeIndex_{index_name} (lowercased by CocoIndex)
    Target name: {index_name}_chunks
    Result: codeindex_{index_name}__{index_name}_chunks

    Args:
        index_name: The name of the search index.

    Returns:
        PostgreSQL table name following CocoIndex convention.
    """
    # CocoIndex lowercases flow names
    flow_name = f"codeindex_{index_name}"
    target_name = f"{index_name}_chunks"
    return f"{flow_name}__{target_name}"
