"""Database operations for dependency edge storage.

Provides functions to create, drop, and populate the dependency edges
table in PostgreSQL. Uses the shared connection pool from
``cocosearch.search.db``.
"""

import json
import logging

from cocosearch.deps.models import (
    DependencyEdge,
    get_deps_table_name,
    get_tracking_table_name,
)
from cocosearch.search.db import get_connection_pool

logger = logging.getLogger(__name__)


def create_deps_table(index_name: str) -> None:
    """Create the dependency edges table and its indexes.

    Creates the table with columns for source/target file and symbol,
    dependency type, JSONB metadata, and a timestamp. Also creates
    indexes on frequently queried column combinations.

    Uses IF NOT EXISTS so the operation is idempotent.

    Args:
        index_name: The index name (validated for safe SQL use).
    """
    table_name = get_deps_table_name(index_name)
    pool = get_connection_pool()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id SERIAL PRIMARY KEY,
                    source_file TEXT NOT NULL,
                    source_symbol TEXT,
                    target_file TEXT,
                    target_symbol TEXT,
                    dep_type TEXT NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{table_name}_source
                ON {table_name} (source_file, dep_type)
            """)

            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{table_name}_target
                ON {table_name} (target_file, target_symbol)
            """)

            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{table_name}_dep_type
                ON {table_name} (dep_type)
            """)

        conn.commit()

    logger.debug("Created deps table %s", table_name)


def drop_deps_table(index_name: str) -> None:
    """Drop the dependency edges table if it exists.

    Args:
        index_name: The index name (validated for safe SQL use).
    """
    table_name = get_deps_table_name(index_name)
    pool = get_connection_pool()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {table_name}")

        conn.commit()

    logger.info("Dropped deps table %s", table_name)


def insert_edges(index_name: str, edges: list[DependencyEdge]) -> None:
    """Batch insert dependency edges into the database.

    Empty list is a no-op (no database calls are made).

    Args:
        index_name: The index name (validated for safe SQL use).
        edges: List of dependency edges to insert.
    """
    if not edges:
        return

    table_name = get_deps_table_name(index_name)
    pool = get_connection_pool()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                f"""
                INSERT INTO {table_name}
                    (source_file, source_symbol, target_file,
                     target_symbol, dep_type, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        edge.source_file,
                        edge.source_symbol,
                        edge.target_file,
                        edge.target_symbol,
                        edge.dep_type,
                        json.dumps(edge.metadata),
                    )
                    for edge in edges
                ],
            )

        conn.commit()

    logger.debug("Inserted %d edges into %s", len(edges), table_name)


def truncate_deps_table(index_name: str) -> None:
    """Truncate the dependency edges table (faster than DROP+CREATE).

    Args:
        index_name: The index name (validated for safe SQL use).
    """
    table_name = get_deps_table_name(index_name)
    pool = get_connection_pool()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE {table_name}")

        conn.commit()

    logger.debug("Truncated deps table %s", table_name)


def read_edges_excluding(
    index_name: str, exclude_files: set[str]
) -> list[DependencyEdge]:
    """Read all edges from the deps table, excluding edges from certain source files.

    Args:
        index_name: The index name (validated for safe SQL use).
        exclude_files: Set of source_file values to exclude.

    Returns:
        List of DependencyEdge objects for non-excluded source files.
    """
    table_name = get_deps_table_name(index_name)
    pool = get_connection_pool()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            if exclude_files:
                placeholders = ",".join(["%s"] * len(exclude_files))
                cur.execute(
                    f"SELECT source_file, source_symbol, target_file, "
                    f"target_symbol, dep_type, metadata "
                    f"FROM {table_name} "
                    f"WHERE source_file NOT IN ({placeholders})",
                    tuple(exclude_files),
                )
            else:
                cur.execute(
                    f"SELECT source_file, source_symbol, target_file, "
                    f"target_symbol, dep_type, metadata "
                    f"FROM {table_name}"
                )

            rows = cur.fetchall()

    edges = []
    for row in rows:
        source_file, source_symbol, target_file, target_symbol, dep_type, metadata = row
        edges.append(
            DependencyEdge(
                source_file=source_file,
                source_symbol=source_symbol,
                target_file=target_file,
                target_symbol=target_symbol,
                dep_type=dep_type,
                metadata=metadata
                if isinstance(metadata, dict)
                else json.loads(metadata or "{}"),
            )
        )

    return edges


def create_tracking_table(index_name: str) -> None:
    """Create the dependency tracking table for content hashes.

    Uses IF NOT EXISTS so the operation is idempotent.

    Args:
        index_name: The index name (validated for safe SQL use).
    """
    table_name = get_tracking_table_name(index_name)
    pool = get_connection_pool()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    filename TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    language_id TEXT NOT NULL
                )
            """)

        conn.commit()

    logger.debug("Created tracking table %s", table_name)


def drop_tracking_table(index_name: str) -> None:
    """Drop the dependency tracking table if it exists.

    Args:
        index_name: The index name (validated for safe SQL use).
    """
    table_name = get_tracking_table_name(index_name)
    pool = get_connection_pool()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {table_name}")

        conn.commit()

    logger.info("Dropped tracking table %s", table_name)


def get_stored_hashes(index_name: str) -> dict[str, str]:
    """Get stored content hashes from the tracking table.

    Args:
        index_name: The index name (validated for safe SQL use).

    Returns:
        Dict mapping filename to content_hash.
    """
    table_name = get_tracking_table_name(index_name)
    pool = get_connection_pool()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT filename, content_hash FROM {table_name}")
            rows = cur.fetchall()

    return {filename: content_hash for filename, content_hash in rows}


def update_tracking(index_name: str, file_hashes: dict[str, tuple[str, str]]) -> None:
    """Replace all tracking entries with current file hashes.

    Truncates the tracking table and inserts all current entries.

    Args:
        index_name: The index name (validated for safe SQL use).
        file_hashes: Dict mapping filename to (content_hash, language_id).
    """
    table_name = get_tracking_table_name(index_name)
    pool = get_connection_pool()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE {table_name}")

            if file_hashes:
                cur.executemany(
                    f"INSERT INTO {table_name} (filename, content_hash, language_id) "
                    f"VALUES (%s, %s, %s)",
                    [
                        (filename, content_hash, language_id)
                        for filename, (content_hash, language_id) in file_hashes.items()
                    ],
                )

        conn.commit()

    logger.debug(
        "Updated tracking table %s with %d entries", table_name, len(file_hashes)
    )
