"""Ollama fixtures for testing.

Provides fixtures that mock LiteLLM embedding functions to enable
testing without running Ollama or making API calls.
"""

import pytest
from unittest.mock import patch

from tests.mocks.ollama import deterministic_embedding


@pytest.fixture
def mock_embed_query():
    """Mock the embed_query() function.

    Patches cocosearch.indexer.embedder.embed_query with a function
    that returns deterministic embeddings. Also patches the imported
    references in search modules.

    Usage:
        def test_search(mock_embed_query, patched_db_pool):
            # embed_query() now returns deterministic embeddings
            result = search("find auth code", "myindex")
    """
    with patch(
        "cocosearch.indexer.embedder.embed_query", side_effect=deterministic_embedding
    ):
        with patch(
            "cocosearch.search.query.embed_query", side_effect=deterministic_embedding
        ):
            with patch(
                "cocosearch.search.hybrid.embed_query",
                side_effect=deterministic_embedding,
            ):
                with patch(
                    "cocosearch.search.multi.embed_query",
                    side_effect=deterministic_embedding,
                ):
                    yield deterministic_embedding


@pytest.fixture
def mock_code_to_embedding(mock_embed_query):
    """Backward-compatible alias for mock_embed_query."""
    return mock_embed_query
