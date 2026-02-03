---
phase: 31-context-expansion
plan: 01
subsystem: search
tags: [tree-sitter, context-expansion, lru-cache, ast-parsing]

# Dependency graph
requires:
  - phase: 29-symbol-extraction
    provides: Tree-sitter parser patterns and LANGUAGE_MAP
provides:
  - ContextExpander class with smart boundary detection
  - Tree-sitter AST traversal for function/class boundaries
  - LRU caching for efficient file reading
  - 50-line hard limit enforcement
affects: [31-02 CLI integration, 31-03 MCP integration, formatter updates]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Instance-level LRU cache via wrapper method
    - Tree-sitter parent node traversal for scope detection
    - Byte offset to line number conversion for AST ranges

key-files:
  created:
    - src/cocosearch/search/context_expander.py
    - tests/unit/search/test_context_expander.py
  modified: []

key-decisions:
  - "Use instance-level LRU cache (not module-level) for search session isolation"
  - "Support 5 languages: Python, JavaScript, TypeScript, Go, Rust"
  - "Return original range when no enclosing scope found (graceful fallback)"

patterns-established:
  - "ContextExpander pattern: Create instance, use for session, call clear_cache() after"
  - "Smart expansion pattern: Expand to boundaries first, then apply 50-line cap centered on match"

# Metrics
duration: 12min
completed: 2026-02-03
---

# Phase 31 Plan 01: Context Expander Module Summary

**Tree-sitter powered context expansion with smart function/class boundary detection and LRU caching**

## Performance

- **Duration:** 12 min
- **Started:** 2026-02-03T11:00:00Z
- **Completed:** 2026-02-03T11:12:00Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments
- ContextExpander class with find_enclosing_scope() for smart boundary detection
- Tree-sitter integration finds enclosing function/class for Python, JS, TS, Go, Rust
- 50-line hard limit enforced, centered on original match when scope exceeds limit
- LRU caching (128 files) prevents repeated I/O during search sessions
- 36 unit tests covering all features and edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1: Create context_expander.py module** - `b92b6d4` (feat)
2. **Task 2: Create unit tests for context expander** - `4b4300b` (test)

## Files Created/Modified
- `src/cocosearch/search/context_expander.py` - Smart context expansion with tree-sitter boundaries (446 lines)
- `tests/unit/search/test_context_expander.py` - Comprehensive unit tests (590 lines)

## Decisions Made
- **Instance-level LRU cache:** Used instance-level cache (not module-level) so each search session gets isolated caching and clear_cache() properly resets state
- **5 language support:** Aligned with existing LANGUAGE_MAP from symbols.py - Python, JavaScript, TypeScript, Go, Rust
- **Graceful fallback:** When tree-sitter fails to find enclosing scope (parse errors, top-level code, unsupported language), return original range unchanged
- **50-line centering:** When smart-expanded scope exceeds 50 lines, cap is applied centered on the original match to keep relevant code visible

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Tree-sitter deprecation warning (FutureWarning about Language constructor) appears in tests - this is a known harmless warning from tree-sitter-languages 1.10.2 awaiting upstream fix (documented in STATE.md)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- ContextExpander ready for integration with CLI (-A/-B/-C flags)
- ContextExpander ready for integration with MCP (context_lines parameter)
- Formatter module will need updates to use new context format

---
*Phase: 31-context-expansion*
*Completed: 2026-02-03*
