# CocoSearch Tests

## Running Tests

```bash
uv run pytest              # Run all tests
uv run pytest -v           # Verbose output
uv run pytest tests/test_search_query.py  # Run specific file
uv run pytest -k "search"  # Run tests matching pattern
```

## Conventions

- Test files: `test_*.py` in tests/ directory
- Test functions: `test_*`
- Async tests: Mark with `@pytest.mark.asyncio`
- Fixtures: Defined in tests/conftest.py or tests/fixtures/ modules

## Directory Structure

```
tests/
    conftest.py          # Root conftest, shared fixtures
    fixtures/            # Fixture modules (db, ollama, data)
    mocks/               # Mock classes (MockCursor, etc.)
    data/                # Test data files
    test_*.py            # Test modules
```

## Available Fixtures

### Built-in
- `tmp_codebase` - Temporary directory with sample Python files
- `reset_db_pool` (autouse) - Resets database pool between tests

### Database (tests.fixtures.db)
- `mock_db_pool` - Factory for mock database pool
- `patched_db_pool` - Auto-patched database pool

### Ollama (tests.fixtures.ollama)
- `mock_embed_query` - Mock embedding function with deterministic output
- `mock_code_to_embedding` - Backward-compatible alias for `mock_embed_query`

## Mocking Philosophy

1. Mock at module boundaries, not library internals
2. Use deterministic mocks (same input = same output)
3. Track mock calls for assertions
4. Reset state between tests
