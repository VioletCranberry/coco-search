"""Tests for the search pipeline analysis module."""

import json

from cocosearch.search.analyze import (
    AnalysisResult,
    analyze,
    format_analysis_pretty,
)
from cocosearch.search.hybrid import (
    KeywordResult,
    VectorResult,
)


def _make_vector_results(count=3, base_score=0.8):
    """Create mock vector search results."""
    return [
        VectorResult(
            filename=f"src/file_{i}.py",
            start_byte=i * 100,
            end_byte=(i + 1) * 100,
            score=base_score - i * 0.05,
            block_type="function",
            hierarchy="",
            language_id="",
            symbol_type="function" if i == 0 else None,
            symbol_name=f"func_{i}" if i == 0 else None,
            symbol_signature=f"def func_{i}()" if i == 0 else None,
        )
        for i in range(count)
    ]


def _make_keyword_results(count=2, base_rank=0.08):
    """Create mock keyword search results."""
    return [
        KeywordResult(
            filename=f"src/file_{i}.py",
            start_byte=i * 100,
            end_byte=(i + 1) * 100,
            ts_rank=base_rank - i * 0.01,
        )
        for i in range(count)
    ]


def _patch_common(mocker):
    """Apply common patches for analyze tests."""
    mocker.patch(
        "cocosearch.search.analyze.validate_query",
        side_effect=lambda q: q,
    )
    mocker.patch(
        "cocosearch.search.analyze.get_table_name",
        return_value="codeindex_test__test_chunks",
    )
    mocker.patch(
        "cocosearch.search.analyze.check_column_exists",
        return_value=True,
    )
    mocker.patch(
        "cocosearch.search.analyze.check_symbol_columns_exist",
        return_value=True,
    )


class TestAnalyzeReturnsResult:
    """Basic smoke test for analyze()."""

    def test_returns_analysis_result(self, mocker):
        """analyze() returns an AnalysisResult with all fields populated."""
        _patch_common(mocker)
        vector_results = _make_vector_results()
        mocker.patch(
            "cocosearch.search.analyze.execute_vector_search",
            return_value=vector_results,
        )
        mocker.patch(
            "cocosearch.search.analyze.execute_keyword_search",
            return_value=_make_keyword_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.apply_definition_boost",
            side_effect=lambda results, *a, **kw: results,
        )

        result = analyze("getUserById", "test_index")

        assert isinstance(result, AnalysisResult)
        assert result.query_analysis is not None
        assert result.search_mode is not None
        assert result.cache is not None
        assert result.vector_search is not None
        assert result.keyword_search is not None
        assert result.fusion is not None
        assert result.definition_boost is not None
        assert result.filtering is not None
        assert result.timings is not None
        assert isinstance(result.results, list)


class TestQueryAnalysis:
    """Tests for query analysis diagnostics."""

    def test_detects_identifier(self, mocker):
        """camelCase query is detected as identifier."""
        _patch_common(mocker)
        mocker.patch(
            "cocosearch.search.analyze.execute_vector_search",
            return_value=_make_vector_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.execute_keyword_search",
            return_value=_make_keyword_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.apply_definition_boost",
            side_effect=lambda results, *a, **kw: results,
        )

        result = analyze("getUserById", "test_index")

        assert result.query_analysis.has_identifier is True
        assert result.query_analysis.original_query == "getUserById"

    def test_no_identifier(self, mocker):
        """Plain English query is not detected as identifier."""
        _patch_common(mocker)
        mocker.patch(
            "cocosearch.search.analyze.execute_vector_search",
            return_value=_make_vector_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.execute_keyword_search",
            return_value=[],
        )

        result = analyze("database connection pool", "test_index")

        assert result.query_analysis.has_identifier is False


