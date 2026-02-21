"""ASGI smoke tests for key API endpoints.

Tests the full Starlette request/response cycle via httpx.AsyncClient
with ASGITransport — complements test_server_routes.py which calls
handler functions directly with mock requests.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest
import pytest_asyncio


@pytest.fixture
def asgi_app():
    """Create the ASGI app from the MCP server."""
    from cocosearch.mcp.server import mcp

    return mcp.sse_app()


@pytest_asyncio.fixture
async def client(asgi_app):
    """Create an httpx AsyncClient wired to the ASGI app."""
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as c:
        yield c


class TestHealthEndpoint:
    """Tests for GET /health."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        """GET /health returns 200 with status ok."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_health_content_type_is_json(self, client):
        """Content-type is application/json."""
        response = await client.get("/health")
        assert "application/json" in response.headers["content-type"]


class TestApiListSmoke:
    """Tests for GET /api/list through the ASGI stack."""

    @pytest.mark.asyncio
    async def test_returns_empty_list(self, client):
        """Returns empty list when cocoindex init fails."""
        with patch(
            "cocosearch.mcp.server._ensure_cocoindex_init",
            side_effect=Exception("DB not ready"),
        ):
            response = await client.get("/api/list")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_returns_index_with_metadata(self, client):
        """Returns index list with enriched metadata."""
        indexes = [
            {"name": "myproject", "table_name": "codeindex_myproject__myproject_chunks"}
        ]
        metadata = {
            "branch": "main",
            "commit_hash": "abc123",
            "status": "indexed",
            "canonical_path": "/projects/myproject",
        }

        with patch("cocosearch.mcp.server._ensure_cocoindex_init"):
            with patch("cocosearch.mcp.server.mgmt_list_indexes", return_value=indexes):
                with patch(
                    "cocosearch.mcp.server.get_index_metadata",
                    return_value=metadata,
                ):
                    response = await client.get("/api/list")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["name"] == "myproject"
        assert body[0]["branch"] == "main"


class TestApiStatsSmoke:
    """Tests for GET /api/stats through the ASGI stack."""

    @pytest.mark.asyncio
    async def test_stats_db_failure_returns_503(self, client):
        """Returns 503 when database is not initialized."""
        with patch(
            "cocosearch.mcp.server._ensure_cocoindex_init",
            side_effect=Exception("DB not ready"),
        ):
            with patch(
                "cocosearch.mcp.server.build_all_stats",
                side_effect=Exception("DB not ready"),
            ):
                response = await client.get("/api/stats")

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_stats_returns_data(self, client):
        """Returns 200 with stats data when DB is available."""
        mock_stats = [{"index": "test", "total_chunks": 100}]

        with patch("cocosearch.mcp.server.build_all_stats", return_value=mock_stats):
            response = await client.get("/api/stats")

        assert response.status_code == 200
        assert response.json() == mock_stats


class TestApiSearchSmoke:
    """Tests for POST /api/search through the ASGI stack."""

    @pytest.mark.asyncio
    async def test_search_missing_query_returns_400(self, client):
        """Returns 400 when query is missing."""
        response = await client.post(
            "/api/search",
            json={"index_name": "myindex"},
        )

        assert response.status_code == 400
        assert "query is required" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_search_returns_results(self, client):
        """Returns 200 with results when search succeeds."""
        mock_result = MagicMock()
        mock_result.filename = "/test/file.py"
        mock_result.start_byte = 0
        mock_result.end_byte = 100
        mock_result.score = 0.9
        mock_result.block_type = "function"
        mock_result.hierarchy = ""
        mock_result.language_id = "python"
        mock_result.match_type = "vector"
        mock_result.vector_score = 0.9
        mock_result.keyword_score = None
        mock_result.symbol_type = "function"
        mock_result.symbol_name = "hello"
        mock_result.symbol_signature = "def hello()"

        with patch("cocosearch.mcp.server._ensure_cocoindex_init"):
            with patch("cocosearch.mcp.server.search", return_value=[mock_result]):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=1):
                    with patch(
                        "cocosearch.mcp.server.read_chunk_content",
                        return_value="def hello(): pass",
                    ):
                        response = await client.post(
                            "/api/search",
                            json={"query": "hello function", "index_name": "myindex"},
                        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["total"] == 1
        assert "query_time_ms" in body
        assert body["results"][0]["file_path"] == "/test/file.py"


class TestApiLanguagesSmoke:
    """Tests for GET /api/languages through the ASGI stack."""

    @pytest.mark.asyncio
    async def test_returns_language_list(self, client):
        """Returns 200 with a list containing python."""
        with patch(
            "cocosearch.handlers.get_registered_handlers",
            return_value=[],
        ):
            with patch(
                "cocosearch.search.context_expander.CONTEXT_EXPANSION_LANGUAGES",
                {"python"},
            ):
                with patch(
                    "cocosearch.search.query.LANGUAGE_EXTENSIONS",
                    {"python": [".py"]},
                ):
                    with patch(
                        "cocosearch.search.query.SYMBOL_AWARE_LANGUAGES",
                        {"python"},
                    ):
                        response = await client.get("/api/languages")

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        names = [lang["name"] for lang in body]
        assert "python" in names


class TestApiGrammarsSmoke:
    """Tests for GET /api/grammars through the ASGI stack."""

    @pytest.mark.asyncio
    async def test_returns_grammar_list(self, client):
        """Returns 200 with a list of grammars."""
        mock_grammar = MagicMock()
        mock_grammar.GRAMMAR_NAME = "github-actions"
        mock_grammar.BASE_LANGUAGE = "yaml"
        mock_grammar.PATH_PATTERNS = [".github/workflows/*.yml"]

        with patch(
            "cocosearch.handlers.get_registered_grammars",
            return_value=[mock_grammar],
        ):
            response = await client.get("/api/grammars")

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["name"] == "github-actions"
