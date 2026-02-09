"""Tests for cocosearch MCP project detection module.

Comprehensive unit tests for file_uri_to_path, _detect_project,
and register_roots_notification.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, Root, ListRootsResult, RootsListChangedNotification
from pydantic import FileUrl

from cocosearch.mcp.project_detection import (
    file_uri_to_path,
    _detect_project,
    register_roots_notification,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_ctx(
    has_roots=False,
    roots=None,
    roots_error=None,
    request=None,
):
    """Create a mock Context for testing _detect_project."""
    ctx = MagicMock()

    # Session mocking
    session = MagicMock()
    if has_roots:
        session.check_client_capability.return_value = True
    else:
        session.check_client_capability.return_value = False

    if roots_error:
        session.list_roots = AsyncMock(side_effect=roots_error)
    elif roots is not None:
        session.list_roots = AsyncMock(return_value=ListRootsResult(roots=roots))
    else:
        session.list_roots = AsyncMock(return_value=ListRootsResult(roots=[]))

    ctx.session = session

    # Request context mocking
    request_context = MagicMock()
    request_context.request = request
    ctx.request_context = request_context

    return ctx


# ---------------------------------------------------------------------------
# TestFileUriToPath
# ---------------------------------------------------------------------------


class TestFileUriToPath:
    """Tests for file_uri_to_path."""

    def test_standard_unix_path(self):
        """file:///tmp/project -> Path('/tmp/project')."""
        result = file_uri_to_path("file:///tmp/project")
        assert result == Path("/tmp/project")

    def test_percent_encoded_spaces(self):
        """file:///my%20project -> Path('/my project')."""
        result = file_uri_to_path("file:///my%20project")
        assert result == Path("/my project")

    def test_percent_encoded_special_chars(self):
        """file:///path/%23special -> Path('/path/#special')."""
        result = file_uri_to_path("file:///path/%23special")
        assert result == Path("/path/#special")

    def test_non_file_uri_returns_none(self):
        """https://example.com -> None."""
        result = file_uri_to_path("https://example.com")
        assert result is None

    def test_empty_string_returns_none(self):
        """Empty string -> None."""
        result = file_uri_to_path("")
        assert result is None

    def test_file_uri_no_path_returns_none(self):
        """file:// with no path component returns None or root."""
        # urlparse("file://") gives path="" which is falsy
        result = file_uri_to_path("file://")
        assert result is None

    def test_nested_path(self):
        """file:///home/user/projects/my-app -> Path('/home/user/projects/my-app')."""
        result = file_uri_to_path("file:///home/user/projects/my-app")
        assert result == Path("/home/user/projects/my-app")


# ---------------------------------------------------------------------------
# TestDetectProjectRoots (async tests)
# ---------------------------------------------------------------------------


class TestDetectProjectRoots:
    """Tests for _detect_project roots priority (highest)."""

    @pytest.mark.asyncio
    async def test_returns_root_path_when_roots_available(self, tmp_path):
        """Mock ctx with roots capability returning a valid root on disk."""
        root_dir = tmp_path / "project"
        root_dir.mkdir()

        root = Root(uri=FileUrl(root_dir.as_uri()), name="project")
        ctx = make_mock_ctx(has_roots=True, roots=[root])

        path, source = await _detect_project(ctx)
        assert path == root_dir
        assert source == "roots"

    @pytest.mark.asyncio
    async def test_skips_nonexistent_root_path(self):
        """Roots returning path that doesn't exist on disk falls through."""
        root = Root(uri=FileUrl("file:///nonexistent/path/xyz"), name="ghost")
        ctx = make_mock_ctx(has_roots=True, roots=[root])

        # Should fall through to cwd since root doesn't exist
        path, source = await _detect_project(ctx)
        assert source != "roots"

    @pytest.mark.asyncio
    async def test_skips_when_client_has_no_roots_capability(self):
        """Client without roots capability should not call list_roots."""
        ctx = make_mock_ctx(has_roots=False)

        path, source = await _detect_project(ctx)
        ctx.session.list_roots.assert_not_awaited()
        assert source != "roots"

    @pytest.mark.asyncio
    async def test_handles_mcp_error_gracefully(self, tmp_path):
        """McpError from list_roots falls through without error."""
        ctx = make_mock_ctx(
            has_roots=True,
            roots_error=McpError(ErrorData(code=-1, message="test error")),
        )

        # Should fall through gracefully, not raise
        path, source = await _detect_project(ctx)
        assert source != "roots"


