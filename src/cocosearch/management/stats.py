"""Index statistics module for cocosearch.

Provides functions to retrieve storage and content statistics
for indexed codebases.
"""

from dataclasses import dataclass, asdict
from datetime import datetime

from cocosearch.search.db import get_connection_pool, get_table_name


def format_bytes(size: int) -> str:
    """Format bytes as human-readable string.

    Args:
        size: Size in bytes.

    Returns:
        Human-readable string (e.g., "1.5 MB", "256 KB").
    """
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"


def get_stats(index_name: str) -> dict:
    """Get statistics for an index.

    Args:
        index_name: The name of the index.

    Returns:
        Dict with keys:
        - name: Index name
        - file_count: Number of unique files indexed
        - chunk_count: Total number of chunks
        - storage_size: Storage size in bytes
        - storage_size_pretty: Human-readable storage size

    Raises:
        ValueError: If the index does not exist.
    """
    pool = get_connection_pool()
    table_name = get_table_name(index_name)

    # First verify the table exists
    check_query = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        )
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(check_query, (table_name,))
            (exists,) = cur.fetchone()

            if not exists:
                raise ValueError(f"Index '{index_name}' not found")

            # Get file count and chunk count
            stats_query = f"""
                SELECT
                    COUNT(DISTINCT filename) as file_count,
                    COUNT(*) as chunk_count
                FROM {table_name}
            """
            cur.execute(stats_query)
            file_count, chunk_count = cur.fetchone()

            # Get storage size
            size_query = "SELECT pg_table_size(%s)"
            cur.execute(size_query, (table_name,))
            (storage_size,) = cur.fetchone()

    return {
        "name": index_name,
        "file_count": file_count,
        "chunk_count": chunk_count,
        "storage_size": storage_size,
        "storage_size_pretty": format_bytes(storage_size),
    }


def get_language_stats(index_name: str) -> list[dict]:
    """Get per-language statistics for an index.

    Uses SQL GROUP BY for efficient aggregation at database level.
    Gracefully handles pre-v1.7 indexes that lack content_text column.

    Args:
        index_name: The name of the index.

    Returns:
        List of dicts with keys:
        - language: Language identifier (e.g., "python", "hcl")
        - file_count: Number of unique files for this language
        - chunk_count: Number of chunks for this language
        - line_count: Number of lines (None if pre-v1.7 index)

        List is sorted by chunk_count descending.

    Raises:
        ValueError: If the index does not exist.
    """
    pool = get_connection_pool()
    table_name = get_table_name(index_name)

    # First verify the table exists
    check_query = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        )
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(check_query, (table_name,))
            (exists,) = cur.fetchone()

            if not exists:
                raise ValueError(f"Index '{index_name}' not found")

            # Check if content_text column exists (v1.7+)
            col_check = """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'content_text'
            """
            cur.execute(col_check, (table_name,))
            has_content_text = cur.fetchone() is not None

            # Build query with conditional line count
            if has_content_text:
                stats_query = f"""
                    SELECT
                        COALESCE(language_id, 'unknown') as language,
                        COUNT(DISTINCT filename) as file_count,
                        COUNT(*) as chunk_count,
                        SUM(array_length(string_to_array(content_text, E'\\n'), 1)) as line_count
                    FROM {table_name}
                    GROUP BY language_id
                    ORDER BY chunk_count DESC
                """
            else:
                # Graceful degradation for pre-v1.7 indexes
                stats_query = f"""
                    SELECT
                        COALESCE(language_id, 'unknown') as language,
                        COUNT(DISTINCT filename) as file_count,
                        COUNT(*) as chunk_count,
                        NULL as line_count
                    FROM {table_name}
                    GROUP BY language_id
                    ORDER BY chunk_count DESC
                """

            cur.execute(stats_query)
            rows = cur.fetchall()

            return [
                {
                    "language": row[0] if row[0] else "unknown",
                    "file_count": row[1],
                    "chunk_count": row[2],
                    "line_count": row[3],
                }
                for row in rows
            ]


@dataclass
class IndexStats:
    """Comprehensive statistics for an index.

    Attributes:
        name: Index name
        file_count: Number of unique files indexed
        chunk_count: Total number of chunks
        storage_size: Storage size in bytes
        storage_size_pretty: Human-readable storage size
        created_at: Index creation timestamp (None if no metadata)
        updated_at: Index last update timestamp (None if no metadata)
        is_stale: True if index hasn't been updated in threshold_days
        staleness_days: Days since last update (-1 if no metadata)
        languages: Per-language statistics (from get_language_stats)
        symbols: Symbol type counts (e.g., {"function": 150, "class": 25})
        warnings: List of warning messages (staleness, zero-chunk files, etc.)
    """

    name: str
    file_count: int
    chunk_count: int
    storage_size: int
    storage_size_pretty: str
    created_at: datetime | None
    updated_at: datetime | None
    is_stale: bool
    staleness_days: int
    languages: list[dict]
    symbols: dict[str, int]
    warnings: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Converts datetime fields to ISO format strings.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        data = asdict(self)
        # Convert datetime to ISO format string for JSON serialization
        if data["created_at"] is not None:
            data["created_at"] = data["created_at"].isoformat()
        if data["updated_at"] is not None:
            data["updated_at"] = data["updated_at"].isoformat()
        return data


