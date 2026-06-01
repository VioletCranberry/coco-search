"""Tests for cross-index search orchestrator."""

from unittest.mock import patch

import pytest

from cocosearch.search.multi import multi_search
from cocosearch.search.query import SearchResult


def _make_result(filename: str, score: float, **kwargs) -> SearchResult:
    return SearchResult(
        filename=filename,
        start_byte=0,
        end_byte=100,
        score=score,
        **kwargs,
    )


@pytest.fixture
def mock_list_indexes():
    with patch("cocosearch.search.multi.list_indexes") as m:
        m.return_value = [
            {"name": "repo_a", "table_name": "codeindex_repo_a__repo_a_chunks"},
            {"name": "repo_b", "table_name": "codeindex_repo_b__repo_b_chunks"},
        ]
        yield m


@pytest.fixture
def mock_metadata():
    with patch("cocosearch.search.multi.get_index_metadata") as m:
        m.return_value = {
            "embedding_provider": "ollama",
            "embedding_model": "nomic-embed-text",
        }
        yield m


@pytest.fixture
def mock_embedding():
    with patch("cocosearch.search.multi.embed_query", return_value=[0.1] * 768) as m:
        yield m


class TestMultiSearch:
    def test_merged_results_sorted_by_score(
        self, mock_list_indexes, mock_metadata, mock_embedding
    ):
        results_a = [
            _make_result("file_a1.py", 0.9),
            _make_result("file_a2.py", 0.5),
        ]
        results_b = [
            _make_result("file_b1.py", 0.8),
            _make_result("file_b2.py", 0.7),
        ]

        with patch("cocosearch.search.multi.search") as mock_search:
            mock_search.side_effect = [results_a, results_b]
            results = multi_search("test query", ["repo_a", "repo_b"], limit=10)

        assert len(results) == 4
        assert results[0].score == 0.9
        assert results[1].score == 0.8
        assert results[2].score == 0.7
        assert results[3].score == 0.5

    def test_results_tagged_with_index_name(
        self, mock_list_indexes, mock_metadata, mock_embedding
    ):
        results_a = [_make_result("a.py", 0.9)]
        results_b = [_make_result("b.py", 0.8)]

        with patch("cocosearch.search.multi.search") as mock_search:
            mock_search.side_effect = [results_a, results_b]
            results = multi_search("test query", ["repo_a", "repo_b"])

        assert results[0].index_name == "repo_a"
        assert results[1].index_name == "repo_b"

    def test_embedding_computed_once(
        self, mock_list_indexes, mock_metadata, mock_embedding
    ):
        with patch("cocosearch.search.multi.search") as mock_search:
            mock_search.return_value = []
            multi_search("test query", ["repo_a", "repo_b"])

        mock_embedding.assert_called_once_with("test query")

    def test_query_embedding_passed_to_search(
        self, mock_list_indexes, mock_metadata, mock_embedding
    ):
        with patch("cocosearch.search.multi.search") as mock_search:
            mock_search.return_value = []
            multi_search("test query", ["repo_a", "repo_b"])

        for call in mock_search.call_args_list:
            assert call.kwargs["query_embedding"] == [0.1] * 768

    def test_limit_respected(self, mock_list_indexes, mock_metadata, mock_embedding):
        results_a = [_make_result(f"a{i}.py", 0.9 - i * 0.1) for i in range(5)]
        results_b = [_make_result(f"b{i}.py", 0.85 - i * 0.1) for i in range(5)]

        with patch("cocosearch.search.multi.search") as mock_search:
            mock_search.side_effect = [results_a, results_b]
            results = multi_search("test query", ["repo_a", "repo_b"], limit=3)

        assert len(results) == 3

    def test_partial_failure_returns_successful_results(
        self, mock_list_indexes, mock_metadata, mock_embedding
    ):
        results_a = [_make_result("a.py", 0.9)]

        with patch("cocosearch.search.multi.search") as mock_search:
            mock_search.side_effect = [results_a, Exception("connection failed")]
            results = multi_search("test query", ["repo_a", "repo_b"])

        assert len(results) == 1
        assert results[0].filename == "a.py"

    def test_all_indexes_fail_raises_error(
        self, mock_list_indexes, mock_metadata, mock_embedding
    ):
        with patch("cocosearch.search.multi.search") as mock_search:
            mock_search.side_effect = [
                Exception("fail 1"),
                Exception("fail 2"),
            ]
            with pytest.raises(ValueError, match="All index searches failed"):
                multi_search("test query", ["repo_a", "repo_b"])

    def test_invalid_index_name_raises_error(
        self, mock_list_indexes, mock_metadata, mock_embedding
    ):
        with pytest.raises(ValueError, match="Unknown index"):
            multi_search("test query", ["repo_a", "nonexistent"])

    def test_single_index_delegates_directly(self, mock_metadata, mock_embedding):
        with patch("cocosearch.search.multi.search") as mock_search:
            mock_search.return_value = [_make_result("a.py", 0.9)]
            results = multi_search("test query", ["repo_a"])

        # Should not call list_indexes for single index
        mock_search.assert_called_once()
        assert results[0].index_name == "repo_a"

    def test_empty_index_list_returns_empty(self):
        results = multi_search("test query", [])
        assert results == []

    def test_embedding_model_mismatch_warns(self, mock_list_indexes, mock_embedding):
        with patch("cocosearch.search.multi.get_index_metadata") as mock_meta:
            mock_meta.side_effect = [
                {"embedding_provider": "ollama", "embedding_model": "nomic-embed-text"},
                {
                    "embedding_provider": "openai",
                    "embedding_model": "text-embedding-3-small",
                },
            ]
            with patch("cocosearch.search.multi.search") as mock_search:
                mock_search.return_value = []
                with patch("cocosearch.search.multi.logger") as mock_logger:
                    multi_search("test query", ["repo_a", "repo_b"])
                    mock_logger.warning.assert_called_once()
                    assert "mismatched" in mock_logger.warning.call_args[0][0]

    def test_model_mismatch_populates_warnings_list(
        self, mock_list_indexes, mock_embedding
    ):
        with patch("cocosearch.search.multi.get_index_metadata") as mock_meta:
            mock_meta.side_effect = [
                {"embedding_provider": "ollama", "embedding_model": "nomic-embed-text"},
                {
                    "embedding_provider": "openai",
                    "embedding_model": "text-embedding-3-small",
                },
            ]
            with patch("cocosearch.search.multi.search") as mock_search:
                mock_search.return_value = []
                warnings: list[dict] = []
                multi_search("test query", ["repo_a", "repo_b"], warnings=warnings)
                assert len(warnings) == 1
                assert warnings[0]["type"] == "embedding_model_mismatch"

    def test_no_mismatch_no_warnings(
        self, mock_list_indexes, mock_metadata, mock_embedding
    ):
        with patch("cocosearch.search.multi.search") as mock_search:
            mock_search.return_value = []
            warnings: list[dict] = []
            multi_search("test query", ["repo_a", "repo_b"], warnings=warnings)
            assert len(warnings) == 0


