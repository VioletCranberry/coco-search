"""Unit test conftest.py - auto-apply unit marker to all tests in this directory."""

import pytest


def pytest_collection_modifyitems(items):
    """Add unit marker to all tests in tests/unit/."""
    for item in items:
        if "/unit/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
