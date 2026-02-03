# Project Research Summary

**Project:** CocoSearch v1.8 (Polish & Observability)
**Domain:** Semantic code search with hybrid retrieval, symbol extraction, and observability features
**Researched:** 2026-02-03
**Confidence:** HIGH

## Executive Summary

CocoSearch v1.8 is a polish and observability milestone that consolidates deferred v1.7 features and adds production-ready monitoring. The research reveals this is fundamentally an integration challenge: adding five feature categories (deferred v1.7 enhancements, symbol extraction expansion, stats dashboard, skills, documentation) to an existing 8,225 LOC local-first tool requires careful attention to performance overhead and architectural boundaries.

The recommended approach prioritizes performance-sensitive features first (query caching, symbol extraction) before user-facing additions (dashboard, skills). Stack additions are minimal and aligned with CocoSearch's local-first philosophy: FastAPI/Uvicorn for optional HTTP stats API, tree-sitter-language-pack migration for expanded language support, and PostgreSQL JSONB for caching. No heavyweight external dependencies like Redis or build tooling are required.

Key risks center on three areas: (1) statistics collection degrading search performance if done synchronously, (2) C/C++ symbol extraction failures due to preprocessor limitations, and (3) cache invalidation correctness for local-first expectations. These are mitigated through async metric collection, graceful fallback for failed symbol extraction, and revision-based cache invalidation. The research shows high confidence in stack choices and moderate confidence in C/C++ parsing capabilities.

## Key Findings

### Recommended Stack

v1.8 requires minimal new dependencies aligned with CocoSearch's local-first philosophy. The core additions are FastAPI + Uvicorn for HTTP stats API (optional feature), tree-sitter-language-pack migration for 5+ language support, PostgreSQL JSONB for query caching (no new external dependencies), and static markdown files for skills (no runtime dependencies).

**Core technologies:**
- **FastAPI 0.128.0+**: HTTP API framework for stats dashboard — de-facto standard for Python APIs, automatic OpenAPI docs, async-native, integrates with existing async codebase
- **Uvicorn 0.40.0+**: ASGI server for stats API — lightweight, production-ready, no heavyweight deployment needed
- **tree-sitter-language-pack 0.2.0+**: Replaces unmaintained tree-sitter-languages — actively maintained with 165+ languages, pre-built wheels, full typing support, includes all required grammars (Java, C, C++, Ruby, PHP)
- **PostgreSQL JSONB**: Query caching storage — already have PostgreSQL, supports fast lookups with partial indexes, no external cache layer required
- **Rich 14.3.2+**: Terminal dashboard UI — already a dependency, supports tables, live updates, layouts

**Philosophy:** Prefer built-in PostgreSQL features over external caching layers. Avoid JavaScript build tooling for web UI (use static HTML + vanilla JS). Keep dependencies optional via feature flags.

### Expected Features

Research identifies features across five categories for v1.8: deferred v1.7 functionality, symbol extraction expansion, observability dashboard, developer skills, and documentation overhaul.

**Must have (table stakes):**
- **Hybrid + symbol filter combination** — v1.7 deferred this, users expect both filters to work together
- **Nested symbol hierarchy** — fully qualified names (Class.method) for disambiguation
- **Query caching** — repeated searches should be instant, expected in production tools
- **Stats dashboard API** — JSON endpoints for monitoring, standard in 2026 tools
- **Basic skill files** — at least 2-3 example skills to demonstrate capability

**Should have (competitive):**
- **Expanded symbol extraction (10 languages)** — Java, C, C++, Ruby, PHP added to existing Python, JS, TS, Go, Rust
- **Terminal dashboard** — rich-based live stats view for CLI users
- **Web dashboard UI** — static HTML visualization of stats
- **Claude Code + OpenCode skills** — installation instructions and skill routing
- **Documentation overhaul** — README rebrand, retrieval logic docs, MCP tools reference

**Defer (v2+):**
- **Redis-backed cache** — start with in-memory, add Redis only if multi-process deployments prove necessary
- **Real-time dashboard updates** — WebSocket/SSE for live stats can wait, polling sufficient for v1.8
- **Symbol cross-references** — "X uses this symbol" count requires two-pass indexing, high value but expensive
- **Advanced query syntax** — phrase matching with tsquery `<->`, negative keywords with `NOT:`, defer to validate demand first

