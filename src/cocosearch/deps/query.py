"""Query API for looking up dependency graph edges.

Provides functions for forward lookups (what does a file depend on?),
reverse lookups (what depends on a file?), and aggregate statistics.
All queries target the ``cocosearch_deps_{index}`` table created by
``cocosearch.deps.db``.
"""

import json
import logging

from cocosearch.deps.models import DependencyEdge, get_deps_table_name
from cocosearch.search.db import get_connection_pool

logger = logging.getLogger(__name__)


def _row_to_edge(row: tuple) -> DependencyEdge:
    """Convert a database row to a DependencyEdge.

    Args:
        row: Tuple of (source_file, source_symbol, target_file,
            target_symbol, dep_type, metadata_json).

    Returns:
        A DependencyEdge with deserialized metadata.
    """
    source_file, source_symbol, target_file, target_symbol, dep_type, metadata_json = (
        row
    )
    metadata = (
        metadata_json
        if isinstance(metadata_json, dict)
        else json.loads(metadata_json)
        if metadata_json is not None
        else {}
    )
    return DependencyEdge(
        source_file=source_file,
        source_symbol=source_symbol,
        target_file=target_file,
        target_symbol=target_symbol,
        dep_type=dep_type,
        metadata=metadata,
    )


def get_dependencies(
    index_name: str,
    file: str,
    symbol: str | None = None,
    dep_type: str | None = None,
) -> list[DependencyEdge]:
    """Forward lookup: what does this file/symbol depend on?

    Queries the dependency edges table for all rows where the given
    file (and optionally symbol) is the source.

    Args:
        index_name: The index name (validated for safe SQL use).
        file: Source file path to look up.
        symbol: Optional source symbol name to filter by.
        dep_type: Optional dependency type to filter by.

    Returns:
        List of DependencyEdge objects ordered by id.
    """
    table_name = get_deps_table_name(index_name)
    pool = get_connection_pool()

    conditions = ["source_file = %s"]
    params: list[str] = [file]

    if symbol is not None:
        conditions.append("source_symbol = %s")
        params.append(symbol)

    if dep_type is not None:
        conditions.append("dep_type = %s")
        params.append(dep_type)

    where_clause = " AND ".join(conditions)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT source_file, source_symbol, target_file,
                       target_symbol, dep_type, metadata
                FROM {table_name}
                WHERE {where_clause}
                ORDER BY id
                """,
                tuple(params),
            )
            rows = cur.fetchall()

    return [_row_to_edge(row) for row in rows]


def get_dependents(
    index_name: str,
    file: str,
    symbol: str | None = None,
    dep_type: str | None = None,
) -> list[DependencyEdge]:
    """Reverse lookup: what depends on this file/symbol?

    Queries the dependency edges table for all rows where the given
    file (and optionally symbol) is the target.

    Args:
        index_name: The index name (validated for safe SQL use).
        file: Target file path to look up.
        symbol: Optional target symbol name to filter by.
        dep_type: Optional dependency type to filter by.

    Returns:
        List of DependencyEdge objects ordered by id.
    """
    table_name = get_deps_table_name(index_name)
    pool = get_connection_pool()

    conditions = ["target_file = %s"]
    params: list[str] = [file]

    if symbol is not None:
        conditions.append("target_symbol = %s")
        params.append(symbol)

    if dep_type is not None:
        conditions.append("dep_type = %s")
        params.append(dep_type)

    where_clause = " AND ".join(conditions)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT source_file, source_symbol, target_file,
                       target_symbol, dep_type, metadata
                FROM {table_name}
                WHERE {where_clause}
                ORDER BY id
                """,
                tuple(params),
            )
            rows = cur.fetchall()

    return [_row_to_edge(row) for row in rows]


def get_dep_stats(index_name: str) -> dict:
    """Get aggregate statistics for the dependency graph.

    Args:
        index_name: The index name (validated for safe SQL use).

    Returns:
        Dict with ``total_edges`` count.
    """
    table_name = get_deps_table_name(index_name)
    pool = get_connection_pool()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            row = cur.fetchone()

    total = row[0] if row else 0
    return {"total_edges": total}
