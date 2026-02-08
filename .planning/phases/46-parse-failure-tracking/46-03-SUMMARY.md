---
phase: 46-parse-failure-tracking
plan: 03
subsystem: mcp-api-testing
tags: [mcp, http-api, parse-tracking, tree-sitter, pytest, unit-tests]

# Dependency graph
requires:
  - phase: 46-01
    provides: parse_tracking.py with detect_parse_status(), _collect_error_lines()
  - phase: 46-02
    provides: get_parse_stats(), get_parse_failures(), IndexStats.parse_stats field
provides:
  - MCP index_stats tool with comprehensive stats and include_failures parameter
  - HTTP /api/stats and /api/stats/{index_name} with include_failures query parameter
  - test_parse_tracking.py with 13 tests covering all parse status categories
  - TestGetParseStats, TestGetParseFailures, TestIndexStatsWithParseStats test classes
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "include_failures opt-in pattern: MCP bool parameter and HTTP query string for optional detail inclusion"

key-files:
  created:
    - tests/unit/indexer/test_parse_tracking.py
  modified:
    - src/cocosearch/mcp/server.py
    - tests/unit/management/test_stats.py
    - tests/unit/test_cli.py

key-decisions:
  - "Top-level import for get_parse_failures in server.py (consistent with get_comprehensive_stats import style)"
  - "MCP index_stats upgraded from get_stats() to get_comprehensive_stats() for richer data including parse_stats"
  - "cocoindex.init() added to index_stats tool since get_comprehensive_stats requires DB access"

patterns-established:
  - "include_failures pattern: bool param on MCP tool, query string on HTTP endpoint, both optional defaulting to false"

# Metrics
duration: 17min
completed: 2026-02-08
---

# Phase 46 Plan 03: Test Suite Summary

**MCP/HTTP endpoint updates with parse stats and include_failures parameter, plus 21 new unit tests covering parse tracking detection, stats aggregation, and failure queries**

## Performance

- **Duration:** 17 min
- **Started:** 2026-02-08T17:43:44Z
- **Completed:** 2026-02-08T18:00:48Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Updated MCP index_stats tool from basic get_stats() to comprehensive get_comprehensive_stats(), now returns parse_stats
- Added include_failures parameter to MCP tool and HTTP endpoints for optional file-level failure details
- Created test_parse_tracking.py with 13 tests covering ok/partial/error/unsupported detection and _collect_error_lines
- Added 8 tests to test_stats.py: TestGetParseStats (4), TestGetParseFailures (2), TestIndexStatsWithParseStats (2)
- Fixed regression in test_cli.py where IndexStats constructor was missing parse_stats field and show_failures arg

## Task Commits

Each task was committed atomically:

1. **Task 1: Update MCP index_stats tool and HTTP /api/stats endpoint with parse stats** - `bc971fa` (feat)
2. **Task 2: Add tests for parse_tracking module and parse stats functions** - `0fa4f47` (test)

## Files Created/Modified
- `src/cocosearch/mcp/server.py` - Updated index_stats to use get_comprehensive_stats, added include_failures to MCP tool and HTTP endpoints
- `tests/unit/indexer/test_parse_tracking.py` - New: 13 tests for detect_parse_status and _collect_error_lines
- `tests/unit/management/test_stats.py` - Added TestGetParseStats, TestGetParseFailures, TestIndexStatsWithParseStats; updated existing IndexStats tests with parse_stats={}
- `tests/unit/test_cli.py` - Fixed test_specific_index_json: added parse_stats={} and show_failures=False to mock args

## Decisions Made
- Used top-level import for get_parse_failures in server.py (consistent with existing import style for get_comprehensive_stats)
- MCP index_stats tool now calls cocoindex.init() since get_comprehensive_stats requires DB access (the old get_stats() also needed it but was handled differently)
- include_failures defaults to False on both MCP and HTTP to keep default responses lean

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_specific_index_json in test_cli.py**
- **Found during:** Task 2 (running full unit test suite)
- **Issue:** IndexStats constructor missing parse_stats field (added in plan 02) and argparse.Namespace missing show_failures attribute (also added in plan 02)
- **Fix:** Added parse_stats={} to IndexStats constructor and show_failures=False to Namespace
- **Files modified:** tests/unit/test_cli.py
- **Verification:** Test passes after fix
- **Committed in:** 0fa4f47 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Pre-existing regression from plan 02 that wasn't caught. Essential fix for test correctness.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 46 (Parse Failure Tracking) is fully complete
- All three plans delivered: foundation, stats display, test suite + endpoint integration
- Pre-existing test failure (test_valid_path_runs_indexing) remains as documented in STATE.md

---
*Phase: 46-parse-failure-tracking*
*Completed: 2026-02-08*
