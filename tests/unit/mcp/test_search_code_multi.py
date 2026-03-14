"""Tests for cross-index search in the search_code MCP tool and /api/search endpoint."""

from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio

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


class TestApiSearchMultiIndex:
    """Tests for POST /api/search with index_names parameter."""

    @pytest.mark.asyncio
    async def test_index_names_routes_to_multi_search(self, client):
        """When index_names has 2+ entries, multi_search is called."""
        mock_results = [
            _make_result("a.py", 0.9, "repo_a"),
            _make_result("b.py", 0.8, "repo_b"),
        ]

        with (
            patch("cocosearch.mcp.server._ensure_cocoindex_init", return_value=True),
            patch("cocosearch.mcp.server.multi_search", return_value=mock_results) as mock_ms,
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
                    "limit": 5,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["total"] == 2
        mock_ms.assert_called_once()

    @pytest.mark.asyncio
    async def test_single_index_names_uses_single_search(self, client):
        """When index_names has 1 entry, regular search is used."""
        mock_results = [_make_result("a.py", 0.9)]

        with (
            patch("cocosearch.mcp.server._ensure_cocoindex_init", return_value=True),
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
                json={
                    "query": "test query",
                    "index_names": ["repo_a"],
                    "limit": 5,
                },
            )

        assert resp.status_code == 200
        mock_s.assert_called_once()

    @pytest.mark.asyncio
    async def test_results_include_index_name_field(self, client):
        """Cross-index results include index_name in each result dict."""
        mock_results = [
            _make_result("a.py", 0.9, "repo_a"),
            _make_result("b.py", 0.8, "repo_b"),
        ]

        with (
            patch("cocosearch.mcp.server._ensure_cocoindex_init", return_value=True),
            patch("cocosearch.mcp.server.multi_search", return_value=mock_results),
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

        data = resp.json()
        assert data["results"][0]["index_name"] == "repo_a"
        assert data["results"][1]["index_name"] == "repo_b"

    @pytest.mark.asyncio
    async def test_index_names_takes_precedence_over_index_name(self, client):
        """When both are provided, index_names wins."""
        mock_results = [_make_result("a.py", 0.9, "repo_a")]

        with (
            patch("cocosearch.mcp.server._ensure_cocoindex_init", return_value=True),
            patch("cocosearch.mcp.server.multi_search", return_value=mock_results) as mock_ms,
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
                    "index_name": "ignored",
                    "index_names": ["repo_a", "repo_b"],
                },
            )

        assert resp.status_code == 200
        mock_ms.assert_called_once()

    @pytest.mark.asyncio
    async def test_backward_compatible_single_index(self, client):
        """Existing single index_name still works."""
        mock_results = [_make_result("a.py", 0.9)]

        with (
            patch("cocosearch.mcp.server._ensure_cocoindex_init", return_value=True),
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
                json={
                    "query": "test query",
                    "index_name": "my_index",
                },
            )

        assert resp.status_code == 200
        mock_s.assert_called_once()
        # Single index results should NOT have index_name field
        data = resp.json()
        assert "index_name" not in data["results"][0]