class TestSearchMode:
    """Tests for search mode selection diagnostics."""

    def test_auto_hybrid(self, mocker):
        """Auto-detects hybrid mode for identifier queries."""
        _patch_common(mocker)
        mocker.patch(
            "cocosearch.search.analyze.execute_vector_search",
            return_value=_make_vector_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.execute_keyword_search",
            return_value=_make_keyword_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.apply_definition_boost",
            side_effect=lambda results, *a, **kw: results,
        )

        result = analyze("getUserById", "test_index")

        assert result.search_mode.mode == "hybrid"
        assert result.search_mode.has_identifier_pattern is True
        assert result.search_mode.has_content_text_column is True

    def test_vector_only_no_identifiers(self, mocker):
        """No identifier pattern results in vector-only mode."""
        _patch_common(mocker)
        mocker.patch(
            "cocosearch.search.analyze.execute_vector_search",
            return_value=_make_vector_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.execute_keyword_search",
            return_value=[],
        )

        result = analyze("database connection pool", "test_index")

        assert result.search_mode.mode == "vector-only"

    def test_explicit_hybrid(self, mocker):
        """use_hybrid=True forces hybrid mode."""
        _patch_common(mocker)
        mocker.patch(
            "cocosearch.search.analyze.execute_vector_search",
            return_value=_make_vector_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.execute_keyword_search",
            return_value=_make_keyword_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.apply_definition_boost",
            side_effect=lambda results, *a, **kw: results,
        )

        result = analyze("database connection", "test_index", use_hybrid=True)

        assert result.search_mode.mode == "hybrid"
        assert result.search_mode.use_hybrid_flag is True


class TestCacheDiagnostics:
    """Tests for cache diagnostics."""

    def test_cache_miss_recorded(self, mocker):
        """Cache miss is recorded correctly."""
        _patch_common(mocker)
        mocker.patch(
            "cocosearch.search.analyze.execute_vector_search",
            return_value=_make_vector_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.execute_keyword_search",
            return_value=[],
        )

        result = analyze("test query", "test_index")

        assert result.cache.checked is True
        assert result.cache.hit is False
        assert result.cache.hit_type == "miss"
        assert len(result.cache.cache_key_prefix) == 16

    def test_no_cache_skips_check(self, mocker):
        """no_cache=True skips cache lookup."""
        _patch_common(mocker)
        mocker.patch(
            "cocosearch.search.analyze.execute_vector_search",
            return_value=_make_vector_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.execute_keyword_search",
            return_value=[],
        )

        result = analyze("test query", "test_index", no_cache=True)

        assert result.cache.checked is False
        assert result.cache.hit is False


class TestTimings:
    """Tests for timing diagnostics."""

    def test_timings_populated(self, mocker):
        """All timing fields are populated with non-negative values."""
        _patch_common(mocker)
        mocker.patch(
            "cocosearch.search.analyze.execute_vector_search",
            return_value=_make_vector_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.execute_keyword_search",
            return_value=_make_keyword_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.apply_definition_boost",
            side_effect=lambda results, *a, **kw: results,
        )

        result = analyze("getUserById", "test_index")

        assert result.timings.query_analysis_ms >= 0
        assert result.timings.cache_check_ms >= 0
        assert result.timings.embedding_ms >= 0
        assert result.timings.vector_search_ms >= 0
        assert result.timings.keyword_search_ms >= 0
        assert result.timings.rrf_fusion_ms >= 0
        assert result.timings.definition_boost_ms >= 0
        assert result.timings.total_ms >= 0


class TestVectorSearchInfo:
    """Tests for vector search diagnostics."""

    def test_vector_search_info(self, mocker):
        """Vector search info captures counts and scores."""
        _patch_common(mocker)
        vector_results = _make_vector_results(5, base_score=0.9)
        mocker.patch(
            "cocosearch.search.analyze.execute_vector_search",
            return_value=vector_results,
        )
        mocker.patch(
            "cocosearch.search.analyze.execute_keyword_search",
            return_value=[],
        )

        result = analyze("test query", "test_index")

        assert result.vector_search.result_count == 5
        assert result.vector_search.top_score == 0.9
        assert result.vector_search.bottom_score == 0.9 - 4 * 0.05


