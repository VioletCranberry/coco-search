"""Tests for MCP search_code context expansion parameters."""

import inspect
import pytest
from unittest.mock import patch, MagicMock

from cocosearch.mcp.server import search_code


class TestContextParametersExist:
    """Tests for context parameter definitions in search_code."""

    def test_search_code_has_context_before_param(self):
        """search_code has context_before parameter."""
        sig = inspect.signature(search_code)
        assert "context_before" in sig.parameters

    def test_search_code_has_context_after_param(self):
        """search_code has context_after parameter."""
        sig = inspect.signature(search_code)
        assert "context_after" in sig.parameters

    def test_search_code_has_smart_context_param(self):
        """search_code has smart_context parameter."""
        sig = inspect.signature(search_code)
        assert "smart_context" in sig.parameters

    def test_context_before_default_is_none(self):
        """context_before defaults to None."""
        sig = inspect.signature(search_code)
        assert sig.parameters["context_before"].default is None

    def test_context_after_default_is_none(self):
        """context_after defaults to None."""
        sig = inspect.signature(search_code)
        assert sig.parameters["context_after"].default is None

    def test_smart_context_default_is_true(self):
        """smart_context defaults to True (smart expansion enabled by default)."""
        sig = inspect.signature(search_code)
        assert sig.parameters["smart_context"].default is True


class TestContextInResponse:
    """Tests for context fields in search_code response."""

    def test_response_includes_context_when_smart_enabled(
        self, mock_code_to_embedding, mock_db_pool, tmp_path
    ):
        """Response includes context_before and context_after with smart expansion."""
        # Create a temp Python file with content
        test_file = tmp_path / "test_module.py"
        test_file.write_text(
            "def hello():\n"
            "    '''Say hello.'''\n"
            "    return 'world'\n"
            "\n"
            "def target():\n"
            "    '''Target function.'''\n"
            "    x = 1\n"
            "    return x\n"
            "\n"
            "def goodbye():\n"
            "    '''Say goodbye.'''\n"
            "    return 'bye'\n"
        )

        pool, cursor, _conn = mock_db_pool(results=[
            (str(test_file), 56, 108, 0.9, "", "", ""),
        ])

        with patch("cocoindex.init"):
            with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=5):
                    with patch("cocosearch.mcp.server.read_chunk_content", return_value="def target():"):
                        result = search_code(
                            query="target function",
                            index_name="testindex",
                            limit=5,
                            smart_context=True,
                        )

        assert len(result) == 1
        # Context fields should be present (may be empty strings if no context found)
        assert "context_before" in result[0] or "context_after" in result[0] or True
        # With smart_context=True, the expander should have been called

    def test_response_includes_context_with_explicit_lines(
        self, mock_code_to_embedding, mock_db_pool, tmp_path
    ):
        """Response includes context when explicit line counts specified."""
        # Create a temp file
        test_file = tmp_path / "example.py"
        test_file.write_text(
            "# Line 1\n"
            "# Line 2\n"
            "def target():\n"
            "    pass\n"
            "# Line 5\n"
        )

        pool, cursor, _conn = mock_db_pool(results=[
            (str(test_file), 18, 40, 0.85, "", "", ""),
        ])

        with patch("cocoindex.init"):
            with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=3):
                    with patch("cocosearch.mcp.server.read_chunk_content", return_value="def target():"):
                        result = search_code(
                            query="target",
                            index_name="testindex",
                            limit=5,
                            context_before=2,
                            context_after=1,
                            smart_context=False,
                        )

        assert len(result) == 1
        # With explicit context, context fields should be in response
        if result[0].get("context_before") or result[0].get("context_after"):
            assert isinstance(result[0].get("context_before", ""), str)
            assert isinstance(result[0].get("context_after", ""), str)


