"""Index clearing module for cocosearch.

Provides functions to delete indexes from the PostgreSQL database.
"""

from cocosearch.search.db import get_connection_pool, get_table_name


def clear_index(index_name: str) -> dict:
    """Clear (delete) an index from PostgreSQL.

    Removes the index table and all associated data. Validates that
    the index exists before attempting deletion.

    Args:
        index_name: The name of the index to delete.

    Returns:
        Dict with keys:
        - success: True if deletion succeeded
        - message: Description of what was done

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

            # Drop the table
            # Using format string is safe here because table_name comes from
            # our own get_table_name function, not user input
            cur.execute(f"DROP TABLE {table_name}")
            conn.commit()

    return {
        "success": True,
        "message": f"Index '{index_name}' deleted successfully",
    }
