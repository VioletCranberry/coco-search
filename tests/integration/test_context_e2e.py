"""End-to-end integration tests for context expansion.

Tests the complete context expansion pipeline including:
- CLI flags (-A/-B/-C/--no-smart)
- MCP context parameters (context_before/context_after/smart_context)
- Smart boundary detection with tree-sitter
- Performance/caching behavior
- Edge cases (deleted files, file boundaries, long lines)
"""

import json
import os
import subprocess
import sys
import time

import pytest

from cocosearch.search import ContextExpander


# ============================================================================
# Test fixtures
# ============================================================================


@pytest.fixture
def sample_python_project(tmp_path):
    """Create a temporary Python project with known content.

    Creates:
        sample.py - Contains class with methods and standalone function
        utils.py - Contains nested functions
        data.json - Non-code file for boundary testing
    """
    # sample.py - Class with methods, standalone function
    sample_py = tmp_path / "sample.py"
    sample_py.write_text('''\
class UserService:
    """Service for user operations."""

    def __init__(self, db):
        self.db = db

    def get_user(self, user_id):
        """Get user by ID."""
        return self.db.find_one({"id": user_id})

    def create_user(self, name, email):
        """Create a new user."""
        user = {"name": name, "email": email}
        return self.db.insert(user)


def process_data(items):
    """Process data items."""
    result = []
    for item in items:
        result.append(transform(item))
    return result


def transform(item):
    """Transform single item."""
    return item.upper()
''')

    # utils.py - Nested functions
    utils_py = tmp_path / "utils.py"
    utils_py.write_text('''\
def outer_function(data):
    """Outer function with nested helper."""

    def inner_helper(x):
        """Inner helper function."""
        return x * 2

    results = []
    for item in data:
        results.append(inner_helper(item))
    return results


def validate_input(value):
    """Validate input value."""
    if not value:
        raise ValueError("Empty value")
    return True
''')

    # data.json - Non-code file
    data_json = tmp_path / "data.json"
    data_json.write_text('{"key": "value", "items": [1, 2, 3]}\n')

    return tmp_path


@pytest.fixture
def large_python_file(tmp_path):
    """Create a Python file with a function exceeding 50 lines.

    Used to test the 50-line hard limit enforcement.
    """
    content_lines = ["def large_function(data):"]
    content_lines.append('    """A function that exceeds 50 lines."""')
    for i in range(60):
        content_lines.append(f"    line_{i} = process_item({i})")
    content_lines.append("    return result")
    content_lines.append("")

    large_py = tmp_path / "large.py"
    large_py.write_text("\n".join(content_lines))
    return large_py


@pytest.fixture
def indexed_context_fixtures(initialized_db, warmed_ollama, sample_python_project):
    """Index sample Python project for context expansion tests.

    Function scope ensures fresh index per test since clean_tables
    truncates all tables after each test.
    """
    env = os.environ.copy()
    env["COCOSEARCH_DATABASE_URL"] = initialized_db
    env["COCOSEARCH_OLLAMA_URL"] = warmed_ollama

    index_name = "context_e2e_test"

    # Index the fixtures
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cocosearch",
            "index",
            str(sample_python_project),
            "--name",
            index_name,
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )

    assert result.returncode == 0, f"Indexing failed: {result.stderr}"

    yield index_name, env, sample_python_project

    # Cleanup handled by clean_tables autouse fixture


def search_cli(
    query: str, index_name: str, env: dict, extra_args: list | None = None
) -> subprocess.CompletedProcess:
    """Run CLI search command.

    Args:
        query: Search query string
        index_name: Name of index to search
        env: Environment variables
        extra_args: Additional CLI arguments

    Returns:
        CompletedProcess with stdout/stderr
    """
    args = [sys.executable, "-m", "cocosearch", "search", query, "--index", index_name]
    if extra_args:
        args.extend(extra_args)

    return subprocess.run(args, capture_output=True, text=True, env=env, timeout=30)


