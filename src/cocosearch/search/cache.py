"""Query cache module for cocosearch.

Implements two-level caching for search queries:
1. Exact match: Hash-based lookup for identical queries
2. Semantic: Embedding similarity for paraphrased queries (cosine > 0.95)

Cache is in-memory for the session and invalidates on reindex.
"""

import hashlib
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Default cache directory (under user home)
DEFAULT_CACHE_DIR = os.path.expanduser("~/.cache/cocosearch/queries")

# Cache settings
MAX_CACHE_ENTRIES = 500  # Max entries before LRU eviction
MAX_SEMANTIC_SCAN = 50  # Max entries to scan for semantic similarity (O(n) search)
DEFAULT_TTL = 86400  # 24 hours
SEMANTIC_THRESHOLD = 0.92  # Cosine similarity threshold for semantic cache hits


@dataclass
class CacheEntry:
    """A cached query result with metadata."""

    results: list[Any]  # SearchResult objects
    embedding: list[float] | None  # Query embedding for semantic matching
    timestamp: float
    index_name: str


def _compute_cache_key(
    query: str,
    index_name: str,
    limit: int,
    min_score: float,
    language_filter: str | None,
    use_hybrid: bool | None,
    symbol_type: str | list[str] | None,
    symbol_name: str | None,
) -> str:
    """Compute SHA256 hash key from query parameters.

    Uses all search parameters to ensure cache hits only for identical searches.

    Args:
        query: Search query text.
        index_name: Index being searched.
        limit: Max results.
        min_score: Minimum score threshold.
        language_filter: Language filter if any.
        use_hybrid: Hybrid search flag.
        symbol_type: Symbol type filter.
        symbol_name: Symbol name filter.

    Returns:
        SHA256 hex digest as cache key.
    """
    # Normalize symbol_type to sorted tuple for consistent hashing
    if isinstance(symbol_type, list):
        symbol_type_str = ",".join(sorted(symbol_type))
    elif symbol_type:
        symbol_type_str = symbol_type
    else:
        symbol_type_str = ""

    # Build deterministic key string
    key_parts = [
        f"query={query}",
        f"index={index_name}",
        f"limit={limit}",
        f"min_score={min_score}",
        f"language={language_filter or ''}",
        f"hybrid={use_hybrid}",
        f"symbol_type={symbol_type_str}",
        f"symbol_name={symbol_name or ''}",
    ]
    key_str = "|".join(key_parts)

    return hashlib.sha256(key_str.encode()).hexdigest()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two embeddings.

    Args:
        a: First embedding vector.
        b: Second embedding vector.

    Returns:
        Cosine similarity in range [-1, 1], typically [0, 1] for embeddings.
    """
    a_np = np.array(a)
    b_np = np.array(b)

    dot = np.dot(a_np, b_np)
    norm_a = np.linalg.norm(a_np)
    norm_b = np.linalg.norm(b_np)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(dot / (norm_a * norm_b))


class QueryCache:
    """Two-level query cache with exact and semantic matching.

    Level 1 (Exact): Hash-based lookup for identical queries
    Level 2 (Semantic): Embedding similarity for paraphrased queries

    Cache entries expire after TTL and are invalidated on reindex.
    """

    def __init__(
        self,
        cache_dir: str = DEFAULT_CACHE_DIR,
        ttl: int = DEFAULT_TTL,
        semantic_threshold: float = SEMANTIC_THRESHOLD,
    ):
        """Initialize the query cache.

        Args:
            cache_dir: Directory for persistent cache storage.
            ttl: Time-to-live in seconds (default 24 hours).
            semantic_threshold: Cosine similarity threshold for semantic hits.
        """
        self.cache_dir = cache_dir
        self.ttl = ttl
        self.semantic_threshold = semantic_threshold
        self._lock = threading.Lock()

        # In-memory cache for fast access (session-scoped)
        # Key: cache_key, Value: CacheEntry
        self._cache: dict[str, CacheEntry] = {}

        # Embedding index for semantic search (index_name -> list of (key, embedding))
        self._embedding_index: dict[str, list[tuple[str, list[float]]]] = {}

        # Ensure cache directory exists
        os.makedirs(cache_dir, exist_ok=True)

        logger.debug(f"Query cache initialized at {cache_dir}")

    def get(
        self,
        query: str,
        index_name: str,
        limit: int,
        min_score: float,
        language_filter: str | None,
        use_hybrid: bool | None,
        symbol_type: str | list[str] | None,
        symbol_name: str | None,
        query_embedding: list[float] | None = None,
    ) -> tuple[list[Any] | None, str]:
        """Look up query in cache (exact then semantic).

        Args:
            query: Search query text.
            index_name: Index being searched.
            limit: Max results.
            min_score: Minimum score threshold.
            language_filter: Language filter if any.
            use_hybrid: Hybrid search flag.
            symbol_type: Symbol type filter.
            symbol_name: Symbol name filter.
            query_embedding: Pre-computed embedding for semantic matching.

        Returns:
            Tuple of (results, hit_type) where:
            - results: Cached results or None if miss
            - hit_type: "exact", "semantic", or "miss"
        """
        cache_key = _compute_cache_key(
            query,
            index_name,
            limit,
            min_score,
            language_filter,
            use_hybrid,
            symbol_type,
            symbol_name,
        )

        with self._lock:
            # Level 1: Exact match
            if cache_key in self._cache:
                entry = self._cache[cache_key]
                # Check TTL
                if time.time() - entry.timestamp < self.ttl:
                    logger.debug(f"Cache hit (exact): {cache_key[:16]}...")
                    return entry.results, "exact"
                else:
                    # Expired - remove from cache
                    del self._cache[cache_key]
                    self._remove_from_embedding_index(index_name, cache_key)

            # Level 2: Semantic match (only if we have embedding)
            # Scan only the most recent entries to bound O(n) cost
            if query_embedding and index_name in self._embedding_index:
                entries = self._embedding_index[index_name]
                for key, cached_embedding in entries[-MAX_SEMANTIC_SCAN:]:
                    if key in self._cache:
                        entry = self._cache[key]
                        # Check TTL
                        if time.time() - entry.timestamp >= self.ttl:
                            continue

                        sim = cosine_similarity(query_embedding, cached_embedding)
                        if sim >= self.semantic_threshold:
                            logger.debug(
                                f"Cache hit (semantic, sim={sim:.3f}): {key[:16]}..."
                            )
                            return entry.results, "semantic"

        return None, "miss"

    def put(
        self,
        query: str,
        index_name: str,
        limit: int,
        min_score: float,
        language_filter: str | None,
        use_hybrid: bool | None,
        symbol_type: str | list[str] | None,
        symbol_name: str | None,
        results: list[Any],
        query_embedding: list[float] | None = None,
    ) -> None:
        """Store query results in cache.

        Args:
            query: Search query text.
            index_name: Index being searched.
            limit: Max results.
            min_score: Minimum score threshold.
            language_filter: Language filter if any.
            use_hybrid: Hybrid search flag.
            symbol_type: Symbol type filter.
            symbol_name: Symbol name filter.
            results: Search results to cache.
            query_embedding: Query embedding for semantic matching.
        """
        cache_key = _compute_cache_key(
            query,
            index_name,
            limit,
            min_score,
            language_filter,
            use_hybrid,
            symbol_type,
            symbol_name,
        )

        entry = CacheEntry(
            results=results,
            embedding=query_embedding,
            timestamp=time.time(),
            index_name=index_name,
        )

        with self._lock:
            self._cache[cache_key] = entry

            # Add to embedding index if we have embedding
            if query_embedding:
                if index_name not in self._embedding_index:
                    self._embedding_index[index_name] = []
                self._embedding_index[index_name].append((cache_key, query_embedding))

            # LRU eviction: remove oldest entries when cache exceeds limit
            if len(self._cache) > MAX_CACHE_ENTRIES:
                self._evict_oldest()

        logger.debug(f"Cache put: {cache_key[:16]}...")

    def invalidate_index(self, index_name: str) -> int:
        """Remove all cached entries for an index.

        Called when reindexing to ensure fresh results.

        Args:
            index_name: Index to invalidate.

        Returns:
            Number of entries removed.
        """
        with self._lock:
            removed = 0

            # Remove from main cache
            keys_to_remove = [
                key
                for key, entry in self._cache.items()
                if entry.index_name == index_name
            ]
            for key in keys_to_remove:
                del self._cache[key]
                removed += 1

            # Remove from embedding index
            if index_name in self._embedding_index:
                del self._embedding_index[index_name]

        logger.info(
            f"Cache invalidated for index '{index_name}': {removed} entries removed"
        )
        return removed

    def _evict_oldest(self) -> None:
        """Evict oldest cache entries to stay within MAX_CACHE_ENTRIES.

        Must be called while holding self._lock.
        """
        entries_to_remove = len(self._cache) - MAX_CACHE_ENTRIES
        if entries_to_remove <= 0:
            return

        # Sort by timestamp ascending (oldest first)
        sorted_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k].timestamp)
        for key in sorted_keys[:entries_to_remove]:
            entry = self._cache.pop(key)
            self._remove_from_embedding_index(entry.index_name, key)

    def _remove_from_embedding_index(self, index_name: str, cache_key: str) -> None:
        """Remove a single entry from the embedding index.

        Deletes the key entirely when the list becomes empty to prevent
        accumulating empty lists over time.
        """
        if index_name in self._embedding_index:
            self._embedding_index[index_name] = [
                (k, e) for k, e in self._embedding_index[index_name] if k != cache_key
            ]
            if not self._embedding_index[index_name]:
                del self._embedding_index[index_name]

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._embedding_index.clear()
        logger.info("Cache cleared")


# Module-level singleton
_query_cache: QueryCache | None = None


def get_query_cache() -> QueryCache:
    """Get or create the global query cache singleton."""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache()
    return _query_cache


def invalidate_index_cache(index_name: str) -> int:
    """Invalidate cache for an index (convenience function).

    Args:
        index_name: Index to invalidate.

    Returns:
        Number of entries removed.
    """
    cache = get_query_cache()
    return cache.invalidate_index(index_name)
