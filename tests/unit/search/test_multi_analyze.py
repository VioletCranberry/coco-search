"""Tests for cross-index analyze."""

from unittest.mock import patch

from cocosearch.search.analyze import (
    AnalysisResult,
    CacheInfo,
    DefinitionBoostInfo,
    FilterInfo,
    FusionInfo,
    KeywordSearchInfo,
    MultiAnalysisResult,
    QueryAnalysisInfo,
    SearchModeInfo,
    StageTimings,
    VectorSearchInfo,
    multi_analyze,
)


def _make_analysis():
    return AnalysisResult(
        query_analysis=QueryAnalysisInfo("q", False, "q"),
        search_mode=SearchModeInfo("vector-only", "test", None, True, False),
        cache=CacheInfo(False, False, "miss", "abc"),
        vector_search=VectorSearchInfo(0, None, None, []),
        keyword_search=KeywordSearchInfo(False, "", 0, None, []),
        fusion=FusionInfo(False, 60, 0, 0, 0, 0),
        definition_boost=DefinitionBoostInfo(False, 1.2, 0, 0),
        filtering=FilterInfo(None, None, None, 0.0, 0, 0),
        timings=StageTimings(1.0, 1.0, 0.0, 10.0, 0.0, 0.0, 0.0, 12.0),
        results=[],
    )


class TestMultiAnalyze:
    @patch("cocosearch.search.analyze.analyze")
    def test_per_index_results(self, mock_analyze):
        mock_analyze.side_effect = lambda **kwargs: _make_analysis()

        result = multi_analyze(query="test", index_names=["idx_a", "idx_b"])

        assert isinstance(result, MultiAnalysisResult)
        assert "idx_a" in result.per_index
        assert "idx_b" in result.per_index
        assert result.total_results == 0
        assert result.errors == {}

    @patch("cocosearch.search.analyze.analyze")
    def test_partial_failure(self, mock_analyze):
        def side_effect(**kwargs):
            if kwargs["index_name"] == "idx_a":
                return _make_analysis()
            raise ValueError("index not found")

        mock_analyze.side_effect = side_effect

        result = multi_analyze(query="test", index_names=["idx_a", "idx_b"])

        assert "idx_a" in result.per_index
        assert "idx_b" in result.errors
        assert "index not found" in result.errors["idx_b"]

    @patch("cocosearch.search.analyze.analyze")
    def test_to_dict(self, mock_analyze):
        mock_analyze.return_value = _make_analysis()

        result = multi_analyze(query="test", index_names=["idx_a"])
        d = result.to_dict()

        assert "per_index" in d
        assert "errors" in d
        assert "total_results" in d
        assert "index_names" in d
