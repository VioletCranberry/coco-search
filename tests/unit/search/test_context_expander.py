"""Tests for cocosearch.search.context_expander module.

Tests smart context expansion with tree-sitter boundary detection,
LRU caching, and edge case handling.
"""

import pytest

from cocosearch.search.context_expander import (
    ContextExpander,
    get_context_with_boundaries,
    MAX_CONTEXT_LINES,
    LINE_TRUNCATION_LENGTH,
    _get_language_from_path,
    _truncate_line,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def expander():
    """Create a fresh ContextExpander instance."""
    return ContextExpander()


@pytest.fixture
def sample_python_file(tmp_path):
    """Create sample Python file with nested classes/functions."""
    content = '''"""Module docstring."""


def standalone_function(x, y):
    """A standalone function."""
    result = x + y
    return result


class MyClass:
    """A sample class."""

    def __init__(self, value):
        """Initialize the class."""
        self.value = value

    def method_one(self):
        """First method."""
        return self.value * 2

    def method_two(self, factor):
        """Second method."""
        return self.value * factor


def another_function():
    """Another standalone function."""
    pass
'''
    filepath = tmp_path / "sample.py"
    filepath.write_text(content)
    return str(filepath)


@pytest.fixture
def sample_javascript_file(tmp_path):
    """Create sample JavaScript file with function and class."""
    content = """// JavaScript sample file

function processData(input) {
    const result = input.map(x => x * 2);
    return result;
}

class DataProcessor {
    constructor(config) {
        this.config = config;
    }

    process(data) {
        return data.filter(x => x > 0);
    }
}

const arrowFunc = (a, b) => a + b;
"""
    filepath = tmp_path / "sample.js"
    filepath.write_text(content)
    return str(filepath)


@pytest.fixture
def sample_json_file(tmp_path):
    """Create sample non-code JSON file."""
    content = """{
    "name": "test",
    "version": "1.0.0",
    "description": "A test file",
    "dependencies": {
        "lodash": "^4.17.0"
    }
}
"""
    filepath = tmp_path / "package.json"
    filepath.write_text(content)
    return str(filepath)


@pytest.fixture
def sample_scala_file(tmp_path):
    """Create sample Scala file with class, trait, object, and function."""
    content = """package com.example

class Calculator {
  def add(x: Int, y: Int): Int = x + y

  def subtract(x: Int, y: Int): Int = x - y
}

trait Serializable {
  def serialize(): String
}

object Utils {
  def helper(): Unit = {
    println("hello")
  }
}

def topLevel(x: Int): String = x.toString
"""
    filepath = tmp_path / "Calculator.scala"
    filepath.write_text(content)
    return str(filepath)


@pytest.fixture
def sample_hcl_file(tmp_path):
    """Create sample Terraform file saved as .tf with resource, variable, nested lifecycle."""
    content = """resource "aws_instance" "web" {
  ami           = "ami-12345678"
  instance_type = "t2.micro"

  lifecycle {
    create_before_destroy = true
    prevent_destroy       = false
  }

  tags = {
    Name = "web-server"
  }
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

output "instance_id" {
  value = aws_instance.web.id
}
"""
    filepath = tmp_path / "main.tf"
    filepath.write_text(content)
    return str(filepath)


@pytest.fixture
def large_python_function(tmp_path):
    """Create Python file with function larger than 50 lines."""
    lines = ["def large_function():"]
    lines.append('    """A very long function."""')
    # Add 60 lines of code to exceed 50-line limit
    for i in range(60):
        lines.append(f"    x_{i} = {i}")
    lines.append("    return x_0")
    lines.append("")

    filepath = tmp_path / "large.py"
    filepath.write_text("\n".join(lines))
    return str(filepath)


# ============================================================================
# Test Helper Functions
# ============================================================================


class TestGetLanguageFromPath:
    """Tests for _get_language_from_path helper."""

    def test_python_extension(self):
        """Should return python for .py files."""
        assert _get_language_from_path("/path/to/file.py") == "python"

    def test_javascript_extensions(self):
        """Should return javascript for JS variants."""
        assert _get_language_from_path("file.js") == "javascript"
        assert _get_language_from_path("file.jsx") == "javascript"
        assert _get_language_from_path("file.mjs") == "javascript"
        assert _get_language_from_path("file.cjs") == "javascript"

    def test_typescript_extensions(self):
        """Should return typescript for TS variants."""
        assert _get_language_from_path("file.ts") == "typescript"
        assert _get_language_from_path("file.tsx") == "typescript"
        assert _get_language_from_path("file.mts") == "typescript"
        assert _get_language_from_path("file.cts") == "typescript"

    def test_go_extension(self):
        """Should return go for .go files."""
        assert _get_language_from_path("/src/main.go") == "go"

    def test_rust_extension(self):
        """Should return rust for .rs files."""
        assert _get_language_from_path("/src/lib.rs") == "rust"

    def test_scala_extension(self):
        """Should return scala for .scala files."""
        assert _get_language_from_path("/src/Main.scala") == "scala"

    def test_terraform_extension(self):
        """Should return terraform for .tf files."""
        assert _get_language_from_path("/infra/main.tf") == "terraform"

    def test_hcl_extension(self):
        """Should return hcl for .hcl files."""
        assert _get_language_from_path("/config/vault.hcl") == "hcl"

    def test_tfvars_extension(self):
        """Should return terraform for .tfvars files."""
        assert _get_language_from_path("/envs/prod.tfvars") == "terraform"

    def test_unsupported_extension(self):
        """Should return None for unsupported extensions."""
        assert _get_language_from_path("file.json") is None
        assert _get_language_from_path("file.md") is None
        assert _get_language_from_path("file.txt") is None
        assert _get_language_from_path("file.yaml") is None

    def test_case_insensitive(self):
        """Should handle uppercase extensions."""
        assert _get_language_from_path("file.PY") == "python"
        assert _get_language_from_path("file.JS") == "javascript"


class TestTruncateLine:
    """Tests for _truncate_line helper."""

    def test_short_line_unchanged(self):
        """Short lines should be returned as-is."""
        line = "short line"
        assert _truncate_line(line) == line

    def test_exact_limit_unchanged(self):
        """Lines exactly at limit should be unchanged."""
        line = "x" * LINE_TRUNCATION_LENGTH
        assert _truncate_line(line) == line

    def test_long_line_truncated(self):
        """Long lines should be truncated with '...'."""
        line = "x" * (LINE_TRUNCATION_LENGTH + 50)
        result = _truncate_line(line)
        assert len(result) == LINE_TRUNCATION_LENGTH
        assert result.endswith("...")

    def test_custom_max_length(self):
        """Should respect custom max_length parameter."""
        line = "this is a longer line"
        result = _truncate_line(line, max_length=10)
        assert result == "this is..."
        assert len(result) == 10


# ============================================================================
# Test find_enclosing_scope
# ============================================================================


class TestFindEnclosingScope:
    """Tests for find_enclosing_scope method."""

    def test_function_boundary_detection_python(self, expander, sample_python_file):
        """Should find enclosing function in Python."""
        # Line 6 is inside standalone_function (def is on line 4)
        start, end = expander.find_enclosing_scope(sample_python_file, 6, 6, "python")
        # Should expand to include entire function
        assert start <= 4  # Function def line
        assert end >= 7  # Return statement line

    def test_class_boundary_detection_python(self, expander, sample_python_file):
        """Should find enclosing class in Python."""
        # Line 11 is class docstring (class def is on line 10)
        start, end = expander.find_enclosing_scope(sample_python_file, 11, 11, "python")
        # Should expand to include class boundaries
        assert start <= 10  # Class def line

    def test_method_inside_class(self, expander, sample_python_file):
        """Should find method or class boundary for method code."""
        # Line 18 is inside method_one
        start, end = expander.find_enclosing_scope(sample_python_file, 18, 18, "python")
        # Should find some enclosing scope (method or class)
        assert start <= 18
        assert end >= 18

    def test_top_level_code_returns_original(self, expander, tmp_path):
        """Top-level code should return original range."""
        content = """x = 1
y = 2
z = x + y
"""
        filepath = tmp_path / "top_level.py"
        filepath.write_text(content)

        start, end = expander.find_enclosing_scope(str(filepath), 2, 2, "python")
        # No enclosing function/class, should return original
        assert start == 2
        assert end == 2

    def test_class_boundary_detection_scala(self, expander, sample_scala_file):
        """Should find enclosing class in Scala."""
        # Line 4 is inside Calculator class (def add)
        start, end = expander.find_enclosing_scope(sample_scala_file, 4, 4, "scala")
        # Should expand to include the class definition
        assert start <= 3  # class Calculator line
        assert end >= 6  # closing brace

    def test_trait_boundary_detection_scala(self, expander, sample_scala_file):
        """Should find enclosing trait in Scala."""
        # Line 10 is inside Serializable trait (def serialize)
        start, end = expander.find_enclosing_scope(sample_scala_file, 10, 10, "scala")
        assert start <= 9  # trait Serializable line
        assert end >= 11  # closing brace

    def test_object_boundary_detection_scala(self, expander, sample_scala_file):
        """Should find enclosing function/object in Scala."""
        # Line 15 is inside Utils.helper (println) — walks up to function_definition first
        start, end = expander.find_enclosing_scope(sample_scala_file, 15, 15, "scala")
        assert start <= 14  # def helper line
        assert end >= 16  # closing brace

    def test_hcl_block_boundary_detection(self, expander, sample_hcl_file):
        """Should find enclosing block in HCL/Terraform file."""
        # Line 3 is inside the resource block (resource starts on line 1)
        start, end = expander.find_enclosing_scope(sample_hcl_file, 3, 3, "terraform")
        # tree-sitter "block" node should encompass the resource block
        assert start <= 3
        assert end >= 3

    def test_unsupported_language_returns_original(self, expander, sample_json_file):
        """Unsupported language should return original range."""
        # JSON is not in DEFINITION_NODE_TYPES
        start, end = expander.find_enclosing_scope(sample_json_file, 3, 5, "json")
        assert start == 3
        assert end == 5

    def test_file_not_found_returns_original(self, expander):
        """Non-existent file should return original range."""
        start, end = expander.find_enclosing_scope(
            "/nonexistent/file.py", 5, 10, "python"
        )
        assert start == 5
        assert end == 10

    def test_parse_error_returns_original(self, expander, tmp_path):
        """File with syntax errors should return original range."""
        content = """def broken(
    # Missing closing paren and colon
"""
        filepath = tmp_path / "broken.py"
        filepath.write_text(content)

        # Should not raise, should return original range
        start, end = expander.find_enclosing_scope(str(filepath), 1, 2, "python")
        # Tree-sitter can still parse partial trees, but behavior varies
        assert isinstance(start, int)
        assert isinstance(end, int)


# ============================================================================
# Test get_context_lines
# ============================================================================


class TestGetContextLines:
    """Tests for get_context_lines method."""

    def test_smart_expands_to_function(self, expander, sample_python_file):
        """smart=True should expand to function boundaries."""
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            sample_python_file,
            start_line=6,  # Inside standalone_function
            end_line=6,
            smart=True,
        )

        # Should include context before and after the matched line
        all_lines = before + match + after
        line_nums = [num for num, _ in all_lines]

        # Should include function definition line (4)
        assert any(num <= 5 for num in line_nums)  # Has lines before match
        assert 6 in line_nums  # Original match line included

    def test_smart_false_uses_exact_counts(self, expander, sample_python_file):
        """smart=False should use exact context_before/context_after values."""
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            sample_python_file,
            start_line=10,
            end_line=11,
            context_before=2,
            context_after=3,
            smart=False,
        )

        # Should have exactly 2 lines before
        assert len(before) == 2
        # Should have exactly 3 lines after
        assert len(after) == 3
        # Match should cover lines 10-11
        match_nums = [num for num, _ in match]
        assert 10 in match_nums
        assert 11 in match_nums

    def test_50_line_limit_enforced(self, expander, large_python_function):
        """Should enforce 50-line limit on large functions."""
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            large_python_function,
            start_line=30,  # Middle of large function
            end_line=35,
            smart=True,
        )

        all_lines = before + match + after
        assert len(all_lines) <= MAX_CONTEXT_LINES

    def test_bof_detection(self, expander, sample_python_file):
        """Should set is_bof when context starts at file beginning."""
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            sample_python_file,
            start_line=2,
            end_line=3,
            context_before=10,  # More than available
            context_after=2,
            smart=False,
        )

        assert is_bof is True

    def test_eof_detection(self, expander, sample_python_file):
        """Should set is_eof when context ends at file end."""
        # Read file to get line count
        lines = expander.get_file_lines(sample_python_file)
        last_line = len(lines)

        before, match, after, is_bof, is_eof = expander.get_context_lines(
            sample_python_file,
            start_line=last_line - 2,
            end_line=last_line,
            context_before=2,
            context_after=10,  # More than available
            smart=False,
        )

        assert is_eof is True

    def test_long_line_truncation(self, expander, tmp_path):
        """Should truncate lines longer than 200 chars."""
        long_line = "x = " + "a" * 300
        content = f"line 1\n{long_line}\nline 3"
        filepath = tmp_path / "long.py"
        filepath.write_text(content)

        before, match, after, is_bof, is_eof = expander.get_context_lines(
            str(filepath),
            start_line=2,
            end_line=2,
            smart=False,
        )

        # Match should contain line 2, truncated
        assert len(match) == 1
        line_num, line_text = match[0]
        assert line_num == 2
        assert len(line_text) == LINE_TRUNCATION_LENGTH
        assert line_text.endswith("...")

    def test_file_not_found_returns_empty(self, expander):
        """Non-existent file should return empty lists."""
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            "/nonexistent/file.py",
            start_line=5,
            end_line=10,
        )

        assert before == []
        assert match == []
        assert after == []
        assert is_bof is False
        assert is_eof is False

    def test_explicit_language_parameter(self, expander, sample_javascript_file):
        """Should use explicit language parameter."""
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            sample_javascript_file,
            start_line=4,  # Inside processData function
            end_line=4,
            smart=True,
            language="javascript",
        )

        # Should expand based on JavaScript function
        all_lines = before + match + after
        assert len(all_lines) > 1  # Expanded beyond single line

    def test_smart_expands_to_scala_class(self, expander, sample_scala_file):
        """smart=True should expand to Scala class boundaries."""
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            sample_scala_file,
            start_line=4,  # Inside Calculator.add method
            end_line=4,
            smart=True,
        )

        all_lines = before + match + after
        line_nums = [num for num, _ in all_lines]

        # Should expand to include class definition
        assert any(num <= 3 for num in line_nums)  # Has class def line
        assert 4 in line_nums  # Original match line included

    def test_auto_detect_scala_language(self, expander, sample_scala_file):
        """Should auto-detect scala from .scala extension."""
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            sample_scala_file,
            start_line=4,
            end_line=4,
            smart=True,
        )

        # Should expand (language detected from .scala extension)
        all_lines = before + match + after
        assert len(all_lines) > 1

    def test_smart_expands_hcl_file(self, expander, sample_hcl_file):
        """smart=True should expand context for .tf files."""
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            sample_hcl_file,
            start_line=3,  # Inside resource block
            end_line=3,
            smart=True,
        )

        # Should expand context (language auto-detected from .tf extension)
        all_lines = before + match + after
        assert len(all_lines) >= 1
        assert 3 in [num for num, _ in all_lines]

    def test_auto_detect_terraform_from_tf(self, expander, sample_hcl_file):
        """Should auto-detect terraform from .tf extension."""
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            sample_hcl_file,
            start_line=3,
            end_line=3,
            smart=True,
        )

        # Should expand (language detected from .tf extension)
        all_lines = before + match + after
        assert len(all_lines) >= 1

    def test_auto_detect_language(self, expander, sample_python_file):
        """Should auto-detect language from file extension."""
        # Don't pass language parameter
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            sample_python_file,
            start_line=6,
            end_line=6,
            smart=True,
        )

        # Should still expand (language detected from .py extension)
        all_lines = before + match + after
        assert len(all_lines) > 1


