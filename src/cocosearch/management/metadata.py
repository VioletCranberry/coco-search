"""Metadata storage module for cocosearch.

Provides functions to store and retrieve path-to-index mappings
with collision detection. Used by auto-detect feature to track
which projects are indexed under which names.
"""

import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from cocosearch.management.context import get_canonical_path
from cocosearch.search.db import get_connection_pool

logger = logging.getLogger(__name__)


def ensure_metadata_table() -> None:
    """Create the metadata table if it doesn't exist.

    Creates cocosearch_index_metadata table with:
    - index_name (TEXT PRIMARY KEY)
    - canonical_path (TEXT NOT NULL)
    - created_at, updated_at (TIMESTAMP)

    Idempotent - safe to call multiple times.
    """
    pool = get_connection_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cocosearch_index_metadata (
                    index_name TEXT PRIMARY KEY,
                    canonical_path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    status TEXT DEFAULT 'indexed'
                )
            """)
            cur.execute("""
                ALTER TABLE cocosearch_index_metadata
                    ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'indexed'
            """)
            cur.execute("""
                ALTER TABLE cocosearch_index_metadata
                    ADD COLUMN IF NOT EXISTS branch TEXT
            """)
            cur.execute("""
                ALTER TABLE cocosearch_index_metadata
                    ADD COLUMN IF NOT EXISTS commit_hash TEXT
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_cocosearch_metadata_path
                    ON cocosearch_index_metadata(canonical_path)
            """)
        conn.commit()


def get_index_metadata(index_name: str) -> dict | None:
    """Get metadata for an index by name.

    Args:
        index_name: The name of the index to look up.

    Returns:
        Dict with keys: index_name, canonical_path, created_at, updated_at, status
        or None if not found (including when metadata table doesn't exist yet).

        When status is "indexing", an additional ``indexing_elapsed_seconds``
        key is included so callers can decide how to present possibly-stale
        indexing status without mutating the database.
    """
    pool = get_connection_pool()
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT index_name, canonical_path, created_at, updated_at, status,
                           branch, commit_hash
                    FROM cocosearch_index_metadata
                    WHERE index_name = %s
                    """,
                    (index_name,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                status = row[4] if len(row) > 4 else "indexed"
                updated_at = row[3]

                result = {
                    "index_name": row[0],
                    "canonical_path": row[1],
                    "created_at": row[2],
                    "updated_at": updated_at,
                    "status": status,
                    "branch": row[5] if len(row) > 5 else None,
                    "commit_hash": row[6] if len(row) > 6 else None,
                }

                # Provide elapsed time so callers can warn about
                # possibly-stale "indexing" status without mutating the DB.
                if status == "indexing" and updated_at is not None:
                    try:
                        if not updated_at.tzinfo:
                            now = datetime.now()
                        else:
                            now = datetime.now(timezone.utc)
                        result["indexing_elapsed_seconds"] = (
                            now - updated_at
                        ).total_seconds()
                    except Exception:
                        pass

                return result
    except Exception:
        # Table doesn't exist yet (fresh database, never indexed)
        return None


@lru_cache(maxsize=128)
def get_index_for_path(canonical_path: str) -> str | None:
    """Get the index name for a canonical path.

    Results are cached for performance since MCP tools call this frequently.

    Args:
        canonical_path: Absolute, symlink-resolved path as string

    Returns:
        Index name if mapping exists, None otherwise (including when
        metadata table doesn't exist yet on fresh database).
    """
    pool = get_connection_pool()
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT index_name
                    FROM cocosearch_index_metadata
                    WHERE canonical_path = %s
                    """,
                    (canonical_path,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return row[0]
    except Exception:
        # Table doesn't exist yet (fresh database, never indexed)
        return None


def register_index_path(
    index_name: str,
    project_path: str | Path,
    branch: str | None = None,
    commit_hash: str | None = None,
) -> None:
    """Register a path-to-index mapping with collision detection.

    Args:
        index_name: The name of the index
        project_path: The project directory path (will be resolved to canonical form)
        branch: Git branch name at time of indexing (optional)
        commit_hash: Git commit hash at time of indexing (optional)

    Raises:
        ValueError: If index_name already maps to a different path (collision)
    """
    # Resolve to canonical path
    canonical = str(get_canonical_path(project_path))

    # Ensure table exists
    ensure_metadata_table()

    # Check for collision: same index_name, different path
    existing = get_index_metadata(index_name)
    if existing and existing["canonical_path"] != canonical:
        raise ValueError(
            f"Index name collision detected: '{index_name}'\n"
            f"  Existing path: {existing['canonical_path']}\n"
            f"  New path: {canonical}\n\n"
            f"To resolve:\n"
            f"  1. Set explicit indexName in cocosearch.yaml at {project_path}, or\n"
            f"  2. Use --index-name flag: cocosearch index {project_path} --name <unique-name>"
        )

    # Upsert the mapping
    pool = get_connection_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cocosearch_index_metadata
                    (index_name, canonical_path, created_at, updated_at, status, branch, commit_hash)
                VALUES (%s, %s, NOW(), NOW(), 'indexing', %s, %s)
                ON CONFLICT (index_name) DO UPDATE SET
                    canonical_path = EXCLUDED.canonical_path,
                    updated_at = NOW(),
                    branch = EXCLUDED.branch,
                    commit_hash = EXCLUDED.commit_hash
                """,
                (index_name, canonical, branch, commit_hash),
            )
        conn.commit()

    # Clear cache since database changed
    get_index_for_path.cache_clear()


def clear_index_path(index_name: str) -> bool:
    """Remove a path-to-index mapping.

    Args:
        index_name: The name of the index to remove

    Returns:
        True if a row was deleted, False if not found (including when
        metadata table doesn't exist yet on fresh database).
    """
    pool = get_connection_pool()
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM cocosearch_index_metadata
                    WHERE index_name = %s
                    """,
                    (index_name,),
                )
                deleted = cur.rowcount > 0
            conn.commit()

        # Clear cache since database changed
        get_index_for_path.cache_clear()

        return deleted
    except Exception:
        # Table doesn't exist yet (fresh database)
        return False


_STALE_INDEXING_THRESHOLD_SECONDS = 300  # 5 minutes


def auto_recover_stale_indexing(index_name: str) -> bool:
    """Auto-recover an index stuck in 'indexing' status.

    If the index has been in 'indexing' status for longer than the stale
    threshold (15 minutes), flips it to 'indexed'. This handles cases
    where the indexing process completed but was interrupted before the
    finally block could update the status.

    Args:
        index_name: The name of the index.

    Returns:
        True if status was recovered, False otherwise.
    """
    metadata = get_index_metadata(index_name)
    if metadata is None:
        return False

    if metadata.get("status") != "indexing":
        return False

    elapsed = metadata.get("indexing_elapsed_seconds")
    if elapsed is None or elapsed < _STALE_INDEXING_THRESHOLD_SECONDS:
        return False

    logger.warning(
        "Auto-recovering stale 'indexing' status for index '%s' "
        "(stuck for %.0f seconds, threshold: %d seconds)",
        index_name,
        elapsed,
        _STALE_INDEXING_THRESHOLD_SECONDS,
    )
    return set_index_status(index_name, "indexed")


def set_index_status(index_name: str, status: str) -> bool:
    """Set the status of an index.

    Args:
        index_name: The name of the index.
        status: The status to set (e.g., 'indexing', 'indexed').

    Returns:
        True if a row was updated, False if not found (including when
        metadata table doesn't exist yet on fresh database).
    """
    pool = get_connection_pool()
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE cocosearch_index_metadata
                    SET status = %s, updated_at = NOW()
                    WHERE index_name = %s
                    """,
                    (status, index_name),
                )
                updated = cur.rowcount > 0
            conn.commit()
        return updated
    except Exception:
        # Table doesn't exist yet (fresh database)
        return False
