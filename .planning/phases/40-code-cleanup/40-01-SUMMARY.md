---
phase: 40-code-cleanup
plan: 01
subsystem: codebase-maintenance
tags: [code-cleanup, refactor, deprecated-code-removal, python]

# Dependency graph
requires:
  - phase: 21-language-chunking-refactor
    provides: Handler architecture with HclHandler, DockerfileHandler, BashHandler
  - phase: 08-custom-language-definitions
    provides: Original language spec constants that were later moved to handlers
provides:
  - Removed deprecated re-export modules (languages.py, metadata.py)
  - Tests import directly from cocosearch.handlers
  - Cleaner import paths without backward-compatibility shims
affects: [41-documentation-polish, 42-final-verification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Direct imports from handlers instead of indexer re-exports"
    - "Test helpers defined locally when testing deprecated interfaces"

key-files:
  created: []
  modified:
    - tests/unit/indexer/test_languages.py
    - tests/unit/indexer/test_metadata.py
    - tests/unit/indexer/test_flow.py
    - src/cocosearch/indexer/__init__.py
    - src/cocosearch/indexer/flow.py
  deleted:
    - src/cocosearch/indexer/languages.py
    - src/cocosearch/indexer/metadata.py

key-decisions:
  - "Removed DevOpsMetadata from indexer __all__ exports (backward-compat wrapper no longer public API)"
  - "Tests that need DevOpsMetadata now define local dataclass rather than importing from deprecated module"
  - "Fixed unused import (extract_extension) discovered during lint check"

patterns-established:
  - "Import from canonical source (cocosearch.handlers) not from re-export shims"
  - "Local test helpers for testing deprecated interfaces without keeping deprecated code"

# Metrics
duration: 2min
completed: 2026-02-05
---

# Phase 40 Plan 01: Remove Deprecated Re-exports Summary

**Removed 137 lines of deprecated re-export code (languages.py and metadata.py modules), tests now import directly from handlers**

## Performance

- **Duration:** 2 min 25 sec
- **Started:** 2026-02-05T21:16:25Z
- **Completed:** 2026-02-05T21:18:50Z
- **Tasks:** 2 (Task 3 was verification-only)
- **Files modified:** 5
- **Files deleted:** 2

## Accomplishments
- Deleted deprecated backward-compatibility modules (137 LOC)
- Updated all test imports to use canonical handler imports
- Verified full test suite passes after removal
- Cleaned up unused imports discovered during removal

## Task Commits

Each task was committed atomically:

1. **Task 1: Update test imports to use handlers directly** - `db675cc` (refactor)
2. **Task 2: Update indexer __init__.py and remove deprecated modules** - `a6c90a0` (refactor)

_Task 3 was verification-only (run full test suite, verify LOC reduction, check lint)_

## Files Created/Modified

**Modified:**
- `tests/unit/indexer/test_languages.py` - Import from handlers, get constants from handler classes
- `tests/unit/indexer/test_metadata.py` - Define local test helpers, import from handlers
- `tests/unit/indexer/test_flow.py` - Import get_custom_languages() from handlers
- `src/cocosearch/indexer/__init__.py` - Import extract_devops_metadata from handlers, remove DevOpsMetadata from exports
- `src/cocosearch/indexer/flow.py` - Remove unused extract_extension import

**Deleted:**
- `src/cocosearch/indexer/languages.py` (26 lines) - Backward-compatibility re-exports
- `src/cocosearch/indexer/metadata.py` (111 lines) - Backward-compatibility re-exports and wrapper

## Decisions Made

**1. DevOpsMetadata no longer exported from indexer module**
- Rationale: It was a backward-compatibility wrapper around handler dict results. Tests that need it define local dataclass.

**2. Tests define local helpers instead of importing from deprecated module**
- Rationale: test_metadata.py tests the old interface behavior, so it creates local versions of extraction functions that wrap handler calls. This preserves test coverage without keeping production code.

**3. Fixed unused import during removal**
- Rationale: Lint check revealed extract_extension was unused in flow.py. Removed as part of cleanup (Rule 1 - auto-fix).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug/Cleanup] Removed unused import in flow.py**
- **Found during:** Task 2 (lint check after removal)
- **Issue:** extract_extension imported but unused in flow.py
- **Fix:** Removed from import statement
- **Files modified:** src/cocosearch/indexer/flow.py
- **Verification:** ruff check passed
- **Committed in:** a6c90a0 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (cleanup)
**Impact on plan:** Minor cleanup discovered during lint check. No scope creep.

## Issues Encountered

None - removal proceeded smoothly. All tests passed after updates.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for next cleanup tasks:**
- Deprecated modules removed successfully
- LOC baseline: 9,274 → 9,138 (136 lines removed net, accounting for test helper code added)
- Test suite fully passing (1022 tests)
- No references to deleted modules remain in source code

**Notes for future cleanup plans:**
- schema_migration.py is NOT deprecated migration code - it's necessary PostgreSQL-specific schema enhancements (TSVECTOR columns, GIN indexes that CocoIndex can't create). Keep this module.
- V1.2 graceful degradation code patterns need discovery (grep for defensive column checks, old schema fallbacks)

---
*Phase: 40-code-cleanup*
*Completed: 2026-02-05*
