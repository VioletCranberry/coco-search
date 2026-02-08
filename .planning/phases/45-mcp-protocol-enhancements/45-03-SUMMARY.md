---
phase: 45-mcp-protocol-enhancements
plan: 03
subsystem: testing
tags: [mcp, async, pytest, pytest-asyncio, project-detection, roots, mock, asyncmock]

# Dependency graph
requires:
  - phase: 45-01
    provides: "project_detection.py with file_uri_to_path, _detect_project, register_roots_notification"
  - phase: 45-02
    provides: "Async search_code with ctx: Context and _detect_project integration"
provides:
  - "Comprehensive unit tests for project detection module (23 tests)"
  - "Fixed pre-existing test failures in TestIndexCodebase (register_index_path mock)"
  - "All search_code tests converted to async with ctx parameter across 3 test files"
  - "Autodetect tests rewritten with _detect_project AsyncMock + find_project_root dual-mock pattern"
affects: [45-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AsyncMock for _detect_project at cocosearch.mcp.project_detection._detect_project"
    - "Dual-mock pattern: _detect_project (AsyncMock) + find_project_root (sync Mock) for auto-detect tests"
    - "_make_mock_ctx() helper for creating minimal mock Context in each test file"
    - "make_mock_ctx() with configurable roots/request/error for project detection tests"

key-files:
  created:
    - tests/unit/mcp/test_project_detection.py
  modified:
    - tests/unit/mcp/test_server.py
    - tests/unit/mcp/test_server_context.py
    - tests/unit/mcp/test_server_autodetect.py

key-decisions:
  - "McpError constructor requires ErrorData(code, message), not a plain string"
  - "mock _detect_project at definition site (cocosearch.mcp.project_detection._detect_project), not import site"
  - "mock find_project_root at cocosearch.management.context.find_project_root (matches local import in server.py)"
  - "'No project detected' error removed in Plan 02; tests updated to expect 'Index not found' when find_project_root returns (None, None)"

patterns-established:
  - "Dual-mock pattern: all auto-detect tests mock both _detect_project and find_project_root at their exact module paths"
  - "_make_mock_ctx() helper in every test file that calls search_code"
  - "make_mock_ctx(has_roots, roots, roots_error, request) factory for project detection tests"

# Metrics
duration: 31min
completed: 2026-02-08
---

# Phase 45 Plan 03: Test Suite for Project Detection and Async search_code Summary

**23 new project detection tests, pre-existing failures fixed, all search_code tests converted to async across 4 test files (82 total MCP tests passing)**

## Performance

- **Duration:** 31 min
- **Started:** 2026-02-08T15:42:38Z
- **Completed:** 2026-02-08T16:13:23Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Created test_project_detection.py with 23 tests covering file_uri_to_path (7), _detect_project priority chain (15), and register_roots_notification (1)
- Fixed 2 pre-existing TestIndexCodebase failures by adding register_index_path mock
- Converted 14 search_code tests to async with ctx parameter in test_server.py and test_server_context.py
- Rewrote 10 autodetect tests with new dual-mock pattern (_detect_project AsyncMock + find_project_root sync Mock)
- Full MCP test suite: 82 tests, 0 failures

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test_project_detection.py** - `5a96298` (test)
2. **Task 2: Fix pre-existing failures and convert test_server.py + test_server_context.py to async** - `1b81464` (fix)
3. **Task 3: Rewrite test_server_autodetect.py mocks for _detect_project** - `a037363` (test)

## Files Created/Modified
- `tests/unit/mcp/test_project_detection.py` - New: 23 unit tests for project detection module (file_uri_to_path, _detect_project, register_roots_notification)
- `tests/unit/mcp/test_server.py` - Fixed register_index_path mock, converted 5 search_code tests to async
- `tests/unit/mcp/test_server_context.py` - Converted 9 search_code tests to async with ctx parameter
- `tests/unit/mcp/test_server_autodetect.py` - Rewrote 10 search_code tests with _detect_project AsyncMock dual-mock pattern

## Decisions Made
- McpError requires ErrorData object (not plain string) -- discovered during test and fixed immediately
- Mock targets use exact module paths: `cocosearch.mcp.project_detection._detect_project` (definition site) and `cocosearch.management.context.find_project_root` (local import target)
- Old "No project detected" error no longer exists after Plan 02 (cwd is unconditional fallback); autodetect tests updated to expect "Index not found" when find_project_root returns (None, None)
- _make_mock_ctx() helper duplicated in each test file for self-contained test modules

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] McpError constructor requires ErrorData, not string**
- **Found during:** Task 1 (test_handles_mcp_error_gracefully)
- **Issue:** McpError("test error") raises AttributeError; constructor expects ErrorData(code, message)
- **Fix:** Changed to McpError(ErrorData(code=-1, message="test error"))
- **Files modified:** tests/unit/mcp/test_project_detection.py
- **Verification:** Test passes, McpError handled gracefully
- **Committed in:** 5a96298 (Task 1 commit)

**2. [Rule 1 - Bug] "No project detected" error removed in Plan 02**
- **Found during:** Task 3 (rewriting autodetect tests)
- **Issue:** Old tests expected "No project detected" error response, but Plan 02 removed this flow -- _detect_project always returns a valid path (cwd fallback)
- **Fix:** Updated test_returns_error_when_no_project and test_no_project_error_format to test the new flow: _detect_project returns cwd, find_project_root returns (None, None), resulting in "Index not found" error
- **Files modified:** tests/unit/mcp/test_server_autodetect.py
- **Verification:** Tests pass and correctly validate the new error path
- **Committed in:** a037363 (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for correct test behavior. No scope creep.

## Issues Encountered
- Pre-existing test failure in tests/unit/test_cli.py::TestIndexCommand::test_valid_path_runs_indexing (unrelated to MCP, caused by missing register_index_path mock for CLI tests -- not in scope for this plan)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 82 MCP tests pass with zero failures across 4 test files
- Test infrastructure established: make_mock_ctx(), _make_mock_ctx(), dual-mock pattern for auto-detect
- Ready for Plan 04 if additional MCP protocol enhancements are planned
- Mock patterns documented for future test authors

---
*Phase: 45-mcp-protocol-enhancements*
*Completed: 2026-02-08*
