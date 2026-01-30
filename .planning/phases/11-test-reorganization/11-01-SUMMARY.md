---
phase: 11-test-reorganization
plan: 01
subsystem: testing
tags: [pytest, markers, test-organization]

# Dependency graph
requires: []
provides:
  - tests/unit/ directory with auto-marking conftest.py
  - tests/integration/ directory with auto-marking conftest.py
  - pytest marker registration (unit, integration)
  - unmarked test warning hook
affects: [11-02, 11-03, 11-04, 11-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - pytest_collection_modifyitems hook for auto-marking
    - --strict-markers for marker discipline

key-files:
  created:
    - tests/unit/__init__.py
    - tests/unit/conftest.py
    - tests/integration/__init__.py
    - tests/integration/conftest.py
  modified:
    - pyproject.toml
    - tests/conftest.py

key-decisions:
  - "Auto-marking via conftest.py hooks rather than manual @pytest.mark decorators"
  - "UserWarning for unmarked tests rather than hard failure to allow gradual migration"

patterns-established:
  - "pytest_collection_modifyitems in directory conftest.py auto-applies markers based on path"
  - "REQUIRED_MARKERS set defines which markers tests must have"

# Metrics
duration: 3min
completed: 2026-01-30
---

# Phase 11 Plan 01: Test Directory Structure Summary

**pytest marker infrastructure with auto-marking conftest.py files for unit/integration test separation**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-30T14:38:00Z
- **Completed:** 2026-01-30T14:41:00Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Created tests/unit/ and tests/integration/ directories with auto-marking conftest.py hooks
- Registered unit and integration markers in pyproject.toml with --strict-markers
- Added unmarked test warning hook to root conftest.py for marker discipline
- Preserved all existing fixtures and pytest_plugins configuration

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test directory structure** - `1fb4b73` (feat)
2. **Task 2: Register pytest markers** - `128f14f` (feat)
3. **Task 3: Add unmarked test warning** - `3be5ad8` (feat)

## Files Created/Modified

- `tests/unit/__init__.py` - Unit test package marker
- `tests/unit/conftest.py` - Auto-applies pytest.mark.unit to all tests in /unit/
- `tests/integration/__init__.py` - Integration test package marker
- `tests/integration/conftest.py` - Auto-applies pytest.mark.integration to all tests in /integration/
- `pyproject.toml` - Registered markers, updated testpaths, added --strict-markers
- `tests/conftest.py` - Added warning hook for unmarked tests

## Decisions Made

- **Auto-marking via conftest.py hooks:** Tests placed in tests/unit/ or tests/integration/ automatically receive the appropriate marker without requiring explicit @pytest.mark decorators on each test
- **UserWarning for unmarked tests:** Chose warnings over hard failures to enable gradual migration of existing 327 tests

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Test directory structure ready for Plan 02 test migration
- `pytest -m unit` will target only unit tests once migrated
- `pytest -m integration` will target only integration tests once migrated
- Existing 327 tests still discoverable and runnable during migration

---
*Phase: 11-test-reorganization*
*Completed: 2026-01-30*
