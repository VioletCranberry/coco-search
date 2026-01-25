# Phase 6: Test Coverage - Research

**Researched:** 2026-01-25
**Domain:** Python unit testing with pytest for CLI, database, MCP server, and Rich output
**Confidence:** HIGH

## Summary

This phase implements comprehensive test coverage for all CocoSearch modules using the test infrastructure established in Phase 5. The codebase consists of 5 module groups (indexer, search, management, CLI, MCP) with distinct testing requirements: pure functions, database operations, subprocess calls, CLI commands, and MCP tool handlers.

The established infrastructure provides mock classes (MockCursor, MockConnection, MockConnectionPool), deterministic embedding functions, and fixture patterns (factory + ready-to-use). Tests will follow the decisions from CONTEXT.md: mirror source structure, use pytest.raises with message verification, mock at boundaries only, and aim for 80% coverage threshold.

**Primary recommendation:** Structure tests to mirror source modules, use existing fixtures extensively, leverage capsys for CLI output capture, and test MCP tools as regular functions with mocked dependencies.

## Standard Stack

The established libraries/tools for this domain:

### Core (Already Configured)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >=9.0.2 | Test framework | Already configured in pyproject.toml |
| pytest-asyncio | >=1.3.0 | Async test support | Strict mode configured |
| pytest-mock | >=3.15.1 | Mocking utilities | Cleaner fixture-based API |
| pytest-httpx | >=0.36.0 | HTTPX mocking | Available for Ollama API mocking if needed |

### Supporting (To Add)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-cov | >=6.1.0 | Coverage reporting | Enforce 80% threshold |
| pytest-subprocess | >=1.5.3 | Subprocess mocking | Test git.py commands |

### Not Needed
| Library | Why Not |
|---------|---------|
| pytest-postgresql | Real DB not needed; mock infrastructure in place |
| inline-snapshot | Complex snapshot testing not required for this codebase |

**Installation:**
```bash
uv add --group dev pytest-cov pytest-subprocess
```

## Architecture Patterns

### Recommended Test Directory Structure
```
tests/
    conftest.py              # Already exists - root fixtures
    fixtures/
        db.py                # Already exists - database fixtures
        ollama.py            # Already exists - embedding fixtures
        data.py              # Already exists - data factories
    mocks/
        db.py                # Already exists - MockCursor, etc.
        ollama.py            # Already exists - deterministic_embedding
    indexer/
        test_config.py       # TEST-IDX-01
        test_flow.py         # TEST-IDX-02
        test_file_filter.py  # TEST-IDX-03
        test_embedder.py     # TEST-IDX-04
        test_progress.py     # TEST-IDX-05
    search/
        test_db.py           # TEST-SRC-01
        test_query.py        # TEST-SRC-02
        test_formatter.py    # TEST-SRC-03
        test_utils.py        # TEST-SRC-04
    management/
        test_git.py          # TEST-MGT-01
        test_clear.py        # TEST-MGT-02
        test_discovery.py    # TEST-MGT-03
        test_stats.py        # TEST-MGT-04
    test_cli.py              # TEST-CLI-01, TEST-CLI-02, TEST-CLI-03
    mcp/
        test_server.py       # TEST-MCP-01, TEST-MCP-02, TEST-MCP-03
```

### Pattern 1: Pure Function Testing
**What:** Direct function calls with assertions on return values
**When to use:** `derive_index_name`, `format_bytes`, `byte_to_line`, `get_table_name`, etc.
**Example:**
```python
# tests/search/test_utils.py
import pytest
from cocosearch.search.utils import byte_to_line, read_chunk_content

class TestByteToLine:
    def test_start_of_file(self, tmp_path):
        """Byte 0 should be line 1."""
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\nline3\n")
        assert byte_to_line(str(f), 0) == 1

    def test_after_newline(self, tmp_path):
        """Byte after newline should be next line."""
        f = tmp_path / "test.py"
        f.write_text("line1\nline2\n")  # 6 bytes in "line1\n"
        assert byte_to_line(str(f), 6) == 2

    def test_file_not_found_returns_zero(self):
        """Non-existent file returns 0."""
        assert byte_to_line("/nonexistent/file.py", 0) == 0
```