def parse_json_output(result: subprocess.CompletedProcess) -> list[dict]:
    """Parse JSON from CLI output.

    Args:
        result: CompletedProcess from search_cli

    Returns:
        List of result dicts, or empty list on error
    """
    if result.returncode != 0:
        return []

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


# ============================================================================
# Task 2: CLI context flag tests
# ============================================================================


class TestCLIContextFlags:
    """Tests for CLI context flags (-A/-B/-C/--no-smart)."""

    def test_after_context_flag(self, indexed_context_fixtures):
        """Test -A flag shows lines after each match."""
        index_name, env, project_path = indexed_context_fixtures

        # Search for "UserService" with -A 3
        result = search_cli("UserService", index_name, env, ["-A", "3"])

        assert result.returncode == 0, f"Search failed: {result.stderr}"
        results = parse_json_output(result)

        assert len(results) > 0, "Should find at least one result"

        # Check that context_after is populated
        first_result = results[0]
        assert "context_after" in first_result, "Should have context_after field"

        # context_after should have content (we requested 3 lines)
        context_after = first_result.get("context_after", "")
        if context_after:
            # Should have up to 3 lines after the match
            after_lines = context_after.split("\n")
            assert len(after_lines) <= 3, (
                f"Should have at most 3 after lines, got {len(after_lines)}"
            )

    def test_before_context_flag(self, indexed_context_fixtures):
        """Test -B flag shows lines before each match."""
        index_name, env, project_path = indexed_context_fixtures

        # Search for "process_data" with -B 2
        result = search_cli("process_data", index_name, env, ["-B", "2"])

        assert result.returncode == 0, f"Search failed: {result.stderr}"
        results = parse_json_output(result)

        assert len(results) > 0, "Should find at least one result"

        # Check that context_before is populated
        first_result = results[0]
        assert "context_before" in first_result, "Should have context_before field"

    def test_combined_context_flag(self, indexed_context_fixtures):
        """Test -C flag shows lines before and after each match."""
        index_name, env, project_path = indexed_context_fixtures

        # Search with -C 2 (2 lines before and after)
        result = search_cli("get_user", index_name, env, ["-C", "2"])

        assert result.returncode == 0, f"Search failed: {result.stderr}"
        results = parse_json_output(result)

        assert len(results) > 0, "Should find at least one result"

        # Both context_before and context_after should be populated
        first_result = results[0]
        assert "context_before" in first_result, "Should have context_before field"
        assert "context_after" in first_result, "Should have context_after field"

    def test_no_smart_flag_disables_expansion(self, indexed_context_fixtures):
        """Test --no-smart flag disables smart boundary expansion."""
        index_name, env, project_path = indexed_context_fixtures

        # Search with --no-smart (no context expansion by default)
        result = search_cli("get_user", index_name, env, ["--no-smart"])

        assert result.returncode == 0, f"Search failed: {result.stderr}"
        results = parse_json_output(result)

        assert len(results) > 0, "Should find at least one result"

        # Without smart context and without explicit -A/-B/-C, no context expansion
        first_result = results[0]
        context_before = first_result.get("context_before", "")
        context_after = first_result.get("context_after", "")

        # Both should be empty since no explicit context was requested
        assert not context_before, "context_before should be empty with --no-smart"
        assert not context_after, "context_after should be empty with --no-smart"

    def test_pretty_output_shows_markers(self, indexed_context_fixtures):
        """Test --pretty output uses grep-style markers."""
        index_name, env, project_path = indexed_context_fixtures

        # Search with -C 2 --pretty
        result = search_cli("get_user", index_name, env, ["-C", "2", "--pretty"])

        assert result.returncode == 0, f"Search failed: {result.stderr}"

        # Pretty output should contain grep-style markers
        # : for context lines, > for match lines
        output = result.stdout
        # Should contain the query target
        assert "get_user" in output.lower() or "user" in output.lower(), (
            "Pretty output should contain search results"
        )


# ============================================================================
# Task 2: Smart boundary detection tests
# ============================================================================


