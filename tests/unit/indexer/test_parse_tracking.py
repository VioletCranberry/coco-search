"""Tests for parse failure tracking module."""

from cocosearch.indexer.parse_tracking import detect_parse_status, _collect_error_lines


class TestDetectParseStatus:
    """Tests for detect_parse_status function."""

    def test_ok_for_valid_python(self):
        """Returns ('ok', None) for syntactically valid Python."""
        status, msg = detect_parse_status("def foo():\n    pass\n", "py")
        assert status == "ok"
        assert msg is None

    def test_ok_for_valid_javascript(self):
        """Returns ('ok', None) for valid JavaScript."""
        status, msg = detect_parse_status("function foo() { return 1; }", "js")
        assert status == "ok"
        assert msg is None

    def test_ok_for_valid_typescript(self):
        """Returns ('ok', None) for valid TypeScript."""
        status, msg = detect_parse_status("const x: number = 1;", "ts")
        assert status == "ok"
        assert msg is None

    def test_partial_for_broken_python(self):
        """Returns ('partial', error_msg) for Python with syntax errors."""
        status, msg = detect_parse_status("def foo(:\n    pass", "py")
        assert status == "partial"
        assert msg is not None
        assert "ERROR" in msg

    def test_partial_includes_line_numbers(self):
        """Error message includes line numbers of ERROR nodes."""
        status, msg = detect_parse_status("def foo(:\n    pass", "py")
        assert status == "partial"
        # Should contain at least one line number
        assert any(c.isdigit() for c in msg)

    def test_unsupported_for_unknown_extension(self):
        """Returns ('unsupported', None) for extensions not in LANGUAGE_MAP."""
        status, msg = detect_parse_status("FROM ubuntu:latest", "dockerfile")
        assert status == "unsupported"
        assert msg is None

    def test_unsupported_for_empty_extension(self):
        """Returns ('unsupported', None) for empty extension."""
        status, msg = detect_parse_status("some content", "")
        assert status == "unsupported"
        assert msg is None

    def test_unsupported_for_unknown_lang(self):
        """Returns ('unsupported', None) for completely unknown extensions."""
        status, msg = detect_parse_status("some content", "zzz")
        assert status == "unsupported"
        assert msg is None

    def test_ok_for_valid_go(self):
        """Returns ('ok', None) for valid Go code."""
        status, msg = detect_parse_status("package main\n\nfunc main() {}\n", "go")
        assert status == "ok"
        assert msg is None

    def test_ok_for_valid_rust(self):
        """Returns ('ok', None) for valid Rust code."""
        status, msg = detect_parse_status("fn main() {}\n", "rs")
        assert status == "ok"
        assert msg is None

    def test_handles_empty_content(self):
        """Does not crash on empty string input."""
        status, msg = detect_parse_status("", "py")
        # Empty content should parse ok (empty tree has no errors)
        assert status == "ok"
        assert msg is None


class TestCollectErrorLines:
    """Tests for _collect_error_lines helper."""

    def test_returns_empty_for_valid_tree(self):
        """Returns empty list when tree has no error nodes."""
        from tree_sitter_language_pack import get_parser

        parser = get_parser("python")
        tree = parser.parse(b"x = 1")
        lines = _collect_error_lines(tree.root_node)
        assert lines == []

    def test_returns_line_numbers_for_errors(self):
        """Returns line numbers of ERROR nodes."""
        from tree_sitter_language_pack import get_parser

        parser = get_parser("python")
        tree = parser.parse(b"def foo(:\n    pass")
        lines = _collect_error_lines(tree.root_node)
        assert len(lines) > 0
        # All lines should be positive integers (1-indexed)
        assert all(isinstance(line, int) and line >= 1 for line in lines)