### Pattern 2: Database Operation Testing with Fixtures
**What:** Use existing patched_db_pool and mock_db_pool fixtures
**When to use:** All tests for search/db.py, search/query.py, management modules
**Example:**
```python
# tests/search/test_query.py
import pytest
from unittest.mock import patch
from cocosearch.search.query import search, SearchResult

class TestSearch:
    def test_search_returns_results(self, mock_code_to_embedding, mock_db_pool):
        """Search returns properly formatted SearchResult objects."""
        pool, cursor = mock_db_pool(results=[
            ("/path/file.py", 0, 100, 0.85),
            ("/path/other.py", 50, 150, 0.72),
        ])

        with patch("cocosearch.search.db.get_connection_pool", return_value=pool):
            results = search(
                query="find auth code",
                index_name="test_index",
                limit=10,
            )

        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].filename == "/path/file.py"
        assert results[0].score == 0.85

        # Verify SQL was executed
        cursor.assert_query_contains("SELECT")
        cursor.assert_query_contains("embedding <=>")
```

### Pattern 3: CLI Testing with capsys
**What:** Use pytest's capsys fixture to capture stdout/stderr
**When to use:** All CLI command tests
**Example:**
```python
# tests/test_cli.py
import pytest
import json
from unittest.mock import patch, MagicMock
from cocosearch.cli import search_command, list_command
import argparse

class TestSearchCommand:
    def test_search_json_output(self, capsys, mock_code_to_embedding, mock_db_pool):
        """Search command outputs valid JSON."""
        pool, cursor = mock_db_pool(results=[
            ("/test/file.py", 0, 100, 0.9),
        ])

        # Mock file read for content extraction
        with patch("cocosearch.search.db.get_connection_pool", return_value=pool):
            with patch("cocosearch.search.utils.read_chunk_content", return_value="def test(): pass"):
                with patch("cocosearch.search.utils.byte_to_line", return_value=1):
                    with patch("cocoindex.init"):
                        args = argparse.Namespace(
                            query="test",
                            index="testindex",
                            limit=10,
                            lang=None,
                            min_score=0.3,
                            context=5,
                            pretty=False,
                            interactive=False,
                        )
                        result = search_command(args)

        captured = capsys.readouterr()
        # JSON output should be parseable
        output = json.loads(captured.out)
        assert isinstance(output, list)
        assert result == 0

    def test_search_error_json_format(self, capsys):
        """Errors in JSON mode return JSON error object."""
        with patch("cocoindex.init", side_effect=ValueError("DB not configured")):
            args = argparse.Namespace(
                query="test",
                index="testindex",
                limit=10,
                lang=None,
                min_score=0.3,
                context=5,
                pretty=False,
                interactive=False,
            )
            result = search_command(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "error" in output
        assert result == 1
```

### Pattern 4: Rich Output Testing with Console Capture
**What:** Pass a Rich Console with StringIO for testable output
**When to use:** Testing progress.py, formatter.py with --pretty output
**Example:**
```python
# tests/indexer/test_progress.py
import io
from rich.console import Console
from cocosearch.indexer.progress import IndexingProgress, print_summary

class TestPrintSummary:
    def test_summary_shows_stats(self):
        """Summary displays all provided stats."""
        output = io.StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        stats = {
            "files_added": 10,
            "files_removed": 2,
            "files_updated": 5,
        }
        print_summary(stats, console=console)

        result = output.getvalue()
        assert "10" in result
        assert "2" in result
        assert "5" in result

class TestIndexingProgress:
    def test_context_manager(self):
        """Progress works as context manager."""
        output = io.StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        with IndexingProgress(console=console) as progress:
            progress.start_indexing("/test/path")
            progress.update_status("Processing...")
            progress.complete({"files_added": 1, "files_removed": 0, "files_updated": 0})

        # Just verify no exceptions - actual output testing is optional
        assert True
```