class TestMultiSearchRewrite:
    """Query-rewrite controller behavior in cross-index search."""

    def test_rewrite_called_once_and_skips_per_index(
        self, mock_list_indexes, mock_metadata, mock_embedding
    ):
        """The controller runs once, and each per-index search() skips its own rewrite."""
        with patch(
            "cocosearch.search.controller.rewrite_query",
            return_value=("auth session token", True),
        ) as mock_rewrite:
            with patch("cocosearch.search.multi.search") as mock_search:
                mock_search.return_value = []
                warnings: list[dict] = []
                multi_search(
                    "how does auth work",
                    ["repo_a", "repo_b"],
                    warnings=warnings,
                )

        # Rewrite invoked exactly once for the whole fan-out.
        mock_rewrite.assert_called_once()
        # Embedding uses the rewritten query.
        mock_embedding.assert_called_once_with("auth session token")
        # Every per-index search() is told to skip its own rewrite.
        for call in mock_search.call_args_list:
            assert call.kwargs["_skip_rewrite"] is True
        # Warning surfaced.
        assert any(w["type"] == "query_rewrite" for w in warnings)

    def test_skip_rewrite_param_bypasses_controller(
        self, mock_list_indexes, mock_metadata, mock_embedding
    ):
        with patch("cocosearch.search.controller.rewrite_query") as mock_rewrite:
            with patch("cocosearch.search.multi.search") as mock_search:
                mock_search.return_value = []
                multi_search("test query", ["repo_a", "repo_b"], skip_rewrite=True)

        mock_rewrite.assert_not_called()

    def test_single_index_skips_inner_rewrite(self, mock_metadata, mock_embedding):
        """Single-index delegate passes _skip_rewrite=True to search()."""
        with patch(
            "cocosearch.search.controller.rewrite_query",
            return_value=("rewritten", True),
        ):
            with patch("cocosearch.search.multi.search") as mock_search:
                mock_search.return_value = []
                multi_search("test query", ["repo_a"])

        assert mock_search.call_args.kwargs["_skip_rewrite"] is True
