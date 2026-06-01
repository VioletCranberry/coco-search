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


class TestApiInfraSmoke:
    """Tests for GET /api/infra through the ASGI stack."""

    @pytest.mark.asyncio
    async def test_infra_all_ok(self, client):
        """Returns all_ok=True when all checks pass."""
        with patch(
            "cocosearch.mcp.server._check_infra_sync",
            return_value={
                "database": {"ok": True},
                "embedding": {
                    "ok": True,
                    "provider": "ollama",
                    "model": "nomic-embed-text",
                },
                "all_ok": True,
            },
        ):
            response = await client.get("/api/infra")

        assert response.status_code == 200
        body = response.json()
        assert body["all_ok"] is True
        assert body["database"]["ok"] is True
        assert body["embedding"]["ok"] is True

    @pytest.mark.asyncio
    async def test_infra_db_down(self, client):
        """Returns all_ok=False when database is unreachable."""
        with patch(
            "cocosearch.mcp.server._check_infra_sync",
            return_value={
                "database": {"ok": False, "error": "PostgreSQL is not reachable"},
                "embedding": {
                    "ok": True,
                    "provider": "ollama",
                    "model": "nomic-embed-text",
                },
                "all_ok": False,
            },
        ):
            response = await client.get("/api/infra")

        assert response.status_code == 200
        body = response.json()
        assert body["all_ok"] is False
        assert body["database"]["ok"] is False
        assert "not reachable" in body["database"]["error"]

    @pytest.mark.asyncio
    async def test_infra_embedding_down(self, client):
        """Returns all_ok=False when embedding provider is unreachable."""
        with patch(
            "cocosearch.mcp.server._check_infra_sync",
            return_value={
                "database": {"ok": True},
                "embedding": {
                    "ok": False,
                    "provider": "ollama",
                    "model": "nomic-embed-text",
                    "error": "Ollama is not reachable",
                },
                "all_ok": False,
            },
        ):
            response = await client.get("/api/infra")

        assert response.status_code == 200
        body = response.json()
        assert body["all_ok"] is False
        assert body["embedding"]["ok"] is False


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
        mock_result.dependencies = None
        mock_result.dependents = None

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


class TestApiSearchWithDeps:
    """Tests for POST /api/search with include_deps through the ASGI stack."""

    @pytest.mark.asyncio
    async def test_search_with_include_deps_returns_dependencies(self, client):
        """Returns dependencies and dependents when include_deps is true."""
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
        mock_result.dependencies = [
            {"target": "os", "dep_type": "import"},
            {"target": "sys", "dep_type": "import"},
        ]
        mock_result.dependents = [
            {"source": "main.py", "dep_type": "import"},
        ]

        with patch("cocosearch.mcp.server._ensure_cocoindex_init"):
            with patch("cocosearch.mcp.server.search", return_value=[mock_result]):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=1):
                    with patch(
                        "cocosearch.mcp.server.read_chunk_content",
                        return_value="def hello(): pass",
                    ):
                        response = await client.post(
                            "/api/search",
                            json={
                                "query": "hello function",
                                "index_name": "myindex",
                                "include_deps": True,
                            },
                        )

        assert response.status_code == 200
        body = response.json()
        result = body["results"][0]
        assert "dependencies" in result
        assert len(result["dependencies"]) == 2
        assert "dependents" in result
        assert len(result["dependents"]) == 1

    @pytest.mark.asyncio
    async def test_search_without_include_deps_omits_dependencies(self, client):
        """Does not include dependencies when include_deps is false/absent."""
        mock_result = MagicMock()
        mock_result.filename = "/test/file.py"
        mock_result.start_byte = 0
        mock_result.end_byte = 100
        mock_result.score = 0.9
        mock_result.block_type = "function"
        mock_result.hierarchy = ""
        mock_result.language_id = "python"
        mock_result.match_type = ""
        mock_result.vector_score = None
        mock_result.keyword_score = None
        mock_result.symbol_type = None
        mock_result.symbol_name = None
        mock_result.symbol_signature = None
        mock_result.dependencies = None
        mock_result.dependents = None

        with patch("cocosearch.mcp.server._ensure_cocoindex_init"):
            with patch("cocosearch.mcp.server.search", return_value=[mock_result]):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=1):
                    with patch(
                        "cocosearch.mcp.server.read_chunk_content",
                        return_value="def hello(): pass",
                    ):
                        response = await client.post(
                            "/api/search",
                            json={"query": "hello", "index_name": "myindex"},
                        )

        assert response.status_code == 200
        result = response.json()["results"][0]
        assert "dependencies" not in result
        assert "dependents" not in result


class TestApiDepsGraphSmoke:
    """Tests for GET /api/deps/graph through the ASGI stack."""

    @pytest.mark.asyncio
    async def test_missing_file_param_returns_400(self, client):
        """Returns 400 when file param is missing."""
        response = await client.get("/api/deps/graph?index=myindex")
        assert response.status_code == 400
        assert "file" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_missing_index_param_returns_400(self, client):
        """Returns 400 when index param is missing."""
        response = await client.get("/api/deps/graph?file=test.py")
        assert response.status_code == 400
        assert "index" in response.json()["error"]