### Pattern 5: Subprocess Mocking for Git Tests
**What:** Use pytest-subprocess to mock git commands
**When to use:** management/git.py tests
**Example:**
```python
# tests/management/test_git.py
import pytest
from pathlib import Path
from cocosearch.management.git import get_git_root, derive_index_from_git

class TestGetGitRoot:
    def test_returns_path_in_git_repo(self, fp):
        """Returns Path when in git repository."""
        fp.register(
            ["git", "rev-parse", "--show-toplevel"],
            stdout="/home/user/myproject\n"
        )

        result = get_git_root()

        assert result == Path("/home/user/myproject")

    def test_returns_none_outside_repo(self, fp):
        """Returns None when not in git repository."""
        fp.register(
            ["git", "rev-parse", "--show-toplevel"],
            returncode=128,
            stderr="fatal: not a git repository"
        )

        result = get_git_root()

        assert result is None
```

### Pattern 6: MCP Tool Testing as Regular Functions
**What:** Test MCP tool handlers directly, mocking dependencies
**When to use:** mcp/server.py tests
**Example:**
```python
# tests/mcp/test_server.py
import pytest
from unittest.mock import patch, MagicMock
from cocosearch.mcp.server import search_code, list_indexes, index_stats, clear_index

class TestSearchCode:
    def test_returns_results_list(self, mock_code_to_embedding, mock_db_pool):
        """search_code returns list of result dicts."""
        pool, cursor = mock_db_pool(results=[
            ("/test/file.py", 0, 100, 0.9),
        ])

        with patch("cocosearch.search.db.get_connection_pool", return_value=pool):
            with patch("cocosearch.search.utils.byte_to_line", return_value=1):
                with patch("cocosearch.search.utils.read_chunk_content", return_value="code"):
                    with patch("cocoindex.init"):
                        result = search_code(
                            query="test",
                            index_name="testindex",
                            limit=5,
                        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["file_path"] == "/test/file.py"
        assert "content" in result[0]

class TestListIndexes:
    def test_returns_index_list(self, mock_db_pool):
        """list_indexes returns list of index dicts."""
        pool, cursor = mock_db_pool(results=[
            ("codeindex_myproject__myproject_chunks",),
        ])

        with patch("cocosearch.search.db.get_connection_pool", return_value=pool):
            result = list_indexes()

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "myproject"

class TestClearIndex:
    def test_returns_success_on_delete(self, mock_db_pool):
        """clear_index returns success dict."""
        pool, cursor = mock_db_pool(results=[(True,)])  # EXISTS returns True

        with patch("cocosearch.search.db.get_connection_pool", return_value=pool):
            result = clear_index(index_name="testindex")

        assert result["success"] is True

    def test_returns_error_for_nonexistent(self, mock_db_pool):
        """clear_index returns error for missing index."""
        pool, cursor = mock_db_pool(results=[(False,)])  # EXISTS returns False

        with patch("cocosearch.search.db.get_connection_pool", return_value=pool):
            result = clear_index(index_name="missing")

        assert result["success"] is False
        assert "error" in result
```

### Anti-Patterns to Avoid
- **Testing Rich markup directly:** Test content presence, not exact Rich formatting tags
- **Relying on file system state:** Use tmp_path fixture for all file operations
- **Testing internal implementation:** Test behavior, not that specific methods were called
- **Sharing mutable state:** Each test gets fresh fixtures via function scope

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Capture stdout/stderr | sys.stdout redirection | pytest capsys fixture | Auto-cleanup, works with pytest capture |
| Subprocess mocking | unittest.mock for subprocess | pytest-subprocess plugin | Handles edge cases, cleaner API |
| Temporary files | Manual cleanup | pytest tmp_path fixture | Automatic cleanup, guaranteed isolation |
| Coverage reporting | Manual line counting | pytest-cov plugin | Accurate, integrates with CI |
| Database mocking | New mock classes | Existing tests/mocks/db.py | Already built and tested |
| Embedding mocking | Random vectors | tests/mocks/ollama.py | Deterministic, already tested |

**Key insight:** Phase 5 built comprehensive mock infrastructure. Use it consistently rather than creating ad-hoc mocks in individual tests.

## Common Pitfalls

### Pitfall 1: Forgetting to Patch at Usage Location
**What goes wrong:** Mock not applied, real code executes
**Why it happens:** Patching `cocosearch.indexer.embedder.code_to_embedding` but code imports it differently
**How to avoid:** Use the `mock_code_to_embedding` fixture which patches both import locations
**Warning signs:** Tests fail with "Ollama not running" errors