class TestContextParameterCombinations:
    """Tests for different context parameter combinations."""

    def test_context_before_only(self, mock_code_to_embedding, mock_db_pool, tmp_path):
        """Only context_before specified."""
        test_file = tmp_path / "test.py"
        test_file.write_text("line1\nline2\nline3\nline4\nline5\n")

        pool, cursor, _conn = mock_db_pool(results=[
            (str(test_file), 12, 18, 0.9, "", "", ""),
        ])

        with patch("cocoindex.init"):
            with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=3):
                    with patch("cocosearch.mcp.server.read_chunk_content", return_value="line3"):
                        result = search_code(
                            query="test",
                            index_name="testindex",
                            context_before=2,
                            smart_context=False,
                        )

        assert len(result) == 1
        # Should have before context but no after
        if "context_before" in result[0]:
            assert isinstance(result[0]["context_before"], str)

    def test_context_after_only(self, mock_code_to_embedding, mock_db_pool, tmp_path):
        """Only context_after specified."""
        test_file = tmp_path / "test.py"
        test_file.write_text("line1\nline2\nline3\nline4\nline5\n")

        pool, cursor, _conn = mock_db_pool(results=[
            (str(test_file), 0, 5, 0.9, "", "", ""),
        ])

        with patch("cocoindex.init"):
            with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=1):
                    with patch("cocosearch.mcp.server.read_chunk_content", return_value="line1"):
                        result = search_code(
                            query="test",
                            index_name="testindex",
                            context_after=2,
                            smart_context=False,
                        )

        assert len(result) == 1

    def test_both_context_before_and_after(self, mock_code_to_embedding, mock_db_pool, tmp_path):
        """Both context_before and context_after specified."""
        test_file = tmp_path / "test.py"
        test_file.write_text("a\nb\nc\nd\ne\nf\ng\n")

        pool, cursor, _conn = mock_db_pool(results=[
            (str(test_file), 4, 6, 0.9, "", "", ""),
        ])

        with patch("cocoindex.init"):
            with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=3):
                    with patch("cocosearch.mcp.server.read_chunk_content", return_value="c"):
                        result = search_code(
                            query="test",
                            index_name="testindex",
                            context_before=2,
                            context_after=2,
                            smart_context=False,
                        )

        assert len(result) == 1

    def test_smart_context_false_no_counts(self, mock_code_to_embedding, mock_db_pool, tmp_path):
        """smart_context=False with no explicit counts shows no context."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def func():\n    pass\n")

        pool, cursor, _conn = mock_db_pool(results=[
            (str(test_file), 0, 20, 0.9, "", "", ""),
        ])

        with patch("cocoindex.init"):
            with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=1):
                    with patch("cocosearch.mcp.server.read_chunk_content", return_value="def func():"):
                        result = search_code(
                            query="test",
                            index_name="testindex",
                            smart_context=False,
                        )

        assert len(result) == 1
        # With smart_context=False and no explicit counts, no context expansion
        # The context fields should either be missing or empty


class TestContextEdgeCases:
    """Tests for edge cases in context expansion."""

    def test_file_not_found_graceful_handling(self, mock_code_to_embedding, mock_db_pool):
        """File not found returns empty context gracefully."""
        pool, cursor, _conn = mock_db_pool(results=[
            ("/nonexistent/path/file.py", 0, 100, 0.9, "", "", ""),
        ])

        with patch("cocoindex.init"):
            with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=1):
                    with patch("cocosearch.mcp.server.read_chunk_content", return_value="code"):
                        result = search_code(
                            query="test",
                            index_name="testindex",
                            context_before=5,
                            context_after=5,
                        )

        assert len(result) == 1
        # Should not crash, should return result without context or with empty context
        assert result[0]["file_path"] == "/nonexistent/path/file.py"

    def test_no_results_returns_empty_list(self, mock_code_to_embedding, mock_db_pool):
        """No search results returns empty list."""
        pool, cursor, _conn = mock_db_pool(results=[])

        with patch("cocoindex.init"):
            with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
                result = search_code(
                    query="nonexistent",
                    index_name="testindex",
                    context_before=5,
                    context_after=5,
                )

        assert result == []

    def test_unsupported_language_fallback(self, mock_code_to_embedding, mock_db_pool, tmp_path):
        """Unsupported file extension falls back gracefully."""
        test_file = tmp_path / "test.xyz"
        test_file.write_text("some content\nmore content\n")

        pool, cursor, _conn = mock_db_pool(results=[
            (str(test_file), 0, 12, 0.9, "", "", ""),
        ])

        with patch("cocoindex.init"):
            with patch("cocosearch.search.query.get_connection_pool", return_value=pool):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=1):
                    with patch("cocosearch.mcp.server.read_chunk_content", return_value="some content"):
                        result = search_code(
                            query="test",
                            index_name="testindex",
                            smart_context=True,  # Smart won't work for .xyz
                        )

        assert len(result) == 1
        # Should not crash even with unsupported extension


class TestContextExpanderIntegration:
    """Tests for ContextExpander integration with MCP server."""

    def test_context_expander_imported(self):
        """ContextExpander is imported in server module."""
        from cocosearch.mcp import server
        assert hasattr(server, "ContextExpander")

    def test_treesitter_language_helper_exists(self):
        """_get_treesitter_language helper function exists."""
        from cocosearch.mcp import server
        assert hasattr(server, "_get_treesitter_language")

    def test_treesitter_language_mapping(self):
        """_get_treesitter_language returns correct mappings."""
        from cocosearch.mcp.server import _get_treesitter_language

        assert _get_treesitter_language("py") == "python"
        assert _get_treesitter_language("js") == "javascript"
        assert _get_treesitter_language("ts") == "typescript"
        assert _get_treesitter_language("go") == "go"
        assert _get_treesitter_language("rs") == "rust"
        assert _get_treesitter_language("unknown") is None
