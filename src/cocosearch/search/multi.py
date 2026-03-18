"""Cross-index search orchestrator for cocosearch.

Provides multi_search() to query multiple indexes in one call and return
a unified, ranked result set. Each index is searched independently using
the existing search() function, results are tagged with their source
index, and then merged into a single ranked list by score.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from cocosearch.indexer.embedder import code_to_embedding
from cocosearch.management.discovery import list_indexes
from cocosearch.management.metadata import get_index_metadata
from cocosearch.search.query import SearchResult, search

logger = logging.getLogger(__name__)


def _get_cs_log():
    """Lazy import to avoid circular dependency."""
    from cocosearch.logging import cs_log

    return cs_log


def multi_search(
    query: str,
    index_names: list[str],
    limit: int = 10,
    min_score: float = 0.0,
    language_filter: str | None = None,
    use_hybrid: bool | None = None,
    symbol_type: str | list[str] | None = None,
    symbol_name: str | None = None,
    no_cache: bool = False,
    include_deps: bool = False,
    warnings: list[dict] | None = None,
) -> list[SearchResult]:
    """Search across multiple indexes and return merged results.

    Computes the query embedding once, then searches each index in parallel
    using ThreadPoolExecutor. Results are tagged with their source index
    and merged by score descending.

    Args:
        query: Natural language search query.
        index_names: List of index names to search.
        limit: Maximum total results to return.
        min_score: Minimum similarity score to include.
        language_filter: Optional language filter.
        use_hybrid: Hybrid search mode (None=auto, True=force, False=vector-only).
        symbol_type: Filter by symbol type.
        symbol_name: Filter by symbol name pattern.
        no_cache: If True, bypass query cache.
        include_deps: If True, attach dependency info to results.
        warnings: Optional list to populate with warning dicts (e.g., model mismatch).

    Returns:
        List of SearchResult ordered by score (highest first), each tagged
        with index_name indicating its source index.

    Raises:
        ValueError: If any index name is not found.
    """
    if not index_names:
        return []

    # Single index: just delegate directly
    if len(index_names) == 1:
        results = search(
            query=query,
            index_name=index_names[0],
            limit=limit,
            min_score=min_score,
            language_filter=language_filter,
            use_hybrid=use_hybrid,
            symbol_type=symbol_type,
            symbol_name=symbol_name,
            no_cache=no_cache,
            include_deps=include_deps,
        )
        for r in results:
            r.index_name = index_names[0]
        return results

    # Validate all index names exist
    available = {idx["name"] for idx in list_indexes()}
    unknown = [name for name in index_names if name not in available]
    if unknown:
        raise ValueError(
            f"Unknown index(es): {', '.join(unknown)}. "
            f"Available: {', '.join(sorted(available))}"
        )

    # Check embedding model compatibility across indexes
    models_seen: dict[str, str] = {}
    for idx_name in index_names:
        meta = get_index_metadata(idx_name)
        if meta:
            model = meta.get("embedding_model", "unknown")
            provider = meta.get("embedding_provider", "unknown")
            key = f"{provider}/{model}"
            models_seen[idx_name] = key

    unique_models = set(models_seen.values())
    if len(unique_models) > 1:
        model_details = ", ".join(f"{k}={v}" for k, v in models_seen.items())
        warning_msg = (
            "Cross-index search with mismatched embedding models — "
            f"scores may not be directly comparable: {model_details}"
        )
        logger.warning(warning_msg)
        if warnings is not None:
            warnings.append(
                {
                    "type": "embedding_model_mismatch",
                    "warning": "Mismatched embedding models across indexes",
                    "message": warning_msg,
                    "models": dict(models_seen),
                }
            )

    # Pre-compute query embedding once
    query_embedding = code_to_embedding.eval(query)

    # Request more results per index for better candidate pool
    per_index_limit = limit * 2

    # Search each index in parallel
    all_results: list[SearchResult] = []
    errors: dict[str, str] = {}
    max_workers = min(len(index_names), 4)

    def _search_index(idx_name: str) -> list[SearchResult]:
        results = search(
            query=query,
            index_name=idx_name,
            limit=per_index_limit,
            min_score=min_score,
            language_filter=language_filter,
            use_hybrid=use_hybrid,
            symbol_type=symbol_type,
            symbol_name=symbol_name,
            no_cache=no_cache,
            include_deps=include_deps,
            query_embedding=query_embedding,
        )
        for r in results:
            r.index_name = idx_name
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_search_index, idx_name): idx_name
            for idx_name in index_names
        }
        for future in as_completed(futures):
            idx_name = futures[future]
            try:
                results = future.result()
                all_results.extend(results)
            except Exception as e:
                errors[idx_name] = str(e)
                logger.warning("Search failed for index '%s': %s", idx_name, e)

    # If all indexes failed, raise
    if errors and not all_results:
        error_details = "; ".join(f"{k}: {v}" for k, v in errors.items())
        raise ValueError(f"All index searches failed: {error_details}")

    # Log partial failures
    if errors:
        _get_cs_log().search(
            "Partial cross-index search failure",
            failed_indexes=list(errors.keys()),
            successful_results=len(all_results),
        )

    # Sort by score descending and take top limit
    all_results.sort(key=lambda r: r.score, reverse=True)
    return all_results[:limit]