### Pitfall 2: Not Mocking cocoindex.init()
**What goes wrong:** Tests try to connect to real database
**Why it happens:** Many functions call `cocoindex.init()` internally
**How to avoid:** Patch `cocoindex.init` in tests that call CLI commands or MCP tools
**Warning signs:** Tests fail with database connection errors

### Pitfall 3: Testing Rich Output with capsys Fails
**What goes wrong:** capsys captures empty or garbled output from Rich
**Why it happens:** Rich detects non-terminal and changes output behavior
**How to avoid:** Create Console with `file=io.StringIO(), force_terminal=True`
**Warning signs:** Tests pass but assertions on output fail

### Pitfall 4: Database Pool Singleton Leaks
**What goes wrong:** Tests pass individually, fail when run together
**Why it happens:** `cocosearch.search.db._pool` singleton persists between tests
**How to avoid:** The `reset_db_pool` autouse fixture handles this
**Warning signs:** Test order affects pass/fail status

### Pitfall 5: File Content Tests Assume Encoding
**What goes wrong:** Tests fail on special characters
**Why it happens:** `read_chunk_content` returns unicode, files might have different encodings
**How to avoid:** Use simple ASCII content in test files, test encoding edge cases explicitly
**Warning signs:** UnicodeDecodeError in tests

### Pitfall 6: SystemExit from argparse
**What goes wrong:** Test crashes with SystemExit
**Why it happens:** Invalid arguments cause argparse to exit
**How to avoid:** Use `pytest.raises(SystemExit)` for error cases, or call commands directly
**Warning signs:** pytest reports SystemExit instead of test failure

## Code Examples

### Complete Test Module Template
```python
# tests/module/test_something.py
"""Tests for cocosearch.module.something."""

import pytest
from unittest.mock import patch, MagicMock

from cocosearch.module.something import function_to_test


class TestFunctionName:
    """Tests for function_name()."""

    def test_happy_path(self):
        """Describe expected behavior."""
        result = function_to_test(valid_input)
        assert result == expected_output

    def test_edge_case(self):
        """Handle edge case X."""
        result = function_to_test(edge_input)
        assert result == edge_expected

    def test_error_case(self):
        """Raise ValueError for invalid input."""
        with pytest.raises(ValueError, match="specific message"):
            function_to_test(invalid_input)

    @pytest.mark.parametrize("input,expected", [
        ("a", "result_a"),
        ("b", "result_b"),
    ])
    def test_multiple_inputs(self, input, expected):
        """Test various input combinations."""
        assert function_to_test(input) == expected
```

### Module-Specific Examples

#### indexer/config.py Tests
```python
# tests/indexer/test_config.py
import pytest
import yaml
from cocosearch.indexer.config import load_config, IndexingConfig

class TestLoadConfig:
    def test_returns_defaults_when_no_config(self, tmp_path):
        """Returns IndexingConfig with defaults when .cocosearch.yaml missing."""
        config = load_config(str(tmp_path))

        assert isinstance(config, IndexingConfig)
        assert "*.py" in config.include_patterns
        assert config.chunk_size == 1000

    def test_loads_from_yaml(self, tmp_path):
        """Loads settings from .cocosearch.yaml file."""
        config_content = {
            "indexing": {
                "include_patterns": ["*.py", "*.js"],
                "chunk_size": 500,
            }
        }
        (tmp_path / ".cocosearch.yaml").write_text(yaml.dump(config_content))

        config = load_config(str(tmp_path))

        assert config.include_patterns == ["*.py", "*.js"]
        assert config.chunk_size == 500

    def test_returns_defaults_on_malformed_yaml(self, tmp_path):
        """Returns defaults when YAML is malformed."""
        (tmp_path / ".cocosearch.yaml").write_text("invalid: yaml: content:")

        config = load_config(str(tmp_path))

        assert isinstance(config, IndexingConfig)
```

