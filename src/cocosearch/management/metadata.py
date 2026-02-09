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

# If status has been "indexing" for longer than this, assume the process
# died (e.g. daemon thread killed, SIGKILL, server restart) and auto-recover.
STALE_INDEXING_TIMEOUT_SECONDS = 900  # 15 minutes


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
    """
    pool = get_connection_pool()
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT index_name, canonical_path, created_at, updated_at, status
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

                # Auto-recover stale "indexing" status — the process likely
                # died without running its finally block (daemon thread killed,
                # SIGKILL, server restart, etc.)
                if status == "indexing" and updated_at is not None:
                    try:
                        if not updated_at.tzinfo:
                            now = datetime.now()
                        else:
                            now = datetime.now(timezone.utc)
                        elapsed = (now - updated_at).total_seconds()
                        if elapsed > STALE_INDEXING_TIMEOUT_SECONDS:
                            logger.info(
                                "Auto-recovering stale 'indexing' status for "
                                "'%s' (stuck for %.0f seconds)",
                                row[0],
                                elapsed,
                            )
                            status = "error"
                            # Best-effort DB update — don't fail the read
                            try:
                                cur.execute(
                                    """
                                    UPDATE cocosearch_index_metadata
                                    SET status = 'error', updated_at = NOW()
                                    WHERE index_name = %s AND status = 'indexing'
                                    """,
                                    (row[0],),
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass  # Don't fail the read on stale detection errors

                return {
                    "index_name": row[0],
                    "canonical_path": row[1],
                    "created_at": row[2],
                    "updated_at": updated_at,
                    "status": status,
                }
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


def register_index_path(index_name: str, project_path: str | Path) -> None:
    """Register a path-to-index mapping with collision detection.

    Args:
        index_name: The name of the index
        project_path: The project directory path (will be resolved to canonical form)

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
                INSERT INTO cocosearch_index_metadata (index_name, canonical_path, created_at, updated_at, status)
                VALUES (%s, %s, NOW(), NOW(), 'indexed')
                ON CONFLICT (index_name) DO UPDATE SET
                    canonical_path = EXCLUDED.canonical_path,
                    updated_at = NOW(),
                    status = 'indexed'
                """,
                (index_name, canonical),
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
