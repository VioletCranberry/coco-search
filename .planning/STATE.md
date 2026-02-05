# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-03)

**Core value:** Semantic code search that runs entirely locally — no data leaves your machine.
**Current focus:** Phase 35 - Stats Dashboard

## Current Position

Phase: 35 of 37 (Stats Dashboard)
Plan: 1 of 3 in current phase
Status: In progress
Last activity: 2026-02-05 — Completed 35-01-PLAN.md

Progress: [==================================........] 85% (35/37 phases, 98/103 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 98
- Milestones shipped: 7 (v1.0-v1.7)
- Current milestone: v1.8 Polish & Observability (phases 33-37, 13 plans)

**By Recent Milestone:**

| Milestone | Phases | Plans | Shipped |
|-----------|--------|-------|---------|
| v1.7 Search Enhancement | 27-32 | 21 | 2026-02-03 |
| v1.6 Docker & Auto-Detect | 23-26 | 11 | 2026-02-02 |
| v1.5 Config & Architecture | 19-22 | 11 | 2026-02-01 |

*Updated: 2026-02-05 after Phase 35 plan 01 complete*

## Accumulated Context

### Decisions

Full decision log in PROJECT.md Key Decisions table.

Recent Phase 35 decisions:
- Use IndexStats dataclass to aggregate all health metrics in one place
- Graceful degradation: symbol stats return empty dict for pre-v1.7 indexes
- Staleness threshold defaults to 7 days, configurable via --staleness-threshold flag
- Visual output as default (--pretty), JSON via explicit --json flag
- Warning banner displays BEFORE stats output for visibility

Recent Phase 34 decisions:
- Migrated from tree-sitter-languages to tree-sitter-language-pack 0.13.0
- Use QueryCursor dict-based captures API (tree-sitter 0.25.x returns dict not list)
- External .scm query files for all 10 languages (user-extensible)
- Query file override: Project > User > Built-in
- Preserve return types in signatures for richer search context
- Map namespaces/modules to "class", traits to "interface"
- Use "::" separator for C++ qualified names
- .h files map to C by default

Recent Phase 33 decisions:
- Apply symbol/language filters BEFORE RRF fusion (not after)
- In-memory session-scoped cache (simpler than diskcache)
- 0.95 cosine similarity threshold for semantic cache hits

### Pending Todos

None — starting Phase 35.

### Blockers/Concerns

**Known technical debt:**
None

**Research flags from SUMMARY.md:**
- Phase 34: Test C/C++ extraction on real codebases with heavy macros, verify failure rates
- Phase 34: Consider parse failure tracking in stats output (per-language counts)
- Phase 35: Benchmark stats collection overhead, evaluate terminal UI options
- Phase 36: Test skill routing with ambiguous queries

## Session Continuity

Last session: 2026-02-05
Stopped at: Completed 35-01-PLAN.md
Resume file: None
