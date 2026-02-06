# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-05)

**Core value:** Semantic code search that runs entirely locally — no data leaves your machine.
**Current focus:** v1.9 Multi-Repo & Polish

## Current Position

Phase: 40 of 42 (Code Cleanup) — COMPLETE
Plan: 2 of 2 — All plans complete
Status: Phase verified, ready for next phase
Last activity: 2026-02-06 — Phase 40 complete (262 LOC removed)

Progress: [##################..] 92% (108/117 estimated plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 106
- Milestones shipped: 8 (v1.0-v1.8)
- Last milestone: v1.8 Polish & Observability (phases 33-37, 13 plans)

**By Recent Milestone:**

| Milestone | Phases | Plans | Shipped |
|-----------|--------|-------|---------|
| v1.8 Polish & Observability | 33-37 | 13 | 2026-02-05 |
| v1.7 Search Enhancement | 27-32 | 21 | 2026-02-03 |
| v1.6 Docker & Auto-Detect | 23-26 | 11 | 2026-02-02 |
| v1.5 Config & Architecture | 19-22 | 11 | 2026-02-01 |

*Updated: 2026-02-05 after v1.9 roadmap created*

## Accumulated Context

### Decisions

Full decision log in PROJECT.md Key Decisions table.

**Phase 40-02 decisions:**
- Removed pre-v1.2 graceful degradation - metadata columns now required
- Preserved v1.7 feature detection for content_text and symbol columns
- Removed TestGracefulDegradation test class testing deprecated behavior

**Phase 40-01 decisions:**
- Removed DevOpsMetadata from indexer __all__ exports (backward-compat wrapper no longer public API)
- Tests that need DevOpsMetadata now define local dataclass rather than importing from deprecated module
- Fixed unused import (extract_extension) discovered during lint check

**Phase 39-01 decisions:**
- Fixed symbol signature extraction bugs rather than updating tests to accept broken output
- Increased signature truncation limit from 120 to 200 characters for realistic code
- Updated CLI test mocks to match refactored stats_command implementation using IndexStats

**Phase 38-01 decisions:**
- Used environment variable (COCOSEARCH_PROJECT_PATH) for CLI-to-MCP workspace communication
- Added type field to search result header/footer for programmatic identification
- Staleness threshold hardcoded to 7 days (matches stats command default)

### Pending Todos

None — ready for phase planning.

### Blockers/Concerns

**From research:**
- uvx cwd behavior needs validation: `os.getcwd()` may return uvx cache path, not workspace. Document `--directory $(pwd)` pattern in MCP registration.
- Old index prevalence RESOLVED (40-02): Pre-v1.2 graceful degradation removed. Users with old indexes will get clear SQL error directing them to re-index.
- CocoIndex schema completeness RESOLVED (40-01): CocoIndex natively creates TEXT/vector columns. schema_migration.py is necessary for PostgreSQL-specific features (TSVECTOR, GIN indexes), not deprecated migration code.

**Research flags from v1.8 (still relevant):**
- Test C/C++ extraction on real codebases with heavy macros, verify failure rates
- Consider parse failure tracking in stats output (per-language counts)

## Session Continuity

Last session: 2026-02-06
Stopped at: Phase 40 complete and verified (9/9 must-haves). Ready for Phase 41.
Resume file: None
