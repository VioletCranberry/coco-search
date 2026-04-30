"""Root conftest.py - pytest configuration and shared fixtures for cocosearch tests.

This module provides common fixtures used across all test modules:
- reset_db_pool: Autouse fixture that resets database pool between tests
- tmp_codebase: Creates temporary directory with sample Python files
"""

import warnings

import pytest

# Built-in markers to ignore when checking for custom markers
BUILTIN_MARKERS = {
    "parametrize",
    "skip",
    "skipif",
    "xfail",
    "usefixtures",
    "filterwarnings",
    "asyncio",
}

# Required custom markers - tests must have at least one
REQUIRED_MARKERS = {"unit"}


def pytest_collection_modifyitems(items):
    """Warn if tests are missing unit marker.

    This hook runs during test collection and emits warnings for any
    test that doesn't have a @pytest.mark.unit marker. Tests in
    tests/unit/ get the marker auto-applied by conftest.py.
    """
    for item in items:
        marker_names = {mark.name for mark in item.iter_markers()}
        custom_markers = marker_names - BUILTIN_MARKERS

        if not custom_markers.intersection(REQUIRED_MARKERS):
            warnings.warn(
                f"Test '{item.nodeid}' has no @pytest.mark.unit marker",
                UserWarning,
            )


# Register fixtures from fixtures directory
pytest_plugins = [
    "tests.fixtures.db",
    "tests.fixtures.ollama",
    "tests.fixtures.data",
]


@pytest.fixture(autouse=True)
def reset_db_pool():
    """Reset database pool singleton between tests.

    This prevents connection pool state from leaking between tests.
    Pre-sets the pool to a mock before each test to prevent any real
    DB connections. Tests that need specific results already patch
    get_connection_pool at the module level (e.g.,
    cocosearch.search.query.get_connection_pool), which overrides
    this default. This safety net catches un-mocked calls from
    metadata.py and other modules that would otherwise create real
    ConnectionPool objects and timeout in CI (~34.5s each).
    """
    import cocosearch.search.db as db_module
    from tests.mocks.db import MockConnection, MockConnectionPool, MockCursor

    db_module._pool = MockConnectionPool(connection=MockConnection(cursor=MockCursor()))
    yield
    db_module._pool = None


@pytest.fixture
def tmp_codebase(tmp_path):
    """Create a temporary codebase directory with sample files.

    Creates a minimal codebase structure for testing:
    - codebase/main.py: Simple Python function
    - codebase/.gitignore: Standard gitignore patterns

    Args:
        tmp_path: pytest built-in fixture for temporary directory

    Returns:
        Path to the temporary codebase directory
    """
    codebase = tmp_path / "codebase"
    codebase.mkdir()

    # Create sample Python file
    (codebase / "main.py").write_text("def hello():\n    return 'world'\n")

    # Create sample gitignore
    (codebase / ".gitignore").write_text("*.pyc\n__pycache__/\n")

    return codebase
