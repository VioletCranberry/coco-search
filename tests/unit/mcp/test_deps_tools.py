"""Tests for dependency graph MCP tools and API endpoints.

Tests mock the query layer to verify correct parameter passing
and response structure.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest
import pytest_asyncio

from cocosearch.deps.models import DependencyEdge, DependencyTree, DepType


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


# ============================================================================
# Tests: POST /api/deps
# ============================================================================


class TestApiDeps:
    """Tests for POST /api/deps endpoint."""

    @pytest.mark.asyncio
    async def test_returns_dependency_tree(self, client):
        tree = DependencyTree(
            file="src/main.py",
            symbol=None,
            dep_type="root",
            children=[
                DependencyTree(
                    file="src/utils.py",
                    symbol=None,
                    dep_type="import",
                    children=[],
                )
            ],
        )

        with patch("cocosearch.deps.query.get_dependency_tree", return_value=tree):
            response = await client.post(
                "/api/deps",
                json={"file": "src/main.py", "index_name": "test", "depth": 3},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["file"] == "src/main.py"
        assert len(body["children"]) == 1
        assert body["children"][0]["file"] == "src/utils.py"

    @pytest.mark.asyncio
    async def test_requires_file(self, client):
        response = await client.post("/api/deps", json={"index_name": "test"})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_requires_index_name(self, client):
        response = await client.post("/api/deps", json={"file": "main.py"})
        assert response.status_code == 400


# ============================================================================
# Tests: POST /api/deps/impact
# ============================================================================


class TestApiDepsImpact:
    """Tests for POST /api/deps/impact endpoint."""

    @pytest.mark.asyncio
    async def test_returns_impact_tree(self, client):
        tree = DependencyTree(
            file="src/utils.py",
            symbol=None,
            dep_type="root",
            children=[
                DependencyTree(
                    file="src/main.py",
                    symbol=None,
                    dep_type="import",
                    children=[],
                )
            ],
        )

        with patch("cocosearch.deps.query.get_impact", return_value=tree):
            response = await client.post(
                "/api/deps/impact",
                json={"file": "src/utils.py", "index_name": "test"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["file"] == "src/utils.py"
        assert len(body["children"]) == 1

    @pytest.mark.asyncio
    async def test_requires_file(self, client):
        response = await client.post("/api/deps/impact", json={"index_name": "test"})
        assert response.status_code == 400


# ============================================================================
# Tests: GET /api/deps/graph
# ============================================================================


class TestApiDepsGraph:
    """Tests for GET /api/deps/graph endpoint."""

    @pytest.mark.asyncio
    async def test_returns_nodes_and_edges(self, client):
        tree = DependencyTree(
            file="a.py",
            symbol=None,
            dep_type="root",
            children=[
                DependencyTree(
                    file="b.py",
                    symbol=None,
                    dep_type="import",
                    children=[],
                )
            ],
        )

        with patch("cocosearch.deps.query.get_dependency_tree", return_value=tree):
            response = await client.get(
                "/api/deps/graph", params={"file": "a.py", "index": "test"}
            )

        assert response.status_code == 200
        body = response.json()
        assert "nodes" in body
        assert "edges" in body
        assert len(body["nodes"]) == 2
        assert len(body["edges"]) == 1

    @pytest.mark.asyncio
    async def test_requires_file(self, client):
        response = await client.get("/api/deps/graph", params={"index": "test"})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_requires_index(self, client):
        response = await client.get("/api/deps/graph", params={"file": "a.py"})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_external_nodes_in_graph(self, client):
        """External nodes should appear with is_external flag and correct labels."""
        tree = DependencyTree(
            file="workflow.yml",
            symbol=None,
            dep_type="root",
            children=[
                DependencyTree(
                    file="actions/checkout@v4",
                    symbol=None,
                    dep_type="reference",
                    children=[],
                    is_external=True,
                ),
                DependencyTree(
                    file="astral-sh/setup-uv@v5",
                    symbol=None,
                    dep_type="reference",
                    children=[],
                    is_external=True,
                ),
            ],
        )
        empty_tree = DependencyTree(
            file="workflow.yml", symbol=None, dep_type="root", children=[]
        )

        with (
            patch("cocosearch.deps.query.get_dependency_tree", return_value=tree),
            patch("cocosearch.deps.query.get_impact", return_value=empty_tree),
        ):
            response = await client.get(
                "/api/deps/graph", params={"file": "workflow.yml", "index": "test"}
            )

        assert response.status_code == 200
        body = response.json()

        # 3 nodes: workflow.yml + 2 external
        assert len(body["nodes"]) == 3
        ext_nodes = [n for n in body["nodes"] if n.get("is_external")]
        assert len(ext_nodes) == 2
        ext_ids = {n["id"] for n in ext_nodes}
        assert ext_ids == {"actions/checkout@v4", "astral-sh/setup-uv@v5"}

        # 2 edges from workflow.yml to each external node
        assert len(body["edges"]) == 2


# ============================================================================
# Tests: MCP tool get_file_dependencies
# ============================================================================


class TestGetFileDependenciesTool:
    """Tests for the get_file_dependencies MCP tool."""

    @pytest.mark.asyncio
    async def test_direct_dependencies(self):
        edges = [
            DependencyEdge(
                source_file="a.py",
                source_symbol=None,
                target_file="b.py",
                target_symbol="helper",
                dep_type=DepType.IMPORT,
                metadata={"module": "b"},
            )
        ]

        with patch("cocosearch.deps.query.get_dependencies", return_value=edges):
            from cocosearch.mcp.server import get_file_dependencies

            ctx = MagicMock()
            result = await get_file_dependencies(
                file="a.py", ctx=ctx, index_name="test", depth=1
            )

        assert result["total"] == 1
        assert result["dependencies"][0]["target_file"] == "b.py"

    @pytest.mark.asyncio
    async def test_transitive_dependencies(self):
        tree = DependencyTree(file="a.py", symbol=None, dep_type="root", children=[])

        with patch("cocosearch.deps.query.get_dependency_tree", return_value=tree):
            from cocosearch.mcp.server import get_file_dependencies

            ctx = MagicMock()
            result = await get_file_dependencies(
                file="a.py", ctx=ctx, index_name="test", depth=3
            )

        assert "tree" in result


# ============================================================================
# Tests: MCP tool get_file_impact
# ============================================================================


class TestGetFileImpactTool:
    """Tests for the get_file_impact MCP tool."""

    @pytest.mark.asyncio
    async def test_impact_tree(self):
        tree = DependencyTree(
            file="utils.py", symbol=None, dep_type="root", children=[]
        )

        with patch("cocosearch.deps.query.get_impact", return_value=tree):
            from cocosearch.mcp.server import get_file_impact

            ctx = MagicMock()
            result = await get_file_impact(
                file="utils.py", ctx=ctx, index_name="test", depth=3
            )

        assert result["file"] == "utils.py"
        assert "impact_tree" in result
