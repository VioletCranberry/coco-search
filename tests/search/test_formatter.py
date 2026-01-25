"""Tests for cocosearch.search.formatter module.

Tests JSON and pretty output formatters with mocked file operations.
"""

import io
import json
from unittest.mock import patch

import pytest
from rich.console import Console

from cocosearch.search.formatter import format_json, format_pretty, EXTENSION_LANG_MAP


class TestFormatJson:
    """Tests for format_json function."""

    def test_returns_valid_json(self, make_search_result):
        """Output should be parseable JSON."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(results)

        # Should parse without error
        parsed = json.loads(output)
        assert isinstance(parsed, list)
        assert len(parsed) == 1

    def test_includes_file_info(self, make_search_result):
        """JSON should contain file_path, start_line, end_line, score."""
        results = [make_search_result(filename="/test/file.py", score=0.85)]

        with patch("cocosearch.search.formatter.byte_to_line", side_effect=[10, 20]):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(results)

        parsed = json.loads(output)
        item = parsed[0]

        assert item["file_path"] == "/test/file.py"
        assert item["start_line"] == 10
        assert item["end_line"] == 20
        assert item["score"] == 0.85

    def test_includes_content(self, make_search_result):
        """JSON should contain code content when include_content is True."""
        results = [make_search_result()]
        code_content = "def hello():\n    return 'world'"

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value=code_content):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(results, include_content=True)

        parsed = json.loads(output)
        assert parsed[0]["content"] == code_content

    def test_excludes_content_when_disabled(self, make_search_result):
        """JSON should not contain content when include_content is False."""
        results = [make_search_result()]

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                output = format_json(results, include_content=False)

        parsed = json.loads(output)
        assert "content" not in parsed[0]

    def test_includes_context_lines(self, make_search_result):
        """JSON should contain context_before and context_after."""
        results = [make_search_result()]
        before = ["# Line before 1", "# Line before 2"]
        after = ["# Line after 1"]

        with patch("cocosearch.search.formatter.byte_to_line", return_value=5):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=(before, after)):
                    output = format_json(results, context_lines=2)

        parsed = json.loads(output)
        assert parsed[0]["context_before"] == before
        assert parsed[0]["context_after"] == after

    def test_no_context_when_zero(self, make_search_result):
        """JSON should not contain context when context_lines is 0."""
        results = [make_search_result()]

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                output = format_json(results, context_lines=0)

        parsed = json.loads(output)
        assert "context_before" not in parsed[0]
        assert "context_after" not in parsed[0]

    def test_multiple_results(self, sample_search_results):
        """Should handle multiple results."""
        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(sample_search_results)

        parsed = json.loads(output)
        assert len(parsed) == 3

    def test_empty_results(self):
        """Should handle empty results list."""
        output = format_json([])
        parsed = json.loads(output)
        assert parsed == []

    def test_score_rounding(self, make_search_result):
        """Score should be rounded to 4 decimal places."""
        results = [make_search_result(score=0.85678901234)]

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                with patch("cocosearch.search.formatter.get_context_lines", return_value=([], [])):
                    output = format_json(results)

        parsed = json.loads(output)
        assert parsed[0]["score"] == 0.8568  # Rounded to 4 decimals


class TestFormatPretty:
    """Tests for format_pretty function."""

    def _make_console(self) -> tuple[Console, io.StringIO]:
        """Create a Rich Console that captures output to a StringIO."""
        output = io.StringIO()
        console = Console(file=output, force_terminal=True, width=100)
        return console, output

    def test_outputs_to_console(self, make_search_result, tmp_path):
        """Should write to Rich console without error."""
        results = [make_search_result()]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="def hello(): pass"):
                # format_pretty should not raise
                format_pretty(results, console=console)

        # Should have written something
        assert len(output.getvalue()) > 0

    def test_shows_filename(self, make_search_result, tmp_path):
        """Output should contain filename."""
        # Create a real file so os.path.exists returns True
        test_file = tmp_path / "testfile.py"
        test_file.write_text("code content")

        results = [make_search_result(filename=str(test_file))]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        # Should contain the filename (may be relative path)
        assert "testfile.py" in captured

    def test_shows_score(self, make_search_result):
        """Output should contain similarity score."""
        results = [make_search_result(score=0.85)]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        assert "0.85" in captured

    def test_shows_line_numbers(self, make_search_result):
        """Output should show line range."""
        results = [make_search_result()]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", side_effect=[10, 25]):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        # Should show line range
        assert "10" in captured
        assert "25" in captured

    def test_no_results_message(self):
        """Should show 'No results found' for empty results."""
        console, output = self._make_console()

        format_pretty([], console=console)

        captured = output.getvalue()
        assert "No results found" in captured

    def test_groups_by_file(self, make_search_result):
        """Results from same file should be grouped together."""
        results = [
            make_search_result(filename="/project/auth.py", start_byte=0, end_byte=50, score=0.9),
            make_search_result(filename="/project/auth.py", start_byte=100, end_byte=150, score=0.7),
        ]
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                format_pretty(results, console=console)

        captured = output.getvalue()
        # File path should appear (grouped, not repeated for each result)
        assert "auth.py" in captured

    def test_result_count_header(self, sample_search_results):
        """Should show total result count."""
        console, output = self._make_console()

        with patch("cocosearch.search.formatter.byte_to_line", return_value=1):
            with patch("cocosearch.search.formatter.read_chunk_content", return_value="code"):
                format_pretty(sample_search_results, console=console)

        captured = output.getvalue()
        # Check for key parts (ANSI codes may break exact string matching)
        assert "Found" in captured
        assert "3" in captured
        assert "results" in captured


class TestExtensionLangMap:
    """Tests for EXTENSION_LANG_MAP constant."""

    def test_python_mapping(self):
        """Python extensions should map to 'python'."""
        assert EXTENSION_LANG_MAP["py"] == "python"
        assert EXTENSION_LANG_MAP["pyw"] == "python"
        assert EXTENSION_LANG_MAP["pyi"] == "python"

    def test_javascript_mapping(self):
        """JavaScript extensions should map to 'javascript'."""
        assert EXTENSION_LANG_MAP["js"] == "javascript"
        assert EXTENSION_LANG_MAP["mjs"] == "javascript"

    def test_typescript_mapping(self):
        """TypeScript extensions should map to 'typescript'."""
        assert EXTENSION_LANG_MAP["ts"] == "typescript"
        assert EXTENSION_LANG_MAP["tsx"] == "typescript"

    def test_common_extensions_present(self):
        """Common file extensions should be present."""
        expected = ["py", "js", "ts", "go", "rs", "java", "rb", "cpp", "c"]
        for ext in expected:
            assert ext in EXTENSION_LANG_MAP
