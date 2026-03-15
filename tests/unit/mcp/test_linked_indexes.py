"""Tests for linkedIndexes config auto-expansion in MCP search_code and /api/search."""

from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio

from cocosearch.config.schema import CocoSearchConfig
from cocosearch.search.query import SearchResult


def _make_result(filename: str, score: float, index_name: str = None) -> SearchResult:
    return SearchResult(
        filename=filename,
        start_byte=0,
        end_byte=100,
        score=score,
        index_name=index_name,
    )


@pytest.fixture
def asgi_app():
    from cocosearch.mcp.server import mcp

    return mcp.sse_app()


@pytest_asyncio.fixture
async def client(asgi_app):
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as c:
        yield c


def _config_with_linked(linked: list[str]) -> CocoSearchConfig:
    return CocoSearchConfig(indexName="main_proj", linkedIndexes=linked)


class TestApiSearchLinkedIndexes:
    """Tests for POST /api/search with linkedIndexes auto-expansion."""

    @pytest.mark.asyncio
    async def test_linked_indexes_triggers_multi_search(self, client):
        """When config has linkedIndexes and linked index exists, multi_search is used."""
        config = _config_with_linked(["shared_lib"])
        mock_results = [
            _make_result("a.py", 0.9, "main_proj"),
            _make_result("b.py", 0.8, "shared_lib"),
        ]

        with (
            patch("cocosearch.mcp.server._ensure_cocoindex_init", return_value=True),
            patch(
                "cocosearch.config.find_config_file",
                return_value="/fake/cocosearch.yaml",
            ),
            patch("cocosearch.config.load_config", return_value=config),
            patch(
                "cocosearch.mcp.server.mgmt_list_indexes",
                return_value=[
                    {"name": "main_proj"},
                    {"name": "shared_lib"},
                ],
            ),
            patch(
                "cocosearch.mcp.server.multi_search", return_value=mock_results
            ) as mock_ms,
            patch(
                "cocosearch.mcp.server.get_index_metadata",
                return_value={"canonical_path": "/tmp/test"},
            ),
            patch("cocosearch.mcp.server.byte_to_line", return_value=1),
            patch("cocosearch.mcp.server.read_chunk_content", return_value="code"),
        ):
            resp = await client.post(
                "/api/search",
                json={"query": "test query", "index_name": "main_proj"},
            )

        assert resp.status_code == 200
        mock_ms.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_linked_index_skipped(self, client):
        """When a linked index doesn't exist, it's skipped and single-index search is used."""
        config = _config_with_linked(["nonexistent"])
        mock_results = [_make_result("a.py", 0.9)]

        with (
            patch("cocosearch.mcp.server._ensure_cocoindex_init", return_value=True),
            patch(
                "cocosearch.config.find_config_file",
                return_value="/fake/cocosearch.yaml",
            ),
            patch("cocosearch.config.load_config", return_value=config),
            patch(
                "cocosearch.mcp.server.mgmt_list_indexes",
                return_value=[{"name": "main_proj"}],
            ),
            patch("cocosearch.mcp.server.search", return_value=mock_results) as mock_s,
            patch(
                "cocosearch.mcp.server.get_index_metadata",
                return_value={"canonical_path": "/tmp/test"},
            ),
            patch("cocosearch.mcp.server.byte_to_line", return_value=1),
            patch("cocosearch.mcp.server.read_chunk_content", return_value="code"),
        ):
            resp = await client.post(
                "/api/search",
                json={"query": "test query", "index_name": "main_proj"},
            )

        assert resp.status_code == 200
        # Falls back to single-index search since no linked indexes exist
        mock_s.assert_called_once()

    @pytest.mark.asyncio
    async def test_explicit_index_names_overrides_linked(self, client):
        """When index_names is explicitly provided, linkedIndexes config is ignored."""
        mock_results = [
            _make_result("a.py", 0.9, "repo_a"),
            _make_result("b.py", 0.8, "repo_b"),
        ]

        with (
            patch("cocosearch.mcp.server._ensure_cocoindex_init", return_value=True),
            patch(
                "cocosearch.mcp.server.multi_search", return_value=mock_results
            ) as mock_ms,
            patch(
                "cocosearch.mcp.server.get_index_metadata",
                return_value={"canonical_path": "/tmp/test"},
            ),
            patch("cocosearch.mcp.server.byte_to_line", return_value=1),
            patch("cocosearch.mcp.server.read_chunk_content", return_value="code"),
        ):
            resp = await client.post(
                "/api/search",
                json={
                    "query": "test query",
                    "index_names": ["repo_a", "repo_b"],
                },
            )

        assert resp.status_code == 200
        mock_ms.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_linked_indexes_stays_single(self, client):
        """When linkedIndexes is empty, single-index search is used."""
        config = _config_with_linked([])
        mock_results = [_make_result("a.py", 0.9)]

        with (
            patch("cocosearch.mcp.server._ensure_cocoindex_init", return_value=True),
            patch(
                "cocosearch.config.find_config_file",
                return_value="/fake/cocosearch.yaml",
            ),
            patch("cocosearch.config.load_config", return_value=config),
            patch(
                "cocosearch.mcp.server.mgmt_list_indexes",
                return_value=[{"name": "main_proj"}],
            ),
            patch("cocosearch.mcp.server.search", return_value=mock_results) as mock_s,
            patch(
                "cocosearch.mcp.server.get_index_metadata",
                return_value={"canonical_path": "/tmp/test"},
            ),
            patch("cocosearch.mcp.server.byte_to_line", return_value=1),
            patch("cocosearch.mcp.server.read_chunk_content", return_value="code"),
        ):
            resp = await client.post(
                "/api/search",
                json={"query": "test query", "index_name": "main_proj"},
            )

        assert resp.status_code == 200
        mock_s.assert_called_once()
