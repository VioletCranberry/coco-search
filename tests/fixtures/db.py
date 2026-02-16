"""Database fixtures for testing.

Provides fixtures that mock cocosearch.search.db module functions
to enable testing without a real PostgreSQL database.
"""

import pytest
from unittest.mock import patch

from tests.mocks.db import MockConnectionPool, MockCursor, MockConnection


@pytest.fixture(autouse=True)
def reset_search_module_state():
    """Reset search module state and patch DB-dependent column checks.

    Autouse fixture that:
    1. Patches check_column_exists to return True (simulates v1.7+ index)
    2. Patches check_symbol_columns_exist to return True (simulates v1.7+ index)
    3. Resets module-level flags after each test
    4. Clears the query cache and symbol columns cache to prevent test pollution

    This prevents column checks from hitting a real database
    and ensures test isolation for module-level state.
    """
    import cocosearch.search.query as query_module
    import cocosearch.search.cache as cache_module
    import cocosearch.search.db as db_module

    with (
        patch.object(query_module, "check_column_exists", return_value=True),
        patch.object(query_module, "check_symbol_columns_exist", return_value=False),
    ):
        yield

    # Reset all module-level flags after test
    query_module._has_content_text_column = True
    query_module._hybrid_warning_emitted = False

    # Clear query cache singleton to prevent test pollution
    cache_module._query_cache = None

    # Clear symbol columns cache to prevent cross-test pollution
    db_module._symbol_columns_available = {}


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
