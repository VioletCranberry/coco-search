"""Data fixtures for testing.

Provides factory fixtures for creating test data objects like
SearchResult, IndexingConfig, and sample file content.
"""

import pytest
from cocosearch.search.query import SearchResult


@pytest.fixture
def make_search_result():
    """Factory for SearchResult objects.

    Usage:
        def test_formatter(make_search_result):
            result = make_search_result(filename="/test/file.py", score=0.95)
    """

    def _make(
        filename: str = "/test/project/main.py",
        start_byte: int = 0,
        end_byte: int = 100,
        score: float = 0.85,
        block_type: str = "",
        hierarchy: str = "",
        language_id: str = "",
        match_type: str = "",
        vector_score: float | None = None,
        keyword_score: float | None = None,
    ) -> SearchResult:
        return SearchResult(
            filename=filename,
            start_byte=start_byte,
            end_byte=end_byte,
            score=score,
            block_type=block_type,
            hierarchy=hierarchy,
            language_id=language_id,
            match_type=match_type,
            vector_score=vector_score,
            keyword_score=keyword_score,
        )

    return _make


@pytest.fixture
def sample_search_results(make_search_result):
    """List of sample SearchResults for testing formatters and displays."""
    return [
        make_search_result(
            filename="/project/auth.py", start_byte=0, end_byte=150, score=0.92
        ),
        make_search_result(
            filename="/project/utils.py", start_byte=50, end_byte=200, score=0.85
        ),
        make_search_result(
            filename="/project/main.py", start_byte=100, end_byte=300, score=0.78
        ),
    ]
