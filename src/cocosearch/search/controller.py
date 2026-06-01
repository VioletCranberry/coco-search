"""Optional query-rewrite controller for cocosearch.

When enabled (default OFF), an LLM rewrites/expands a natural-language search
query into better search terms before retrieval. For example:

    "how does login work" -> "authentication session credential login user token"

This is a thin, additive layer in front of the existing deterministic retrieval
pipeline (auto hybrid-vs-vector selection, dynamic prefetch, RRF fusion, two-level
cache). It is configured exactly like the embedding provider — provider, model,
baseUrl (env COCOSEARCH_CONTROLLER_*) — and reuses LiteLLM.

The controller is designed to NEVER break search: when disabled, on any error,
timeout, or empty/garbage model output, ``rewrite_query`` returns the original
query unchanged. Search therefore degrades gracefully to today's behavior.
"""

import os

import litellm

from cocosearch.config.schema import default_controller_model_for_provider

_REWRITE_SYSTEM_PROMPT = (
    "You rewrite a software code-search query into better search terms.\n"
    "Rules:\n"
    "- Expand the intent into 4-10 relevant search keywords.\n"
    "- PRESERVE any code identifiers verbatim (camelCase, snake_case, "
    "PascalCase, dotted.paths).\n"
    "- Do NOT add explanations, punctuation, quotes, or markdown.\n"
    "- Return ONLY the rewritten query on a single line.\n"
    'Example: "how does login work" -> '
    '"authentication session credential login user token"'
)


def _get_cs_log():
    """Lazy import to avoid circular dependency (search -> logging -> mcp -> search)."""
    from cocosearch.logging import cs_log

    return cs_log


def _controller_enabled() -> bool:
    """Whether the query-rewrite controller is enabled via config/env."""
    return os.environ.get("COCOSEARCH_CONTROLLER_ENABLED", "false").lower() in (
        "true",
        "1",
        "yes",
    )


def _default_model(provider: str) -> str:
    return default_controller_model_for_provider(provider)


def _get_litellm_model() -> str:
    """Build the LiteLLM model string from COCOSEARCH_CONTROLLER_* env vars."""
    provider = os.environ.get("COCOSEARCH_CONTROLLER_PROVIDER", "ollama")
    model = os.environ.get("COCOSEARCH_CONTROLLER_MODEL") or _default_model(provider)

    if provider == "ollama":
        return f"ollama/{model}"
    elif provider == "openrouter":
        return f"openrouter/{model}"
    return model


def _get_litellm_kwargs() -> dict:
    """Build kwargs dict for litellm.completion() calls.

    Reads api_base and api_key from COCOSEARCH_CONTROLLER_* env vars, mirroring
    the embedder. For the ollama provider, falls back to COCOSEARCH_OLLAMA_URL.
    If no controller API key is set but the controller uses the SAME provider as
    embedding, the embedding API key is reused — so you don't have to duplicate
    it (e.g. both on openrouter).
    """
    provider = os.environ.get("COCOSEARCH_CONTROLLER_PROVIDER", "ollama")
    kwargs: dict = {}

    api_base = os.environ.get("COCOSEARCH_CONTROLLER_BASE_URL")
    if api_base is None and provider == "ollama":
        api_base = os.environ.get("COCOSEARCH_OLLAMA_URL")
    if api_base:
        kwargs["api_base"] = api_base

    api_key = os.environ.get("COCOSEARCH_CONTROLLER_API_KEY")
    if not api_key and provider == os.environ.get("COCOSEARCH_EMBEDDING_PROVIDER"):
        api_key = os.environ.get("COCOSEARCH_EMBEDDING_API_KEY")
    if api_key:
        kwargs["api_key"] = api_key

    return kwargs


def _timeout() -> float:
    """Hard timeout (seconds) so a slow controller never hangs search."""
    try:
        return float(os.environ.get("COCOSEARCH_CONTROLLER_TIMEOUT", "5.0"))
    except ValueError:
        return 5.0


def _validate_rewrite(original: str, raw: str) -> str | None:
    """Sanitize model output.

    Returns a cleaned single-line query, or None to reject (caller falls back to
    the original query). Rejects empty, multiline, and runaway-length output.
    """
    if not raw:
        return None
    text = raw.strip().splitlines()[0].strip().strip('"').strip("`").strip()
    if not text:
        return None
    if "\n" in text:
        return None
    if len(text) > 4 * len(original) + 64:
        return None
    return text


def rewrite_query(query: str) -> tuple[str, bool]:
    """Rewrite/expand a search query using the configured controller model.

    Args:
        query: The original (already validated) search query.

    Returns:
        Tuple of ``(effective_query, was_rewritten)``. ``effective_query`` is the
        rewritten query when the controller is enabled and produced valid output,
        otherwise the original query. This function NEVER raises — any error,
        timeout, disabled state, or garbage output falls back to the original.
    """
    if not _controller_enabled():
        return query, False

    try:
        response = litellm.completion(
            model=_get_litellm_model(),
            messages=[
                {"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            timeout=_timeout(),
            temperature=0.0,
            max_tokens=64,
            **_get_litellm_kwargs(),
        )
        raw = (response.choices[0].message.content or "").strip()
    except Exception as e:  # noqa: BLE001 - controller must never break search
        _get_cs_log().search(
            "Query rewrite failed, using original query",
            level="DEBUG",
            error=str(e),
        )
        return query, False

    cleaned = _validate_rewrite(query, raw)
    if cleaned is None or cleaned == query:
        return query, False

    _get_cs_log().search(
        "Query rewritten by controller",
        original=query[:100],
        rewritten=cleaned[:100],
    )
    return cleaned, True
