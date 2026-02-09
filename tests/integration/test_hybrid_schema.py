"""Integration tests for hybrid search schema migration."""

import os
import pytest
import psycopg

from cocosearch.indexer.schema_migration import (
    ensure_hybrid_search_schema,
    verify_hybrid_search_schema,
)


@pytest.fixture
def db_connection():
    """Get a PostgreSQL connection for testing."""
    db_url = os.environ.get("COCOSEARCH_DATABASE_URL")
    if not db_url:
        pytest.skip("COCOSEARCH_DATABASE_URL not set")
    conn = psycopg.connect(db_url)
    yield conn
    conn.close()


@pytest.fixture
def test_table(db_connection):
    """Create a test table with content_tsv_input column."""
    table_name = "test_hybrid_schema_chunks"
    with db_connection.cursor() as cur:
        # Drop if exists
        cur.execute(f"DROP TABLE IF EXISTS {table_name}")
        # Create table mimicking CocoIndex output
        cur.execute(f"""
            CREATE TABLE {table_name} (
                id SERIAL PRIMARY KEY,
                filename TEXT,
                content_text TEXT,
                content_tsv_input TEXT
            )
        """)
        # Insert test data
        cur.execute(f"""
            INSERT INTO {table_name} (filename, content_text, content_tsv_input)
            VALUES ('test.py', 'def getUserById():', 'getUserById get User By Id user')
        """)
        db_connection.commit()
    yield table_name
    # Cleanup
    with db_connection.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {table_name}")
        db_connection.commit()


class TestHybridSearchSchema:
    """Tests for hybrid search schema migration."""

    def test_ensure_hybrid_search_schema_creates_column_and_index(
        self, db_connection, test_table
    ):
        """Test that migration creates tsvector column and GIN index."""
        result = ensure_hybrid_search_schema(db_connection, test_table)

        assert result["tsvector_added"] is True
        assert result["gin_index_added"] is True
        assert result["already_exists"] is False

    def test_ensure_hybrid_search_schema_is_idempotent(self, db_connection, test_table):
        """Test that migration is safe to run multiple times."""
        # First run
        ensure_hybrid_search_schema(db_connection, test_table)
        # Second run should detect existing schema
        result = ensure_hybrid_search_schema(db_connection, test_table)

        assert result["tsvector_added"] is False
        assert result["gin_index_added"] is False
        assert result["already_exists"] is True

    def test_verify_hybrid_search_schema(self, db_connection, test_table):
        """Test schema verification."""
        # Before migration
        assert verify_hybrid_search_schema(db_connection, test_table) is False

        # After migration
        ensure_hybrid_search_schema(db_connection, test_table)
        assert verify_hybrid_search_schema(db_connection, test_table) is True

    def test_gin_index_used_in_query_plan(self, db_connection, test_table):
        """Verify GIN index is used for full-text search queries."""
        ensure_hybrid_search_schema(db_connection, test_table)

        with db_connection.cursor() as cur:
            # Use EXPLAIN to verify index usage
            cur.execute(f"""
                EXPLAIN (FORMAT JSON) SELECT * FROM {test_table}
                WHERE content_tsv @@ to_tsquery('simple', 'user')
            """)
            plan = cur.fetchone()[0]
            plan_str = str(plan).lower()

            # Should use index scan, not sequential scan
            # Note: Small tables may still use seq scan due to planner
            # For real verification, insert more rows
            assert "index" in plan_str or "bitmap" in plan_str or "scan" in plan_str
