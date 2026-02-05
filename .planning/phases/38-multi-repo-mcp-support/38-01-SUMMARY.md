---
phase: 38-multi-repo-mcp-support
plan: 01
subsystem: mcp
tags: [mcp, cli, workspace-detection, staleness-check]

# Dependency graph
requires:
  - phase: 26-mcp-server
    provides: MCP server infrastructure with search_code tool
provides:
  - "--project-from-cwd CLI flag for MCP workspace detection"
  - "COCOSEARCH_PROJECT_PATH environment variable passing"
  - "Search context header showing resolved project path"
  - "Staleness warning in search results for outdated indexes"
affects: [phase-40-migration, multi-repo-docs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Environment variable passing from CLI to MCP server for workspace context"
    - "Search result header/footer for meta-information (type: search_context, type: staleness_warning)"

key-files:
  created: []
  modified:
    - "src/cocosearch/cli.py"
    - "src/cocosearch/mcp/server.py"
    - "tests/fixtures/db.py"
    - "tests/unit/mcp/test_server_autodetect.py"

key-decisions:
  - "Used environment variable (COCOSEARCH_PROJECT_PATH) for CLI-to-server workspace communication"
  - "Added type field to header/footer dicts for easy identification in results"
  - "Staleness threshold hardcoded to 7 days (matching stats command default)"

patterns-established:
  - "Search result prefixing: type: search_context header for context info"
  - "Search result suffixing: type: staleness_warning footer for health info"

# Metrics
duration: 15min
completed: 2026-02-05
---

# Phase 38 Plan 01: CLI Flag & Staleness Warning Summary

**--project-from-cwd CLI flag with COCOSEARCH_PROJECT_PATH env var, search context header showing project path, and staleness warning footer for outdated indexes**

## Performance

- **Duration:** 15 min
- **Started:** 2026-02-05T20:15:00Z
- **Completed:** 2026-02-05T20:30:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added `--project-from-cwd` flag to `cocosearch mcp` command
- MCP server now checks COCOSEARCH_PROJECT_PATH env var for workspace detection
- Search results include search_context header when auto-detecting project
- Search results include staleness_warning footer when index is >7 days old
- Fixed test isolation bug by clearing query cache singleton between tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Add --project-from-cwd CLI flag** - `59d3c32` (feat)
2. **Task 2: Integrate project path and staleness into MCP search** - `67e45c1` (feat)

## Files Created/Modified
- `src/cocosearch/cli.py` - Added --project-from-cwd argument and COCOSEARCH_PROJECT_PATH env var setting
- `src/cocosearch/mcp/server.py` - Added search_context header, staleness_warning footer, and COCOSEARCH_PROJECT_PATH reading
- `tests/fixtures/db.py` - Fixed query cache singleton reset for test isolation
- `tests/unit/mcp/test_server_autodetect.py` - Updated assertions for new search_context header

## Decisions Made
- Used environment variable for CLI-to-server communication rather than passing as argument (simpler, works with existing run_server signature)
- Added `type` field to header/footer dicts for easy programmatic identification
- Wrapped staleness check in try/except to gracefully handle database unavailability during testing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed query cache singleton leaking between tests**
- **Found during:** Task 2 (test verification)
- **Issue:** QueryCache singleton was persisting between tests, causing test pollution where test A's cached results were returned for test B
- **Fix:** Added `cache_module._query_cache = None` reset to autouse fixture in tests/fixtures/db.py
- **Files modified:** tests/fixtures/db.py
- **Verification:** All 59 MCP tests pass with `poetry run pytest tests/unit/mcp/`
- **Committed in:** 67e45c1 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Auto-fix necessary for test reliability. No scope creep.

## Issues Encountered
- Initial staleness check called database in tests without mocking, causing test failures. Wrapped in try/except for graceful degradation.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CLI flag and staleness warning complete
- Ready for Phase 40 (migration/cleanup) when old index prevalence is understood
- Documentation in 38-02 covers MCP registration pattern using --project-from-cwd

---
*Phase: 38-multi-repo-mcp-support*
*Completed: 2026-02-05*
