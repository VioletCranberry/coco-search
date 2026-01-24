"""Embedding module for cocosearch indexer.

Provides shared embedding functions used by both indexing and search
to ensure consistent embeddings.
"""

import os

import cocoindex


@cocoindex.op.function()
def extract_extension(filename: str) -> str:
    """Extract file extension for language detection.

    Args:
        filename: File name or path.

    Returns:
        File extension without the leading dot (e.g., "py" for "test.py").
        Returns empty string if no extension.
    """
    _, ext = os.path.splitext(filename)
    # Remove leading dot if present
    return ext[1:] if ext else ""


@cocoindex.transform_flow()
def code_to_embedding(
    text: cocoindex.DataSlice[str],
) -> cocoindex.DataSlice[list[float]]:
    """Shared embedding function for indexing and querying.

    Uses Ollama with nomic-embed-text model to generate 768-dimensional
    embeddings. This function should be used by both the indexing flow
    and search queries to ensure consistent embeddings.

    Args:
        text: Text to embed.

    Returns:
        768-dimensional embedding vector.
    """
    return text.transform(
        cocoindex.functions.EmbedText(
            api_type=cocoindex.LlmApiType.OLLAMA,
            model="nomic-embed-text",
        )
    )
