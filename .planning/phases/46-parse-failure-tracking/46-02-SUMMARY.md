---
phase: 46-parse-failure-tracking
plan: 02
subsystem: management-cli
tags: [stats, parse-tracking, cli, rich-tables, json-api]

# Dependency graph
requires:
  - phase: 46-01
    provides: parse_results table with per-file parse status data
provides:
  - get_parse_stats() for per-language parse status aggregation
  - get_parse_failures() for individual file failure details
  - IndexStats.parse_stats field in get_comprehensive_stats()
  - CLI parse health display (format_parse_health, format_parse_failures)
  - --show-failures CLI flag for detailed failure output
affects: [46-03 test-suite]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Graceful degradation: empty dict {} for pre-v46 indexes without parse_results table"
    - "Color-coded health display: green >= 95%, yellow >= 80%, red < 80%"
    - "--show-failures opt-in pattern for verbose failure detail output"

key-files:
  created: []
  modified:
    - src/cocosearch/management/stats.py
    - src/cocosearch/management/__init__.py
    - src/cocosearch/cli.py

key-decisions:
  - "Parse health shown by default when available (not gated by --verbose)"
  - "Failure details require explicit --show-failures flag (keeps default output clean)"
  - "JSON output includes parse_stats via to_dict(); parse_failures added only with --show-failures"

patterns-established:
  - "Table existence check before querying optional tables (graceful degradation pattern)"
  - "Color-coded percentage display pattern for health metrics"

# Metrics
duration: 3min
completed: 2026-02-08
---

# Phase 46 Plan 02: Stats Display Summary

**Parse stats aggregation layer with per-language breakdown queries, IndexStats extension, and CLI display with color-coded health percentage and --show-failures flag**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-08T17:38:49Z
- **Completed:** 2026-02-08T17:41:57Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added get_parse_stats() that aggregates parse_results table by language with ok/partial/error/unsupported counts and overall health percentage
- Added get_parse_failures() that returns individual file failure details for non-ok parse statuses
- Extended IndexStats dataclass with parse_stats field, automatically serialized via asdict()
- Updated get_comprehensive_stats() to populate parse_stats from get_parse_stats()
- Added format_parse_health() with color-coded summary line and Rich per-language table
- Added format_parse_failures() with file-level failure detail table
- Added --show-failures flag to stats CLI parser
- Parse health displayed in both single-index and --all output modes
- JSON output includes parse_stats; --show-failures adds parse_failures to JSON

## Task Commits

Each task was committed atomically:

1. **Task 1: Add parse stats query functions and extend IndexStats** - `4abdfc6` (feat)
2. **Task 2: Update CLI stats_command with parse health display and --show-failures** - `ae66900` (feat)

## Files Created/Modified
- `src/cocosearch/management/stats.py` - Added get_parse_stats(), get_parse_failures(), parse_stats field on IndexStats, updated get_comprehensive_stats()
- `src/cocosearch/management/__init__.py` - Exported get_parse_stats and get_parse_failures
- `src/cocosearch/cli.py` - Added format_parse_health(), format_parse_failures(), --show-failures flag, parse health in stats output

## Decisions Made
- Parse health is shown by default when parse_stats is non-empty (not gated behind --verbose), since it is a primary metric users should always see
- Failure details require explicit --show-failures flag to keep default output clean
- JSON output always includes parse_stats via to_dict(); parse_failures only included when --show-failures is passed
- Pre-v46 indexes return empty dict from get_parse_stats(), which causes no display (silent graceful degradation)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Stats aggregation and CLI display complete
- Ready for 46-03 (test suite) to add unit tests for get_parse_stats(), get_parse_failures(), and CLI formatting functions
- All query functions use table existence checks for graceful degradation testing

---
*Phase: 46-parse-failure-tracking*
*Completed: 2026-02-08*
