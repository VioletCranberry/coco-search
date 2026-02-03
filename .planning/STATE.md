# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-03)

**Core value:** Semantic code search that runs entirely locally — no data leaves your machine.
**Current focus:** v1.8 Polish & Observability

## Current Position

Phase: Not started (researching)
Plan: —
Status: Researching v1.8 features
Last activity: 2026-02-03 — Milestone v1.8 started

Progress: Defining requirements

## Performance Metrics

**Velocity:**
- Total plans completed: 90
- Milestones shipped: 7 (v1.0-v1.7)
- Current milestone: None (ready for v1.8 planning)

**By Recent Milestone:**

| Milestone | Phases | Plans | Shipped |
|-----------|--------|-------|---------|
| v1.7 Search Enhancement | 27-32 | 21 | 2026-02-03 |
| v1.6 Docker & Auto-Detect | 23-26 | 11 | 2026-02-02 |
| v1.5 Config & Architecture | 19-22 | 11 | 2026-02-01 |

*Updated: 2026-02-03 after v1.7 milestone archived*

## Accumulated Context

### Decisions

Full decision log in PROJECT.md Key Decisions table.

Recent v1.7 decisions:
- RRF k=60 for hybrid search (standard value)
- PostgreSQL 'simple' text config for code identifiers
- Two-phase tsvector: Python preprocessing + PostgreSQL generated column
- Tree-sitter 0.21.x for API compatibility
- Instance-level LRU cache for context expansion
- 50-line context cap centered on match
- Definition boost (2x) after RRF fusion

### Pending Todos

None — milestone complete.

### Blockers/Concerns

None — v1.7 shipped successfully.

**Known technical debt for v1.8:**
- TODO: Add symbol filter support to hybrid search (query.py:268)
- Tree-sitter deprecation warning in tree-sitter-languages 1.10.2 (harmless, awaiting upstream fix)

## Session Continuity

Last session: 2026-02-03
Stopped at: v1.8 milestone started — researching
Resume file: None
