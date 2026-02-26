"""Query API for looking up dependency graph edges.

Provides functions for forward lookups (what does a file depend on?),
reverse lookups (what depends on a file?), transitive BFS traversals
(full dependency tree and impact analysis), and aggregate statistics.
All queries target the ``cocosearch_deps_{index}`` table created by
``cocosearch.deps.db``.
"""

from __future__ import annotations

import json
import logging
from collections import deque

from cocosearch.deps.models import DependencyEdge, DependencyTree, get_deps_table_name
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


def get_dependency_tree(
    index_name: str,
    file: str,
    max_depth: int = 5,
    dep_type: str | None = None,
) -> DependencyTree:
    """Forward BFS: build a transitive dependency tree.

    Starting from *file*, follows ``target_file`` links to discover
    what this file depends on transitively.  Cycles are detected via
    a visited set.

    Args:
        index_name: The index name.
        file: Root file path.
        max_depth: Maximum traversal depth (default 5).
        dep_type: Optional dependency type filter.

    Returns:
        A DependencyTree rooted at *file*.
    """
    root = DependencyTree(file=file, symbol=None, dep_type="root", children=[])
    visited: set[str] = {file}

    # BFS queue: (parent_tree_node, depth)
    queue: deque[tuple[DependencyTree, int]] = deque([(root, 0)])

    while queue:
        node, depth = queue.popleft()
        if depth >= max_depth:
            continue

        edges = get_dependencies(index_name, node.file, dep_type=dep_type)
        for edge in edges:
            target = edge.target_file
            if target is None:
                # External/unresolved dependency — add as non-traversable leaf
                ext_label = (
                    edge.metadata.get("module")
                    or edge.metadata.get("ref")
                    or edge.target_symbol
                    or "unknown"
                )
                child = DependencyTree(
                    file=ext_label,
                    symbol=edge.target_symbol,
                    dep_type=edge.dep_type,
                    children=[],
                    is_external=True,
                )
                node.children.append(child)
                continue
            if target in visited:
                continue
            visited.add(target)
            child = DependencyTree(
                file=target,
                symbol=edge.target_symbol,
                dep_type=edge.dep_type,
                children=[],
            )
            node.children.append(child)
            queue.append((child, depth + 1))

    return root


def get_impact(
    index_name: str,
    file: str,
    max_depth: int = 5,
    dep_type: str | None = None,
) -> DependencyTree:
    """Reverse BFS: build an impact tree.

    Starting from *file*, follows ``source_file`` links to discover
    what would be impacted if this file changes.  Cycles are detected
    via a visited set.

    Args:
        index_name: The index name.
        file: Root file path.
        max_depth: Maximum traversal depth (default 5).
        dep_type: Optional dependency type filter.

    Returns:
        A DependencyTree rooted at *file*, with children being files
        that depend on it (transitively).
    """
    root = DependencyTree(file=file, symbol=None, dep_type="root", children=[])
    visited: set[str] = {file}

    queue: deque[tuple[DependencyTree, int]] = deque([(root, 0)])

    while queue:
        node, depth = queue.popleft()
        if depth >= max_depth:
            continue

        edges = get_dependents(index_name, node.file, dep_type=dep_type)
        for edge in edges:
            source = edge.source_file
            if source in visited:
                continue
            visited.add(source)
            child = DependencyTree(
                file=source,
                symbol=edge.source_symbol,
                dep_type=edge.dep_type,
                children=[],
            )
            node.children.append(child)
            queue.append((child, depth + 1))

    return root


def get_dep_stats_detailed(index_name: str) -> dict:
    """Get detailed dependency graph statistics.

    Returns per-type edge counts, per-language breakdown, and
    top files by connection count.

    Args:
        index_name: The index name.

    Returns:
        Dict with ``total_edges``, ``by_type``, ``top_sources``,
        and ``top_targets``.
    """
    table_name = get_deps_table_name(index_name)
    pool = get_connection_pool()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            # Total
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            total = cur.fetchone()[0]

            # By type
            cur.execute(
                f"SELECT dep_type, COUNT(*) FROM {table_name} "
                f"GROUP BY dep_type ORDER BY COUNT(*) DESC"
            )
            by_type = {row[0]: row[1] for row in cur.fetchall()}

            # Top sources (files with most outgoing edges)
            cur.execute(
                f"SELECT source_file, COUNT(*) as cnt FROM {table_name} "
                f"GROUP BY source_file ORDER BY cnt DESC LIMIT 10"
            )
            top_sources = [(row[0], row[1]) for row in cur.fetchall()]

            # Top targets (most depended-on files)
            cur.execute(
                f"SELECT target_file, COUNT(*) as cnt FROM {table_name} "
                f"WHERE target_file IS NOT NULL "
                f"GROUP BY target_file ORDER BY cnt DESC LIMIT 10"
            )
            top_targets = [(row[0], row[1]) for row in cur.fetchall()]

    return {
        "total_edges": total,
        "by_type": by_type,
        "top_sources": top_sources,
        "top_targets": top_targets,
    }
