"""Tests for context expansion in cocosearch.search.formatter module.

Tests grep-style context output with smart boundary detection.
"""

import io
import json
from unittest.mock import MagicMock, patch

from rich.console import Console

from cocosearch.search.formatter import (
    format_json,
    format_pretty,
    _get_tree_sitter_language,
)


class TestFormatJsonContext:
    """Tests for context expansion in format_json output."""

    def test_context_before_and_after_fields_appear(self, make_search_result):
        """JSON output should include context_before and context_after fields."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = (
            [(8, "# context line 1"), (9, "# context line 2")],  # before
            [(10, "def func():"), (11, "    pass")],  # match
            [(12, "# after line 1")],  # after
            False,  # is_bof
            False,  # is_eof
        )

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=10):
                with patch(
                    "cocosearch.search.formatter.read_chunk_content",
                    return_value="def func():\n    pass",
                ):
                    output = format_json(results, context_before=2, context_after=1)

        parsed = json.loads(output)
        item = parsed[0]

        assert "context_before" in item
        assert "context_after" in item
        assert "# context line 1" in item["context_before"]
        assert "# after line 1" in item["context_after"]

    def test_smart_expansion_uses_function_boundaries(self, make_search_result):
        """Smart expansion should call expander with smart=True."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = (
            [(5, "def calculate():"), (6, '    """Calculate value."""')],
            [(7, "    x = 1"), (8, "    return x")],
            [(9, "")],
            True,  # is_bof
            False,  # is_eof
        )

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=7):
                with patch(
                    "cocosearch.search.formatter.read_chunk_content",
                    return_value="x = 1",
                ):
                    format_json(results, smart_context=True)

        # Verify smart=True was passed (when no explicit context values)
        mock_expander.get_context_lines.assert_called()
        call_kwargs = mock_expander.get_context_lines.call_args[1]
        assert call_kwargs["smart"] is True

    def test_explicit_context_overrides_smart(self, make_search_result):
        """Explicit -A/-B values should override smart expansion."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = ([], [], [], False, False)

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=10):
                with patch(
                    "cocosearch.search.formatter.read_chunk_content",
                    return_value="code",
                ):
                    format_json(
                        results, context_before=5, context_after=3, smart_context=True
                    )

        # Verify smart=False when explicit context values provided
        call_kwargs = mock_expander.get_context_lines.call_args[1]
        assert call_kwargs["smart"] is False
        assert call_kwargs["context_before"] == 5
        assert call_kwargs["context_after"] == 3

    def test_no_smart_disables_boundary_detection(self, make_search_result):
        """--no-smart flag should disable smart expansion."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = ([], [], [], False, False)

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=10):
                with patch(
                    "cocosearch.search.formatter.read_chunk_content",
                    return_value="code",
                ):
                    format_json(
                        results, smart_context=False, context_before=3, context_after=3
                    )

        call_kwargs = mock_expander.get_context_lines.call_args[1]
        assert call_kwargs["smart"] is False

    def test_context_as_newline_separated_strings(self, make_search_result):
        """Context should be formatted as newline-separated strings."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = (
            [(1, "line1"), (2, "line2"), (3, "line3")],  # before
            [(4, "match")],  # match
            [(5, "after1"), (6, "after2")],  # after
            True,  # is_bof
            False,  # is_eof
        )

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=4):
                with patch(
                    "cocosearch.search.formatter.read_chunk_content",
                    return_value="match",
                ):
                    output = format_json(results, context_before=3, context_after=2)

        parsed = json.loads(output)
        item = parsed[0]

        # Should be newline-separated
        assert item["context_before"] == "line1\nline2\nline3"
        assert item["context_after"] == "after1\nafter2"


class TestFormatPrettyContext:
    """Tests for context expansion in format_pretty output."""

    def _make_console(self) -> tuple[Console, io.StringIO]:
        """Create a Rich Console that captures plain text (no ANSI codes)."""
        output = io.StringIO()
        console = Console(file=output, no_color=True, width=100)
        return console, output

    def test_grep_style_markers_context_colon(self, make_search_result):
        """Context lines should use colon (:) marker like grep."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]
        console, output = self._make_console()

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = (
            [(8, "# before context")],  # before
            [(9, "matched line")],  # match
            [(10, "# after context")],  # after
            False,
            False,
        )

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=9):
                format_pretty(
                    results, context_before=1, context_after=1, console=console
                )

        captured = output.getvalue()
        # Context lines use colon marker
        assert "8: # before context" in captured
        assert "10: # after context" in captured

    def test_grep_style_markers_match_angle(self, make_search_result):
        """Match lines should use angle bracket (>) marker like grep."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]
        console, output = self._make_console()

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = (
            [(8, "before")],
            [(9, "matched line"), (10, "also matched")],  # multiple match lines
            [(11, "after")],
            False,
            False,
        )

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=9):
                format_pretty(
                    results, context_before=1, context_after=1, console=console
                )

        captured = output.getvalue()
        # Match lines use > marker
        assert "9> matched line" in captured
        assert "10> also matched" in captured

    def test_line_numbers_shown(self, make_search_result):
        """Line numbers should be shown for all lines."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]
        console, output = self._make_console()

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = (
            [(100, "context")],
            [(101, "match")],
            [(102, "after")],
            False,
            False,
        )

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=101):
                format_pretty(
                    results, context_before=1, context_after=1, console=console
                )

        captured = output.getvalue()
        assert "100:" in captured
        assert "101>" in captured
        assert "102:" in captured

    def test_bof_marker_at_file_start(self, make_search_result):
        """BOF marker should appear when context starts at file beginning."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]
        console, output = self._make_console()

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = (
            [(1, "first line")],  # before - at file start
            [(2, "match")],
            [],
            True,  # is_bof
            False,
        )

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=2):
                format_pretty(results, context_before=5, console=console)

        captured = output.getvalue()
        assert "[Beginning of file]" in captured

    def test_eof_marker_at_file_end(self, make_search_result):
        """EOF marker should appear when context ends at file end."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]
        console, output = self._make_console()

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = (
            [],
            [(99, "match")],
            [(100, "last line")],  # at file end
            False,
            True,  # is_eof
        )

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=99):
                format_pretty(results, context_after=5, console=console)

        captured = output.getvalue()
        assert "[End of file]" in captured

    def test_no_bof_marker_when_not_at_start(self, make_search_result):
        """BOF marker should not appear when context doesn't start at file beginning."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]
        console, output = self._make_console()

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = (
            [(50, "context")],
            [(51, "match")],
            [],
            False,  # is_bof = False
            False,
        )

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=51):
                format_pretty(results, context_before=1, console=console)

        captured = output.getvalue()
        assert "[Beginning of file]" not in captured


class TestBackwardCompatibility:
    """Tests for backward compatibility with legacy parameters."""

    def test_context_lines_parameter_still_works(self, make_search_result):
        """Legacy context_lines parameter should still work for format_json."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = (
            [(1, "before")],
            [(2, "match")],
            [(3, "after")],
            False,
            False,
        )

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=2):
                with patch(
                    "cocosearch.search.formatter.read_chunk_content",
                    return_value="match",
                ):
                    format_json(results, context_lines=5)

        call_kwargs = mock_expander.get_context_lines.call_args[1]
        assert call_kwargs["context_before"] == 5
        assert call_kwargs["context_after"] == 5

    def test_format_calls_without_context_params(self, make_search_result):
        """Calls without context params should work (smart context by default)."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = ([], [], [], False, False)

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
                with patch(
                    "cocosearch.search.formatter.read_chunk_content",
                    return_value="code",
                ):
                    # Should not raise
                    output = format_json(results)

        parsed = json.loads(output)
        assert len(parsed) == 1

    def test_format_pretty_without_context_params(self, make_search_result):
        """format_pretty without context params should use smart expansion."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]
        console, output_buffer = (
            Console(file=io.StringIO(), no_color=True, width=100),
            io.StringIO(),
        )
        console = Console(file=output_buffer, no_color=True, width=100)

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = (
            [(1, "context")],
            [(2, "match")],
            [],
            True,
            False,
        )

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=2):
                format_pretty(results, console=console)

        # Verify smart=True by default
        call_kwargs = mock_expander.get_context_lines.call_args[1]
        assert call_kwargs["smart"] is True


