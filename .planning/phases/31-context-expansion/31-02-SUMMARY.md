---
phase: 31-context-expansion
plan: 02
subsystem: search
tags: [cli, formatter, context-expansion, grep-style, tree-sitter]

# Dependency graph
requires:
  - phase: 31-01
    provides: ContextExpander class with tree-sitter smart boundary detection
provides:
  - CLI flags -A/-B/-C for context lines control
  - --no-smart flag to disable smart boundary expansion
  - Updated formatters with grep-style output markers
  - JSON context_before/context_after as strings
  - Pretty output with BOF/EOF markers
affects: [31-03-mcp-integration, 31-04-repl-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - grep-style context markers (: for context, > for match)
    - Smart vs explicit context expansion mode

key-files:
  created:
    - tests/unit/search/test_formatter_context.py
  modified:
    - src/cocosearch/cli.py
    - src/cocosearch/search/formatter.py
    - tests/unit/search/test_formatter.py

key-decisions:
  - "Smart context expansion enabled by default (no flags needed)"
  - "Explicit -A/-B/-C flags override smart expansion"
  - "Context output as newline-separated strings (not lists)"
  - "Grep-style markers: colon for context, angle bracket for match"
  - "BOF/EOF markers only shown when context hits file boundaries"

patterns-established:
  - "Context expansion: CLI flags parsed into context_before/context_after/smart_context triple"
  - "Formatter pattern: Create ContextExpander, process all results, clear_cache()"

# Metrics
duration: 4min
completed: 2026-02-03
---

# Phase 31 Plan 02: CLI Context Flags Summary

**CLI context expansion with -A/-B/-C flags and grep-style output markers in JSON and pretty formatters**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-03T12:41:14Z
- **Completed:** 2026-02-03T12:45:08Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- CLI supports grep-style -A/-B/-C context flags
- --no-smart flag disables tree-sitter boundary expansion
- JSON output includes context_before/context_after as strings
- Pretty output uses grep-style markers (: for context, > for match)
- BOF/EOF markers indicate when context hits file boundaries
- Full backward compatibility with context_lines parameter

## Task Commits

Each task was committed atomically:

1. **Task 1: Add CLI context flags** - `6c57b3f` (feat)
2. **Task 2: Update formatters with context expansion** - `2afef2e` (feat)
3. **Task 3: Add formatter context tests** - `cbbf80d` (test)

## Files Created/Modified
- `src/cocosearch/cli.py` - Added -A/-B/-C/--no-smart flags, context param parsing
- `src/cocosearch/search/formatter.py` - ContextExpander integration, grep-style output
- `tests/unit/search/test_formatter_context.py` - 22 tests for context expansion
- `tests/unit/search/test_formatter.py` - Updated 2 tests for new context format

## Decisions Made
- Smart context expansion enabled by default - user gets function boundaries without flags
- Explicit -A/-B/-C overrides smart mode - when user specifies lines, we use exact counts
- Context stored as newline-separated strings in JSON (not lists) for consistency
- Grep-style markers match expected UX: `:` for context lines, `>` for match lines
- BOF/EOF markers only appear when there are actual before/after lines (not on match alone)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed existing formatter tests for new context format**
- **Found during:** Task 3 (test verification)
- **Issue:** Original test_formatter.py tests expected list format for context and no context fields when context_lines=0
- **Fix:** Updated 2 tests to expect string format and mock ContextExpander
- **Files modified:** tests/unit/search/test_formatter.py
- **Verification:** All 36 original formatter tests pass
- **Committed in:** cbbf80d (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Necessary fix for backward compatibility test expectations. No scope creep.

## Issues Encountered
None - plan executed smoothly.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CLI context expansion complete and verified
- Formatter integration with ContextExpander working
- Ready for 31-03 MCP integration with context_lines parameter
- Ready for 31-04 REPL integration with context display

---
*Phase: 31-context-expansion*
*Completed: 2026-02-03*
