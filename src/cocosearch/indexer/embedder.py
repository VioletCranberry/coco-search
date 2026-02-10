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


@cocoindex.op.function()
def extract_language(filename: str, content: str) -> str:
    """Extract language identifier for SplitRecursively routing.

    Checks grammar handlers first (path + content matching), then filename
    patterns (for extensionless files like Dockerfile), then falls back to
    extension-based detection.

    Priority: Grammar match > Filename pattern > Extension.

    Args:
        filename: File name or path.
        content: File content for grammar detection.

    Returns:
        Language identifier string (e.g., "github-actions", "dockerfile", "py").
        Returns empty string if no language detected.
    """
    from cocosearch.handlers import detect_grammar

    # Grammar-based routing (path + content matching)
    grammar = detect_grammar(filename, content)
    if grammar is not None:
        return grammar

    basename = os.path.basename(filename)

    # Filename-based routing (extensionless files)
    if basename == "Containerfile" or basename.startswith("Dockerfile"):
        return "dockerfile"

    # Extension-based routing (standard behavior, same as extract_extension)
    _, ext = os.path.splitext(filename)
    return ext[1:] if ext else ""


@cocoindex.transform_flow()
def code_to_embedding(
    text: cocoindex.DataSlice[str],
) -> cocoindex.DataSlice[list[float]]:
    """Shared embedding function for indexing and querying.

    Uses Ollama with nomic-embed-text model to generate 768-dimensional
    embeddings. This function should be used by both the indexing flow
    and search queries to ensure consistent embeddings.

    Reads COCOSEARCH_OLLAMA_URL environment variable to determine Ollama server address.
    Defaults to None (which uses CocoIndex default: http://localhost:11434).

    Args:
        text: Text to embed.

    Returns:
        768-dimensional embedding vector.
    """
    # Read Ollama URL from environment
    # If not set, EmbedText will use its default (localhost:11434)
    ollama_url = os.environ.get("COCOSEARCH_OLLAMA_URL")

    return text.transform(
        cocoindex.functions.EmbedText(
            api_type=cocoindex.LlmApiType.OLLAMA,
            model="nomic-embed-text",
            address=ollama_url,
        )
    )