class TestApiLanguagesSmoke:
    """Tests for GET /api/languages through the ASGI stack."""

    @pytest.mark.asyncio
    async def test_returns_language_list(self, client):
        """Returns 200 with a list containing python."""
        with patch(
            "cocosearch.deps.registry.get_all_extractor_language_ids",
            return_value={"py"},
        ):
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

    @pytest.mark.asyncio
    async def test_includes_deps_key(self, client):
        """Each language entry should include a 'deps' key."""
        with patch(
            "cocosearch.deps.registry.get_all_extractor_language_ids",
            return_value={"py"},
        ):
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

        body = response.json()
        for lang in body:
            assert "deps" in lang, f"Missing 'deps' key for {lang['name']}"
        python_lang = next(lang for lang in body if lang["name"] == "python")
        assert python_lang["deps"] is True


class TestApiExtractDepsSmoke:
    """Tests for POST /api/extract-deps through the ASGI stack."""

    @pytest.mark.asyncio
    async def test_missing_index_name_returns_400(self, client):
        """Returns 400 when index_name is missing."""
        response = await client.post("/api/extract-deps", json={})
        assert response.status_code == 400
        assert "index_name is required" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_no_source_path_returns_400(self, client):
        """Returns 400 when index has no source path and none provided."""
        with patch("cocosearch.mcp.server.get_index_metadata", return_value=None):
            response = await client.post(
                "/api/extract-deps", json={"index_name": "myindex"}
            )
        assert response.status_code == 400
        assert "not found or has no source path" in response.json()["error"]

    @pytest.mark.asyncio
    async def test_successful_extraction(self, client):
        """Returns 200 with edge count on success."""
        metadata = {"canonical_path": "/projects/myproject"}
        stats = {
            "files_processed": 10,
            "files_skipped": 2,
            "edges_found": 42,
            "errors": 0,
        }

        with patch("cocosearch.mcp.server.get_index_metadata", return_value=metadata):
            with patch(
                "cocosearch.deps.extractor.extract_dependencies",
                return_value=stats,
            ):
                response = await client.post(
                    "/api/extract-deps", json={"index_name": "myindex"}
                )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "42" in body["message"]
        assert body["stats"]["edges_found"] == 42

    @pytest.mark.asyncio
    async def test_default_extraction_is_incremental(self, client):
        """Omitting fresh forwards fresh=False (incremental) to the extractor."""
        metadata = {"canonical_path": "/projects/myproject"}
        stats = {"edges_found": 42}

        with patch("cocosearch.mcp.server.get_index_metadata", return_value=metadata):
            with patch(
                "cocosearch.deps.extractor.extract_dependencies",
                return_value=stats,
            ) as mock_extract:
                response = await client.post(
                    "/api/extract-deps", json={"index_name": "myindex"}
                )

        assert response.status_code == 200
        mock_extract.assert_called_once_with(
            "myindex", "/projects/myproject", fresh=False
        )

    @pytest.mark.asyncio
    async def test_extraction_with_fresh_flag(self, client):
        """fresh=True is forwarded to extract_dependencies (full re-extraction)."""
        metadata = {"canonical_path": "/projects/myproject"}
        stats = {"edges_found": 42}

        with patch("cocosearch.mcp.server.get_index_metadata", return_value=metadata):
            with patch(
                "cocosearch.deps.extractor.extract_dependencies",
                return_value=stats,
            ) as mock_extract:
                response = await client.post(
                    "/api/extract-deps",
                    json={"index_name": "myindex", "fresh": True},
                )

        assert response.status_code == 200
        mock_extract.assert_called_once_with(
            "myindex", "/projects/myproject", fresh=True
        )


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
            "cocosearch.deps.registry.get_all_extractor_language_ids",
            return_value={"github-actions"},
        ):
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

    @pytest.mark.asyncio
    async def test_includes_deps_key(self, client):
        """Each grammar entry should include a 'deps' key."""
        mock_grammar = MagicMock()
        mock_grammar.GRAMMAR_NAME = "github-actions"
        mock_grammar.BASE_LANGUAGE = "yaml"
        mock_grammar.PATH_PATTERNS = [".github/workflows/*.yml"]

        with patch(
            "cocosearch.deps.registry.get_all_extractor_language_ids",
            return_value={"github-actions"},
        ):
            with patch(
                "cocosearch.handlers.get_registered_grammars",
                return_value=[mock_grammar],
            ):
                response = await client.get("/api/grammars")

        body = response.json()
        assert body[0]["deps"] is True


