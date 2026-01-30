"""Integration test conftest.py - Docker checks and auto-apply integration marker."""

import pytest

# Register container fixtures for integration tests
pytest_plugins = ["tests.fixtures.containers", "tests.fixtures.ollama_integration"]


def pytest_configure(config):
    """Check Docker availability at test session start.

    Locked decision from CONTEXT.md: "Fail immediately if Docker unavailable --
    hard error forces Docker availability"

    Only check when running integration tests (not unit tests).
    """
    # Only check Docker when running integration tests
    # Check if we're collecting integration tests by looking at markers
    marker_expr = getattr(config.option, "markexpr", "")
    if marker_expr and "integration" in marker_expr:
        try:
            import docker

            client = docker.from_env()
            client.ping()
        except Exception as e:
            pytest.exit(
                f"Docker is not available: {e}\n\n"
                f"Integration tests require Docker to be installed and running.\n"
                f"Install Docker: https://docs.docker.com/get-docker/\n\n"
                f"To run unit tests only (no Docker required):\n"
                f"  pytest -m unit",
                returncode=1,
            )


def pytest_collection_modifyitems(items):
    """Add integration marker to all tests in tests/integration/."""
    for item in items:
        if "/integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
