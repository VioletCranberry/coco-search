"""Index discovery module for cocosearch.

Provides functions to discover and list all CocoIndex tables
in the PostgreSQL database.
"""

from cocosearch.search.db import get_connection_pool


def list_indexes() -> list[dict]:
    """List all indexes stored in PostgreSQL.

    Queries information_schema.tables for tables matching the CocoIndex
    naming pattern `codeindex_%__%_chunks` and parses the index names.

    Returns:
        List of dicts with keys:
        - name: The extracted index name
        - table_name: The full PostgreSQL table name
    """
    pool = get_connection_pool()

    query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name LIKE 'codeindex_%'
          AND table_name LIKE '%_chunks'
        ORDER BY table_name
    """

    indexes = []
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

            for (table_name,) in rows:
                # Parse table name: codeindex_{name}__{name}_chunks
                # Extract name from the part before '__'
                if "__" in table_name:
                    prefix_part = table_name.split("__")[0]
                    # Remove 'codeindex_' prefix
                    if prefix_part.startswith("codeindex_"):
                        name = prefix_part[len("codeindex_") :]
                        indexes.append({"name": name, "table_name": table_name})

    return indexes