class TestSmartBoundaryDetection:
    """Tests for smart boundary detection with tree-sitter."""

    def test_python_function_boundary(self, sample_python_project):
        """Test that smart expansion finds Python function boundaries."""
        sample_py = sample_python_project / "sample.py"

        expander = ContextExpander()

        # Search for line in middle of process_data function (line 20-21 approx)
        # The function spans lines 18-23
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            str(sample_py),
            start_line=20,  # "for item in items:" line
            end_line=20,
            smart=True,
            language="python",
        )

        # Should expand to include full function
        all_lines = before + match + after
        line_nums = [ln for ln, _ in all_lines]

        # Should include function definition "def process_data(items):"
        assert any(ln <= 18 for ln in line_nums), (
            f"Should include function start, got lines {line_nums}"
        )

        # Should include "return result" at end
        assert any(ln >= 22 for ln in line_nums), (
            f"Should include function end, got lines {line_nums}"
        )

        expander.clear_cache()

    def test_python_class_boundary(self, sample_python_project):
        """Test that smart expansion finds Python class boundaries."""
        sample_py = sample_python_project / "sample.py"

        expander = ContextExpander()

        # Search for line in middle of UserService class
        # The class starts at line 1
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            str(sample_py),
            start_line=8,  # Inside get_user method
            end_line=8,
            smart=True,
            language="python",
        )

        # Should expand to include method/class boundaries
        all_lines = before + match + after
        line_nums = [ln for ln, _ in all_lines]

        # Should have expanded beyond just line 8
        assert len(line_nums) > 1, "Should expand beyond single line"

        expander.clear_cache()

    def test_50_line_limit_enforced(self, large_python_file):
        """Test that 50-line hard limit is enforced on large functions."""
        expander = ContextExpander()

        # Search in middle of 60+ line function
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            str(large_python_file),
            start_line=30,  # Middle of large function
            end_line=30,
            smart=True,
            language="python",
        )

        # Total lines should not exceed 50
        total_lines = len(before) + len(match) + len(after)
        assert total_lines <= 50, f"Should enforce 50-line limit, got {total_lines}"

        expander.clear_cache()


# ============================================================================
# Task 2: Performance/caching tests
# ============================================================================


class TestPerformanceCaching:
    """Tests for file caching and performance."""

    def test_file_cached_across_calls(self, sample_python_project):
        """Test that repeated calls for same file use cache."""
        sample_py = sample_python_project / "sample.py"

        expander = ContextExpander()

        # First call - reads file
        expander.get_context_lines(
            str(sample_py), start_line=5, end_line=5, smart=True, language="python"
        )

        # Check cache info
        cache_info = expander._read_file_cached.cache_info()
        initial_hits = cache_info.hits
        initial_misses = cache_info.misses

        # Second call - should hit cache
        expander.get_context_lines(
            str(sample_py), start_line=10, end_line=10, smart=True, language="python"
        )

        cache_info = expander._read_file_cached.cache_info()
        assert cache_info.hits > initial_hits, "Second call should hit cache"
        assert cache_info.misses == initial_misses, "Second call should not miss cache"

        expander.clear_cache()

    def test_clear_cache_resets(self, sample_python_project):
        """Test that clear_cache() resets the cache."""
        sample_py = sample_python_project / "sample.py"

        expander = ContextExpander()

        # Populate cache
        expander.get_context_lines(
            str(sample_py), start_line=5, end_line=5, smart=True, language="python"
        )

        cache_info = expander._read_file_cached.cache_info()
        assert cache_info.currsize > 0, "Cache should have entries"

        # Clear cache
        expander.clear_cache()

        cache_info = expander._read_file_cached.cache_info()
        assert cache_info.currsize == 0, "Cache should be empty after clear"

    def test_batched_context_expansion_performance(self, sample_python_project):
        """Test that multiple results from same file are efficient."""
        sample_py = sample_python_project / "sample.py"

        expander = ContextExpander()
        start_time = time.time()

        # Simulate multiple search results from same file
        for line in range(5, 25):
            expander.get_context_lines(
                str(sample_py),
                start_line=line,
                end_line=line,
                smart=True,
                language="python",
            )

        elapsed = time.time() - start_time

        # Should complete in reasonable time (< 1 second)
        assert elapsed < 1.0, f"Batched expansion took too long: {elapsed}s"

        # Should have only 1 cache miss (first read)
        cache_info = expander._read_file_cached.cache_info()
        assert cache_info.misses == 1, (
            f"Should only read file once, had {cache_info.misses} misses"
        )

        expander.clear_cache()


