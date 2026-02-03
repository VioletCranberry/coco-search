---
phase: 32-full-language-coverage-documentation
plan: 02
subsystem: management
tags: [cli, stats, sql, aggregation, language-stats]

# Dependency graph
requires:
  - phase: 30-symbol-aware-search
    provides: language_id column in index tables
provides:
  - Per-language statistics aggregation function
  - Enhanced stats CLI with language breakdown
  - JSON output with languages array
affects: [documentation, cli-ux]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - SQL GROUP BY aggregation for per-language stats
    - Graceful degradation for pre-v1.7 indexes

key-files:
  created: []
  modified:
    - src/cocosearch/management/stats.py
    - src/cocosearch/management/__init__.py
    - src/cocosearch/cli.py

key-decisions:
  - "Use SQL GROUP BY at database level for efficient per-language aggregation"
  - "Check content_text column existence to detect v1.7+ indexes"
  - "Display N/A for line counts on pre-v1.7 indexes (graceful degradation)"
  - "Add TOTAL row at bottom of table summing all languages"
  - "JSON output includes languages array in response object"

patterns-established:
  - "Column existence checks for feature detection (v1.7+ vs pre-v1.7)"
  - "Rich table with section separator for totals row"
  - "Summary line + detailed table format for CLI output"

# Metrics
duration: 2min 46sec
completed: 2026-02-03
---

# Phase 32 Plan 02: Per-Language Statistics Summary

**Per-language stats with SQL aggregation showing files/chunks/lines breakdown for each language in codebase**

## Performance

- **Duration:** 2 minutes 46 seconds
- **Started:** 2026-02-03T14:36:44Z
- **Completed:** 2026-02-03T14:39:29Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- SQL GROUP BY aggregation for efficient per-language statistics
- Enhanced stats CLI showing Language, Files, Chunks, Lines columns
- TOTAL row summing all languages at bottom of table
- JSON output includes languages array with per-language data
- Graceful degradation for pre-v1.7 indexes (N/A for line counts)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add get_language_stats function** - `976a0c7` (feat)
2. **Task 2: Update stats CLI for per-language display** - `a4efeb3` (feat)

## Files Created/Modified
- `src/cocosearch/management/stats.py` - Added get_language_stats function with SQL GROUP BY aggregation
- `src/cocosearch/management/__init__.py` - Exported get_language_stats
- `src/cocosearch/cli.py` - Updated stats_command to show per-language table

## Decisions Made

1. **SQL GROUP BY aggregation** - Implemented aggregation at database level using SQL GROUP BY for efficiency instead of fetching all rows and aggregating in Python

2. **Content_text column detection** - Check for content_text column existence to detect v1.7+ indexes, enabling graceful degradation for older indexes

3. **TOTAL row format** - Added Rich table section separator before TOTAL row for visual clarity

4. **Summary + detail layout** - Show summary stats (Files, Chunks, Size) in dim text before detailed per-language table for context

5. **JSON structure** - Include languages array directly in stats response object (flat structure, not nested)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - implementation proceeded smoothly with SQL GROUP BY for aggregation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Per-language statistics complete
- Ready for language detection documentation (plan 32-03)
- Stats command provides visibility into codebase language composition
- Graceful degradation ensures backward compatibility with pre-v1.7 indexes

---
*Phase: 32-full-language-coverage-documentation*
*Completed: 2026-02-03*
