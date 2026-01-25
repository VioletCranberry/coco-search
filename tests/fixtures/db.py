"""Database fixtures for testing.

Provides fixtures that mock cocosearch.search.db module functions
to enable testing without a real PostgreSQL database.
"""

import pytest
from unittest.mock import patch

from tests.mocks.db import MockConnectionPool, MockCursor, MockConnection


@pytest.fixture
def mock_db_pool():
    """Factory fixture for creating mock database pools.

    Returns a function that creates a configured (pool, cursor) tuple.
    The cursor can be pre-loaded with results for testing.

    Usage:
        def test_something(mock_db_pool):
            pool, cursor = mock_db_pool(results=[
                ("/path/file.py", 0, 100, 0.85),
            ])
            # Use pool in test...
            cursor.assert_query_contains("SELECT")
    """

    def _make_pool(
        results: list[tuple] | None = None,
    ) -> tuple[MockConnectionPool, MockCursor]:
        cursor = MockCursor(results=results)
        conn = MockConnection(cursor=cursor)
        pool = MockConnectionPool(connection=conn)
        return pool, cursor

    return _make_pool


@pytest.fixture
def patched_db_pool(mock_db_pool):
    """Fixture that auto-patches get_connection_pool.

    Patches cocosearch.search.db.get_connection_pool to return a mock pool.
    Returns (pool, cursor) for test assertions.

    Usage:
        def test_search(patched_db_pool):
            pool, cursor = patched_db_pool
            # Now any code calling get_connection_pool() gets the mock
    """
    pool, cursor = mock_db_pool()
    with patch("cocosearch.search.db.get_connection_pool", return_value=pool):
        yield pool, cursor


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