### Architecture Approach

All four v1.8 features integrate cleanly with minimal architectural changes. The existing modular package structure (cli.py, mcp/server.py, indexer/, search/, management/, config/) supports natural extension points. Stats dashboard extends MCP server with HTTP routes (no new process needed), skills add a new module with file-based storage, symbol extraction refactors existing code to use external query files, and query caching adds an in-memory layer before embedding generation.

**Major components:**
1. **Stats Dashboard** — Extend FastMCP server with `/dashboard` (HTML) and `/api/stats` (JSON) routes, reuse management/stats.py functions, serve static HTML with Chart.js via CDN
2. **Query Cache** — In-memory LRU cache for embeddings (1000 entries, 1-hour TTL), revision-based invalidation on index updates, separate cache for query text → embedding vs results
3. **Symbol Extraction** — Migrate from hardcoded Python functions to external `.scm` tree-sitter query files per language, generic loader with caching, custom query override via config
4. **Skills System** — Markdown files with YAML frontmatter, discovery mechanism (project `.cocosearch/skills/` > user `~/.cocosearch/skills/` > built-in), CLI commands for list/show/install, optional MCP integration
5. **Docker Integration** — No new services required, all features integrate with existing MCP process or as mounted volumes

### Critical Pitfalls

Research identifies five critical pitfalls specific to adding features to an existing system, not building from scratch.

1. **Statistics collection degrades search performance** — Synchronous metric collection adds latency, database write amplification creates I/O contention. MySQL Query Cache was deprecated for exactly this reason. **Prevention:** Async collection, in-memory aggregation with periodic flush, separate stats schema, opt-in via flag, HTTP-only dashboard pulls metrics instead of pushing during search.

2. **MCP skill routing becomes unpredictable** — Claude Code skill selection uses LLM reasoning not algorithmic dispatch, poor descriptions or tool permission mistakes lead to wrong skills invoked. 54% of developers use 6+ tools leading to context fragmentation. **Prevention:** Specific skill names ("Installing CocoSearch" not "Installing Packages"), clear routing triggers in description, minimal tool permissions, test with ambiguous queries before shipping.

3. **Tree-sitter C/C++ symbol extraction fails silently** — Preprocessor macros and templates fundamentally challenge tree-sitter parsing, "macros cannot be 100% correctly parsed by a grammar that isn't contextually aware." **Prevention:** Per-language extraction confidence tracking, fallback to chunk-only indexing if symbols fail, log at INFO level but don't block, test against real-world codebases (Linux kernel, Chromium), document limitations explicitly.

4. **Query cache invalidation becomes correctness bug** — Index updates must invalidate cache immediately or users see stale results. Local-first tools need instant updates after re-indexing. **Prevention:** Revision-based cache keys (`{index_name}:{revision}:{query_hash}`), increment revision on re-index, size-bounded LRU (1000 entries max), short TTL (5 minutes), cache embeddings not final results.

5. **Documentation fragments into maintenance nightmare** — 69% of developers lose 8+ hours per week to fragmented tools and unclear navigation. Multiple doc locations (README, docs/, wiki, CLI help) go stale as code evolves. **Prevention:** Single source of truth (README for quickstart, docs/ for deep dives, no wiki), inline docstrings drive MCP tool descriptions, maintenance checklist in PR template, keep focused on user-facing features not internal functions.

## Implications for Roadmap

Based on research, suggested phase structure prioritizes performance-sensitive integrations before user-facing features:

### Phase 1: Deferred v1.7 Foundation
**Rationale:** Completes functionality deferred from v1.7, unblocks other phases. Hybrid + symbol filter combination is dependency for stats accuracy. Nested symbol hierarchy needed before expanding to 10 languages. Query caching provides immediate performance improvement (60-75% latency reduction) with highest ROI.

**Delivers:** Hybrid search works with symbol filters, nested symbol hierarchy (Class.method format), query caching with revision-based invalidation

**Addresses:** Table stakes features users expect from v1.7

