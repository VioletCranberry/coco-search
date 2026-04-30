"""Embedding module for cocosearch indexer.

Provides shared embedding functions used by both indexing and search
to ensure consistent embeddings. Uses LiteLLM for provider abstraction.
"""

import os

import litellm


def extract_extension(filename: str) -> str:
    """Extract file extension for language detection.

    Args:
        filename: File name or path.

    Returns:
        File extension without the leading dot (e.g., "py" for "test.py").
        Returns empty string if no extension.
    """
    _, ext = os.path.splitext(filename)
    return ext[1:] if ext else ""


def extract_language(filename: str, content: str) -> str:
    """Extract language identifier for RecursiveSplitter routing.

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

    grammar = detect_grammar(filename, content)
    if grammar is not None:
        return grammar

    basename = os.path.basename(filename)

    if basename == "Containerfile" or basename.startswith("Dockerfile"):
        return "dockerfile"

    _, ext = os.path.splitext(filename)
    return ext[1:] if ext else ""


def add_filename_context(text: str, filename: str) -> str:
    """Prepend filename context to text for embedding generation.

    Gives the embedding model file path context so that queries like
    "release flow" can match files named release.yaml even if the
    chunk text doesn't mention "release".

    Only used for embedding input — the stored content_text remains raw.

    Args:
        text: Raw chunk text.
        filename: File path (e.g., ".github/workflows/release.yaml").

    Returns:
        Text with filename prefix, or original text if filename is empty.
    """
    if filename:
        return f"File: {filename}\n{text}"
    return text


_KNOWN_DIMENSIONS: dict[str, int] = {
    "nomic-embed-text": 768,
    "text-embedding-3-small": 1536,
    "openai/text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "openai/text-embedding-3-large": 3072,
}


def _resolve_output_dimension(model: str) -> int | None:
    """Resolve embedding output dimension from env var or known models map.

    Priority: COCOSEARCH_EMBEDDING_OUTPUT_DIMENSION env var > known map > None.
    """
    output_dim_str = os.environ.get("COCOSEARCH_EMBEDDING_OUTPUT_DIMENSION")
    if output_dim_str:
        return int(output_dim_str)
    return _KNOWN_DIMENSIONS.get(model)


def _default_model(provider: str) -> str:
    """Return the default embedding model for a provider."""
    from cocosearch.config.schema import default_model_for_provider

    return default_model_for_provider(provider)


def _get_litellm_model() -> str:
    """Build the LiteLLM model string from COCOSEARCH env vars.

    Maps COCOSEARCH_EMBEDDING_PROVIDER + COCOSEARCH_EMBEDDING_MODEL
    to a LiteLLM-compatible model identifier.

    Returns:
        LiteLLM model string (e.g., "ollama/nomic-embed-text").
    """
    provider = os.environ.get("COCOSEARCH_EMBEDDING_PROVIDER", "ollama")
    model = os.environ.get("COCOSEARCH_EMBEDDING_MODEL", _default_model(provider))

    if provider == "ollama":
        return f"ollama/{model}"
    elif provider == "openrouter":
        return f"openrouter/{model}"
    return model


def _get_litellm_kwargs() -> dict:
    """Build kwargs dict for litellm.embedding() calls.

    Reads api_base and api_key from COCOSEARCH env vars.
    """
    provider = os.environ.get("COCOSEARCH_EMBEDDING_PROVIDER", "ollama")
    kwargs: dict = {}

    api_base = os.environ.get("COCOSEARCH_EMBEDDING_BASE_URL")
    if api_base is None and provider == "ollama":
        api_base = os.environ.get("COCOSEARCH_OLLAMA_URL")
    if api_base:
        kwargs["api_base"] = api_base

    api_key = os.environ.get("COCOSEARCH_EMBEDDING_API_KEY")
    if api_key:
        kwargs["api_key"] = api_key

    return kwargs


def embed_query(text: str) -> list[float]:
    """Embed a single text for search queries.

    Uses LiteLLM to call the configured embedding provider synchronously.
    This function is used by the search side (query.py, hybrid.py, multi.py)
    to embed search queries without needing a CocoIndex runtime.

    Args:
        text: Text to embed.

    Returns:
        Embedding vector as list of floats.
    """
    model = _get_litellm_model()
    kwargs = _get_litellm_kwargs()

    response = litellm.embedding(model=model, input=[text], **kwargs)
    return [float(x) for x in response.data[0]["embedding"]]