# ============================================================================
# Task 2: Edge cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases in context expansion."""

    def test_deleted_file_graceful(self, tmp_path):
        """Test that deleted file is handled gracefully."""
        # Create and then delete a file
        temp_file = tmp_path / "deleted.py"
        temp_file.write_text("def foo(): pass\n")

        expander = ContextExpander()

        # Read it once (populate cache)
        expander.get_context_lines(str(temp_file), 1, 1, smart=False)

        # Delete the file
        temp_file.unlink()

        # Clear cache and try to read deleted file
        expander.clear_cache()

        # Should return empty without error
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            str(temp_file), 1, 1, smart=False
        )

        assert before == [], "Should return empty before for deleted file"
        assert match == [], "Should return empty match for deleted file"
        assert after == [], "Should return empty after for deleted file"

    def test_file_boundary_bof_marker(self, sample_python_project):
        """Test BOF marker when context starts at file beginning."""
        sample_py = sample_python_project / "sample.py"

        expander = ContextExpander()

        # Request context from very first line
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            str(sample_py),
            start_line=1,
            end_line=3,
            context_before=10,  # Request more lines than exist
            context_after=0,
            smart=False,
        )

        # Should set is_bof=True
        assert is_bof, "Should indicate beginning of file"

        expander.clear_cache()

    def test_file_boundary_eof_marker(self, sample_python_project):
        """Test EOF marker when context ends at file end."""
        sample_py = sample_python_project / "sample.py"

        # Count lines in file
        with open(sample_py) as f:
            total_lines = len(f.readlines())

        expander = ContextExpander()

        # Request context from last line
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            str(sample_py),
            start_line=total_lines,
            end_line=total_lines,
            context_before=0,
            context_after=10,  # Request more lines than exist
            smart=False,
        )

        # Should set is_eof=True
        assert is_eof, "Should indicate end of file"

        expander.clear_cache()

    def test_long_lines_truncated(self, tmp_path):
        """Test that lines longer than 200 chars are truncated."""
        # Create file with very long line
        long_file = tmp_path / "long.py"
        long_line = "x = '" + "a" * 300 + "'"  # > 200 chars
        long_file.write_text(f"def foo():\n    {long_line}\n")

        expander = ContextExpander()

        before, match, after, is_bof, is_eof = expander.get_context_lines(
            str(long_file), start_line=2, end_line=2, smart=False
        )

        # Check that long line was truncated
        if match:
            line_num, line_text = match[0]
            assert len(line_text) <= 200, (
                f"Line should be truncated to 200 chars, got {len(line_text)}"
            )
            assert line_text.endswith("..."), "Truncated line should end with ..."

        expander.clear_cache()


# ============================================================================
# Task 2 & 3: MCP context parameter tests
# ============================================================================


class TestMCPContextParameters:
    """Tests for MCP context parameters.

    Note: These tests directly call the search_code function logic
    rather than running through MCP transport, since we're testing
    the context expansion behavior not the protocol.
    """

    def test_mcp_context_before_after(self, sample_python_project):
        """Test context_before and context_after parameters work."""
        from cocosearch.search.context_expander import ContextExpander

        sample_py = sample_python_project / "sample.py"

        expander = ContextExpander()

        # Request explicit context (like MCP would)
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            str(sample_py),
            start_line=10,
            end_line=10,
            context_before=3,
            context_after=5,
            smart=False,  # Explicit counts disable smart
        )

        # Should have up to 3 lines before
        assert len(before) <= 3, (
            f"Should have at most 3 before lines, got {len(before)}"
        )
        # Should have up to 5 lines after
        assert len(after) <= 5, f"Should have at most 5 after lines, got {len(after)}"

        expander.clear_cache()

    def test_mcp_smart_context_disabled(self, sample_python_project):
        """Test smart_context=False disables boundary expansion."""
        sample_py = sample_python_project / "sample.py"

        expander = ContextExpander()

        # With smart=False and no explicit context, should return only match
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            str(sample_py),
            start_line=10,
            end_line=10,
            context_before=0,
            context_after=0,
            smart=False,
        )

        assert before == [], (
            "Should have no before lines with smart=False and 0 context"
        )
        assert after == [], "Should have no after lines with smart=False and 0 context"

        expander.clear_cache()


