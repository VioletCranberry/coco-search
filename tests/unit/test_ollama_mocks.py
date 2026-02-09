"""Tests to verify Ollama mocking and data fixture infrastructure."""

from tests.mocks.ollama import deterministic_embedding, similar_embedding


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


def test_similar_embedding_creates_similar_vector():
    """Verify similar_embedding creates related vectors."""
    base = deterministic_embedding("test query")
    similar = similar_embedding(base, similarity=0.95)

    # Should have same dimensions
    assert len(similar) == len(base)

    # Values should still be in valid range
    assert all(-1 <= v <= 1 for v in similar)


def test_mock_code_to_embedding_fixture(mock_code_to_embedding):
    """Verify mock_code_to_embedding patches correctly."""
    from cocosearch.search.query import code_to_embedding

    result = code_to_embedding.eval("test query")

    assert len(result) == 768
    # Should be deterministic
    assert result == deterministic_embedding("test query")


def test_embedding_for_fixture(embedding_for):
    """Verify embedding_for returns consistent embeddings."""
    embedding1 = embedding_for("test")
    embedding2 = embedding_for("test")

    assert embedding1 == embedding2


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


def test_sample_search_result_fixture(sample_search_result):
    """Verify ready-to-use SearchResult fixture."""
    assert sample_search_result.filename == "/test/project/main.py"
    assert sample_search_result.score == 0.85


def test_sample_search_results_fixture(sample_search_results):
    """Verify list of SearchResults fixture."""
    assert len(sample_search_results) == 3
    # Should be sorted by score (highest first)
    assert sample_search_results[0].score > sample_search_results[1].score


def test_sample_code_content_fixture(sample_code_content):
    """Verify sample code content fixture."""
    assert "def authenticate" in sample_code_content["content"]
    assert sample_code_content["filename"] == "/project/auth.py"


def test_make_config_dict_factory(make_config_dict):
    """Verify config dict factory."""
    config = make_config_dict(include=["*.py", "*.js"], chunk_size=500)

    assert config["include"] == ["*.py", "*.js"]
    assert config["chunk_size"] == 500
    assert "exclude" not in config  # Only included if provided


def test_sample_config_dict_fixture(sample_config_dict):
    """Verify ready-to-use config dict fixture."""
    assert "*.py" in sample_config_dict["include"]
    assert "tests/" in sample_config_dict["exclude"]
