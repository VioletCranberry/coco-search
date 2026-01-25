"""Root conftest.py - pytest configuration and shared fixtures for cocosearch tests.

This module provides common fixtures used across all test modules:
- reset_db_pool: Autouse fixture that resets database pool between tests
- tmp_codebase: Creates temporary directory with sample Python files
"""

import pytest

# Register fixtures from fixtures directory (added by subsequent plans)
pytest_plugins = [
    # "tests.fixtures.db",      # Added by Plan 02
    "tests.fixtures.ollama",  # Added by Plan 03
    "tests.fixtures.data",    # Added by Plan 03
]


@pytest.fixture(autouse=True)
def reset_db_pool():
    """Reset database pool singleton between tests.

    This prevents connection pool state from leaking between tests.
    The pool is reset in teardown to ensure each test starts fresh.
    """
    yield
    # Teardown: reset pool singleton
    import cocosearch.search.db as db_module

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
