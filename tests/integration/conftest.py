"""Integration test conftest.py - auto-apply integration marker to all tests in this directory."""

import pytest


def pytest_collection_modifyitems(items):
    """Add integration marker to all tests in tests/integration/."""
    for item in items:
        if "/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
