"""Tests to verify database mocking infrastructure works correctly."""


def test_mock_cursor_tracks_queries(mock_db_pool):
    """Verify MockCursor tracks executed queries."""
    pool, cursor, conn = mock_db_pool()

    cursor.execute("SELECT * FROM test WHERE id = %s", (1,))
    cursor.execute("INSERT INTO test VALUES (%s)", ("value",))

    assert len(cursor.calls) == 2
    cursor.assert_query_contains("SELECT")
    cursor.assert_query_contains("INSERT")


def test_mock_cursor_returns_results(mock_db_pool):
    """Verify MockCursor returns configured results."""
    results = [
        ("/path/file1.py", 0, 100, 0.9),
        ("/path/file2.py", 50, 150, 0.8),
    ]
    pool, cursor, conn = mock_db_pool(results=results)

    cursor.execute("SELECT * FROM test")
    rows = cursor.fetchall()

    assert len(rows) == 2
    assert rows[0][0] == "/path/file1.py"
    assert rows[1][3] == 0.8


def test_mock_cursor_fetchone(mock_db_pool):
    """Verify MockCursor fetchone returns rows one at a time."""
    results = [("row1",), ("row2",)]
    pool, cursor, conn = mock_db_pool(results=results)

    cursor.execute("SELECT * FROM test")
    assert cursor.fetchone() == ("row1",)
    assert cursor.fetchone() == ("row2",)
    assert cursor.fetchone() is None


def test_mock_pool_context_manager(mock_db_pool):
    """Verify MockConnectionPool works as context manager."""
    pool, cursor, _conn = mock_db_pool(results=[("test",)])

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()

    assert result == ("test",)


def test_patched_db_pool_patches_module(patched_db_pool):
    """Verify patched_db_pool patches the actual module."""
    from cocosearch.search.db import get_connection_pool

    pool, cursor, conn = patched_db_pool
    actual_pool = get_connection_pool()

    # Should return our mock, not try to connect to real DB
    assert actual_pool is pool


def test_mock_search_results_fixture(mock_search_results):
    """Verify mock_search_results provides sample data."""
    assert len(mock_search_results) == 3
    assert mock_search_results[0][0] == "/path/to/main.py"
    assert mock_search_results[0][3] == 0.92  # score
