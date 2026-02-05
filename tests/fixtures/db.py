"""Database fixtures for testing.

Provides fixtures that mock cocosearch.search.db module functions
to enable testing without a real PostgreSQL database.
"""

import pytest
from unittest.mock import patch

from tests.mocks.db import MockConnectionPool, MockCursor, MockConnection


@pytest.fixture(autouse=True)
def reset_search_module_state():
    """Reset search module state and patch check_column_exists.

    Autouse fixture that:
    1. Patches check_column_exists to return True (simulates v1.7+ index)
    2. Resets module-level flags after each test
    3. Clears the query cache to prevent test pollution

    This prevents the hybrid column check from hitting a real database
    and ensures test isolation for module-level state.
    """
    import cocosearch.search.query as query_module
    import cocosearch.search.cache as cache_module

    with patch.object(query_module, "check_column_exists", return_value=True):
        yield

    # Reset all module-level flags after test
    query_module._has_metadata_columns = True
    query_module._metadata_warning_emitted = False
    query_module._has_content_text_column = True
    query_module._hybrid_warning_emitted = False

    # Clear query cache singleton to prevent test pollution
    cache_module._query_cache = None


@pytest.fixture
def mock_db_pool():
    """Factory fixture for creating mock database pools.

    Returns a function that creates a configured (pool, cursor, connection) tuple.
    The cursor can be pre-loaded with results for testing.
    The connection exposes commit tracking.

    Usage:
        def test_something(mock_db_pool):
            pool, cursor, conn = mock_db_pool(results=[
                ("/path/file.py", 0, 100, 0.85),
            ])
            # Use pool in test...
            cursor.assert_query_contains("SELECT")
            assert conn.committed  # verify commit was called
    """

    def _make_pool(
        results: list[tuple] | None = None,
    ) -> tuple[MockConnectionPool, MockCursor, MockConnection]:
        cursor = MockCursor(results=results)
        conn = MockConnection(cursor=cursor)
        pool = MockConnectionPool(connection=conn)
        return pool, cursor, conn

    return _make_pool


@pytest.fixture
def patched_db_pool(mock_db_pool):
    """Fixture that auto-patches get_connection_pool.

    Patches cocosearch.search.db.get_connection_pool to return a mock pool.
    Returns (pool, cursor, conn) for test assertions.

    Usage:
        def test_search(patched_db_pool):
            pool, cursor, conn = patched_db_pool
            # Now any code calling get_connection_pool() gets the mock
    """
    pool, cursor, conn = mock_db_pool()
    with patch("cocosearch.search.db.get_connection_pool", return_value=pool):
        yield pool, cursor, conn


@pytest.fixture
def mock_search_results():
    """Sample search results for testing.

    Returns a list of tuples in the format returned by search queries:
    (filename, start_byte, end_byte, score)
    """
    return [
        ("/path/to/main.py", 0, 150, 0.92),
        ("/path/to/utils.py", 50, 200, 0.85),
        ("/path/to/config.py", 100, 250, 0.78),
    ]
