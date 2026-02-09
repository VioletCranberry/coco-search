"""Unit tests for symbol display in search result formatters.

Tests that symbol metadata (symbol_type, symbol_name, symbol_signature)
displays correctly in both JSON and pretty output formats.
"""

import json
from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from cocosearch.search.formatter import format_json, format_pretty
from cocosearch.search.query import SearchResult


@pytest.fixture
def mock_result_with_symbol():
    """Create a SearchResult with symbol metadata."""
    return SearchResult(
        filename="/path/to/file.py",
        start_byte=100,
        end_byte=200,
        score=0.85,
        block_type="",
        hierarchy="",
        language_id="",
        symbol_type="method",
        symbol_name="UserService.get_user",
        symbol_signature="def get_user(self, user_id: str)",
    )


@pytest.fixture
def mock_result_without_symbol():
    """Create a SearchResult without symbol metadata."""
    return SearchResult(
        filename="/path/to/file.py",
        start_byte=100,
        end_byte=200,
        score=0.75,
        block_type="",
        hierarchy="",
        language_id="",
    )


@pytest.fixture
def mock_result_with_long_signature():
    """Create a SearchResult with a long symbol signature for truncation testing."""
    return SearchResult(
        filename="/path/to/file.py",
        start_byte=100,
        end_byte=200,
        score=0.90,
        block_type="",
        hierarchy="",
        language_id="",
        symbol_type="function",
        symbol_name="process_data",
        symbol_signature="def process_data(self, items: list[str], options: dict[str, Any], callback: Callable)",
    )


class TestFormatJsonSymbols:
    """Tests for symbol display in JSON output."""

    @patch("cocosearch.search.formatter.byte_to_line")
    @patch("cocosearch.search.formatter.read_chunk_content")
    def test_json_includes_symbol_fields(
        self, mock_content, mock_byte_to_line, mock_result_with_symbol
    ):
        """Verify JSON output includes symbol_type, symbol_name, symbol_signature."""
        mock_byte_to_line.return_value = 10
        mock_content.return_value = "def get_user(self, user_id: str):"

        output = format_json(
            [mock_result_with_symbol],
            include_content=False,
            smart_context=False,
        )
        data = json.loads(output)

        assert len(data) == 1
        assert data[0]["symbol_type"] == "method"
        assert data[0]["symbol_name"] == "UserService.get_user"
        assert data[0]["symbol_signature"] == "def get_user(self, user_id: str)"

    @patch("cocosearch.search.formatter.byte_to_line")
    @patch("cocosearch.search.formatter.read_chunk_content")
    def test_json_omits_symbol_fields_when_none(
        self, mock_content, mock_byte_to_line, mock_result_without_symbol
    ):
        """Verify JSON output omits symbol fields when they are None."""
        mock_byte_to_line.return_value = 10
        mock_content.return_value = "some code"

        output = format_json(
            [mock_result_without_symbol],
            include_content=False,
            smart_context=False,
        )
        data = json.loads(output)

        assert len(data) == 1
        assert "symbol_type" not in data[0]
        assert "symbol_name" not in data[0]
        assert "symbol_signature" not in data[0]

    @patch("cocosearch.search.formatter.byte_to_line")
    @patch("cocosearch.search.formatter.read_chunk_content")
    def test_json_mixed_results(
        self,
        mock_content,
        mock_byte_to_line,
        mock_result_with_symbol,
        mock_result_without_symbol,
    ):
        """Verify JSON output handles mixed results (some with symbols, some without)."""
        mock_byte_to_line.return_value = 10
        mock_content.return_value = "code"

        output = format_json(
            [mock_result_with_symbol, mock_result_without_symbol],
            include_content=False,
            smart_context=False,
        )
        data = json.loads(output)

        assert len(data) == 2
        # First result has symbol fields
        assert data[0]["symbol_name"] == "UserService.get_user"
        # Second result omits symbol fields
        assert "symbol_name" not in data[1]


class TestFormatPrettySymbols:
    """Tests for symbol display in pretty output."""

    @patch("cocosearch.search.formatter.byte_to_line")
    @patch("cocosearch.search.formatter.read_chunk_content")
    def test_pretty_displays_symbol_info(
        self, mock_content, mock_byte_to_line, mock_result_with_symbol
    ):
        """Verify pretty output includes symbol type and qualified name."""
        mock_byte_to_line.return_value = 10
        mock_content.return_value = "def get_user(self, user_id: str):"

        # Capture output with a string buffer
        output_buffer = StringIO()
        console = Console(file=output_buffer, force_terminal=False, no_color=True)

        format_pretty(
            [mock_result_with_symbol],
            smart_context=False,
            console=console,
        )

        output = output_buffer.getvalue()
        # Check that symbol info is displayed
        assert "[method] UserService.get_user" in output
        assert "def get_user(self, user_id: str)" in output

    @patch("cocosearch.search.formatter.byte_to_line")
    @patch("cocosearch.search.formatter.read_chunk_content")
    def test_pretty_handles_missing_symbol_info(
        self, mock_content, mock_byte_to_line, mock_result_without_symbol
    ):
        """Verify pretty output handles results without symbol metadata."""
        mock_byte_to_line.return_value = 10
        mock_content.return_value = "some code"

        # Capture output with a string buffer
        output_buffer = StringIO()
        console = Console(file=output_buffer, force_terminal=False, no_color=True)

        # Should not raise exception
        format_pretty(
            [mock_result_without_symbol],
            smart_context=False,
            console=console,
        )

        output = output_buffer.getvalue()
        # Should NOT contain symbol display
        assert "[method]" not in output
        assert "[function]" not in output
        # Should still show basic info
        assert "0.75" in output  # score

    @patch("cocosearch.search.formatter.byte_to_line")
    @patch("cocosearch.search.formatter.read_chunk_content")
    def test_pretty_truncates_long_signature(
        self, mock_content, mock_byte_to_line, mock_result_with_long_signature
    ):
        """Verify pretty output truncates signatures longer than 60 chars."""
        mock_byte_to_line.return_value = 10
        mock_content.return_value = "code"

        output_buffer = StringIO()
        console = Console(file=output_buffer, force_terminal=False, no_color=True)

        format_pretty(
            [mock_result_with_long_signature],
            smart_context=False,
            console=console,
        )

        output = output_buffer.getvalue()
        # Check that symbol name is displayed
        assert "[function] process_data" in output
        # Check that signature is truncated (original is 90+ chars)
        assert "..." in output
        # Full signature should NOT be in output
        assert "Callable)" not in output

    @patch("cocosearch.search.formatter.byte_to_line")
    @patch("cocosearch.search.formatter.read_chunk_content")
    def test_pretty_escapes_brackets_in_symbol_display(
        self, mock_content, mock_byte_to_line
    ):
        """Verify brackets in symbol type are escaped for Rich markup."""
        result = SearchResult(
            filename="/path/to/file.py",
            start_byte=0,
            end_byte=100,
            score=0.8,
            symbol_type="class",
            symbol_name="MyClass",
            symbol_signature="class MyClass:",
        )
        mock_byte_to_line.return_value = 1
        mock_content.return_value = "class MyClass:"

        output_buffer = StringIO()
        console = Console(file=output_buffer, force_terminal=False, no_color=True)

        # Should not raise exception due to unescaped brackets
        format_pretty(
            [result],
            smart_context=False,
            console=console,
        )

        output = output_buffer.getvalue()
        # The brackets should appear in output (escaped for Rich, displayed as-is)
        assert "[class] MyClass" in output
