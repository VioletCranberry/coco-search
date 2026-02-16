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
