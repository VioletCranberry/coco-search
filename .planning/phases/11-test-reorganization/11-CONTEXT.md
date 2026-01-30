# Phase 11: Test Reorganization - Context

**Gathered:** 2026-01-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Separate unit tests from integration tests with clear execution boundaries. Unit tests use mocks, integration tests use real infrastructure (PostgreSQL+pgvector, Ollama). Existing 327 unit tests move to new structure unchanged.

</domain>

<decisions>
## Implementation Decisions

### Directory Structure
- Two top-level directories: `tests/unit/` and `tests/integration/`
- Both mirror `src/` module structure (e.g., `tests/unit/indexing/`, `tests/integration/search/`)
- Layered conftest.py: shared fixtures in `tests/conftest.py`, specific fixtures in `tests/unit/conftest.py` and `tests/integration/conftest.py`

### Migration Approach
- Copy existing tests to `tests/unit/`, delete originals (clean slate over git history)
- All 327 existing tests are unit tests (they use mocks)

### Marker Strategy
- Both marker types required: `@pytest.mark.unit` and `@pytest.mark.integration`
- Unmarked tests should fail/warn (enforce discipline)
- Default `pytest` runs both unit and integration tests
- Skip integration via standard filtering: `pytest -m "not integration"`

### Execution Boundaries
- **Unit test** = uses mocks, no real infrastructure
- **Integration test** = uses real PostgreSQL, Ollama, or both

### Claude's Discretion
- Exact warning/error mechanism for unmarked tests (pytest hook vs CI check)
- conftest.py fixture organization details
- Any helper utilities needed for the migration

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 11-test-reorganization*
*Context gathered: 2026-01-30*
