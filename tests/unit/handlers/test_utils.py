"""Tests for shared handler utilities."""

import re

from cocosearch.handlers.utils import strip_leading_comments

# Common comment patterns used across handlers
_HASH_COMMENT = re.compile(r"^\s*#.*$", re.MULTILINE)
_SLASH_COMMENT = re.compile(r"^\s*//.*$", re.MULTILINE)
_DOC_COMMENT = re.compile(r"^\s*(?:/\*|\*).*$", re.MULTILINE)


class TestStripLeadingComments:
    """Tests for strip_leading_comments()."""

    def test_no_comments(self):
        text = "def foo():\n    pass"
        assert strip_leading_comments(text, [_HASH_COMMENT]) == text

    def test_all_comments(self):
        text = "# comment 1\n# comment 2\n"
        assert strip_leading_comments(text, [_HASH_COMMENT]) == ""

    def test_comments_then_code(self):
        text = "# header comment\n# license\ndef foo():\n    pass"
        assert strip_leading_comments(text, [_HASH_COMMENT]) == "def foo():\n    pass"

    def test_blank_lines_between_comments_and_code(self):
        text = "# comment\n\n\ndef foo():\n    pass"
        assert strip_leading_comments(text, [_HASH_COMMENT]) == "def foo():\n    pass"

    def test_leading_whitespace_stripped(self):
        text = "\n\n  # comment\ncode_here"
        assert strip_leading_comments(text, [_HASH_COMMENT]) == "code_here"

    def test_multiple_comment_patterns(self):
        text = "// line comment\n* doc line\nclass Foo"
        result = strip_leading_comments(text, [_SLASH_COMMENT, _DOC_COMMENT])
        assert result == "class Foo"

    def test_skip_strings(self):
        text = "---\n# comment\napiVersion: v1"
        result = strip_leading_comments(text, [_HASH_COMMENT], skip_strings=["---"])
        assert result == "apiVersion: v1"

    def test_skip_strings_only(self):
        text = "---\n---\n"
        result = strip_leading_comments(text, [], skip_strings=["---"])
        assert result == ""

    def test_empty_text(self):
        assert strip_leading_comments("", [_HASH_COMMENT]) == ""

    def test_whitespace_only(self):
        assert strip_leading_comments("   \n\n  ", [_HASH_COMMENT]) == ""

    def test_no_patterns(self):
        text = "# this stays\ncode"
        assert strip_leading_comments(text, []) == "# this stays\ncode"

    def test_indented_comment(self):
        text = "  # indented comment\ncode"
        assert strip_leading_comments(text, [_HASH_COMMENT]) == "code"

    def test_mixed_comment_types(self):
        """Test Scala-style: // line comments followed by /* doc comments."""
        text = "// Copyright\n/* Class doc */\n* continued\nclass Foo"
        result = strip_leading_comments(text, [_SLASH_COMMENT, _DOC_COMMENT])
        assert result == "class Foo"