# ---------------------------------------------------------------------------
# TestDetectProjectQueryParam (async tests)
# ---------------------------------------------------------------------------


class TestDetectProjectQueryParam:
    """Tests for query_param priority (second)."""

    @pytest.mark.asyncio
    async def test_returns_path_from_query_param(self, tmp_path):
        """Query param with existing absolute path returns (path, 'query_param')."""
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()

        mock_request = MagicMock()
        mock_request.query_params = {"project_path": str(project_dir)}
        ctx = make_mock_ctx(has_roots=False, request=mock_request)

        path, source = await _detect_project(ctx)
        assert path == project_dir
        assert source == "query_param"

    @pytest.mark.asyncio
    async def test_rejects_relative_path(self, tmp_path):
        """Query param with relative path falls through."""
        mock_request = MagicMock()
        mock_request.query_params = {"project_path": "relative/path"}
        ctx = make_mock_ctx(has_roots=False, request=mock_request)

        path, source = await _detect_project(ctx)
        assert source != "query_param"

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_path(self):
        """Query param with absolute path that doesn't exist falls through."""
        mock_request = MagicMock()
        mock_request.query_params = {"project_path": "/nonexistent/absolute/path/xyz"}
        ctx = make_mock_ctx(has_roots=False, request=mock_request)

        path, source = await _detect_project(ctx)
        assert source != "query_param"

    @pytest.mark.asyncio
    async def test_skips_when_no_request(self):
        """stdio transport has no request -- falls through."""
        ctx = make_mock_ctx(has_roots=False, request=None)

        path, source = await _detect_project(ctx)
        assert source != "query_param"


# ---------------------------------------------------------------------------
# TestDetectProjectEnvVar (async tests)
# ---------------------------------------------------------------------------


class TestDetectProjectEnvVar:
    """Tests for env priority (third)."""

    @pytest.mark.asyncio
    async def test_returns_path_from_cocosearch_project_path_env(
        self, tmp_path, monkeypatch
    ):
        """COCOSEARCH_PROJECT_PATH env var returns (path, 'env')."""
        project_dir = tmp_path / "env_project"
        project_dir.mkdir()

        monkeypatch.setenv("COCOSEARCH_PROJECT_PATH", str(project_dir))
        monkeypatch.delenv("COCOSEARCH_PROJECT", raising=False)

        ctx = make_mock_ctx(has_roots=False, request=None)
        path, source = await _detect_project(ctx)
        assert path == project_dir
        assert source == "env"

    @pytest.mark.asyncio
    async def test_returns_path_from_cocosearch_project_env(
        self, tmp_path, monkeypatch
    ):
        """COCOSEARCH_PROJECT env var returns (path, 'env')."""
        project_dir = tmp_path / "env_project2"
        project_dir.mkdir()

        monkeypatch.delenv("COCOSEARCH_PROJECT_PATH", raising=False)
        monkeypatch.setenv("COCOSEARCH_PROJECT", str(project_dir))

        ctx = make_mock_ctx(has_roots=False, request=None)
        path, source = await _detect_project(ctx)
        assert path == project_dir
        assert source == "env"

    @pytest.mark.asyncio
    async def test_cocosearch_project_path_takes_precedence(
        self, tmp_path, monkeypatch
    ):
        """COCOSEARCH_PROJECT_PATH takes precedence over COCOSEARCH_PROJECT."""
        dir_a = tmp_path / "dir_a"
        dir_a.mkdir()
        dir_b = tmp_path / "dir_b"
        dir_b.mkdir()

        monkeypatch.setenv("COCOSEARCH_PROJECT_PATH", str(dir_a))
        monkeypatch.setenv("COCOSEARCH_PROJECT", str(dir_b))

        ctx = make_mock_ctx(has_roots=False, request=None)
        path, source = await _detect_project(ctx)
        assert path == dir_a
        assert source == "env"


