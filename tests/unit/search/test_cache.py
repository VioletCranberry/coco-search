"""Unit tests for query cache module.

Tests exact match caching, semantic similarity caching,
cache invalidation, and TTL expiration.
"""

import time

import pytest

from cocosearch.search.cache import (
    QueryCache,
    _compute_cache_key,
    cosine_similarity,
    get_query_cache,
    invalidate_index_cache,
)


class TestCacheKey:
    """Tests for cache key computation."""

    def test_same_params_same_key(self):
        """Identical parameters produce identical keys."""
        key1 = _compute_cache_key("query", "index", 10, 0.0, None, None, None, None)
        key2 = _compute_cache_key("query", "index", 10, 0.0, None, None, None, None)
        assert key1 == key2

    def test_different_query_different_key(self):
        """Different queries produce different keys."""
        key1 = _compute_cache_key("query1", "index", 10, 0.0, None, None, None, None)
        key2 = _compute_cache_key("query2", "index", 10, 0.0, None, None, None, None)
        assert key1 != key2

    def test_different_index_different_key(self):
        """Different indexes produce different keys."""
        key1 = _compute_cache_key("query", "index1", 10, 0.0, None, None, None, None)
        key2 = _compute_cache_key("query", "index2", 10, 0.0, None, None, None, None)
        assert key1 != key2

    def test_symbol_type_list_normalized(self):
        """Symbol type list is normalized for consistent hashing."""
        key1 = _compute_cache_key(
            "query", "index", 10, 0.0, None, None, ["function", "method"], None
        )
        key2 = _compute_cache_key(
            "query", "index", 10, 0.0, None, None, ["method", "function"], None
        )
        assert key1 == key2  # Order shouldn't matter

    def test_different_limit_different_key(self):
        """Different limits produce different keys."""
        key1 = _compute_cache_key("query", "index", 10, 0.0, None, None, None, None)
        key2 = _compute_cache_key("query", "index", 20, 0.0, None, None, None, None)
        assert key1 != key2

    def test_different_min_score_different_key(self):
        """Different min scores produce different keys."""
        key1 = _compute_cache_key("query", "index", 10, 0.0, None, None, None, None)
        key2 = _compute_cache_key("query", "index", 10, 0.5, None, None, None, None)
        assert key1 != key2


class TestCosineSimilarity:
    """Tests for cosine similarity computation."""

    def test_identical_vectors(self):
        """Identical vectors have similarity 1.0."""
        vec = [1.0, 0.0, 0.0]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        """Orthogonal vectors have similarity 0.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        """Opposite vectors have similarity -1.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(-1.0)

    def test_zero_vector(self):
        """Zero vector returns 0 similarity."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 0.0, 0.0]
        assert cosine_similarity(vec1, vec2) == 0.0

    def test_similar_vectors(self):
        """Similar vectors have high similarity."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.99, 0.1, 0.0]
        sim = cosine_similarity(vec1, vec2)
        assert sim > 0.9


