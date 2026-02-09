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
def sample_search_result(make_search_result):
    """Ready-to-use SearchResult for simple tests."""
    return make_search_result()


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


@pytest.fixture
def sample_code_content():
    """Sample Python code content for testing.

    Returns a dict mapping byte ranges to code content.
    """
    code = '''def authenticate(username: str, password: str) -> bool:
    """Check if username and password are valid."""
    if not username or not password:
        return False
    # Check against database
    user = get_user(username)
    if user and verify_password(password, user.password_hash):
        return True
    return False
'''
    return {
        "content": code,
        "filename": "/project/auth.py",
        "start_byte": 0,
        "end_byte": len(code.encode("utf-8")),
    }


@pytest.fixture
def make_config_dict():
    """Factory for .cocosearch.yaml config dictionaries.

    Usage:
        def test_config(make_config_dict):
            config = make_config_dict(include=["*.py", "*.js"])
    """

    def _make(
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 300,
    ) -> dict:
        config = {}
        if include:
            config["include"] = include
        if exclude:
            config["exclude"] = exclude
        config["chunk_size"] = chunk_size
        config["chunk_overlap"] = chunk_overlap
        return config

    return _make


@pytest.fixture
def sample_config_dict(make_config_dict):
    """Ready-to-use config dict with common settings."""
    return make_config_dict(include=["*.py"], exclude=["*_test.py", "tests/"])