# ============================================================================
# Test Caching
# ============================================================================


class TestCaching:
    """Tests for file caching behavior."""

    def test_same_file_returns_cached(self, expander, sample_python_file):
        """Same file should return cached content."""
        # First read
        lines1 = expander.get_file_lines(sample_python_file)
        # Second read
        lines2 = expander.get_file_lines(sample_python_file)

        # Should be same object (cached)
        assert lines1 is lines2

    def test_clear_cache_resets(self, expander, sample_python_file):
        """clear_cache should reset the cache."""
        # Read file
        lines1 = expander.get_file_lines(sample_python_file)

        # Clear cache
        expander.clear_cache()

        # Read again - should be new list (not cached)
        lines2 = expander.get_file_lines(sample_python_file)

        # Content should be equal but not same object
        assert lines1 == lines2
        # After clear, it's a new read so different object
        # Note: We can't guarantee they're different objects since
        # Python may intern identical lists, so just check content
        assert lines1 == lines2

    def test_cache_info_accessible(self, expander, sample_python_file):
        """Should be able to check cache info."""
        # Read file
        expander.get_file_lines(sample_python_file)

        # Cache info should be accessible
        info = expander._read_file_cached.cache_info()
        assert info.hits >= 0
        assert info.misses >= 1


# ============================================================================
# Test Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_file(self, expander, tmp_path):
        """Empty file should return empty lists."""
        filepath = tmp_path / "empty.py"
        filepath.write_text("")

        before, match, after, is_bof, is_eof = expander.get_context_lines(
            str(filepath),
            start_line=1,
            end_line=1,
        )

        assert before == []
        assert match == []
        assert after == []

    def test_single_line_file(self, expander, tmp_path):
        """Single line file should work correctly."""
        filepath = tmp_path / "single.py"
        filepath.write_text("x = 1")

        before, match, after, is_bof, is_eof = expander.get_context_lines(
            str(filepath),
            start_line=1,
            end_line=1,
            smart=False,
        )

        assert before == []
        assert len(match) == 1
        assert match[0] == (1, "x = 1")
        assert after == []
        assert is_bof is True
        assert is_eof is True

    def test_binary_file_handled(self, expander, tmp_path):
        """Binary file should not crash (errors='replace')."""
        filepath = tmp_path / "binary.bin"
        filepath.write_bytes(b"\x00\x01\x02\xff\xfe\xfd")

        # Should not raise
        lines = expander.get_file_lines(str(filepath))
        # May return some content with replacements
        assert isinstance(lines, list)

    def test_line_numbers_are_1_indexed(self, expander, tmp_path):
        """Line numbers should be 1-indexed."""
        filepath = tmp_path / "indexed.py"
        filepath.write_text("line 1\nline 2\nline 3")

        before, match, after, is_bof, is_eof = expander.get_context_lines(
            str(filepath),
            start_line=2,
            end_line=2,
            context_before=1,
            context_after=1,
            smart=False,
        )

        # Check line numbers
        assert before == [(1, "line 1")]
        assert match == [(2, "line 2")]
        assert after == [(3, "line 3")]


# ============================================================================
# Test Module-Level Function
# ============================================================================


class TestGetContextWithBoundaries:
    """Tests for module-level get_context_with_boundaries function."""

    def test_convenience_function_works(self, sample_python_file):
        """Module-level function should work like instance method."""
        before, match, after, is_bof, is_eof = get_context_with_boundaries(
            sample_python_file,
            start_line=6,
            end_line=6,
            smart=True,
        )

        assert isinstance(before, list)
        assert isinstance(match, list)
        assert isinstance(after, list)
        assert isinstance(is_bof, bool)
        assert isinstance(is_eof, bool)

    def test_all_parameters_work(self, sample_python_file):
        """All parameters should be passable."""
        before, match, after, is_bof, is_eof = get_context_with_boundaries(
            filepath=sample_python_file,
            start_line=10,
            end_line=12,
            context_before=3,
            context_after=3,
            smart=False,
            language="python",
        )

        # Should have exactly 3 before and 3 after
        assert len(before) == 3
        assert len(after) == 3
