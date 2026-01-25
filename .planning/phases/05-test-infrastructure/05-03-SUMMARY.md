---
phase: 05-test-infrastructure
plan: 03
subsystem: testing
tags: [pytest, mocking, ollama, embeddings, fixtures]

# Dependency graph
requires:
  - phase: 05-01
    provides: pytest configuration and test directory structure
provides:
  - deterministic embedding mock function
  - mock_code_to_embedding fixture for patching
  - SearchResult and config factory fixtures
  - 12 tests verifying mock infrastructure
affects: [05-04, 05-05, 06-unit-tests, 06-integration-tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - deterministic hash-based embedding mocks
    - factory fixtures for test data
    - pytest_plugins registration pattern

key-files:
  created:
    - tests/mocks/ollama.py
    - tests/fixtures/ollama.py
    - tests/fixtures/data.py
    - tests/test_ollama_mocks.py
  modified:
    - tests/conftest.py

key-decisions:
  - "Hash-based deterministic embeddings ensure same input = same output"
  - "Patch code_to_embedding in both embedder.py and query.py locations"
  - "Factory fixtures for SearchResult and config enable customizable test data"

patterns-established:
  - "deterministic_embedding(text, dimensions): hash-based fake embeddings"
  - "Factory fixture pattern: make_X returns function that creates X"
  - "Ready-to-use fixtures: sample_X provides default instance"

# Metrics
duration: 3min
completed: 2026-01-25
---

# Phase 5 Plan 03: Ollama Mocks and Data Fixtures Summary

**Deterministic embedding mocks using SHA256 hash, with factory fixtures for SearchResult and config data**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-25T22:12:19Z
- **Completed:** 2026-01-25T22:15:22Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Deterministic embedding generation producing consistent 768-dim vectors from text hash
- mock_code_to_embedding fixture that patches both embedder.py and query.py imports
- Factory fixtures for SearchResult, config dicts, and sample code content
- 12 passing tests verifying the mock infrastructure works correctly

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Ollama mock module** - `10b2740` (feat)
2. **Task 2: Create Ollama and data fixtures** - `6fd4114` (feat)
3. **Task 3: Verify Ollama mocking and data fixtures work** - `42bb73c` (test)

## Files Created/Modified

- `tests/mocks/ollama.py` - deterministic_embedding and similar_embedding functions
- `tests/fixtures/ollama.py` - mock_code_to_embedding and embedding_for fixtures
- `tests/fixtures/data.py` - SearchResult and config factory fixtures
- `tests/test_ollama_mocks.py` - 12 tests verifying mock infrastructure
- `tests/conftest.py` - Registered ollama and data fixture plugins
- `tests/mocks/__init__.py` - Package init (created)
- `tests/fixtures/__init__.py` - Package init (created)

## Decisions Made

- **Hash-based embeddings:** Used SHA256 hash cycling through bytes to fill 768 dimensions, ensuring determinism (same input = same output)
- **Dual patching:** mock_code_to_embedding patches both `cocosearch.indexer.embedder.code_to_embedding` and `cocosearch.search.query.code_to_embedding` to handle both import locations
- **Factory + ready-to-use pattern:** Each data type has both a `make_X` factory for custom creation and `sample_X` for simple tests

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created minimal test infrastructure**
- **Found during:** Pre-task analysis
- **Issue:** Plans 01-02 not yet executed, tests/ directory missing
- **Fix:** Created tests/, tests/mocks/, tests/fixtures/, tests/conftest.py with minimal structure
- **Files modified:** tests/__init__.py, tests/mocks/__init__.py, tests/fixtures/__init__.py, tests/conftest.py
- **Verification:** pytest discovers and runs tests successfully
- **Committed in:** 10b2740 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minimal test infrastructure required for plan execution. Consistent with plan 01 structure but created incrementally.

## Issues Encountered

- Linter/formatter was reverting conftest.py changes, had to re-apply pytest_plugins updates between commits

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ollama mocking infrastructure ready for search and indexer tests
- Data fixtures available for testing formatters and query handlers
- Full test suite passing (20 tests total)
- Ready for Plan 04 (MCP testing utilities) and Phase 6 unit tests

---
*Phase: 05-test-infrastructure*
*Completed: 2026-01-25*
