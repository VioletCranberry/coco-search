# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-02)

**Core value:** Semantic code search that runs entirely locally — no data leaves your machine.
**Current focus:** Phase 31 - Context Expansion Enhancement

## Current Position

Phase: 30 of 32 complete (Symbol Search Filters)
Plan: 4 of 4 in phase 30 (verified)
Status: Phase 30 verified, ready for Phase 31 planning
Last activity: 2026-02-03 — Phase 30 executed and verified

Progress: [████████████████████████████████░] 97% (83 of 85 estimated plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 83
- Milestones shipped: 6 (v1.0-v1.6)
- Current milestone: v1.7 Search Enhancement

**By Recent Milestone:**

| Milestone | Phases | Plans | Shipped |
|-----------|--------|-------|---------|
| v1.6 Docker & Auto-Detect | 23-26 | 11 | 2026-02-02 |
| v1.5 Config & Architecture | 19-22 | 11 | 2026-02-01 |
| v1.4 Dogfooding | 15-18 | 7 | 2026-01-31 |

*Updated: 2026-02-03 after Phase 30 verification*

## Accumulated Context

### Decisions

Recent decisions affecting v1.7 work:

- **30-04**: Definition keywords detected via prefix match (fast heuristic, false positives acceptable)
- **30-04**: Apply 2x boost after RRF fusion, before limit
- **30-04**: Skip boost silently for pre-v1.7 indexes (DEBUG log level)
- **30-03**: CLI --symbol-type uses action=append for OR filtering
- **30-03**: MCP symbol_type accepts both str and list[str] for flexibility
- **30-03**: MCP response always includes symbol_type, symbol_name, symbol_signature (None if unavailable)
- **30-03**: ValueError from search() returns structured MCP error with message field
- **30-01**: LANGUAGE_MAP with 12 extension mappings (js/jsx/mjs/cjs, ts/tsx/mts/cts, go, rs, py)
- **30-01**: TypeScript type aliases map to "interface" symbol_type
- **30-01**: Go structs and Rust structs/enums map to "class" symbol_type
- **30-01**: Rust traits map to "interface" symbol_type
- **30-01**: Methods use ClassName.methodName format in all languages
- **30-02**: Escape SQL chars (%, _) BEFORE converting glob wildcards (*, ?) - order matters
- **30-02**: Symbol filtering uses vector-only mode - hybrid + symbol filters is future enhancement
- **30-02**: Include symbol columns in SELECT only when symbol filtering is active
- **30-02**: Symbol filters combine with language filters via AND logic
- **29-03**: Module-level cache for symbol column availability (prevent repeated queries)
- **29-03**: All-or-nothing check (require all 3 symbol columns for True)
- **29-03**: INFO-level logging for pre-v1.7 detection (not WARNING)
- **29-02**: Call ensure_symbol_columns() after flow.setup() but before flow.update()
- **29-02**: Use CocoIndex table naming: codeindex_{index_name}__{index_name}_chunks
- **29-02**: Symbol columns as nullable TEXT (backward compatible, no defaults)
- **29-02**: Schema migration is idempotent (safe to run multiple times)
- **29-01**: Tree-sitter 0.21.x for API compatibility with tree-sitter-languages
- **29-01**: Async function detection via AST child nodes (not text prefix)
- **29-01**: Skip nested functions (implementation details)
- **29-01**: Return first symbol when chunk contains multiple
- **29-01**: Qualified method names format: ClassName.method_name
- **28-04**: Fresh embedding flow per integration test with explicit Ollama URL
- **28-04**: Integration tests skip gracefully when Ollama unavailable
- **28-03**: Escaped brackets (\\[semantic]) for Rich markup compatibility
- **28-03**: JSON output omits hybrid fields when None (cleaner backward compat)
- **28-02**: use_hybrid parameter: None=auto, True=force, False=disabled
- **28-02**: No hybrid+language filter combination (future enhancement)
- **28-02**: Match type color coding: cyan=semantic, green=keyword, yellow=both
- **28-01**: RRF k=60 (standard value) for rank fusion constant
- **28-01**: Keyword matches favored on tie-break
- **28-01**: Silent fallback to vector-only when keyword search unavailable
- **27-03**: Use PostgreSQL 'simple' text config (no stemming for code identifiers)
- **27-03**: Two-phase tsvector: Python preprocessing + PostgreSQL generated column
- **27-03**: Preserve original identifiers while splitting camelCase/snake_case
- **27-02**: Proactive column check before first search (not reactive error handling)
- **27-02**: Centralized autouse fixture for test module state reset
- **27-01**: Store raw chunk text in content_text field (no transformation)
- **v1.6**: All-in-one Docker image with SSE transport for Claude Desktop
- **v1.6**: Auto-detect project from cwd with collision detection
- **v1.5**: Registry-based language handlers with autodiscovery
- **v1.4**: Dogfooding CocoSearch's own codebase
- **Research**: PostgreSQL-native tsvector/tsquery over external BM25 extensions
- **Research**: RRF fusion algorithm for hybrid search (avoids score normalization issues)

Full decision log in PROJECT.md Key Decisions table.

### Pending Todos

None yet.

### Blockers/Concerns

**v1.7 Architecture:**
- Adding content_text column requires re-indexing existing indexes (breaking change)
- Symbol extraction, indexing, and detection complete - Phase 30 search integration complete
- Symbol column detection enables graceful degradation for pre-v1.7 indexes
- Symbol columns are nullable TEXT - pre-v1.7 indexes work without re-indexing
- Tree-sitter deprecation warning in tree-sitter-languages 1.10.2 (harmless, awaiting upstream fix)
- Definition boost automatically applied in hybrid_search (2x for function/class definitions)

## Session Continuity

Last session: 2026-02-03
Stopped at: Phase 30 verified, ready for Phase 31 planning
Resume file: None
