"""Ollama fixtures for testing.

Provides fixtures that mock CocoIndex embedding functions to enable
testing without running Ollama or making API calls.
"""

import pytest
from unittest.mock import patch, MagicMock

from tests.mocks.ollama import deterministic_embedding


@pytest.fixture
def mock_code_to_embedding():
    """Mock the code_to_embedding.eval() function.

    Patches cocosearch.indexer.embedder.code_to_embedding with a mock
    that returns deterministic embeddings. The mock tracks calls for
    assertion.

    Usage:
        def test_search(mock_code_to_embedding, patched_db_pool):
            # code_to_embedding.eval() now returns deterministic embeddings
            result = search("find auth code", "myindex")
            mock_code_to_embedding.eval.assert_called_once()
    """
    mock = MagicMock()
    mock.eval = lambda text: deterministic_embedding(text)

    with patch("cocosearch.indexer.embedder.code_to_embedding", mock):
        # Also patch in search.query where it's imported
        with patch("cocosearch.search.query.code_to_embedding", mock):
            yield mock