# ---------------------------------------------------------------------------
# TestDetectProjectCwd (async tests)
# ---------------------------------------------------------------------------


class TestDetectProjectCwd:
    """Tests for cwd fallback (lowest)."""

    @pytest.mark.asyncio
    async def test_returns_cwd_as_last_resort(self, monkeypatch):
        """No roots, no request, no env vars -> returns (cwd, 'cwd')."""
        monkeypatch.delenv("COCOSEARCH_PROJECT_PATH", raising=False)
        monkeypatch.delenv("COCOSEARCH_PROJECT", raising=False)

        ctx = make_mock_ctx(has_roots=False, request=None)
        path, source = await _detect_project(ctx)
        assert path == Path.cwd()
        assert source == "cwd"


# ---------------------------------------------------------------------------
# TestDetectProjectPriorityChain (async tests)
# ---------------------------------------------------------------------------


class TestDetectProjectPriorityChain:
    """End-to-end priority tests."""

    @pytest.mark.asyncio
    async def test_roots_beats_query_param(self, tmp_path):
        """Roots available alongside query_param -- roots wins."""
        roots_dir = tmp_path / "roots_project"
        roots_dir.mkdir()
        query_dir = tmp_path / "query_project"
        query_dir.mkdir()

        root = Root(uri=FileUrl(roots_dir.as_uri()), name="roots_proj")
        mock_request = MagicMock()
        mock_request.query_params = {"project_path": str(query_dir)}
        ctx = make_mock_ctx(has_roots=True, roots=[root], request=mock_request)

        path, source = await _detect_project(ctx)
        assert path == roots_dir
        assert source == "roots"

    @pytest.mark.asyncio
    async def test_query_param_beats_env(self, tmp_path, monkeypatch):
        """Query param available alongside env -- query_param wins."""
        query_dir = tmp_path / "query_project"
        query_dir.mkdir()
        env_dir = tmp_path / "env_project"
        env_dir.mkdir()

        monkeypatch.setenv("COCOSEARCH_PROJECT_PATH", str(env_dir))

        mock_request = MagicMock()
        mock_request.query_params = {"project_path": str(query_dir)}
        ctx = make_mock_ctx(has_roots=False, request=mock_request)

        path, source = await _detect_project(ctx)
        assert path == query_dir
        assert source == "query_param"

    @pytest.mark.asyncio
    async def test_env_beats_cwd(self, tmp_path, monkeypatch):
        """Env set, falls to env not cwd."""
        env_dir = tmp_path / "env_project"
        env_dir.mkdir()

        monkeypatch.setenv("COCOSEARCH_PROJECT_PATH", str(env_dir))

        ctx = make_mock_ctx(has_roots=False, request=None)
        path, source = await _detect_project(ctx)
        assert path == env_dir
        assert source == "env"


# ---------------------------------------------------------------------------
# TestRegisterRootsNotification
# ---------------------------------------------------------------------------


class TestRegisterRootsNotification:
    """Tests for register_roots_notification."""

    def test_registers_handler_on_low_level_server(self):
        """Registers RootsListChangedNotification handler on _mcp_server."""
        mock_mcp = MagicMock()
        mock_mcp._mcp_server.notification_handlers = {}

        register_roots_notification(mock_mcp)

        assert (
            RootsListChangedNotification in mock_mcp._mcp_server.notification_handlers
        )
        handler = mock_mcp._mcp_server.notification_handlers[
            RootsListChangedNotification
        ]
        assert callable(handler)
