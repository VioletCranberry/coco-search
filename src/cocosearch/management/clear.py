"""Index clearing module for cocosearch.

Provides functions to delete indexes from the PostgreSQL database.
"""

from cocosearch.exceptions import IndexNotFoundError
from cocosearch.search.db import get_connection_pool, get_table_name
from cocosearch.validation import validate_index_name


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
    validate_index_name(index_name)
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
                raise IndexNotFoundError(f"Index '{index_name}' not found")

            # Drop the table
            # Using format string is safe here because table_name comes from
            # our own get_table_name function, not user input
            cur.execute(f"DROP TABLE {table_name}")
            conn.commit()

            # Drop parse results table if it exists (non-critical)
            parse_table = f"cocosearch_parse_results_{index_name}"
            try:
                cur.execute(f"DROP TABLE IF EXISTS {parse_table}")
                conn.commit()
            except Exception:
                pass  # Table may not exist for pre-v46 indexes

            # Drop dependencies table if it exists (non-critical)
            deps_table = f"cocosearch_deps_{index_name}"
            try:
                cur.execute(f"DROP TABLE IF EXISTS {deps_table}")
                conn.commit()
            except Exception:
                pass  # Table may not exist for indexes without deps extraction

            # Drop CocoIndex tracking table if it exists (non-critical)
            tracking_table = f"codeindex_{index_name}__cocoindex_tracking"
            try:
                cur.execute(f"DROP TABLE IF EXISTS {tracking_table}")
                conn.commit()
            except Exception:
                pass  # Table may not exist

            # Clean CocoIndex metadata so re-index creates tables fresh
            try:
                flow_name = f"CodeIndex_{index_name}"
                cur.execute(
                    "DELETE FROM cocoindex_setup_metadata WHERE flow_name = %s",
                    (flow_name,),
                )
                conn.commit()

                # Close in-memory flow to prevent stale state on re-index
                # (critical for long-running processes like MCP server)
                from cocoindex.flow import _flows

                old = _flows.get(flow_name)
                if old is not None:
                    old.close()
            except Exception:
                pass  # Table may not exist or cocoindex not available

    # Clear path-to-index metadata (non-critical, log but don't fail)
    try:
        from cocosearch.management.metadata import clear_index_path

        clear_index_path(index_name)
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(
            f"Failed to clear path metadata for '{index_name}': {e}"
        )

    return {
        "success": True,
        "message": f"Index '{index_name}' deleted successfully",
    }