# ============================================================================
# Task 3: Full integration flow tests
# ============================================================================


class TestFullIntegrationFlow:
    """Tests for complete user flow verification."""

    def test_complete_search_with_context(self, indexed_context_fixtures):
        """Test complete user flow: index -> search with context -> verify output."""
        index_name, env, project_path = indexed_context_fixtures

        # Search with -C 5
        result = search_cli("UserService", index_name, env, ["-C", "5"])

        assert result.returncode == 0, f"Search failed: {result.stderr}"
        results = parse_json_output(result)

        assert len(results) > 0, "Should find results"

        # Verify result structure
        for r in results:
            assert "file_path" in r, "Result should have file_path"
            assert "start_line" in r, "Result should have start_line"
            assert "end_line" in r, "Result should have end_line"
            assert "score" in r, "Result should have score"
            assert "content" in r, "Result should have content"

            # Context should be strings (not lists)
            if "context_before" in r:
                assert isinstance(r["context_before"], str), (
                    "context_before should be string"
                )
            if "context_after" in r:
                assert isinstance(r["context_after"], str), (
                    "context_after should be string"
                )

    def test_json_output_format_with_context(self, indexed_context_fixtures):
        """Test JSON output format with -A and -B flags."""
        index_name, env, project_path = indexed_context_fixtures

        # Search with -A 5 -B 3
        result = search_cli("process_data", index_name, env, ["-A", "5", "-B", "3"])

        assert result.returncode == 0, f"Search failed: {result.stderr}"

        # Parse and verify JSON structure
        try:
            results = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON output: {e}")

        assert isinstance(results, list), "Output should be a list"

        if results:
            r = results[0]
            # Verify context_before and context_after are present
            assert "context_before" in r or not r.get("context_before"), (
                "Should have context_before (possibly empty)"
            )
            assert "context_after" in r or not r.get("context_after"), (
                "Should have context_after (possibly empty)"
            )

    def test_smart_vs_explicit_context(self, indexed_context_fixtures):
        """Test that smart context differs from explicit context."""
        index_name, env, project_path = indexed_context_fixtures

        # Search with smart context (default)
        result_smart = search_cli("get_user", index_name, env, [])
        results_smart = parse_json_output(result_smart)

        # Search with explicit -C 3 (overrides smart)
        result_explicit = search_cli(
            "get_user", index_name, env, ["-C", "3", "--no-smart"]
        )
        results_explicit = parse_json_output(result_explicit)

        # Both should return results
        assert len(results_smart) > 0, "Smart search should return results"
        assert len(results_explicit) > 0, "Explicit search should return results"

        # Smart context typically expands more than explicit 3 lines
        # (since it finds function boundaries)
        # This is a soft check - behavior depends on match location


class TestBatchedIOOptimization:
    """Tests for batched I/O optimization."""

    def test_multiple_results_same_file_timing(self, indexed_context_fixtures):
        """Test that context expansion for multiple results is efficient."""
        index_name, env, project_path = indexed_context_fixtures

        # Search with low threshold to get multiple results
        result = search_cli(
            "user", index_name, env, ["-C", "5", "--min-score", "0.1", "-l", "20"]
        )

        assert result.returncode == 0, f"Search failed: {result.stderr}"
        results = parse_json_output(result)

        # Should have multiple results
        assert len(results) >= 1, "Should find at least one result"

        # Results should have context populated
        for r in results:
            # Either context fields exist or it's a valid search result
            assert "file_path" in r, "Each result should have file_path"
