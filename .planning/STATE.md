# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-03)

**Core value:** Semantic code search that runs entirely locally — no data leaves your machine.
**Current focus:** v1.8 milestone complete

## Current Position

Phase: 37 of 37 (Documentation Rebrand)
Plan: 1 of 1 in current phase
Status: Milestone complete
Last activity: 2026-02-05 — Phase 37 verified and complete, v1.8 milestone shipped

Progress: [==========================================] 100% (37/37 phases, 103/103 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 103
- Milestones shipped: 8 (v1.0-v1.8)
- Current milestone: v1.8 Polish & Observability (phases 33-37, 13 plans) - COMPLETE

**By Recent Milestone:**

| Milestone | Phases | Plans | Shipped |
|-----------|--------|-------|---------|
| v1.8 Polish & Observability | 33-37 | 13 | 2026-02-05 |
| v1.7 Search Enhancement | 27-32 | 21 | 2026-02-03 |
| v1.6 Docker & Auto-Detect | 23-26 | 11 | 2026-02-02 |
| v1.5 Config & Architecture | 19-22 | 11 | 2026-02-01 |

*Updated: 2026-02-05 after Phase 37 complete (ALL PHASES COMPLETE)*

## Accumulated Context

### Decisions

Full decision log in PROJECT.md Key Decisions table.

Recent Phase 37 decisions:
- Lead with 'Hybrid search for codebases' tagline, not semantic search
- Quick Start as first section for immediate action
- 10 symbol-aware languages (Python, JS, TS, Go, Rust, Java, C, C++, Ruby, PHP) in Full Support tier
- Observability section at same level as Search Features (v1.8 capability)
- Troubleshooting de-emphasized by moving to end of document
- --no-cache flag documented in CLI reference for query caching (Phase 33 feature)

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

None — All 103 plans complete.

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
Stopped at: v1.8 milestone complete — ready for /gsd:audit-milestone
Resume file: None
