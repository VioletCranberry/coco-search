"""Tests for cocosearch.search.utils module.

Tests utility functions for byte offset to line conversion,
chunk content reading, and context line extraction.
"""

import pytest

from cocosearch.search.utils import byte_to_line, read_chunk_content, get_context_lines


class TestByteToLine:
    """Tests for byte_to_line function."""

    def test_start_of_file(self, tmp_path):
        """Byte 0 should return line 1."""
        test_file = tmp_path / "test.py"
        test_file.write_text("first line\nsecond line\n")

        result = byte_to_line(str(test_file), 0)
        assert result == 1

    def test_after_newline(self, tmp_path):
        """Byte after first newline should return line 2."""
        test_file = tmp_path / "test.py"
        content = "first line\nsecond line\n"
        test_file.write_text(content)

        # Byte offset right after first newline
        newline_pos = content.index("\n") + 1
        result = byte_to_line(str(test_file), newline_pos)
        assert result == 2

    def test_middle_of_line(self, tmp_path):
        """Byte in middle of line should return that line number."""
        test_file = tmp_path / "test.py"
        content = "first line\nsecond line\nthird line\n"
        test_file.write_text(content)

        # Find position in middle of second line
        second_line_start = content.index("\n") + 1
        middle_of_second = second_line_start + 5
        result = byte_to_line(str(test_file), middle_of_second)
        assert result == 2

    def test_file_not_found_returns_zero(self):
        """Non-existent file should return 0."""
        result = byte_to_line("/nonexistent/path/file.py", 0)
        assert result == 0

    def test_multiline_content(self, tmp_path):
        """Should correctly count lines in multiline content."""
        test_file = tmp_path / "test.py"
        content = "line 1\nline 2\nline 3\nline 4\nline 5\n"
        test_file.write_text(content)

        # Find position after 4 newlines (should be line 5)
        pos = 0
        for i in range(4):
            pos = content.index("\n", pos) + 1
        result = byte_to_line(str(test_file), pos)
        assert result == 5


class TestReadChunkContent:
    """Tests for read_chunk_content function."""

    def test_reads_correct_bytes(self, tmp_path):
        """Should return content between start_byte and end_byte."""
        test_file = tmp_path / "test.py"
        content = "def hello():\n    return 'world'\n"
        test_file.write_text(content)

        # Read first 12 bytes ("def hello():")
        result = read_chunk_content(str(test_file), 0, 12)
        assert result == "def hello():"

    def test_reads_middle_section(self, tmp_path):
        """Should read content from middle of file."""
        test_file = tmp_path / "test.py"
        content = "prefix_content_suffix"
        test_file.write_text(content)

        # Read "content" (bytes 7-14)
        result = read_chunk_content(str(test_file), 7, 14)
        assert result == "content"

    def test_handles_utf8(self, tmp_path):
        """Should correctly decode UTF-8 content."""
        test_file = tmp_path / "test.py"
        content = "# Unicode: \u00e9\u00e8\u00ea \u00e0\u00e2\u00e4\n"
        test_file.write_bytes(content.encode("utf-8"))

        result = read_chunk_content(str(test_file), 0, len(content.encode("utf-8")))
        assert result == content

    def test_file_not_found_returns_empty(self):
        """Non-existent file should return empty string."""
        result = read_chunk_content("/nonexistent/path/file.py", 0, 100)
        assert result == ""

    def test_full_file_read(self, tmp_path):
        """Should read entire file when given full range."""
        test_file = tmp_path / "test.py"
        content = "complete file content"
        test_file.write_text(content)

        result = read_chunk_content(str(test_file), 0, len(content))
        assert result == content


class TestGetContextLines:
    """Tests for get_context_lines function."""

    def test_returns_lines_before_and_after(self, tmp_path):
        """Should get context lines around chunk."""
        test_file = tmp_path / "test.py"
        lines = [f"line {i}" for i in range(1, 11)]  # line 1 through line 10
        test_file.write_text("\n".join(lines) + "\n")

        # Get context around lines 5-6 (with default 5 context lines)
        before, after = get_context_lines(str(test_file), 5, 6, context=2)

        # Before: lines 3-4
        assert before == ["line 3", "line 4"]
        # After: lines 7-8
        assert after == ["line 7", "line 8"]

    def test_handles_file_start(self, tmp_path):
        """No lines before when chunk is at file start."""
        test_file = tmp_path / "test.py"
        lines = [f"line {i}" for i in range(1, 6)]
        test_file.write_text("\n".join(lines) + "\n")

        # Get context around lines 1-2
        before, after = get_context_lines(str(test_file), 1, 2, context=2)

        # Before: empty (no lines before line 1)
        assert before == []
        # After: lines 3-4
        assert after == ["line 3", "line 4"]

    def test_handles_file_end(self, tmp_path):
        """No lines after when chunk is at file end."""
        test_file = tmp_path / "test.py"
        lines = [f"line {i}" for i in range(1, 6)]
        test_file.write_text("\n".join(lines) + "\n")

        # Get context around lines 4-5 (end of file)
        before, after = get_context_lines(str(test_file), 4, 5, context=2)

        # Before: lines 2-3
        assert before == ["line 2", "line 3"]
        # After: empty (no lines after line 5)
        assert after == []

    def test_file_not_found_returns_empty(self):
        """Non-existent file should return empty lists."""
        before, after = get_context_lines("/nonexistent/file.py", 1, 5, context=2)
        assert before == []
        assert after == []

    def test_strips_line_endings(self, tmp_path):
        """Should strip newline characters from context lines."""
        test_file = tmp_path / "test.py"
        test_file.write_text("line 1\r\nline 2\nline 3\r\nline 4\n")

        before, after = get_context_lines(str(test_file), 2, 3, context=1)

        assert before == ["line 1"]
        assert after == ["line 4"]

    def test_default_context_size(self, tmp_path):
        """Default context should be 5 lines."""
        test_file = tmp_path / "test.py"
        lines = [f"line {i}" for i in range(1, 16)]  # 15 lines
        test_file.write_text("\n".join(lines) + "\n")

        # Get context around lines 8-9 with default context
        before, after = get_context_lines(str(test_file), 8, 9)

        # Default is 5 lines
        assert len(before) == 5  # lines 3-7
        assert len(after) == 5  # lines 10-14
