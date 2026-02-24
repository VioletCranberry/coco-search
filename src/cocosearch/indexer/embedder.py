"""Embedding module for cocosearch indexer.

Provides shared embedding functions used by both indexing and search
to ensure consistent embeddings.
"""

import os

import cocoindex


@cocoindex.op.function(behavior_version=1)
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


@cocoindex.op.function(behavior_version=1)
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


@cocoindex.op.function(behavior_version=1)
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


PROVIDER_MAP: dict[str, "cocoindex.LlmApiType"] = {
    "ollama": cocoindex.LlmApiType.OLLAMA,
    "openai": cocoindex.LlmApiType.OPENAI,
    "openrouter": cocoindex.LlmApiType.OPEN_ROUTER,
}


def _default_model(provider: str) -> str:
    """Return the default embedding model for a provider."""
    from cocosearch.config.schema import default_model_for_provider

    return default_model_for_provider(provider)


@cocoindex.transform_flow()
def code_to_embedding(
    text: cocoindex.DataSlice[str],
) -> cocoindex.DataSlice[list[float]]:
    """Shared embedding function for indexing and querying.

    Supports multiple embedding providers (Ollama, OpenAI, OpenRouter).
    Provider selection is controlled via environment variables.

    Environment variables:
        COCOSEARCH_EMBEDDING_PROVIDER: Provider name (default: ollama).
        COCOSEARCH_OLLAMA_URL: Ollama server address (default: http://localhost:11434).
        COCOSEARCH_EMBEDDING_MODEL: Embedding model name (default depends on provider).
        COCOSEARCH_EMBEDDING_API_KEY: API key for remote providers (OpenAI, OpenRouter).

    Args:
        text: Text to embed.

    Returns:
        Embedding vector.
    """
    provider = os.environ.get("COCOSEARCH_EMBEDDING_PROVIDER", "ollama")
    model = os.environ.get("COCOSEARCH_EMBEDDING_MODEL", _default_model(provider))
    api_type = PROVIDER_MAP.get(provider, cocoindex.LlmApiType.OLLAMA)

    kwargs: dict = {"api_type": api_type, "model": model}

    if provider == "ollama":
        kwargs["address"] = os.environ.get("COCOSEARCH_OLLAMA_URL")
    else:
        api_key = os.environ.get("COCOSEARCH_EMBEDDING_API_KEY")
        if api_key:
            kwargs["api_key"] = cocoindex.auth_registry.add_transient_auth_entry(
                api_key
            )

    return text.transform(cocoindex.functions.EmbedText(**kwargs))