**Avoids:** Query cache invalidation bugs (Pitfall #4), hybrid + symbol filter complexity issues (Pitfall #6)

**Research flag:** Standard patterns, skip phase-specific research

### Phase 2: Symbol Extraction Expansion
**Rationale:** Natural extension of existing indexer/symbols.py. Migration to query files enables community contributions and unblocks language expansion. Must happen before stats dashboard to show accurate language coverage.

**Delivers:** 5 new languages (Java, C, C++, Ruby, PHP), tree-sitter-language-pack migration, external .scm query files, graceful fallback for parsing failures

**Uses:** tree-sitter-language-pack 0.2.0+, query file loader with caching

**Implements:** Generic symbol extraction replacing hardcoded per-language functions

**Avoids:** C/C++ silent extraction failures (Pitfall #3), symbol hierarchy display truncation (Pitfall #10)

**Research flag:** Phase needs validation — test C/C++ extraction on 5+ real codebases during implementation, verify failure rates and fallback behavior

### Phase 3: Stats Dashboard
**Rationale:** Builds on stable search/stats APIs from Phase 1. Requires symbol extraction accuracy from Phase 2. Lower priority than performance features but high value for Docker deployments. Async collection design prevents performance degradation.

**Delivers:** HTTP API endpoints (/api/stats), terminal dashboard (rich-based), web UI (static HTML + Chart.js), language statistics

**Uses:** FastAPI 0.128.0+, Uvicorn 0.40.0+, Rich 14.3.2+ (existing), Chart.js via CDN

**Implements:** FastMCP server extension with custom routes, management/stats.py aggregation functions

**Avoids:** Performance overhead from sync collection (Pitfall #1), HTTP API security issues (Pitfall #7)

**Research flag:** Needs framework evaluation — which terminal UI library (rich vs textual vs blessed), HTTP framework choice (FastAPI vs Flask vs http.server), benchmark stats collection overhead with CocoSearch's stack

### Phase 4: Claude Code & OpenCode Skills
**Rationale:** Independent of other features, CLI-first approach, foundation for MCP enhancements. User-facing value from skills depends on stats/search quality from earlier phases.

**Delivers:** Skill discovery system, CLI commands (list/show/install), 3-5 built-in example skills, installation documentation

**Implements:** skills/ module with YAML frontmatter parser, registry with caching, optional MCP tool integration

**Avoids:** Skill routing unpredictability (Pitfall #2), YAML frontmatter errors (Pitfall #9)

**Research flag:** Needs user testing — validate skill routing with ambiguous queries ("search this codebase", "install dependencies"), test both Claude Code and OpenCode independently

### Phase 5: Documentation Overhaul
**Rationale:** Must happen after all features stable. README rebrand reflects new positioning (v1.8 as "polish & observability"). Retrieval logic docs and MCP tools reference depend on complete feature set.

**Delivers:** Restructured README (quickstart focus), docs/ARCHITECTURE.md (retrieval logic deep dive), docs/MCP_TOOLS.md (tool reference with examples), updated CLI help

**Addresses:** Documentation fragmentation prevention (Pitfall #5)

**Avoids:** Multiple sources of truth, content gaps for new features, over-documentation of internals (Pitfall #9)

**Research flag:** Standard patterns, skip research — follow established documentation structure conventions

### Phase Ordering Rationale

- **Performance first:** Query caching (Phase 1) provides immediate ROI, stats collection (Phase 3) must be async to avoid degradation
- **Dependencies respected:** Symbol extraction (Phase 2) must precede stats dashboard (Phase 3) for accurate language statistics
- **Integration risk managed:** Test deferred v1.7 features (Phase 1) before adding observability layer (Phase 3)
- **User-facing last:** Skills (Phase 4) and docs (Phase 5) depend on stable search/stats foundation from earlier phases
- **Module boundaries clear:** Each phase has defined module (cache in search/, symbols in indexer/, stats in management/, skills in skills/), prevents coupling

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Symbol Extraction):** Test C/C++ parsing on real-world codebases (Linux kernel, Chromium), measure actual failure rates, validate fallback behavior
- **Phase 3 (Stats Dashboard):** Benchmark stats collection overhead, evaluate terminal UI library options, test HTTP framework performance
- **Phase 4 (Skills):** User testing for skill routing validation, test LLM-based selection with ambiguous queries

Phases with standard patterns (skip research-phase):
- **Phase 1 (Deferred v1.7):** Well-documented RRF hybrid search, cache invalidation patterns established
- **Phase 5 (Documentation):** Standard documentation structure, no novel patterns

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Official docs for FastAPI/Uvicorn/Rich verified, tree-sitter-language-pack actively maintained with verified grammars, PostgreSQL JSONB well-documented for caching patterns |
| Features | HIGH | Context7 library research on hybrid search and symbol extraction, 2026 industry research on observability tools, official Claude Code skills documentation |
| Architecture | HIGH | Clean integration points identified, minimal coupling, all features additive and backward-compatible, Docker integration requires no new services |
| Pitfalls | MEDIUM | High confidence on stats overhead and cache invalidation (well-researched), LOW confidence on C/C++ parsing failure severity (known limitations but unclear real-world impact) |

**Overall confidence:** HIGH

### Gaps to Address

Research was comprehensive but several areas need validation during implementation:

- **C/C++ symbol extraction failure rate:** Known that preprocessor macros cause issues, but what percentage of real-world files fail? Need production data from testing against 5+ large C/C++ codebases (Linux kernel, LLVM, Chromium, etc.)
- **Query cache hit rate for code search:** General semantic caching achieves 60-80% hit rates, but code search queries may differ due to specificity. Monitor actual hit rates during implementation.
- **Stats collection overhead magnitude:** Research shows async collection prevents major degradation, but exact millisecond cost for CocoSearch's stack needs benchmarking. Set threshold: fail CI if >10% regression.
- **Skill routing accuracy with ambiguous queries:** LLM-based routing has no algorithmic fallback. Test with 20+ ambiguous queries ("search code", "find bugs", "install dependencies") to validate routing quality before shipping.
- **Dashboard UI framework choice:** Rich vs Textual vs blessed for terminal, FastAPI vs Flask for HTTP. Needs prototyping to evaluate developer experience and performance tradeoffs.

## Sources

### Primary (HIGH confidence)
- [FastAPI Official Documentation](https://fastapi.tiangolo.com/) — API patterns, async integration
- [Anthropic Claude Code Skills Documentation](https://code.claude.com/docs/en/skills) — skill format, routing behavior
- [tree-sitter-language-pack GitHub](https://github.com/Goldziher/tree-sitter-language-pack) — language support verification, API compatibility
- [Tree-sitter Official Site](https://tree-sitter.github.io/tree-sitter/) — query system, parser capabilities
- [Redis Semantic Caching Guide](https://redis.io/blog/what-is-semantic-caching/) — cache architecture patterns
- [PostgreSQL as JSON Database (AWS)](https://aws.amazon.com/blogs/database/postgresql-as-a-json-database-advanced-patterns-and-best-practices/) — JSONB optimization techniques
- [Tree-sitter C Preprocessor Issues #108](https://github.com/tree-sitter/tree-sitter-c/issues/108) — macro parsing limitations

### Secondary (MEDIUM confidence)
- [Claude Skills Deep Dive (Lee Han Chung)](https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/) — routing mechanism analysis
- [MCP Observability Overview](https://www.merge.dev/blog/mcp-observability) — 2026 monitoring patterns
- [Hybrid Search: BM25 + Vector (Medium 2026)](https://medium.com/codex/96-hybrid-search-combining-bm25-and-vector-search-7a93adfd3f4e) — RRF implementation
- [Redis Cache Invalidation (Milan Jovanovic)](https://www.milanjovanovic.tech/blog/solving-the-distributed-cache-invalidation-problem-with-redis-and-hybridcache) — distributed cache pitfalls
- [Technical Debt Guide 2026 (Monday.com)](https://monday.com/blog/rnd/technical-debt/) — incremental feature development risks
- [Developer Documentation Tools 2026](https://documentation.ai/blog/ai-tools-for-documentation) — fragmentation issues

### Tertiary (LOW confidence)
- [Claude Code Best Practices (Medium)](https://medium.com/@rub1cc/how-claude-codes-creator-uses-it-10-best-practices-from-the-team-e43be312836f) — skill count recommendations
- [Tree-sitter Complications (Mastering Emacs)](https://www.masteringemacs.org/article/tree-sitter-complications-of-parsing-languages) — error recovery patterns

---
*Research completed: 2026-02-03*
*Ready for roadmap: yes*
