"""Tests for file interaction endpoints: open-in-editor and file-content."""

import os
from unittest.mock import patch, MagicMock

import pytest

from cocosearch.mcp.server import (
    _validate_file_path,
    _resolve_editor,
    _build_editor_command,
    _get_prism_language,
)


class TestValidateFilePath:
    """Tests for _validate_file_path."""

    def test_empty_path(self):
        assert _validate_file_path("") == "file_path is required"

    def test_relative_path(self):
        assert _validate_file_path("relative/path.py") == "file_path must be absolute"

    def test_path_traversal(self):
        assert (
            _validate_file_path("/foo/../bar/file.py") == "path traversal not allowed"
        )

    def test_nonexistent_file(self):
        assert _validate_file_path("/nonexistent/file.py") == "file not found"

    def test_valid_file(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("hello")
        assert _validate_file_path(str(f)) is None

    def test_directory_not_file(self, tmp_path):
        assert _validate_file_path(str(tmp_path)) == "file not found"


class TestResolveEditor:
    """Tests for _resolve_editor."""

    def test_cocosearch_editor_first(self):
        with patch.dict(os.environ, {"COCOSEARCH_EDITOR": "code", "EDITOR": "vim"}):
            assert _resolve_editor() == "code"

    def test_falls_back_to_editor(self):
        env = {"EDITOR": "vim"}
        with patch.dict(os.environ, env, clear=True):
            assert _resolve_editor() == "vim"

    def test_falls_back_to_visual(self):
        env = {"VISUAL": "emacs"}
        with patch.dict(os.environ, env, clear=True):
            assert _resolve_editor() == "emacs"

    def test_none_when_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _resolve_editor() is None


class TestBuildEditorCommand:
    """Tests for _build_editor_command."""

    @patch("shutil.which", return_value="/usr/bin/code")
    def test_vscode_goto(self, mock_which):
        cmd = _build_editor_command("code", "/tmp/file.py", 42)
        assert cmd == ["/usr/bin/code", "--goto", "/tmp/file.py:42"]

    @patch("shutil.which", return_value="/usr/bin/code-insiders")
    def test_vscode_insiders(self, mock_which):
        cmd = _build_editor_command("code-insiders", "/tmp/file.py", 10)
        assert cmd == ["/usr/bin/code-insiders", "--goto", "/tmp/file.py:10"]

    @patch("shutil.which", return_value="/usr/bin/vim")
    def test_vim_plus_line(self, mock_which):
        cmd = _build_editor_command("vim", "/tmp/file.py", 42)
        assert cmd == ["/usr/bin/vim", "+42", "/tmp/file.py"]

    @patch("shutil.which", return_value="/usr/bin/nvim")
    def test_nvim_plus_line(self, mock_which):
        cmd = _build_editor_command("nvim", "/tmp/file.py", 5)
        assert cmd == ["/usr/bin/nvim", "+5", "/tmp/file.py"]

    @patch("shutil.which", return_value="/usr/bin/nano")
    def test_nano_plus_line(self, mock_which):
        cmd = _build_editor_command("nano", "/tmp/file.py", 3)
        assert cmd == ["/usr/bin/nano", "+3", "/tmp/file.py"]

    @patch("shutil.which", return_value="/usr/bin/emacs")
    def test_emacs_plus_line(self, mock_which):
        cmd = _build_editor_command("emacs", "/tmp/file.py", 7)
        assert cmd == ["/usr/bin/emacs", "+7", "/tmp/file.py"]

    @patch("shutil.which", return_value="/usr/bin/subl")
    def test_sublime_colon_line(self, mock_which):
        cmd = _build_editor_command("subl", "/tmp/file.py", 42)
        assert cmd == ["/usr/bin/subl", "/tmp/file.py:42"]

    @patch("shutil.which", return_value="/usr/bin/idea")
    def test_jetbrains_line_flag(self, mock_which):
        cmd = _build_editor_command("idea", "/tmp/file.py", 42)
        assert cmd == ["/usr/bin/idea", "--line", "42", "/tmp/file.py"]

    @patch("shutil.which", return_value="/usr/bin/unknown-editor")
    def test_unknown_editor_no_line(self, mock_which):
        cmd = _build_editor_command("unknown-editor", "/tmp/file.py", 42)
        assert cmd == ["/usr/bin/unknown-editor", "/tmp/file.py"]

    @patch("shutil.which", return_value="/usr/bin/vim")
    def test_no_line_number(self, mock_which):
        cmd = _build_editor_command("vim", "/tmp/file.py", None)
        assert cmd == ["/usr/bin/vim", "/tmp/file.py"]

    @patch("shutil.which", return_value=None)
    def test_which_not_found_uses_raw_name(self, mock_which):
        cmd = _build_editor_command("myeditor", "/tmp/file.py", 1)
        assert cmd == ["myeditor", "/tmp/file.py"]


class TestGetPrismLanguage:
    """Tests for _get_prism_language."""

    def test_python_file(self):
        assert _get_prism_language("/foo/bar.py") == "python"

    def test_typescript_file(self):
        assert _get_prism_language("/foo/bar.ts") == "typescript"

    def test_tsx_file(self):
        assert _get_prism_language("/foo/component.tsx") == "tsx"

    def test_dockerfile(self):
        assert _get_prism_language("/foo/Dockerfile") == "docker"

    def test_makefile(self):
        assert _get_prism_language("/foo/Makefile") == "makefile"

    def test_unknown_extension(self):
        assert _get_prism_language("/foo/bar.xyz") == "plain"

    def test_no_extension(self):
        assert _get_prism_language("/foo/README") == "plain"

    def test_yaml_file(self):
        assert _get_prism_language("/foo/config.yaml") == "yaml"

    def test_rust_file(self):
        assert _get_prism_language("/foo/main.rs") == "rust"

    def test_go_file(self):
        assert _get_prism_language("/foo/main.go") == "go"


def _async_json(data):
    """Create an async mock for request.json()."""

    async def _json():
        return data

    return _json


class TestOpenInEditorEndpoint:
    """Tests for POST /api/open-in-editor (MCP server)."""

    @pytest.mark.asyncio
    async def test_missing_file_path(self):
        from cocosearch.mcp.server import api_open_in_editor

        request = MagicMock()
        request.json = _async_json({"file_path": "", "line": 1})

        resp = await api_open_in_editor(request)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_relative_path_rejected(self):
        from cocosearch.mcp.server import api_open_in_editor

        request = MagicMock()
        request.json = _async_json({"file_path": "relative/path.py", "line": 1})

        resp = await api_open_in_editor(request)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_no_editor_configured(self, tmp_path):
        from cocosearch.mcp.server import api_open_in_editor

        f = tmp_path / "test.py"
        f.write_text("hello")

        request = MagicMock()
        request.json = _async_json({"file_path": str(f), "line": 1})

        with patch.dict(os.environ, {}, clear=True):
            resp = await api_open_in_editor(request)
        assert resp.status_code == 400
        assert b"No editor configured" in resp.body

    @pytest.mark.asyncio
    async def test_success(self, tmp_path):
        from cocosearch.mcp.server import api_open_in_editor

        f = tmp_path / "test.py"
        f.write_text("hello")

        request = MagicMock()
        request.json = _async_json({"file_path": str(f), "line": 5})

        with patch.dict(os.environ, {"COCOSEARCH_EDITOR": "code"}):
            with patch("subprocess.Popen") as mock_popen:
                resp = await api_open_in_editor(request)

        assert resp.status_code == 200
        mock_popen.assert_called_once()


class TestFileContentEndpoint:
    """Tests for GET /api/file-content (MCP server)."""

    @pytest.mark.asyncio
    async def test_missing_path(self):
        from cocosearch.mcp.server import api_file_content

        request = MagicMock()
        request.query_params = {"path": ""}

        resp = await api_file_content(request)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_nonexistent_file(self):
        from cocosearch.mcp.server import api_file_content

        request = MagicMock()
        request.query_params = {"path": "/nonexistent/file.py"}

        resp = await api_file_content(request)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self):
        from cocosearch.mcp.server import api_file_content

        request = MagicMock()
        request.query_params = {"path": "/tmp/../etc/passwd"}

        resp = await api_file_content(request)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_success_returns_content(self, tmp_path):
        import json
        from cocosearch.mcp.server import api_file_content

        f = tmp_path / "test.py"
        f.write_text("def hello():\n    pass\n")

        request = MagicMock()
        request.query_params = {"path": str(f)}

        resp = await api_file_content(request)
        assert resp.status_code == 200

        body = json.loads(resp.body)
        assert body["language"] == "python"
        assert body["lines"] == 2
        assert "def hello()" in body["content"]

    @pytest.mark.asyncio
    async def test_detects_language(self, tmp_path):
        import json
        from cocosearch.mcp.server import api_file_content

        f = tmp_path / "app.ts"
        f.write_text("const x = 1;\n")

        request = MagicMock()
        request.query_params = {"path": str(f)}

        resp = await api_file_content(request)
        body = json.loads(resp.body)
        assert body["language"] == "typescript"
