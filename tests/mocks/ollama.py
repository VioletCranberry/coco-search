"""Ollama mock utilities for testing.

Provides deterministic embedding generation that produces consistent
results for the same input, enabling predictable test assertions.
"""

import hashlib


def deterministic_embedding(text: str, dimensions: int = 768) -> list[float]:
    """Generate a deterministic fake embedding from text hash.

    Same input always produces the same output, enabling predictable
    test assertions. The output mimics real embedding characteristics:
    - 768 dimensions (matching nomic-embed-text)
    - Values in [-1, 1] range
    - Deterministic based on input text

    Args:
        text: Text to generate embedding for.
        dimensions: Number of embedding dimensions (default 768).

    Returns:
        List of floats representing the fake embedding vector.
    """
    # Create a hash of the input text
    hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()

    # Expand hash to fill dimensions
    embedding = []
    for i in range(dimensions):
        # Cycle through hash bytes to fill all dimensions
        byte_idx = i % len(hash_bytes)
        # Normalize to [-1, 1] range typical for embeddings
        value = (hash_bytes[byte_idx] / 255.0) * 2 - 1
        embedding.append(value)

    return embedding


def similar_embedding(
    base_embedding: list[float], similarity: float = 0.9
) -> list[float]:
    """Create an embedding that has a specific similarity to the base.

    Useful for testing similarity thresholds and ranking.

    Args:
        base_embedding: The reference embedding.
        similarity: Target cosine similarity (0-1, default 0.9).

    Returns:
        New embedding with approximately the target similarity.
    """
    import random

    # Mix the base with noise based on similarity
    noise_factor = 1 - similarity
    result = []
    for val in base_embedding:
        noise = (random.random() * 2 - 1) * noise_factor
        new_val = val * similarity + noise
        # Clamp to [-1, 1]
        result.append(max(-1, min(1, new_val)))

    return result