#### search/db.py Tests
```python
# tests/search/test_db.py
import pytest
import os
from unittest.mock import patch
from cocosearch.search.db import get_connection_pool, get_table_name

class TestGetConnectionPool:
    def test_raises_without_env_var(self):
        """Raises ValueError when COCOINDEX_DATABASE_URL not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear any existing pool
            import cocosearch.search.db as db
            db._pool = None

            with pytest.raises(ValueError, match="COCOINDEX_DATABASE_URL"):
                get_connection_pool()

class TestGetTableName:
    def test_generates_correct_name(self):
        """Generates CocoIndex-style table name."""
        result = get_table_name("myproject")

        assert result == "codeindex_myproject__myproject_chunks"

    def test_handles_underscores(self):
        """Handles index names with underscores."""
        result = get_table_name("my_project")

        assert result == "codeindex_my_project__my_project_chunks"
```

#### CLI Error Handling Tests
```python
# tests/test_cli.py (partial)
import pytest
import argparse
from unittest.mock import patch
from cocosearch.cli import index_command

class TestIndexCommandErrors:
    def test_invalid_path_returns_error(self, capsys):
        """Returns 1 and prints error for nonexistent path."""
        args = argparse.Namespace(
            path="/nonexistent/path",
            name=None,
            include=None,
            exclude=None,
            no_gitignore=False,
        )

        result = index_command(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out
        assert "does not exist" in captured.out

    def test_indexing_failure_returns_error(self, capsys, tmp_codebase):
        """Returns 1 when indexing fails."""
        with patch("cocosearch.cli.run_index", side_effect=Exception("DB error")):
            args = argparse.Namespace(
                path=str(tmp_codebase),
                name="test",
                include=None,
                exclude=None,
                no_gitignore=False,
            )

            result = index_command(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Ad-hoc mocking | Dedicated mock modules | Phase 5 | Consistent, reusable mocks |
| Real subprocess in tests | pytest-subprocess | 2024 | Faster, more reliable git tests |
| capsys for Rich | Console(file=StringIO) | Rich 10+ | Proper terminal output capture |
| Manual coverage tracking | pytest-cov --fail-under | Standard | Automated enforcement |

**Current best practices:**
- pytest-cov for coverage with fail_under threshold
- pytest-subprocess for git command mocking
- Rich Console capture via StringIO for output testing
- Factory fixtures for configurable test data

## Open Questions

Things that couldn't be fully resolved:

1. **CocoIndex Flow Testing Depth**
   - What we know: flow.py creates CocoIndex flows with decorators
   - What's unclear: Whether to unit test flow creation or just integration test via run_index
   - Recommendation: Test run_index with mocked cocoindex.init() and flow execution; skip testing flow decorator internals

2. **REPL Testing Strategy**
   - What we know: SearchREPL uses cmd.Cmd with readline integration
   - What's unclear: Best way to test interactive REPL commands
   - Recommendation: Test individual methods (default, handle_setting) directly; skip cmdloop() integration

3. **MCP Server Async Testing**
   - What we know: MCP tools are regular sync functions in this codebase
   - What's unclear: Whether to use async test patterns for future-proofing
   - Recommendation: Test as sync functions since they're implemented as sync; add async markers if tools become async

## Sources

### Primary (HIGH confidence)
- [pytest capsys documentation](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) - stdout/stderr capture
- [pytest-cov configuration](https://pytest-cov.readthedocs.io/en/latest/config.html) - coverage thresholds
- [Rich console.capture()](https://rich.readthedocs.io/en/stable/reference/console.html) - Rich output testing
- [pytest-subprocess docs](https://pytest-subprocess.readthedocs.io/) - subprocess mocking

### Secondary (MEDIUM confidence)
- [Testing argparse CLIs](https://pytest-with-eric.com/pytest-advanced/pytest-argparse-typer/) - CLI test patterns
- [FastMCP testing patterns](https://gofastmcp.com/patterns/testing) - MCP server testing
- [Rich GitHub issue #1093](https://github.com/Textualize/rich/discussions/1093) - Progress bar testing

### Tertiary (LOW confidence)
- Existing tests/mocks/* and tests/fixtures/* - Phase 5 implementation (verified by code review)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest ecosystem well-documented, Phase 5 infrastructure in place
- Architecture: HIGH - Patterns derived from pytest best practices and codebase analysis
- Pitfalls: HIGH - Identified from codebase structure and common pytest issues

**Research date:** 2026-01-25
**Valid until:** 60 days (stable testing patterns, minimal ecosystem churn)

---
*Phase: 06-test-coverage*
*Research completed: 2026-01-25*
