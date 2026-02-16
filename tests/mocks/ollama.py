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
