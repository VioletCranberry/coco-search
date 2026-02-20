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

    def test_no_grammar_for_unknown_extension(self):
        """Returns ('no_grammar', None) for extensions not in LANGUAGE_MAP."""
        status, msg = detect_parse_status("FROM ubuntu:latest", "dockerfile")
        assert status == "no_grammar"
        assert msg is None

    def test_no_grammar_for_markdown(self):
        """Markdown has no tree-sitter grammar — returns no_grammar."""
        status, msg = detect_parse_status("# Hello\nSome text", "md")
        assert status == "no_grammar"
        assert msg is None

    def test_no_grammar_for_empty_extension(self):
        """Returns ('no_grammar', None) for empty extension."""
        status, msg = detect_parse_status("some content", "")
        assert status == "no_grammar"
        assert msg is None

    def test_no_grammar_for_unknown_lang(self):
        """Returns ('no_grammar', None) for completely unknown extensions."""
        status, msg = detect_parse_status("some content", "zzz")
        assert status == "no_grammar"
        assert msg is None

    def test_ok_for_valid_bash(self):
        """Returns ('ok', None) for valid Bash script."""
        status, msg = detect_parse_status("#!/bin/bash\necho hello\n", "sh")
        assert status == "ok"
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


class TestSkipParseExtensions:
    """Tests for _SKIP_PARSE_EXTENSIONS exclusion set."""

    def test_markdown_in_skip_set(self):
        from cocosearch.indexer.parse_tracking import _SKIP_PARSE_EXTENSIONS

        assert "md" in _SKIP_PARSE_EXTENSIONS
        assert "mdx" in _SKIP_PARSE_EXTENSIONS

    def test_text_formats_in_skip_set(self):
        from cocosearch.indexer.parse_tracking import _SKIP_PARSE_EXTENSIONS

        for ext in ("txt", "json", "yaml", "yml", "toml", "xml", "csv"):
            assert ext in _SKIP_PARSE_EXTENSIONS, f"{ext} should be skipped"

    def test_gotmpl_in_skip_set(self):
        """gotmpl has no tree-sitter grammar and should be skipped."""
        from cocosearch.indexer.parse_tracking import _SKIP_PARSE_EXTENSIONS

        assert "gotmpl" in _SKIP_PARSE_EXTENSIONS

    def test_dockerfile_in_skip_set(self):
        """dockerfile has no tree-sitter grammar and should be skipped."""
        from cocosearch.indexer.parse_tracking import _SKIP_PARSE_EXTENSIONS

        assert "dockerfile" in _SKIP_PARSE_EXTENSIONS

    def test_tpl_in_skip_set(self):
        """tpl has no tree-sitter grammar and should be skipped."""
        from cocosearch.indexer.parse_tracking import _SKIP_PARSE_EXTENSIONS

        assert "tpl" in _SKIP_PARSE_EXTENSIONS

    def test_code_extensions_not_in_skip_set(self):
        from cocosearch.indexer.parse_tracking import _SKIP_PARSE_EXTENSIONS

        for ext in ("py", "js", "ts", "go", "rs", "sh"):
            assert ext not in _SKIP_PARSE_EXTENSIONS, f"{ext} should NOT be skipped"


class TestGrammarNamesSkip:
    """Tests for _GRAMMAR_NAMES exclusion set."""

    def test_grammar_names_skipped_in_parse_tracking(self):
        """Grammar handler names are included in _GRAMMAR_NAMES skip set."""
        from cocosearch.indexer.parse_tracking import _GRAMMAR_NAMES

        # These are the registered grammar handlers
        for name in ("docker-compose", "github-actions", "gitlab-ci"):
            assert name in _GRAMMAR_NAMES, f"{name} should be in _GRAMMAR_NAMES"

    def test_code_extensions_not_in_grammar_names(self):
        """Regular code extensions are not in _GRAMMAR_NAMES."""
        from cocosearch.indexer.parse_tracking import _GRAMMAR_NAMES

        for ext in ("py", "js", "ts", "go", "yaml"):
            assert ext not in _GRAMMAR_NAMES, f"{ext} should NOT be in _GRAMMAR_NAMES"