class TestApiCreditsSmoke:
    """Tests for GET /api/credits through the ASGI stack."""

    @pytest.fixture(autouse=True)
    def _reset_credits_cache(self):
        """Clear the in-process credits cache before each test."""
        from cocosearch.mcp import server

        server._CREDITS_CACHE["data"] = None
        server._CREDITS_CACHE["ts"] = 0.0
        yield
        server._CREDITS_CACHE["data"] = None
        server._CREDITS_CACHE["ts"] = 0.0

    @pytest.mark.asyncio
    async def test_ollama_reports_no_credits(self, client):
        """Local-only (ollama) setups report ok=False with a reason."""
        with patch(
            "cocosearch.mcp.server._credits_sync",
            return_value={
                "ok": False,
                "provider": "ollama",
                "reason": "no remote provider with a credits API in use",
            },
        ):
            response = await client.get("/api/credits")

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body["provider"] == "ollama"

    @pytest.mark.asyncio
    async def test_openrouter_returns_balance(self, client):
        """OpenRouter account balance is surfaced as 'remaining'."""
        with patch(
            "cocosearch.mcp.server._credits_sync",
            return_value={
                "ok": True,
                "provider": "openrouter",
                "model": "openai/gpt-4o-mini",
                "total_credits": 222.0,
                "total_usage": 213.3,
                "remaining": 8.7,
                "is_free_tier": False,
            },
        ):
            response = await client.get("/api/credits")

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["provider"] == "openrouter"
        assert body["remaining"] == 8.7
        assert body["total_credits"] == 222.0

    @pytest.mark.asyncio
    async def test_failure_degrades_gracefully(self, client):
        """A controller exception still returns 200 with ok=False."""
        with patch(
            "cocosearch.mcp.server._credits_sync",
            side_effect=RuntimeError("boom"),
        ):
            response = await client.get("/api/credits")

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert "boom" in body.get("error", "")


class TestFetchOpenRouterCredits:
    """Unit tests for the OpenRouter credits helper (mocked urllib)."""

    @staticmethod
    def _resp_for(url_payloads):
        """Return a urlopen side_effect that serves a payload per URL substring."""
        import json

        class _Resp:
            def __init__(self, payload):
                self._payload = payload

            def read(self):
                return json.dumps(self._payload).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def _side_effect(req, *a, **kw):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            for substr, payload in url_payloads.items():
                if substr in url:
                    return _Resp(payload)
            raise OSError(f"unexpected url {url}")

        return _side_effect

    def test_account_balance_is_primary_remaining(self):
        """Account total/usage from /credits yields the primary 'remaining'."""
        from cocosearch.mcp import server

        side = self._resp_for(
            {
                "/api/v1/credits": {
                    "data": {"total_credits": 222.0, "total_usage": 213.3}
                },
                "/api/v1/key": {
                    "data": {
                        "limit": None,
                        "limit_remaining": None,
                        "usage": 1.14,
                        "is_free_tier": False,
                    }
                },
            }
        )
        with patch("urllib.request.urlopen", side_effect=side):
            result = server._fetch_openrouter_credits("sk-test")

        assert result["ok"] is True
        assert result["total_credits"] == 222.0
        assert round(result["remaining"], 1) == 8.7
        assert result["is_free_tier"] is False

    def test_falls_back_to_key_limit_remaining(self):
        """When /credits has no totals, per-key limit_remaining is used."""
        from cocosearch.mcp import server

        side = self._resp_for(
            {
                "/api/v1/credits": {"data": {}},
                "/api/v1/key": {
                    "data": {
                        "limit": 10.0,
                        "limit_remaining": 6.0,
                        "usage": 4.0,
                        "is_free_tier": True,
                    }
                },
            }
        )
        with patch("urllib.request.urlopen", side_effect=side):
            result = server._fetch_openrouter_credits("sk-test")

        assert result["ok"] is True
        assert result["remaining"] == 6.0
        assert result["is_free_tier"] is True

    def test_network_error_returns_not_ok(self):
        """Both endpoints failing returns ok=False with an error."""
        from cocosearch.mcp import server

        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            result = server._fetch_openrouter_credits("sk-test")

        assert result["ok"] is False
        assert "error" in result


class TestControllerStatusInStats:
    """The configured controller status is injected into stats for the header."""

    def test_controller_disabled_by_default(self, monkeypatch):
        from cocosearch.mcp import server

        monkeypatch.delenv("COCOSEARCH_CONTROLLER_ENABLED", raising=False)
        result: dict = {}
        server._inject_configured_embedding(result)
        assert result["controller_enabled"] is False
        assert "controller_provider" not in result

    def test_controller_enabled_includes_provider_model(self, monkeypatch):
        from cocosearch.mcp import server

        monkeypatch.setenv("COCOSEARCH_CONTROLLER_ENABLED", "true")
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_PROVIDER", "openrouter")
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_MODEL", "openai/gpt-4o-mini")
        result: dict = {}
        server._inject_configured_embedding(result)
        assert result["controller_enabled"] is True
        assert result["controller_provider"] == "openrouter"
        assert result["controller_model"] == "openai/gpt-4o-mini"
