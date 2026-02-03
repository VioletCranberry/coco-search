# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-03)

**Core value:** Semantic code search that runs entirely locally — no data leaves your machine.
**Current focus:** Phase 34 - Symbol Extraction Expansion

## Current Position

Phase: 34 of 37 (Symbol Extraction Expansion)
Plan: 03 of 03 (C and C++ Symbol Extraction)
Status: Phase complete
Last activity: 2026-02-03 — Completed 34-03: C and C++ symbol extraction

Progress: [==================================........] 84% (34/37 phases, 97/103 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 96
- Milestones shipped: 7 (v1.0-v1.7)
- Current milestone: v1.8 Polish & Observability (phases 33-37, 13 plans)

**By Recent Milestone:**

| Milestone | Phases | Plans | Shipped |
|-----------|--------|-------|---------|
| v1.7 Search Enhancement | 27-32 | 21 | 2026-02-03 |
| v1.6 Docker & Auto-Detect | 23-26 | 11 | 2026-02-02 |
| v1.5 Config & Architecture | 19-22 | 11 | 2026-02-01 |

*Updated: 2026-02-03 after Phase 33 complete*

## Accumulated Context

### Decisions

Full decision log in PROJECT.md Key Decisions table.

Recent Phase 34 decisions:
- Use QueryCursor dict-based captures API (tree-sitter 0.25.x returns dict not list)
- Remove field names from TypeScript/JavaScript queries (grammars use positional matching)
- Preserve return types in signatures for richer search context
- Extract receiver types for Go methods to build qualified names (Server.Start)
- Prioritize method patterns in Rust queries to distinguish from top-level functions
- Only extract C/C++ definitions with body (ignore forward declarations)
- Map C++ namespaces to "class" symbol type (organizational containers)
- Use "::" separator for C++ qualified names (MyClass::method)
- .h files map to C by default (users can override via .cocosearch/queries/)

Recent Phase 33 decisions:
- Apply symbol/language filters BEFORE RRF fusion (not after)
- Add symbol fields to VectorResult and HybridSearchResult dataclasses
- Pass include_symbol_columns flag to execute_vector_search for conditional SELECT
- In-memory session-scoped cache (simpler than diskcache)
- 0.95 cosine similarity threshold for semantic cache hits

### Pending Todos

None — starting Phase 34.

### Blockers/Concerns

**Known technical debt:**
None - tree-sitter deprecation warnings resolved in Phase 34-01.

**Research flags from SUMMARY.md:**
- Phase 34-01: Test C/C++ extraction on real codebases with heavy macros, verify failure rates
- Phase 34: Consider parse failure tracking in stats output (per-language counts)
- Phase 35: Benchmark stats collection overhead, evaluate terminal UI options
- Phase 36: Test skill routing with ambiguous queries

## Session Continuity

Last session: 2026-02-03 19:44 UTC
Stopped at: Completed Phase 34 (Symbol Extraction Expansion)
Resume file: None