class TestRRFFusion:
    """Tests for RRF fusion diagnostics."""

    def test_rrf_fusion_match_type_counts(self, mocker):
        """Fusion info correctly counts both/semantic/keyword matches."""
        _patch_common(mocker)

        # Create overlapping results (file_0 appears in both)
        vector_results = _make_vector_results(3)
        keyword_results = _make_keyword_results(2)

        mocker.patch(
            "cocosearch.search.analyze.execute_vector_search",
            return_value=vector_results,
        )
        mocker.patch(
            "cocosearch.search.analyze.execute_keyword_search",
            return_value=keyword_results,
        )
        mocker.patch(
            "cocosearch.search.analyze.apply_definition_boost",
            side_effect=lambda results, *a, **kw: results,
        )

        result = analyze("getUserById", "test_index")

        assert result.fusion.executed is True
        assert result.fusion.k_constant == 60
        # file_0 and file_1 appear in both lists
        assert result.fusion.both_count == 2
        # file_2 appears only in vector
        assert result.fusion.vector_only_count == 1
        assert result.fusion.keyword_only_count == 0
        assert result.fusion.total_fused == 3


class TestDefinitionBoost:
    """Tests for definition boost diagnostics."""

    def test_definition_boost_tracking(self, mocker):
        """Definition boost info tracks boosted count."""
        _patch_common(mocker)
        vector_results = _make_vector_results(3)
        keyword_results = _make_keyword_results(2)

        mocker.patch(
            "cocosearch.search.analyze.execute_vector_search",
            return_value=vector_results,
        )
        mocker.patch(
            "cocosearch.search.analyze.execute_keyword_search",
            return_value=keyword_results,
        )
        # Real apply_definition_boost — will boost results with symbol_type
        mocker.patch(
            "cocosearch.search.hybrid.check_symbol_columns_exist",
            return_value=True,
        )

        result = analyze("getUserById", "test_index")

        assert result.definition_boost.executed is True
        assert result.definition_boost.boost_multiplier == 2.0


class TestFiltering:
    """Tests for result filtering diagnostics."""

    def test_min_score_filtering(self, mocker):
        """min_score filter reduces result count."""
        _patch_common(mocker)
        # Create results with varying scores
        vector_results = _make_vector_results(5, base_score=0.5)
        mocker.patch(
            "cocosearch.search.analyze.execute_vector_search",
            return_value=vector_results,
        )
        mocker.patch(
            "cocosearch.search.analyze.execute_keyword_search",
            return_value=[],
        )

        result = analyze("test query", "test_index", min_score=0.45)

        assert result.filtering.min_score == 0.45
        assert result.filtering.pre_filter_count == 5
        # Scores: 0.5, 0.45, 0.4, 0.35, 0.3 — only first 2 pass
        assert result.filtering.post_filter_count == 2


class TestSerialization:
    """Tests for serialization."""

    def test_to_dict_json_serializable(self, mocker):
        """to_dict() produces JSON-serializable output."""
        _patch_common(mocker)
        mocker.patch(
            "cocosearch.search.analyze.execute_vector_search",
            return_value=_make_vector_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.execute_keyword_search",
            return_value=_make_keyword_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.apply_definition_boost",
            side_effect=lambda results, *a, **kw: results,
        )

        result = analyze("getUserById", "test_index")
        d = result.to_dict()

        # Should not raise
        serialized = json.dumps(d)
        assert isinstance(serialized, str)
        parsed = json.loads(serialized)
        assert "query_analysis" in parsed
        assert "timings" in parsed
        assert "results" in parsed


class TestFormatPretty:
    """Tests for Rich formatting."""

    def test_format_analysis_pretty_no_error(self, mocker):
        """format_analysis_pretty() renders without errors."""
        _patch_common(mocker)
        mocker.patch(
            "cocosearch.search.analyze.execute_vector_search",
            return_value=_make_vector_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.execute_keyword_search",
            return_value=_make_keyword_results(),
        )
        mocker.patch(
            "cocosearch.search.analyze.apply_definition_boost",
            side_effect=lambda results, *a, **kw: results,
        )
        # Mock format_pretty to avoid file I/O in results display
        mocker.patch("cocosearch.search.formatter.format_pretty")

        result = analyze("getUserById", "test_index")

        # Should not raise
        format_analysis_pretty(result, "test_index")