def check_staleness(index_name: str, threshold_days: int = 7) -> tuple[bool, int]:
    """Check if an index is stale (not updated recently).

    Args:
        index_name: The name of the index.
        threshold_days: Days before considering index stale (default: 7).

    Returns:
        Tuple of (is_stale, days_since_update):
        - is_stale: True if index hasn't been updated in threshold_days
        - days_since_update: Days since last update, -1 if no metadata

    Note:
        If metadata is missing or updated_at is NULL, returns (True, -1).
    """
    pool = get_connection_pool()

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Query cocosearch_index_metadata for updated_at
                metadata_query = """
                    SELECT updated_at
                    FROM cocosearch_index_metadata
                    WHERE index_name = %s
                """
                cur.execute(metadata_query, (index_name,))
                row = cur.fetchone()

                if not row or row[0] is None:
                    # No metadata or no updated_at
                    return True, -1

                updated_at = row[0]
                # Calculate days since update
                from datetime import datetime, timezone

                now = datetime.now(timezone.utc)
                # Handle timezone-aware and naive datetimes
                if updated_at.tzinfo is None:
                    # Assume UTC if naive
                    from datetime import timezone
                    updated_at = updated_at.replace(tzinfo=timezone.utc)

                delta = now - updated_at
                days_since_update = delta.days

                is_stale = days_since_update >= threshold_days

                return is_stale, days_since_update
    except Exception:
        # Table doesn't exist or other database error - treat as no metadata
        return True, -1


def get_symbol_stats(index_name: str) -> dict[str, int]:
    """Get symbol type counts for an index.

    Args:
        index_name: The name of the index.

    Returns:
        Dictionary mapping symbol types to counts (e.g., {"function": 150, "class": 25}).
        Empty dict if symbol_type column doesn't exist (pre-v1.7 index).

    Raises:
        ValueError: If the index does not exist.
    """
    pool = get_connection_pool()
    table_name = get_table_name(index_name)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            # Check if symbol_type column exists
            col_check = """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'symbol_type'
            """
            cur.execute(col_check, (table_name,))
            has_symbol_type = cur.fetchone() is not None

            if not has_symbol_type:
                # Graceful degradation for pre-v1.7 indexes
                return {}

            # Get symbol type counts
            stats_query = f"""
                SELECT symbol_type, COUNT(*) as count
                FROM {table_name}
                WHERE symbol_type IS NOT NULL
                GROUP BY symbol_type
                ORDER BY count DESC
            """
            cur.execute(stats_query)
            rows = cur.fetchall()

            return {row[0]: row[1] for row in rows}


def collect_warnings(index_name: str, is_stale: bool, staleness_days: int) -> list[str]:
    """Collect warnings for an index.

    Args:
        index_name: The name of the index.
        is_stale: Whether the index is stale.
        staleness_days: Days since last update.

    Returns:
        List of warning messages.
    """
    warnings = []

    # Staleness warning
    if is_stale:
        if staleness_days == -1:
            warnings.append("No metadata found - index may be corrupted or very old")
        else:
            warnings.append(f"Index is stale ({staleness_days} days since last update)")

    # Check for files with zero chunks
    pool = get_connection_pool()
    table_name = get_table_name(index_name)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            # Count distinct files
            file_count_query = f"""
                SELECT COUNT(DISTINCT filename) FROM {table_name}
            """
            cur.execute(file_count_query)
            total_files = cur.fetchone()[0]

            # Count files with at least one chunk
            files_with_chunks_query = f"""
                SELECT COUNT(DISTINCT filename)
                FROM {table_name}
                WHERE 1=1
            """
            cur.execute(files_with_chunks_query)
            files_with_chunks = cur.fetchone()[0]

            # If there's a discrepancy, it would show in the metadata
            # For now, we skip this check as it requires joining with metadata
            # which may not exist for all indexes

    return warnings


def get_comprehensive_stats(index_name: str, staleness_threshold: int = 7) -> IndexStats:
    """Get comprehensive statistics for an index.

    Combines all available statistics into a single IndexStats object:
    - Basic stats (files, chunks, size)
    - Language distribution
    - Symbol type counts (if available)
    - Staleness information
    - Warnings

    Args:
        index_name: The name of the index.
        staleness_threshold: Days before considering index stale (default: 7).

    Returns:
        IndexStats instance with all available information.

    Raises:
        ValueError: If the index does not exist.
    """
    # Get basic stats
    basic_stats = get_stats(index_name)

    # Get language stats
    languages = get_language_stats(index_name)

    # Get symbol stats
    symbols = get_symbol_stats(index_name)

    # Check staleness
    is_stale, staleness_days = check_staleness(index_name, staleness_threshold)

    # Get metadata timestamps
    pool = get_connection_pool()
    created_at = None
    updated_at = None

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                metadata_query = """
                    SELECT created_at, updated_at
                    FROM cocosearch_index_metadata
                    WHERE index_name = %s
                """
                cur.execute(metadata_query, (index_name,))
                row = cur.fetchone()
                if row:
                    created_at, updated_at = row
    except Exception:
        # Table doesn't exist - timestamps remain None
        pass

    # Collect warnings
    warnings = collect_warnings(index_name, is_stale, staleness_days)

    return IndexStats(
        name=index_name,
        file_count=basic_stats["file_count"],
        chunk_count=basic_stats["chunk_count"],
        storage_size=basic_stats["storage_size"],
        storage_size_pretty=basic_stats["storage_size_pretty"],
        created_at=created_at,
        updated_at=updated_at,
        is_stale=is_stale,
        staleness_days=staleness_days,
        languages=languages,
        symbols=symbols,
        warnings=warnings,
    )
