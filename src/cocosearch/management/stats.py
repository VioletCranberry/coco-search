"""Index statistics module for cocosearch.

Provides functions to retrieve storage and content statistics
for indexed codebases.
"""

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
