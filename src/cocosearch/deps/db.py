"""Database operations for dependency edge storage.

Provides functions to create, drop, and populate the dependency edges
table in PostgreSQL. Uses the shared connection pool from
``cocosearch.search.db``.
"""

import json
import logging

from cocosearch.deps.models import DependencyEdge, get_deps_table_name
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

    logger.info("Created deps table %s", table_name)


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
            for edge in edges:
                cur.execute(
                    f"""
                    INSERT INTO {table_name}
                        (source_file, source_symbol, target_file,
                         target_symbol, dep_type, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        edge.source_file,
                        edge.source_symbol,
                        edge.target_file,
                        edge.target_symbol,
                        edge.dep_type,
                        json.dumps(edge.metadata),
                    ),
                )

        conn.commit()

    logger.info("Inserted %d edges into %s", len(edges), table_name)
