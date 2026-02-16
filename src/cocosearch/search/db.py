"""Database connection module for cocosearch search.

Provides connection pool management and table name resolution for
querying CocoIndex-created vector tables in PostgreSQL.
"""

import logging
import threading

from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from cocosearch.config.env_validation import get_database_url
from cocosearch.validation import validate_index_name

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()

# Module-level cache for symbol column availability per table
_symbol_columns_available: dict[str, bool] = {}


def get_connection_pool() -> ConnectionPool:
    """Get or create the database connection pool.

    Creates a singleton connection pool with pgvector type registration.
    Uses double-checked locking to prevent duplicate pool creation under
    concurrent access.

    The pool reads the database URL from COCOSEARCH_DATABASE_URL environment
    variable, falling back to the default if not set.

    On fresh databases where the pgvector extension hasn't been created yet,
    vector registration is skipped gracefully — non-vector queries (list,
    stats, information_schema lookups) will still work.

    Returns:
        ConnectionPool configured with pgvector support (when available).
    """
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                conninfo = get_database_url()

                def configure(conn):
                    try:
                        register_vector(conn)
                    except Exception as e:
                        # pgvector extension not installed yet (fresh database).
                        # Non-vector queries will still work; vector search will
                        # fail with a clear error when actually attempted.
                        logger.debug(f"pgvector registration skipped: {e}")

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

    Validates index_name to prevent SQL injection via dynamic table names.

    Args:
        index_name: The name of the search index.

    Returns:
        PostgreSQL table name following CocoIndex convention.

    Raises:
        ValueError: If index_name contains invalid characters.
    """
    validate_index_name(index_name)
    # CocoIndex lowercases flow names
    flow_name = f"codeindex_{index_name}"
    target_name = f"{index_name}_chunks"
    return f"{flow_name}__{target_name}"


def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table.

    Used for feature detection when schema versions differ
    (e.g., hybrid search requires content_text column added in v1.7).

    Args:
        table_name: Full table name (e.g., "codeindex_myproject__myproject_chunks")
        column_name: Column name to check (e.g., "content_text")

    Returns:
        True if column exists, False otherwise.
    """
    pool = get_connection_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = %s AND column_name = %s
                )
                """,
                (table_name, column_name),
            )
            result = cur.fetchone()
            return result[0] if result else False


def check_symbol_columns_exist(table_name: str) -> bool:
    """Check if symbol columns exist in a table.

    Uses module-level caching to avoid repeated database queries.
    Pre-v1.7 indexes lack symbol columns; this enables graceful degradation.

    Args:
        table_name: Full table name (e.g., "codeindex_myproject__myproject_chunks")

    Returns:
        True if all symbol columns (symbol_type, symbol_name, symbol_signature) exist.
    """
    # Check cache first
    if table_name in _symbol_columns_available:
        return _symbol_columns_available[table_name]

    # Query database
    result = _check_all_symbol_columns(table_name)
    _symbol_columns_available[table_name] = result

    if not result:
        logger.info(f"Index {table_name} lacks symbol columns (pre-v1.7)")

    return result


def _check_all_symbol_columns(table_name: str) -> bool:
    """Internal: Check if all three symbol columns exist."""
    required_columns = {"symbol_type", "symbol_name", "symbol_signature"}
    existing = set()

    pool = get_connection_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND column_name = ANY(%s)
                """,
                (table_name, list(required_columns)),
            )
            existing = {row[0] for row in cur.fetchall()}

    return existing == required_columns


def reset_symbol_columns_cache() -> None:
    """Reset the symbol columns availability cache.

    Used by tests to ensure clean state between test runs.
    """
    global _symbol_columns_available
    _symbol_columns_available = {}
