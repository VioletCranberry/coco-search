"""Container fixtures for integration testing.

Provides session-scoped PostgreSQL container using testcontainers-python.
Container starts once per test session and is reused across all integration tests.
"""

import os

import psycopg
import pytest
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool
from testcontainers.postgres import PostgresContainer

# Environment variable configuration with defaults
TEST_DB_PORT = int(os.getenv("COCOSEARCH_TEST_DB_PORT", "5433"))
TEST_DB_USER = os.getenv("COCOSEARCH_TEST_DB_USER", "cocosearch_test")
TEST_DB_PASSWORD = os.getenv("COCOSEARCH_TEST_DB_PASSWORD", "test_password")
TEST_DB_NAME = os.getenv("COCOSEARCH_TEST_DB_NAME", "cocosearch_test")


@pytest.fixture(scope="session")
def postgres_container():
    """Start PostgreSQL container for entire test session.

    Locked decisions from Phase 12 CONTEXT:
    - Session scope (one container for all tests)
    - 60s timeout (handles slow CI, first pull)
    - Pin pg16 (reproducible, explicit upgrades)
    - Port 5433 (avoid local PostgreSQL on 5432)
    """
    with PostgresContainer(
        image="pgvector/pgvector:pg16",
        port=5432,  # Internal port, testcontainers maps to random external port
        username=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        dbname=TEST_DB_NAME,
    ).with_env("POSTGRES_HOST_AUTH_METHOD", "trust") as postgres:
        # Wait for container ready (testcontainers handles this automatically)
        yield postgres


@pytest.fixture(scope="session")
def test_db_url(postgres_container):
    """Get connection URL for test database.

    Returns psycopg3-compatible connection URL.
    """
    return postgres_container.get_connection_url(driver=None)


@pytest.fixture(scope="session")
def initialized_db(test_db_url):
    """Initialize database with pgvector extension.

    Runs once per session after container starts.
    pgvector/pgvector image has extension files installed,
    just need CREATE EXTENSION to enable it.

    Locked decision from CONTEXT.md: "pgvector extension baked into
    container entrypoint -- ready before tests connect"
    """
    with psycopg.connect(test_db_url) as conn:
        # Enable pgvector extension (idempotent)
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()

    return test_db_url


@pytest.fixture(autouse=True)
def clean_tables(initialized_db, request):
    """Clean all tables between tests using TRUNCATE CASCADE.

    Locked decision from CONTEXT.md: "TRUNCATE tables between tests --
    fast cleanup, keeps schema"

    CASCADE handles foreign key constraints automatically.
    Only runs for integration tests (checks marker).
    """
    # Only run cleanup for integration tests
    if "integration" not in [m.name for m in request.node.iter_markers()]:
        yield
        return

    yield  # Run test first

    # Cleanup after test
    with psycopg.connect(initialized_db) as conn:
        with conn.cursor() as cur:
            # Get all user tables (exclude system tables)
            cur.execute("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
            """)
            tables = [row[0] for row in cur.fetchall()]

            if tables:
                # Quote table names for safety, CASCADE for foreign keys
                quoted = ', '.join(f'"{t}"' for t in tables)
                cur.execute(f"TRUNCATE TABLE {quoted} CASCADE")

        conn.commit()


@pytest.fixture
def integration_db_pool(initialized_db):
    """Provide connection pool with pgvector support for integration tests.

    Function scope: fresh pool per test.
    Registers pgvector type handler for vector operations.
    """
    def configure(conn):
        register_vector(conn)

    pool = ConnectionPool(
        conninfo=initialized_db,
        configure=configure,
        min_size=1,
        max_size=5,
        timeout=10,
    )

    # Wait for min_size connections (catches config errors early)
    pool.wait()

    yield pool

    # Always close to prevent connection leaks
    pool.close()