class TestTreeSitterLanguageHelper:
    """Tests for _get_tree_sitter_language helper."""

    def test_python_extensions(self):
        """Python files should map to 'python' language."""
        assert _get_tree_sitter_language("/test/file.py") == "python"
        assert _get_tree_sitter_language("/test/file.pyw") == "python"
        assert _get_tree_sitter_language("/test/file.pyi") == "python"

    def test_javascript_extensions(self):
        """JavaScript files should map to 'javascript' language."""
        assert _get_tree_sitter_language("/test/file.js") == "javascript"
        assert _get_tree_sitter_language("/test/file.jsx") == "javascript"
        assert _get_tree_sitter_language("/test/file.mjs") == "javascript"
        assert _get_tree_sitter_language("/test/file.cjs") == "javascript"

    def test_typescript_extensions(self):
        """TypeScript files should map to 'typescript' language."""
        assert _get_tree_sitter_language("/test/file.ts") == "typescript"
        assert _get_tree_sitter_language("/test/file.tsx") == "typescript"
        assert _get_tree_sitter_language("/test/file.mts") == "typescript"
        assert _get_tree_sitter_language("/test/file.cts") == "typescript"

    def test_go_extension(self):
        """Go files should map to 'go' language."""
        assert _get_tree_sitter_language("/test/file.go") == "go"

    def test_rust_extension(self):
        """Rust files should map to 'rust' language."""
        assert _get_tree_sitter_language("/test/file.rs") == "rust"

    def test_unsupported_extension_returns_none(self):
        """Unsupported extensions should return None."""
        assert _get_tree_sitter_language("/test/file.java") is None
        assert _get_tree_sitter_language("/test/file.rb") is None
        assert _get_tree_sitter_language("/test/file.txt") is None


class TestFormatterCacheManagement:
    """Tests for expander cache management in formatters."""

    def test_json_formatter_clears_cache(self, make_search_result):
        """format_json should clear expander cache after processing."""
        results = [make_search_result(filename="/test/file.py")]

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = ([], [], [], False, False)

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
                with patch(
                    "cocosearch.search.formatter.read_chunk_content",
                    return_value="code",
                ):
                    format_json(results, context_before=3)

        mock_expander.clear_cache.assert_called_once()

    def test_pretty_formatter_clears_cache(self, make_search_result):
        """format_pretty should clear expander cache after processing."""
        results = [make_search_result(filename="/test/file.py")]
        console = Console(file=io.StringIO(), no_color=True)

        mock_expander = MagicMock()
        mock_expander.get_context_lines.return_value = ([], [], [], False, False)

        with patch(
            "cocosearch.search.formatter.ContextExpander", return_value=mock_expander
        ):
            with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
                format_pretty(results, context_before=3, console=console)

        mock_expander.clear_cache.assert_called_once()
