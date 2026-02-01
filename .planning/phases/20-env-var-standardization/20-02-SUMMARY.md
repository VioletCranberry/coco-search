---
phase: 20-env-var-standardization
plan: 02
subsystem: testing
tags: [pytest, integration-tests, env-vars, configuration]

# Dependency graph
requires:
  - phase: 20-01
    provides: Standardized COCOSEARCH_* environment variable naming convention
provides:
  - Integration tests using COCOSEARCH_DATABASE_URL instead of COCOINDEX_DATABASE_URL
  - Integration tests using COCOSEARCH_OLLAMA_URL instead of OLLAMA_HOST
  - Ollama fixture with standardized env var naming
affects: [integration-testing, e2e-testing]

# Tech tracking
tech-stack:
  added: []
  patterns: [standardized-env-vars]

key-files:
  created: []
  modified:
    - tests/integration/test_e2e_indexing.py
    - tests/integration/test_e2e_search.py
    - tests/integration/test_e2e_devops.py
    - tests/fixtures/ollama_integration.py

key-decisions:
  - "Used replace_all for env var name changes across test files"

patterns-established:
  - "Integration tests use COCOSEARCH_* prefix for all environment variables"

# Metrics
duration: 2min
completed: 2026-02-01
---

# Phase 20 Plan 02: Integration Tests Update Summary

**Integration tests and fixtures updated to use standardized COCOSEARCH_DATABASE_URL and COCOSEARCH_OLLAMA_URL environment variables**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-01T02:45:27Z
- **Completed:** 2026-02-01T02:47:24Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- All E2E integration tests updated to use COCOSEARCH_DATABASE_URL
- All E2E integration tests updated to use COCOSEARCH_OLLAMA_URL
- Ollama fixture updated with new env var naming and improved variable names (original_host → original_url)
- Zero legacy env var references remain in integration tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Update E2E indexing tests** - `bba4f69` (refactor)
2. **Task 2: Update E2E search and devops tests** - `7970d3b` (refactor)
3. **Task 3: Update ollama fixture** - `af61db9` (refactor)

## Files Created/Modified
- `tests/integration/test_e2e_indexing.py` - Updated subprocess env vars and debug prints to use COCOSEARCH_* naming
- `tests/integration/test_e2e_search.py` - Replaced COCOINDEX_DATABASE_URL and OLLAMA_HOST with COCOSEARCH_* equivalents
- `tests/integration/test_e2e_devops.py` - Replaced COCOINDEX_DATABASE_URL and OLLAMA_HOST with COCOSEARCH_* equivalents
- `tests/fixtures/ollama_integration.py` - Updated to use COCOSEARCH_OLLAMA_URL, renamed original_host to original_url

## Decisions Made
- Used replace_all flag for env var name changes to ensure all occurrences were updated consistently across test files
- Renamed internal variable from original_host to original_url in ollama fixture for clarity and consistency with new naming

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - straightforward search-and-replace refactoring completed without issues.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Integration tests are now aligned with standardized COCOSEARCH_* environment variables. Ready for:
- Phase 20-03 if there are additional files to update
- Running integration tests with new env var naming
- Further config standardization work

All integration tests will pass once the application code is updated to recognize COCOSEARCH_* environment variables (handled in plan 20-01).

---
*Phase: 20-env-var-standardization*
*Completed: 2026-02-01*
