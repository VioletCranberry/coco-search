"""Shared fixtures for dashboard HTML structure and ASGI integration tests."""

import re
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from bs4 import BeautifulSoup

STATIC_DIR = (
    Path(__file__).parents[3] / "src" / "cocosearch" / "dashboard" / "web" / "static"
)
JS_DIR = STATIC_DIR / "js"
CSS_DIR = STATIC_DIR / "css"


@pytest.fixture
def html_content():
    """Load the dashboard HTML as a string."""
    return (STATIC_DIR / "index.html").read_text()


@pytest.fixture
def soup(html_content):
    """Parse the dashboard HTML with BeautifulSoup."""
    return BeautifulSoup(html_content, "html.parser")


@pytest.fixture
def js_files():
    """Return a dict mapping filename -> content for all JS files."""
    result = {}
    for path in JS_DIR.glob("*.js"):
        result[path.name] = path.read_text()
    return result


@pytest.fixture
def all_js_content(js_files):
    """Return all JS content concatenated."""
    return "\n".join(js_files.values())


@pytest.fixture
def referenced_ids(all_js_content):
    """Extract all element IDs referenced via getElementById in JS files.

    Filters out dynamic IDs containing template literal expressions (${...}).
    """
    raw_ids = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", all_js_content))
    return {id_ for id_ in raw_ids if "${" not in id_}


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
