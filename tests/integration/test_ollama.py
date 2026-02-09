"""Ollama integration tests.

Tests validating real Ollama embedding generation:
- Embedding dimensions (768 for nomic-embed-text)
- Value range checks (floats, not NaN/Inf)
- Similarity sanity (similar texts produce similar embeddings)

These tests require Ollama (native or Docker) and are marked with @pytest.mark.integration.
The marker is auto-applied by tests/integration/conftest.py.
"""

import numpy as np

import cocoindex


class TestEmbeddingGeneration:
    """Tests for basic embedding generation properties."""

    def test_embedding_dimensions(self, warmed_ollama):
        """Verify embeddings have exactly 768 dimensions.

        Requirement: OLLAMA-03 (Embedding dimension validation)
        """
        # Generate embedding for sample code
        sample_code = "def hello_world():\n    print('Hello')"

        embedding_flow = cocoindex.transform_flow()(
            lambda text: text.transform(
                cocoindex.functions.EmbedText(
                    api_type=cocoindex.LlmApiType.OLLAMA,
                    model="nomic-embed-text",
                )
            )
        )

        result = embedding_flow(cocoindex.DataSlice([sample_code]))
        embedding = result[0]

        assert len(embedding) == 768, f"Expected 768 dimensions, got {len(embedding)}"

    def test_embedding_values_valid(self, warmed_ollama):
        """Verify embedding values are valid floats without NaN/Inf.

        Requirement: OLLAMA-03 (Embedding value validation)
        """
        sample_text = "Python function for sorting a list"

        embedding_flow = cocoindex.transform_flow()(
            lambda text: text.transform(
                cocoindex.functions.EmbedText(
                    api_type=cocoindex.LlmApiType.OLLAMA,
                    model="nomic-embed-text",
                )
            )
        )

        result = embedding_flow(cocoindex.DataSlice([sample_text]))
        embedding = np.array(result[0])

        # Check all values are floats
        assert embedding.dtype in [np.float32, np.float64], (
            f"Expected float values, got {embedding.dtype}"
        )

        # Check for NaN values
        assert not np.any(np.isnan(embedding)), "Embedding contains NaN values"

        # Check for Inf values
        assert not np.any(np.isinf(embedding)), "Embedding contains Inf values"

        # Check values are in reasonable range (normalized vectors usually smaller)
        assert np.all(embedding >= -10) and np.all(embedding <= 10), (
            f"Embedding values outside reasonable range: "
            f"min={embedding.min()}, max={embedding.max()}"
        )

    def test_embedding_consistent(self, warmed_ollama):
        """Verify embeddings are deterministic for same input.

        Requirement: OLLAMA-01 (Consistent embedding generation)
        """
        sample_text = "Python method to sort an array"

        embedding_flow = cocoindex.transform_flow()(
            lambda text: text.transform(
                cocoindex.functions.EmbedText(
                    api_type=cocoindex.LlmApiType.OLLAMA,
                    model="nomic-embed-text",
                )
            )
        )

        # Generate embedding twice
        result1 = embedding_flow(cocoindex.DataSlice([sample_text]))
        result2 = embedding_flow(cocoindex.DataSlice([sample_text]))

        embedding1 = np.array(result1[0])
        embedding2 = np.array(result2[0])

        # Embeddings should be identical (deterministic model)
        assert np.array_equal(embedding1, embedding2), (
            "Embeddings for same text should be identical"
        )


def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


class TestEmbeddingSimilarity:
    """Tests for semantic similarity of embeddings."""

    def test_similar_texts_high_similarity(self, warmed_ollama):
        """Verify semantically similar texts produce similar embeddings.

        Requirement: OLLAMA-01 (Real embedding behavior validation)
        """
        # Semantically similar texts
        text1 = "Python function for sorting a list"
        text2 = "Python method to sort an array"

        embedding_flow = cocoindex.transform_flow()(
            lambda text: text.transform(
                cocoindex.functions.EmbedText(
                    api_type=cocoindex.LlmApiType.OLLAMA,
                    model="nomic-embed-text",
                )
            )
        )

        result = embedding_flow(cocoindex.DataSlice([text1, text2]))
        embedding1 = np.array(result[0])
        embedding2 = np.array(result[1])

        similarity = cosine_similarity(embedding1, embedding2)

        assert similarity > 0.8, (
            f"Similar texts should have similarity > 0.8, got {similarity:.4f}"
        )

    def test_dissimilar_texts_lower_similarity(self, warmed_ollama):
        """Verify semantically dissimilar texts produce different embeddings.

        Requirement: OLLAMA-01 (Real embedding semantic understanding)
        """
        # Semantically dissimilar texts
        text1 = "Python function for sorting a list"
        text2 = "Recipe for chocolate cake"

        embedding_flow = cocoindex.transform_flow()(
            lambda text: text.transform(
                cocoindex.functions.EmbedText(
                    api_type=cocoindex.LlmApiType.OLLAMA,
                    model="nomic-embed-text",
                )
            )
        )

        result = embedding_flow(cocoindex.DataSlice([text1, text2]))
        embedding1 = np.array(result[0])
        embedding2 = np.array(result[1])

        similarity = cosine_similarity(embedding1, embedding2)

        assert similarity < 0.7, (
            f"Dissimilar texts should have similarity < 0.7, got {similarity:.4f}"
        )

    def test_code_vs_natural_language(self, warmed_ollama):
        """Verify code embeddings work for code search use case.

        Requirement: OLLAMA-01 (Code embedding validation)
        """
        # Code and its natural language description
        code = "def sort_list(items): return sorted(items)"
        description = "A function that sorts a list"

        embedding_flow = cocoindex.transform_flow()(
            lambda text: text.transform(
                cocoindex.functions.EmbedText(
                    api_type=cocoindex.LlmApiType.OLLAMA,
                    model="nomic-embed-text",
                )
            )
        )

        result = embedding_flow(cocoindex.DataSlice([code, description]))
        code_embedding = np.array(result[0])
        desc_embedding = np.array(result[1])

        similarity = cosine_similarity(code_embedding, desc_embedding)

        # Code and description should be reasonably similar (for code search)
        # but not identical
        assert similarity > 0.5, (
            f"Code and description should have similarity > 0.5, got {similarity:.4f}"
        )
        assert similarity < 1.0, (
            f"Code and description should not be identical, got {similarity:.4f}"
        )
