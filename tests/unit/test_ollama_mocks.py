"""Tests to verify Ollama mocking and data fixture infrastructure."""

from tests.mocks.ollama import deterministic_embedding


def test_deterministic_embedding_consistent():
    """Verify same input produces same embedding."""
    text = "find authentication code"

    embedding1 = deterministic_embedding(text)
    embedding2 = deterministic_embedding(text)

    assert embedding1 == embedding2
    assert len(embedding1) == 768


def test_deterministic_embedding_different_inputs():
    """Verify different inputs produce different embeddings."""
    embedding1 = deterministic_embedding("search for auth")
    embedding2 = deterministic_embedding("database queries")

    # Should be different
    assert embedding1 != embedding2


def test_deterministic_embedding_dimensions():
    """Verify embedding has correct dimensions."""
    embedding = deterministic_embedding("test", dimensions=768)
    assert len(embedding) == 768

    # All values should be in [-1, 1] range
    assert all(-1 <= v <= 1 for v in embedding)


def test_mock_code_to_embedding_fixture(mock_code_to_embedding):
    """Verify mock_code_to_embedding patches correctly."""
    from cocosearch.search.query import code_to_embedding

    result = code_to_embedding.eval("test query")

    assert len(result) == 768
    # Should be deterministic
    assert result == deterministic_embedding("test query")


def test_make_search_result_factory(make_search_result):
    """Verify SearchResult factory works."""
    result = make_search_result(
        filename="/custom/path.py",
        score=0.99,
    )

    assert result.filename == "/custom/path.py"
    assert result.score == 0.99
    assert result.start_byte == 0  # default
    assert result.end_byte == 100  # default


def test_sample_search_results_fixture(sample_search_results):
    """Verify list of SearchResults fixture."""
    assert len(sample_search_results) == 3
    # Should be sorted by score (highest first)
    assert sample_search_results[0].score > sample_search_results[1].score
