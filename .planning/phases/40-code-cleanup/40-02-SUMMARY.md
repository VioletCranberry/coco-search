---
phase: 40-code-cleanup
plan: 02
subsystem: search
tags: [postgresql, vector-search, hybrid-search, metadata, schema-migration]

# Dependency graph
requires:
  - phase: 40-01
    provides: Removed deprecated re-export modules (languages.py, metadata.py)
provides:
  - Search modules simplified by removing ~100 LOC of v1.2 graceful degradation code
  - Fail-fast behavior for pre-v1.2 indexes instead of silent degradation
  - Clearer distinction between v1.2 requirements (mandatory) and v1.7 features (optional)
affects: [search, indexing, error-handling]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fail-fast for unsupported schema versions instead of graceful degradation"
    - "Clear separation between mandatory columns (v1.2+) and optional features (v1.7+)"

key-files:
  created: []
  modified:
    - src/cocosearch/search/query.py
    - src/cocosearch/search/hybrid.py
    - src/cocosearch/search/db.py
    - src/cocosearch/management/stats.py
    - tests/unit/search/test_query.py

key-decisions:
  - "Removed pre-v1.2 graceful degradation - metadata columns now required"
  - "Preserved v1.7 feature detection for content_text and symbol columns"
  - "Removed TestGracefulDegradation test class testing deprecated behavior"

patterns-established:
  - "Feature detection for v1.7+ columns (content_text, symbol_type) remains active"
  - "Pre-v1.2 indexes fail with clear SQL error directing users to re-index"

# Metrics
duration: 3min
completed: 2026-02-06
---

# Phase 40 Plan 02: Remove v1.2 Graceful Degradation Summary

**Removed ~100 LOC of pre-v1.2 backward compatibility code from search modules, replacing silent degradation with fail-fast errors**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-06T08:25:14Z
- **Completed:** 2026-02-06T08:28:54Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- Removed module-level flags and try/except fallback for missing metadata columns
- Search functions now assume block_type, hierarchy, and language_id columns exist
- Preserved v1.7 feature detection for content_text (hybrid search) and symbol columns
- All 1018 tests pass after cleanup

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove pre-v1.2 graceful degradation from query.py** - `d55c239` (refactor)
2. **Task 2: Remove pre-v1.2 graceful degradation from hybrid.py** - `db7cc4b` (refactor)
3. **Task 3: Update stats.py and db.py, run full verification** - `be5b541` (refactor)

## Files Created/Modified
- `src/cocosearch/search/query.py` - Removed _has_metadata_columns flag, DevOps check, try/except UndefinedColumn fallback
- `src/cocosearch/search/hybrid.py` - Removed pre-v1.2 fallback from execute_vector_search()
- `src/cocosearch/search/db.py` - Updated check_column_exists() docstring for clarity
- `src/cocosearch/management/stats.py` - Clarified v1.7 feature detection comments
- `tests/unit/search/test_query.py` - Removed TestGracefulDegradation class (4 tests)

## Decisions Made

**1. Removed pre-v1.2 backward compatibility entirely**
- Metadata columns (block_type, hierarchy, language_id) now required
- Pre-v1.2 indexes fail fast with SQL UndefinedColumn error
- Rationale: v1.2 was released months ago, simplifies codebase by ~100 LOC

**2. Preserved v1.7 feature detection**
- content_text column check for hybrid search remains (warns + falls back to vector-only)
- symbol_type/symbol_name/symbol_signature checks for symbol filtering remain
- Rationale: v1.7 features are enhancements, not core requirements

**3. Removed TestGracefulDegradation test class**
- 4 tests specifically for pre-v1.2 behavior removed
- Rationale: Tests for deprecated functionality no longer relevant

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for phase 40-03 (remove unused handlers and utilities).

**Notes:**
- ~100 LOC removed from search modules
- Code is simpler and easier to maintain
- Error messages direct users to re-index for old schemas
- v1.7 feature detection preserved for optional enhancements

## Self-Check: PASSED

All files and commits verified.

---
*Phase: 40-code-cleanup*
*Completed: 2026-02-06*
