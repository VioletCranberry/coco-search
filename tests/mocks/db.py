"""Database mock classes for testing.

Provides MockCursor, MockConnection, and MockConnectionPool that mimic
psycopg/psycopg_pool interfaces without requiring a real database.
"""

from typing import Any
from collections.abc import Sequence


class MockCursor:
    """Mock database cursor with call tracking.

    Tracks all executed queries and parameters for assertion in tests.
    Returns canned results configured at construction.
    """

    def __init__(self, results: Sequence[tuple] | None = None):
        """Initialize mock cursor with optional canned results.

        Args:
            results: List of tuples to return from fetch methods.
        """
        self.results = list(results) if results else []
        self.calls: list[tuple[str, tuple | None]] = []
        self._fetch_index = 0

    def execute(self, query: str, params: tuple | None = None) -> None:
        """Record query execution for later assertions."""
        self.calls.append((query, params))

    def fetchone(self) -> tuple | None:
        """Return next result row."""
        if self._fetch_index < len(self.results):
            row = self.results[self._fetch_index]
            self._fetch_index += 1
            return row
        return None

    def fetchall(self) -> list[tuple]:
        """Return all remaining results."""
        remaining = self.results[self._fetch_index:]
        self._fetch_index = len(self.results)
        return remaining

    def __enter__(self) -> "MockCursor":
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def assert_query_contains(self, substring: str) -> None:
        """Assert that any executed query contains substring."""
        for query, _ in self.calls:
            if substring in query:
                return
        raise AssertionError(
            f"No query containing '{substring}' was executed. "
            f"Queries: {[q for q, _ in self.calls]}"
        )

    def assert_called_with_param(self, param: Any) -> None:
        """Assert that any query was called with a specific parameter."""
        for _, params in self.calls:
            if params and param in params:
                return
        raise AssertionError(f"No query called with parameter '{param}'")


class MockConnection:
    """Mock database connection."""

    def __init__(self, cursor: MockCursor | None = None):
        """Initialize with optional pre-configured cursor."""
        self._cursor = cursor or MockCursor()
        self.committed = False

    def cursor(self) -> MockCursor:
        """Return the mock cursor."""
        return self._cursor

    def commit(self) -> None:
        """Record that commit was called."""
        self.committed = True

    def __enter__(self) -> "MockConnection":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class MockConnectionPool:
    """Mock psycopg_pool.ConnectionPool.

    Mimics the connection() context manager interface.
    """

    def __init__(self, connection: MockConnection | None = None):
        """Initialize with optional pre-configured connection."""
        self._connection = connection or MockConnection()

    def connection(self) -> MockConnection:
        """Return a context manager yielding the mock connection."""
        return self._connection
