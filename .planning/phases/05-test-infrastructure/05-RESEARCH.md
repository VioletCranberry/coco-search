# Phase 5: Test Infrastructure - Research

**Researched:** 2026-01-25
**Domain:** Python testing with pytest, async testing, mocking PostgreSQL and Ollama
**Confidence:** HIGH

## Summary

This phase establishes pytest test infrastructure for CocoSearch with async support and mocking capabilities. The codebase has two primary external dependencies requiring mocks: PostgreSQL (via psycopg/psycopg_pool) and Ollama (via CocoIndex's EmbedText function which uses HTTP internally).

The standard approach is pytest with pytest-asyncio for async test support, using strict mode with explicit `@pytest.mark.asyncio` markers as decided in CONTEXT.md. For mocking, the recommended pattern is to mock at the module boundary level (e.g., `cocosearch.search.db` functions) rather than low-level database connections, and mock HTTP responses for Ollama embedding calls.

**Primary recommendation:** Use pytest + pytest-asyncio (strict mode) with dedicated mock modules in `tests/mocks/` and fixtures in `tests/fixtures/`, mocking at the application's module boundaries rather than third-party library internals.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >=9.0.2 | Test framework | Already in dev dependencies, industry standard |
| pytest-asyncio | >=0.25.0 | Async test support | Official asyncio testing plugin, supports strict mode |
| pytest-mock | >=3.14.0 | Mocking utilities | Cleaner API than unittest.mock, pytest-native |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-httpx | >=0.34.0 | HTTPX mocking | Mock Ollama API HTTP calls |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-httpx | respx | respx has slightly different API, pytest-httpx integrates better as pytest fixture |
| pytest-mock | unittest.mock | unittest.mock works but pytest-mock provides cleaner fixture-based API |
| Dedicated mock modules | pytest-postgresql | pytest-postgresql requires real PostgreSQL; dedicated mocks provide faster, isolated tests |

**Installation:**
```bash
uv add --group dev pytest-asyncio pytest-mock pytest-httpx
```

## Architecture Patterns

### Recommended Project Structure
```
tests/
    conftest.py              # Root conftest with pytest-asyncio config
    fixtures/
        __init__.py          # Makes fixtures importable
        db.py                # Database fixtures (mock_db_pool, mock_search_results)
        ollama.py            # Ollama fixtures (mock_embeddings, httpx_mock config)
        data.py              # Sample data fixtures (sample_search_result, sample_config)
    mocks/
        __init__.py          # Makes mocks importable
        db.py                # MockConnectionPool, MockCursor classes
        ollama.py            # Mock embedding responses, httpx mock helpers
    data/
        sample_config.yaml   # Sample .cocosearch.yaml for testing
        sample_gitignore     # Sample .gitignore content
    test_cli.py              # CLI command tests
    test_search_db.py        # search/db.py tests
    test_search_query.py     # search/query.py tests
    test_search_formatter.py # search/formatter.py tests
    test_search_utils.py     # search/utils.py tests
    test_indexer_config.py   # indexer/config.py tests
    test_indexer_flow.py     # indexer/flow.py tests
    test_indexer_filter.py   # indexer/file_filter.py tests
    test_indexer_embedder.py # indexer/embedder.py tests
    test_indexer_progress.py # indexer/progress.py tests
    test_management_git.py   # management/git.py tests
    test_management_clear.py # management/clear.py tests
    test_management_discovery.py # management/discovery.py tests
    test_management_stats.py # management/stats.py tests
    test_mcp_server.py       # mcp/server.py tests
    README.md                # Test conventions documentation
```

### Pattern 1: Module-Level Database Mocking
**What:** Mock database functions at `cocosearch.search.db` level, not psycopg internals
**When to use:** All tests that involve database operations
**Example:**
```python
# tests/mocks/db.py
from unittest.mock import MagicMock, AsyncMock

class MockCursor:
    """Mock database cursor returning canned results."""

    def __init__(self, results: list = None):
        self.results = results or []
        self._index = 0

    def execute(self, query: str, params: tuple = None):
        """Track executed query for assertions."""
        self.last_query = query
        self.last_params = params

    def fetchone(self):
        if self._index < len(self.results):
            result = self.results[self._index]
            self._index += 1
            return result
        return None

    def fetchall(self):
        return self.results

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

class MockConnection:
    """Mock database connection."""

    def __init__(self, cursor: MockCursor = None):
        self._cursor = cursor or MockCursor()

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

class MockConnectionPool:
    """Mock psycopg_pool.ConnectionPool."""

    def __init__(self, connection: MockConnection = None):
        self._connection = connection or MockConnection()

    def connection(self):
        return self._connection

# tests/fixtures/db.py
import pytest
from unittest.mock import patch
from tests.mocks.db import MockConnectionPool, MockCursor, MockConnection

@pytest.fixture
def mock_db_pool():
    """Fixture that patches get_connection_pool to return mock pool."""
    def _make_pool(results: list = None):
        cursor = MockCursor(results=results)
        conn = MockConnection(cursor=cursor)
        pool = MockConnectionPool(connection=conn)
        return pool, cursor
    return _make_pool

@pytest.fixture
def patched_db_pool(mock_db_pool):
    """Fixture that auto-patches the db module."""
    pool, cursor = mock_db_pool()
    with patch('cocosearch.search.db.get_connection_pool', return_value=pool):
        yield pool, cursor
```

### Pattern 2: Deterministic Embedding Mocks
**What:** Hash-based fake embeddings that return consistent results for same input
**When to use:** All tests involving embedding generation
**Example:**
```python
# tests/mocks/ollama.py
import hashlib

def deterministic_embedding(text: str, dimensions: int = 768) -> list[float]:
    """Generate deterministic fake embedding from text hash.

    Same input always produces same output, enabling predictable test assertions.
    """
    hash_bytes = hashlib.sha256(text.encode()).digest()
    # Expand hash to fill dimensions
    embedding = []
    for i in range(dimensions):
        byte_idx = i % len(hash_bytes)
        # Normalize to [-1, 1] range typical for embeddings
        value = (hash_bytes[byte_idx] / 255.0) * 2 - 1
        embedding.append(value)
    return embedding

# tests/fixtures/ollama.py
import pytest
from unittest.mock import patch, MagicMock
from tests.mocks.ollama import deterministic_embedding

@pytest.fixture
def mock_code_to_embedding():
    """Mock the code_to_embedding.eval() function."""
    def _mock_eval(text: str) -> list[float]:
        return deterministic_embedding(text)

    mock = MagicMock()
    mock.eval = _mock_eval

    with patch('cocosearch.indexer.embedder.code_to_embedding', mock):
        yield mock
```

### Pattern 3: HTTP-Level Ollama Mocking with pytest-httpx
**What:** Mock HTTPX responses for Ollama API endpoint
**When to use:** Tests that call CocoIndex embedding functions directly
**Example:**
```python
# tests/fixtures/ollama.py (additional)
import pytest
from pytest_httpx import HTTPXMock
from tests.mocks.ollama import deterministic_embedding

@pytest.fixture
def mock_ollama_api(httpx_mock: HTTPXMock):
    """Configure httpx mock for Ollama embedding API."""
    def callback(request):
        import json
        data = json.loads(request.content)
        text = data.get("prompt", data.get("input", ""))
        embedding = deterministic_embedding(text)
        return httpx.Response(
            200,
            json={"embedding": embedding}
        )

    httpx_mock.add_callback(callback, url__startswith="http://localhost:11434")
    return httpx_mock
```

### Pattern 4: Factory Fixtures for Test Data
**What:** Functions that create test objects with customizable parameters
**When to use:** When tests need variations of the same data structure
**Example:**
```python
# tests/fixtures/data.py
import pytest
from cocosearch.search.query import SearchResult
from cocosearch.indexer.config import IndexingConfig

@pytest.fixture
def make_search_result():
    """Factory for SearchResult objects."""
    def _make(
        filename: str = "/test/file.py",
        start_byte: int = 0,
        end_byte: int = 100,
        score: float = 0.85,
    ) -> SearchResult:
        return SearchResult(
            filename=filename,
            start_byte=start_byte,
            end_byte=end_byte,
            score=score,
        )
    return _make

@pytest.fixture
def sample_search_result(make_search_result):
    """Ready-to-use SearchResult for simple tests."""
    return make_search_result()

@pytest.fixture
def make_indexing_config():
    """Factory for IndexingConfig objects."""
    def _make(
        include_patterns: list[str] = None,
        exclude_patterns: list[str] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 300,
    ) -> IndexingConfig:
        return IndexingConfig(
            include_patterns=include_patterns or ["*.py"],
            exclude_patterns=exclude_patterns or [],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    return _make

@pytest.fixture
def sample_config(make_indexing_config):
    """Ready-to-use IndexingConfig for simple tests."""
    return make_indexing_config()
```

### Anti-Patterns to Avoid
- **Mocking psycopg internals directly:** Creates brittle tests coupled to library implementation. Mock at `cocosearch.search.db` boundary instead.
- **Non-deterministic embedding mocks:** Random embeddings make tests unpredictable. Use hash-based deterministic approach.
- **Sharing state between tests:** Each test should have isolated mocks. Use function-scoped fixtures.
- **Auto mode for pytest-asyncio:** Per CONTEXT.md decision, use explicit marking (`@pytest.mark.asyncio`) for clarity.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async test support | Custom event loop management | pytest-asyncio | Handles loop lifecycle, fixture integration |
| HTTP mocking | Manual httpx patching | pytest-httpx | Proper request/response matching, cleanup |
| Mock management | Raw unittest.mock | pytest-mock's `mocker` | Auto-cleanup, better pytest integration |
| Fixture organization | Inline fixtures everywhere | conftest.py hierarchy | pytest auto-discovers, reduces imports |

**Key insight:** The pytest ecosystem has mature plugins for every common testing need. Using established plugins ensures proper cleanup and pytest integration.

## Common Pitfalls

### Pitfall 1: Event Loop Conflicts
**What goes wrong:** Tests fail with "event loop is closed" or "attached to different loop" errors
**Why it happens:** Sharing event loops between tests or fixtures with mismatched scopes
**How to avoid:** Use function-scoped event loops (default in pytest-asyncio strict mode), explicit `@pytest.mark.asyncio` markers
**Warning signs:** Tests pass individually but fail when run together

### Pitfall 2: Mock Not Applied to Correct Import Path
**What goes wrong:** Mock doesn't take effect, real code executes
**Why it happens:** Patching wrong module path (e.g., patching `psycopg_pool.ConnectionPool` instead of `cocosearch.search.db.get_connection_pool`)
**How to avoid:** Patch where the function is *used*, not where it's *defined*
**Warning signs:** Tests unexpectedly require real database/API

### Pitfall 3: Missing Async Context Managers
**What goes wrong:** `TypeError: object MagicMock can't be used in 'await' expression`
**Why it happens:** Using regular Mock for async context manager (`async with`)
**How to avoid:** Use `AsyncMock` for async methods, implement `__aenter__`/`__aexit__` for async context managers
**Warning signs:** Async test code works with real objects but not mocks

### Pitfall 4: Fixture Import Confusion
**What goes wrong:** `fixture 'xxx' not found`
**Why it happens:** Fixtures in `tests/fixtures/` not registered in conftest.py
**How to avoid:** Import fixtures in `tests/conftest.py` using `pytest_plugins` or explicit imports
**Warning signs:** Fixtures work in some files but not others

### Pitfall 5: Database Connection Pool Singleton
**What goes wrong:** Tests pollute each other through shared pool state
**Why it happens:** `cocosearch.search.db._pool` is a module-level singleton
**How to avoid:** Reset `_pool = None` in fixture teardown, or always patch `get_connection_pool`
**Warning signs:** Tests pass in isolation, fail when run together

## Code Examples

Verified patterns from official sources and codebase analysis:

### pytest.ini / pyproject.toml Configuration
```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "strict"
asyncio_default_fixture_loop_scope = "function"
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
```

### Root conftest.py
```python
# tests/conftest.py
"""Root conftest.py - pytest configuration and shared fixtures."""

import pytest

# Register fixtures from fixtures directory
pytest_plugins = [
    "tests.fixtures.db",
    "tests.fixtures.ollama",
    "tests.fixtures.data",
]

@pytest.fixture(autouse=True)
def reset_db_pool():
    """Reset database pool singleton between tests."""
    yield
    # Teardown: reset pool singleton
    import cocosearch.search.db as db_module
    db_module._pool = None

@pytest.fixture
def tmp_codebase(tmp_path):
    """Create a temporary codebase directory with sample files."""
    codebase = tmp_path / "codebase"
    codebase.mkdir()

    # Create sample Python file
    (codebase / "main.py").write_text("def hello():\n    return 'world'\n")

    # Create sample gitignore
    (codebase / ".gitignore").write_text("*.pyc\n__pycache__/\n")

    return codebase
```

### Async Test Example
```python
# tests/test_search_query.py
import pytest
from unittest.mock import patch, MagicMock
from cocosearch.search.query import search, SearchResult

@pytest.mark.asyncio
async def test_search_returns_results(mock_code_to_embedding, patched_db_pool):
    """Test search returns properly formatted results."""
    pool, cursor = patched_db_pool

    # Setup mock cursor to return sample data
    cursor.results = [
        ("/path/to/file.py", 0, 100, 0.85),
        ("/path/to/other.py", 50, 150, 0.72),
    ]

    results = search(
        query="find authentication code",
        index_name="test_index",
        limit=10,
    )

    assert len(results) == 2
    assert results[0].filename == "/path/to/file.py"
    assert results[0].score == 0.85
    assert isinstance(results[0], SearchResult)
```

### CLI Test Example
```python
# tests/test_cli.py
import pytest
from unittest.mock import patch, MagicMock
from cocosearch.cli import derive_index_name, index_command
import argparse

def test_derive_index_name_simple():
    """Test index name derivation from path."""
    assert derive_index_name("/home/user/MyProject") == "myproject"
    assert derive_index_name("/tmp/test-repo/") == "test_repo"

def test_derive_index_name_special_chars():
    """Test index name sanitization."""
    assert derive_index_name("/path/to/My-Cool_Project") == "my_cool_project"

@patch('cocosearch.cli.run_index')
@patch('cocosearch.cli.IndexingProgress')
def test_index_command_success(mock_progress, mock_run_index, tmp_codebase):
    """Test successful index command execution."""
    # Setup
    mock_context = MagicMock()
    mock_progress.return_value.__enter__ = MagicMock(return_value=mock_context)
    mock_progress.return_value.__exit__ = MagicMock(return_value=False)
    mock_run_index.return_value = MagicMock(stats={"files": {"num_insertions": 5}})

    args = argparse.Namespace(
        path=str(tmp_codebase),
        name=None,
        include=None,
        exclude=None,
        no_gitignore=False,
    )

    result = index_command(args)

    assert result == 0
    mock_run_index.assert_called_once()
```

### Mock Module Example
```python
# tests/mocks/db.py
"""Database mock classes for testing."""

from typing import Any
from collections.abc import Sequence

class MockCursor:
    """Mock database cursor with call tracking."""

    def __init__(self, results: Sequence[tuple] | None = None):
        self.results = list(results) if results else []
        self.calls: list[tuple[str, tuple | None]] = []
        self._fetch_index = 0

    def execute(self, query: str, params: tuple | None = None) -> None:
        """Record query execution for later assertions."""
        self.calls.append((query, params))

    def fetchone(self) -> tuple | None:
        """Return next result row."""
        if self._fetch_index < len(self.results):
            row = self.results[self._fetch_index]
            self._fetch_index += 1
            return row
        return None

    def fetchall(self) -> list[tuple]:
        """Return all remaining results."""
        remaining = self.results[self._fetch_index:]
        self._fetch_index = len(self.results)
        return remaining

    def __enter__(self) -> "MockCursor":
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def assert_query_contains(self, substring: str) -> None:
        """Assert that any executed query contains substring."""
        for query, _ in self.calls:
            if substring in query:
                return
        raise AssertionError(f"No query containing '{substring}' was executed")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `event_loop` fixture | Loop scope via markers/config | pytest-asyncio 1.0 (May 2025) | Remove custom event_loop fixtures |
| `asyncio_mode = "auto"` | `asyncio_mode = "strict"` | Best practice 2025 | Explicit markers prevent accidental sync test execution |
| Monolithic conftest.py | Fixture modules + conftest imports | pytest best practice | Better organization, easier maintenance |

**Deprecated/outdated:**
- Custom `event_loop` fixture definitions: Use loop scope markers instead (pytest-asyncio 1.0+)
- `asyncio_mode = "legacy"`: Removed in recent pytest-asyncio versions

## Open Questions

Things that couldn't be fully resolved:

1. **CocoIndex Flow Mocking Strategy**
   - What we know: CocoIndex uses `@cocoindex.flow_def` and `@cocoindex.transform_flow` decorators that compile to internal representations
   - What's unclear: Exact internal mechanism for mocking flow execution in unit tests
   - Recommendation: Mock at the `run_index` function level for most tests; flow internals tested via integration tests in Phase 6

2. **MCP Server Testing Approach**
   - What we know: FastMCP server uses `@mcp.tool()` decorators, runs with stdio transport
   - What's unclear: Best approach to test MCP tools without starting actual server
   - Recommendation: Test tool functions directly (they're regular Python functions), mock `cocoindex.init()` and database calls

## Sources

### Primary (HIGH confidence)
- [pytest-asyncio Configuration Documentation](https://pytest-asyncio.readthedocs.io/en/stable/reference/configuration.html) - asyncio_mode, loop scope options
- [pytest Fixtures Documentation](https://docs.pytest.org/en/stable/how-to/fixtures.html) - fixture factories, scope, conftest organization
- [pytest-httpx PyPI](https://pypi.org/project/pytest-httpx/) - HTTPX mocking API

### Secondary (MEDIUM confidence)
- [pytest-asyncio Migration Guide](https://thinhdanggroup.github.io/pytest-asyncio-v1-migrate/) - pytest-asyncio 1.0 changes
- [pytest-mock Best Practices](https://pytest-with-eric.com/pytest-best-practices/pytest-conftest/) - conftest organization
- [Five Advanced Pytest Fixture Patterns](https://www.inspiredpython.com/article/five-advanced-pytest-fixture-patterns) - factory pattern

### Tertiary (LOW confidence)
- CocoIndex documentation - Limited testing documentation available

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest and pytest-asyncio are well-documented, project already uses pytest
- Architecture: HIGH - Follows pytest best practices and matches CONTEXT.md decisions
- Pitfalls: HIGH - Common pytest issues are well-documented, codebase-specific issues identified from code review

**Research date:** 2026-01-25
**Valid until:** 60 days (stable domain, pytest ecosystem changes slowly)

---
*Phase: 05-test-infrastructure*
*Research completed: 2026-01-25*
