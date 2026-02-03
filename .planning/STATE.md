# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-02)

**Core value:** Semantic code search that runs entirely locally — no data leaves your machine.
**Current focus:** Phase 29 - Symbol-Aware Indexing

## Current Position

Phase: 28 of 32 complete (Hybrid Search Query)
Plan: 4 of 4 in phase 28 (verified)
Status: Phase 28 verified, ready for Phase 29
Last activity: 2026-02-03 — Phase 28 executed and verified

Progress: [██████████████████████████████░░] 89% (76 of 85 estimated plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 76
- Milestones shipped: 6 (v1.0-v1.6)
- Current milestone: v1.7 Search Enhancement

**By Recent Milestone:**

| Milestone | Phases | Plans | Shipped |
|-----------|--------|-------|---------|
| v1.6 Docker & Auto-Detect | 23-26 | 11 | 2026-02-02 |
| v1.5 Config & Architecture | 19-22 | 11 | 2026-02-01 |
| v1.4 Dogfooding | 15-18 | 7 | 2026-01-31 |

*Updated: 2026-02-03 after Plan 28-04 completion (Phase 28 complete)*

## Accumulated Context

### Decisions

Recent decisions affecting v1.7 work:

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
- Symbol extraction quality depends on Tree-sitter query patterns (validate during Phase 29)
- RRF k parameter may need tuning based on codebase characteristics (benchmark during Phase 28)

## Session Continuity

Last session: 2026-02-03
Stopped at: Phase 28 verified, ready for Phase 29 planning
Resume file: None
