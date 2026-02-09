"""PostgreSQL integration tests.

Tests validating real PostgreSQL+pgvector behavior:
- pgvector extension loading
- Vector similarity search operations
- Table cleanup between tests
- Connection pool functionality

These tests require Docker and are marked with @pytest.mark.integration.
The marker is auto-applied by tests/integration/conftest.py.
"""


class TestPgvectorExtension:
    """Tests for pgvector extension functionality."""

    def test_pgvector_extension_loaded(self, integration_db_pool):
        """Verify pgvector extension is installed and working.

        Requirement: PG-02 (pgvector extension initialized automatically)
        """
        with integration_db_pool.connection() as conn:
            with conn.cursor() as cur:
                # Check extension is installed
                cur.execute("""
                    SELECT extname FROM pg_extension
                    WHERE extname = 'vector'
                """)
                result = cur.fetchone()
                assert result is not None, "pgvector extension not installed"
                assert result[0] == "vector"

    def test_vector_type_available(self, integration_db_pool):
        """Verify vector type can be used in queries.

        Requirement: PG-02 (pgvector extension initialized automatically)
        """
        with integration_db_pool.connection() as conn:
            with conn.cursor() as cur:
                # Create a test table with vector column
                cur.execute("""
                    CREATE TEMPORARY TABLE test_vectors (
                        id SERIAL PRIMARY KEY,
                        embedding vector(3)
                    )
                """)
                # Insert a vector
                cur.execute("""
                    INSERT INTO test_vectors (embedding)
                    VALUES ('[1,2,3]')
                """)
                # Query it back
                cur.execute("SELECT embedding FROM test_vectors")
                result = cur.fetchone()
                assert result is not None
                # pgvector returns numpy array when registered
                import numpy as np

                assert isinstance(result[0], np.ndarray)
                assert list(result[0]) == [1.0, 2.0, 3.0]


class TestVectorSimilaritySearch:
    """Tests for vector similarity search operations."""

    def test_cosine_distance_operator(self, integration_db_pool):
        """Verify cosine distance operator (<=>) works correctly.

        Requirement: PG-05 (Vector similarity search works correctly)
        """
        with integration_db_pool.connection() as conn:
            with conn.cursor() as cur:
                # Create test table
                cur.execute("""
                    CREATE TEMPORARY TABLE test_search (
                        id SERIAL PRIMARY KEY,
                        content TEXT,
                        embedding vector(3)
                    )
                """)
                # Insert test vectors
                cur.execute("""
                    INSERT INTO test_search (content, embedding) VALUES
                    ('similar', '[1,0,0]'),
                    ('different', '[0,1,0]'),
                    ('orthogonal', '[0,0,1]')
                """)

                # Search for vector similar to [1,0,0]
                cur.execute("""
                    SELECT content, 1 - (embedding <=> '[1,0,0]'::vector) AS score
                    FROM test_search
                    ORDER BY embedding <=> '[1,0,0]'::vector
                    LIMIT 3
                """)
                results = cur.fetchall()

                # First result should be 'similar' with score ~1.0
                assert results[0][0] == "similar"
                assert results[0][1] > 0.99  # cosine similarity ~1.0

                # Other results should have lower scores
                assert results[1][1] < 0.1  # orthogonal vectors
                assert results[2][1] < 0.1

    def test_vector_index_creation(self, integration_db_pool):
        """Verify IVFFlat index can be created for vectors.

        Requirement: PG-05 (Vector similarity search works correctly)
        """
        with integration_db_pool.connection() as conn:
            with conn.cursor() as cur:
                # Create test table
                cur.execute("""
                    CREATE TEMPORARY TABLE test_indexed (
                        id SERIAL PRIMARY KEY,
                        embedding vector(768)
                    )
                """)
                # Create IVFFlat index (used by CocoIndex)
                cur.execute("""
                    CREATE INDEX ON test_indexed
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 1)
                """)
                # Verify index was created
                cur.execute("""
                    SELECT indexname FROM pg_indexes
                    WHERE tablename = 'test_indexed'
                    AND indexdef LIKE '%ivfflat%'
                """)
                result = cur.fetchone()
                assert result is not None, "IVFFlat index not created"


class TestTableCleanup:
    """Tests verifying table cleanup between tests."""

    def test_table_creation_first(self, integration_db_pool):
        """Create a persistent table and insert data.

        This test runs first and creates state that should be cleaned up.
        """
        with integration_db_pool.connection() as conn:
            with conn.cursor() as cur:
                # Create a non-temporary table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS cleanup_test (
                        id SERIAL PRIMARY KEY,
                        data TEXT
                    )
                """)
                cur.execute("INSERT INTO cleanup_test (data) VALUES ('test1')")
            conn.commit()

            # Verify data exists
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM cleanup_test")
                count = cur.fetchone()[0]
                assert count == 1

    def test_table_cleaned_second(self, integration_db_pool):
        """Verify the table from previous test was truncated.

        Requirement: INFRA-04 (Test isolation via database state cleanup)
        Requirement: PG-04 (Database state cleaned between tests)

        The clean_tables fixture should have truncated cleanup_test
        after test_table_creation_first.
        """
        with integration_db_pool.connection() as conn:
            with conn.cursor() as cur:
                # Table should exist but be empty
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM pg_tables
                        WHERE tablename = 'cleanup_test'
                    )
                """)
                table_exists = cur.fetchone()[0]

                if table_exists:
                    # If table exists, it should be empty (truncated)
                    cur.execute("SELECT COUNT(*) FROM cleanup_test")
                    count = cur.fetchone()[0]
                    assert count == 0, "Table should be empty after cleanup"


class TestConnectionPool:
    """Tests for connection pool functionality."""

    def test_pool_provides_connections(self, integration_db_pool):
        """Verify pool can provide multiple connections.

        Requirement: INFRA-05 (Session-scoped container fixtures for performance)
        """
        # Get multiple connections from pool
        with integration_db_pool.connection() as conn1:
            with conn1.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone()[0] == 1

        with integration_db_pool.connection() as conn2:
            with conn2.cursor() as cur:
                cur.execute("SELECT 2")
                assert cur.fetchone()[0] == 2

    def test_pool_has_pgvector_registered(self, integration_db_pool):
        """Verify pgvector type handler is registered on pool connections.

        Requirement: PG-01 (Integration tests connect to real PostgreSQL+pgvector)
        """
        import numpy as np

        with integration_db_pool.connection() as conn:
            with conn.cursor() as cur:
                # Query a vector literal - should return numpy array
                cur.execute("SELECT '[1,2,3]'::vector")
                result = cur.fetchone()[0]
                assert isinstance(result, np.ndarray), (
                    "pgvector type handler not registered"
                )
