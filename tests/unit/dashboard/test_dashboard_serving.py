"""ASGI integration tests for dashboard HTML and static file serving.

Tests the full Starlette request/response cycle via httpx.AsyncClient
with ASGITransport — no real server, no browser, no infrastructure.
"""

import re

import pytest

# All JS modules that should be servable (excluding app.js which is tested separately)
JS_MODULES = [
    "state.js",
    "api.js",
    "utils.js",
    "charts.js",
    "dashboard.js",
    "index-mgmt.js",
    "search.js",
    "chat.js",
    "logs.js",
]


class TestDashboardServing:
    """Tests for GET /dashboard endpoint."""

    @pytest.mark.asyncio
    async def test_dashboard_returns_200(self, client):
        """GET /dashboard returns 200."""
        response = await client.get("/dashboard")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_dashboard_content_type_is_html(self, client):
        """Content-type includes text/html."""
        response = await client.get("/dashboard")
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_dashboard_references_external_css(self, client):
        """Served HTML has a link to /static/css/styles.css."""
        response = await client.get("/dashboard")
        assert '/static/css/styles.css"' in response.text

    @pytest.mark.asyncio
    async def test_dashboard_references_app_js_module(self, client):
        """Served HTML has a script tag for /static/js/app.js as a module."""
        response = await client.get("/dashboard")
        assert 'type="module"' in response.text
        assert '/static/js/app.js"' in response.text

    @pytest.mark.asyncio
    async def test_dashboard_has_cdn_scripts(self, client):
        """Chart.js, Prism, Marked, and DOMPurify CDN scripts are present."""
        response = await client.get("/dashboard")
        html = response.text
        assert "chart.js" in html.lower() or "chart.umd.js" in html
        assert "prism.min.js" in html
        assert "marked.min.js" in html
        assert "purify.min.js" in html

    @pytest.mark.asyncio
    async def test_dashboard_has_critical_sections(self, client):
        """Dashboard HTML contains header, search input, charts, log panel, and file modal."""
        response = await client.get("/dashboard")
        html = response.text
        assert "<header>" in html or "<header " in html
        assert 'id="searchInput"' in html
        assert 'id="languageChart"' in html
        assert 'class="logs-btn"' in html or "LOGS" in html
        assert 'id="fileModal"' in html or "file-modal" in html


class TestStaticFileServing:
    """Tests for GET /static/{path} endpoint."""

    @pytest.mark.asyncio
    async def test_css_returns_200_with_correct_type(self, client):
        """/static/css/styles.css returns 200 with text/css content-type."""
        response = await client.get("/static/css/styles.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_css_has_content(self, client):
        """CSS response body is substantial (>1000 chars)."""
        response = await client.get("/static/css/styles.css")
        assert len(response.text) > 1000

    @pytest.mark.asyncio
    async def test_app_js_returns_200_with_correct_type(self, client):
        """/static/js/app.js returns 200 with application/javascript."""
        response = await client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("module", JS_MODULES)
    async def test_all_js_modules_return_200(self, client, module):
        """Each JS module file returns 200."""
        response = await client.get(f"/static/js/{module}")
        assert response.status_code == 200, (
            f"/static/js/{module} returned {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, client):
        """Path traversal via /static/../../../etc/passwd returns 403 or 404."""
        response = await client.get("/static/../../../etc/passwd")
        assert response.status_code in (403, 404)

    @pytest.mark.asyncio
    async def test_nonexistent_file_returns_404(self, client):
        """/static/js/nonexistent.js returns 404."""
        response = await client.get("/static/js/nonexistent.js")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_directory_traversal_in_filename_blocked(self, client):
        """Path traversal via nested ../ in filename returns 403 or 404."""
        response = await client.get("/static/css/../../mcp/server.py")
        assert response.status_code in (403, 404)


class TestDashboardStaticIntegration:
    """Cross-reference: all static refs in HTML actually resolve."""

    @pytest.mark.asyncio
    async def test_all_css_references_in_html_resolve(self, client):
        """Every /static/css/* href in the HTML responds 200."""
        response = await client.get("/dashboard")
        hrefs = re.findall(r'href="(/static/css/[^"]+)"', response.text)
        assert len(hrefs) > 0, "No CSS references found in HTML"
        for href in hrefs:
            css_response = await client.get(href)
            assert css_response.status_code == 200, (
                f"{href} returned {css_response.status_code}"
            )

    @pytest.mark.asyncio
    async def test_all_js_references_in_html_resolve(self, client):
        """Every /static/js/* src in the HTML responds 200."""
        response = await client.get("/dashboard")
        srcs = re.findall(r'src="(/static/js/[^"]+)"', response.text)
        assert len(srcs) > 0, "No JS references found in HTML"
        for src in srcs:
            js_response = await client.get(src)
            assert js_response.status_code == 200, (
                f"{src} returned {js_response.status_code}"
            )
