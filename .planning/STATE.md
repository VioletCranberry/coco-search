# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-03)

**Core value:** Semantic code search that runs entirely locally — no data leaves your machine.
**Current focus:** Phase 34 - Symbol Extraction Expansion

## Current Position

Phase: 34 of 37 (Symbol Extraction Expansion)
Plan: — (phase not yet planned)
Status: Ready to plan
Last activity: 2026-02-03 — Phase 33 complete, verified

Progress: [=================================.........] 80% (33/37 phases, 93/103 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 93
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

Recent Phase 33 decisions:
- Apply symbol/language filters BEFORE RRF fusion (not after)
- Add symbol fields to VectorResult and HybridSearchResult dataclasses
- Pass include_symbol_columns flag to execute_vector_search for conditional SELECT
- Omit symbol fields when None for clean JSON output
- Display [symbol_type] symbol_name format in pretty output
- Truncate signatures >60 chars with ellipsis
- In-memory session-scoped cache (simpler than diskcache)
- 0.95 cosine similarity threshold for semantic cache hits
- 24-hour default TTL for cache entries

Recent v1.7 decisions:
- RRF k=60 for hybrid search (standard value)
- PostgreSQL 'simple' text config for code identifiers
- Tree-sitter 0.21.x for API compatibility
- Definition boost (2x) after RRF fusion

### Pending Todos

None — starting Phase 34.

### Blockers/Concerns

**Known technical debt:**
- Tree-sitter deprecation warning in tree-sitter-languages 1.10.2 — addressed in Phase 34 migration

**Research flags from SUMMARY.md:**
- Phase 34: Test C/C++ extraction on real codebases, verify failure rates
- Phase 35: Benchmark stats collection overhead, evaluate terminal UI options
- Phase 36: Test skill routing with ambiguous queries

## Session Continuity

Last session: 2026-02-03
Stopped at: Phase 33 complete, ready to plan Phase 34
Resume file: None
