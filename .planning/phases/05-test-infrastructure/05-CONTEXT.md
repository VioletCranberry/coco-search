# Phase 5: Test Infrastructure - Context

**Gathered:** 2026-01-25
**Status:** Ready for planning

<domain>
## Phase Boundary

pytest configured with mocking infrastructure for isolated testing. Tests can run without real PostgreSQL or Ollama. Common fixtures available for typical test scenarios.

</domain>

<decisions>
## Implementation Decisions

### Fixture design
- Dedicated fixtures module: `tests/fixtures/` directory with importable fixtures
- Mock database returns canned responses (predefined test data), not in-memory state tracking
- Both factory functions and ready-to-use objects: factories for complex cases, ready objects for simple
- Embeddings are deterministic: same input always returns same fake embedding (hash-based or similar)

### Mocking approach
- Dedicated mock modules: `tests/mocks/db.py`, `tests/mocks/ollama.py` — reusable across tests
- PostgreSQL mock at db module level: mock `search.db.search_files()` etc., not low-level asyncpg
- Ollama mock at HTTP level: mock httpx/aiohttp responses for fake API behavior
- Mocks track and assert call patterns — verify how they were called, not just return values

### Test organization
- Flat structure: all test files in `tests/` directory — simple and searchable
- `tests/data/` directory for test data (sample files, expected outputs)
- Include `tests/README.md` documenting conventions, how to run, what fixtures exist

### Async test patterns
- Use pytest-asyncio with `@pytest.mark.asyncio` markers
- Function-scoped event loops: new loop per test for isolation
- Native async fixtures via pytest-asyncio support
- Explicit marking required (not auto mode) — `@pytest.mark.asyncio` on each async test

### Claude's Discretion
- Test file naming convention (based on module complexity)
- Exact structure of mock response data
- Helper utilities organization

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-test-infrastructure*
*Context gathered: 2026-01-25*