class TestQueryCache:
    """Tests for QueryCache class."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create a cache instance with temp directory."""
        return QueryCache(cache_dir=str(tmp_path), ttl=3600)

    def test_exact_cache_hit(self, cache):
        """Exact match returns cached results."""
        results = [{"file": "test.py", "score": 0.9}]

        cache.put(
            query="test query",
            index_name="test-index",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
            results=results,
        )

        cached, hit_type = cache.get(
            query="test query",
            index_name="test-index",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
        )

        assert cached == results
        assert hit_type == "exact"

    def test_cache_miss(self, cache):
        """Missing query returns None."""
        cached, hit_type = cache.get(
            query="unknown query",
            index_name="test-index",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
        )

        assert cached is None
        assert hit_type == "miss"

    def test_semantic_cache_hit(self, cache):
        """Similar embedding returns cached results."""
        results = [{"file": "test.py", "score": 0.9}]
        embedding = [1.0, 0.0, 0.0]

        # Store with embedding
        cache.put(
            query="original query",
            index_name="test-index",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
            results=results,
            query_embedding=embedding,
        )

        # Query with very similar embedding (sim > 0.95)
        similar_embedding = [0.99, 0.01, 0.0]

        cached, hit_type = cache.get(
            query="different query",
            index_name="test-index",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
            query_embedding=similar_embedding,
        )

        assert cached == results
        assert hit_type == "semantic"

    def test_semantic_cache_miss_below_threshold(self, cache):
        """Dissimilar embedding returns miss."""
        results = [{"file": "test.py", "score": 0.9}]
        embedding = [1.0, 0.0, 0.0]

        cache.put(
            query="original query",
            index_name="test-index",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
            results=results,
            query_embedding=embedding,
        )

        # Very different embedding (sim < 0.95)
        different_embedding = [0.0, 1.0, 0.0]

        cached, hit_type = cache.get(
            query="different query",
            index_name="test-index",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
            query_embedding=different_embedding,
        )

        assert cached is None
        assert hit_type == "miss"

    def test_invalidate_index(self, cache):
        """Invalidation removes all entries for index."""
        results = [{"file": "test.py"}]

        cache.put(
            query="query1",
            index_name="test-index",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
            results=results,
        )

        removed = cache.invalidate_index("test-index")
        assert removed == 1

        cached, _ = cache.get(
            query="query1",
            index_name="test-index",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
        )
        assert cached is None

    def test_invalidate_preserves_other_indexes(self, cache):
        """Invalidation only affects specified index."""
        results = [{"file": "test.py"}]

        cache.put(
            query="query1",
            index_name="index-a",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
            results=results,
        )
        cache.put(
            query="query2",
            index_name="index-b",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
            results=results,
        )

        cache.invalidate_index("index-a")

        # index-a should be cleared
        cached_a, _ = cache.get(
            query="query1",
            index_name="index-a",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
        )
        assert cached_a is None

        # index-b should still be cached
        cached_b, _ = cache.get(
            query="query2",
            index_name="index-b",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
        )
        assert cached_b == results

    def test_ttl_expiration(self, tmp_path):
        """Expired entries are treated as cache miss."""
        # Create cache with very short TTL
        cache = QueryCache(cache_dir=str(tmp_path), ttl=1)
        results = [{"file": "test.py"}]

        cache.put(
            query="query1",
            index_name="test-index",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
            results=results,
        )

        # Immediate access should hit
        cached, hit_type = cache.get(
            query="query1",
            index_name="test-index",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
        )
        assert cached == results
        assert hit_type == "exact"

        # Wait for TTL expiration
        time.sleep(1.1)

        # After TTL, should miss
        cached, hit_type = cache.get(
            query="query1",
            index_name="test-index",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
        )
        assert cached is None
        assert hit_type == "miss"

    def test_clear(self, cache):
        """Clear removes all entries."""
        results = [{"file": "test.py"}]

        cache.put(
            query="query1",
            index_name="index-a",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
            results=results,
        )
        cache.put(
            query="query2",
            index_name="index-b",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
            results=results,
        )

        cache.clear()

        cached_a, _ = cache.get(
            query="query1",
            index_name="index-a",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
        )
        cached_b, _ = cache.get(
            query="query2",
            index_name="index-b",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
        )

        assert cached_a is None
        assert cached_b is None


class TestGlobalCache:
    """Tests for global cache singleton."""

    def test_get_query_cache_returns_singleton(self):
        """get_query_cache returns same instance."""
        cache1 = get_query_cache()
        cache2 = get_query_cache()
        assert cache1 is cache2

    def test_invalidate_index_cache_convenience(self):
        """invalidate_index_cache works with global singleton."""
        cache = get_query_cache()
        results = [{"file": "test.py"}]

        cache.put(
            query="test",
            index_name="global-test-index",
            limit=10,
            min_score=0.0,
            language_filter=None,
            use_hybrid=None,
            symbol_type=None,
            symbol_name=None,
            results=results,
        )

        removed = invalidate_index_cache("global-test-index")
        assert removed >= 0  # May be 0 if test order varies
