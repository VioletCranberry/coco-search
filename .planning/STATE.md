# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-03)

**Core value:** Semantic code search that runs entirely locally — no data leaves your machine.
**Current focus:** Phase 36 - Developer Skills

## Current Position

Phase: 36 of 37 (Developer Skills)
Plan: 2 of 2 in current phase
Status: Phase complete
Last activity: 2026-02-05 — Phase 36 verified and complete

Progress: [======================================....] 95% (36/37 phases, 102/103 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 102
- Milestones shipped: 7 (v1.0-v1.7)
- Current milestone: v1.8 Polish & Observability (phases 33-37, 13 plans)

**By Recent Milestone:**

| Milestone | Phases | Plans | Shipped |
|-----------|--------|-------|---------|
| v1.7 Search Enhancement | 27-32 | 21 | 2026-02-03 |
| v1.6 Docker & Auto-Detect | 23-26 | 11 | 2026-02-02 |
| v1.5 Config & Architecture | 19-22 | 11 | 2026-02-01 |

*Updated: 2026-02-05 after Phase 36 complete*

## Accumulated Context

### Decisions

Full decision log in PROJECT.md Key Decisions table.

Recent Phase 36 decisions:
- OpenCode MCP config format differs: type: local, command array, environment not env, enabled: true
- No troubleshooting section in skills - footer reference to README keeps focused
- 184-line format for OpenCode skill balances comprehensiveness with context budget
- Force-add .claude/skills/ files despite global gitignore for team sharing (applies to both skills)
- Include 6 examples instead of minimum 5 for comprehensive coverage (both skills)
- Keep Troubleshooting section as README pointer only (no content duplication)

Recent Phase 35 decisions:
- Use IndexStats dataclass to aggregate all health metrics in one place
- Graceful degradation: symbol stats return empty dict for pre-v1.7 indexes
- Staleness threshold defaults to 7 days, configurable via --staleness-threshold flag
- Visual output as default (--pretty), JSON via explicit --json flag
- Warning banner displays BEFORE stats output for visibility
- Use FastMCP custom_route decorator for HTTP API endpoints (cleaner than raw Starlette)
- Cache-Control: no-cache header on API responses to prevent stale data
- htop-style layout: header/summary/details for maximum information density
- Static snapshot mode (--live) vs. auto-refresh mode (--live --watch)
- Single-page HTML with embedded CSS/JS (no build step, no bundler required)
- Chart.js via CDN for zero-config setup and browser caching
- CSS variables with prefers-color-scheme for automatic dark/light mode
- serve-dashboard reuses MCP server infrastructure (no duplicate HTTP code)

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

None — Phase 36 plan 02 complete.

### Blockers/Concerns

**Known technical debt:**
None

**Research flags from SUMMARY.md:**
- Phase 34: Test C/C++ extraction on real codebases with heavy macros, verify failure rates
- Phase 34: Consider parse failure tracking in stats output (per-language counts)
- Phase 35: Benchmark stats collection overhead, evaluate terminal UI options
- Phase 36: Test skill routing decision tree effectiveness with both Claude Code and OpenCode users
- Phase 36: Verify line count optimization (172 Claude Code, 184 OpenCode vs target ~100)

## Session Continuity

Last session: 2026-02-05
Stopped at: Phase 36 complete, verified
Resume file: None
