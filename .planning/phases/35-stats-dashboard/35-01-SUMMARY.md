---
phase: 35-stats-dashboard
plan: 01
subsystem: observability
tags: [cli, statistics, rich, visualization, monitoring]

# Dependency graph
requires:
  - phase: 34-symbol-extraction-expansion
    provides: symbol_type column in index tables for enhanced stats
provides:
  - IndexStats dataclass with comprehensive health metrics
  - CLI stats command with visual output (Unicode bars, warning banners)
  - JSON output mode for automation/monitoring tools
  - Staleness detection and warning system
  - Symbol type statistics (function, class, method counts)
affects: [36-skill-routing, monitoring, observability]

# Tech tracking
tech-stack:
  added: [rich.bar, rich.panel]
  patterns: [dataclass-based stats aggregation, graceful degradation for old indexes]

key-files:
  created: [tests/unit/management/test_stats.py]
  modified: [src/cocosearch/management/stats.py, src/cocosearch/cli.py]

key-decisions:
  - "Use IndexStats dataclass to aggregate all health metrics in one place"
  - "Graceful degradation: symbol stats return empty dict for pre-v1.7 indexes"
  - "Staleness threshold defaults to 7 days, configurable via --staleness-threshold flag"
  - "Visual output as default (--pretty), JSON via explicit --json flag"
  - "Warning banner displays BEFORE stats output for visibility"

patterns-established:
  - "Stats collection follows get_comprehensive_stats() → IndexStats pattern"
  - "Rich UI components (Panel, Table, Bar) for visual CLI output"
  - "Auto-detect index from cwd when not specified (consistency with search command)"

# Metrics
duration: 7 min
completed: 2026-02-04
---

# Phase 35 Plan 01: Stats Dashboard Summary

**Visual index health dashboard with Unicode bar charts, staleness warnings, symbol statistics, and JSON export for monitoring**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-04T00:53:01+04:00
- **Completed:** 2026-02-04T01:00:28+04:00
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- IndexStats dataclass captures all health metrics: files, chunks, size, timestamps, staleness, languages, symbols, warnings
- Visual CLI output with Unicode bar charts showing per-language distribution
- Warning banner prominently displays index health issues (staleness, missing metadata)
- Symbol type statistics available in verbose mode (-v flag)
- JSON output mode (--json) for automation and monitoring integration
- Auto-detect index from current working directory (consistent with search command)
- Graceful degradation for pre-v1.7 indexes without symbol_type column
- 25 comprehensive unit tests covering all new functionality

## Task Commits

Each task was committed atomically:

1. **Task 1: Create IndexStats dataclass and comprehensive stats collection** - `c1440f1` (feat)
   - IndexStats dataclass with all health metric fields
   - check_staleness() function detecting stale indexes (>7 days)
   - get_symbol_stats() for symbol type counts with graceful degradation
   - collect_warnings() for index health warnings
   - get_comprehensive_stats() combining all stats into single object
   - to_dict() method for JSON serialization with datetime handling

2. **Task 2: Enhance CLI stats command with visual output and new flags** - `99b44c0` (feat)
   - Added -v/--verbose, --json, --all, --staleness-threshold CLI flags
   - Auto-detect index from cwd when not specified
   - print_warnings() displays warning banner with rich.Panel
   - format_language_table() creates Unicode bar charts with rich.Bar
   - format_symbol_table() shows symbol type breakdown
   - Summary header with timestamps and days-since-update

3. **Task 3: Add unit tests for new stats functionality** - `128bab8` (test)
   - TestIndexStats: dataclass instantiation, to_dict(), datetime serialization
   - TestCheckStaleness: staleness detection, threshold boundaries, missing metadata
   - TestGetSymbolStats: symbol counts, graceful degradation, empty handling
   - TestCollectWarnings: warning generation, multiple warnings
   - TestFormatBytes: edge cases (0 bytes, KB/MB/GB boundaries)
   - All 25 tests passing

## Files Created/Modified

- `src/cocosearch/management/stats.py` (+264 lines) - IndexStats dataclass, check_staleness(), get_symbol_stats(), collect_warnings(), get_comprehensive_stats()
- `src/cocosearch/cli.py` (+199 lines, -82 lines refactored) - Enhanced stats_command with visual output, print_warnings(), format_language_table(), format_symbol_table()
- `src/cocosearch/management/__init__.py` (+1 export) - Export get_comprehensive_stats for CLI
- `tests/unit/management/test_stats.py` (+276 lines) - Comprehensive unit test suite

## Decisions Made

1. **IndexStats dataclass aggregation** - Centralize all health metrics in single dataclass for consistent access pattern and JSON serialization
2. **Graceful degradation strategy** - Return empty dict for symbol stats on pre-v1.7 indexes rather than errors, maintaining backward compatibility
3. **Default staleness threshold of 7 days** - Balance between too-aggressive warnings and catching truly stale indexes; configurable via CLI flag
4. **Visual output as default** - Users benefit more from visual dashboard than JSON; explicit --json flag for automation use cases
5. **Warning banner placement** - Display warnings BEFORE stats output for immediate visibility of health issues
6. **Auto-detect consistency** - Match search command behavior: derive index from cwd when not specified

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all functionality implemented as specified, tests passing.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for next phase.** Stats dashboard provides comprehensive observability foundation for:
- Phase 35-02: Stats persistence and historical tracking
- Phase 36: Skill routing (can use stats for index health checks)
- Monitoring integrations (JSON output ready for external tools)

No blockers. Index health metrics, staleness detection, and visual output all working correctly.

---
*Phase: 35-stats-dashboard*
*Completed: 2026-02-04*
