# Domain Pitfalls: v1.8 Feature Integration

**Project:** CocoSearch v1.8
**Domain:** Adding observability, skills, expanded symbol extraction, query caching, and documentation to existing semantic code search tool
**Researched:** 2026-02-03
**Milestone:** v1.8 -- Polish & Observability
**Confidence:** MEDIUM (verified with official docs and 2026 sources where available, LOW confidence on C/C++ symbol extraction specifics)

## Executive Summary

Adding these five feature categories to an existing 8,225 LOC local-first tool introduces integration risks:

1. **Stats dashboard**: Performance overhead from metric collection can degrade search latency
2. **Claude Code/OpenCode skills**: Routing complexity and tool permission mistakes
3. **Symbol extraction expansion**: Language-specific parsing pitfalls, especially C/C++ preprocessor handling
4. **Query caching**: Cache invalidation complexity and memory bloat in local-first context
5. **Documentation overhaul**: Maintenance burden and content fragmentation

This document focuses on pitfalls specific to **adding features to an existing system**, not building from scratch.

---

## Critical Pitfalls

### Pitfall 1: Statistics Collection Degrades Search Performance

**What goes wrong:**

Adding monitoring to CLI/MCP tools can introduce performance overhead that defeats the purpose of a fast local-first tool. Users run CocoSearch on laptops during active development - every millisecond counts.

**Why it happens:**

1. **Synchronous metric collection**: Recording stats in-line with search operations adds latency
2. **Database write amplification**: Writing stats to PostgreSQL for every search query creates I/O contention with vector operations
3. **Memory pressure**: Keeping metrics in-memory without bounds leads to gradual degradation
4. **Excessive granularity**: Tracking too many metrics (per-chunk timings, per-file stats) creates overhead

**Real-world evidence:**

- MySQL Query Cache was deprecated due to cache invalidation overhead where "any write to a table invalidated all cached queries for that table, memory fragmentation over time" [(Source: OneUpTime)](https://oneuptime.com/blog/post/2026-01-24-mysql-query-cache-deprecated/view)
- Performance monitoring overhead varies based on "cache size, number and size of cached queries, and cache hit ratio" requiring monitoring of "cache statistics like hit ratio, free memory, and prune ratio" [(Source: LinkedIn)](https://www.linkedin.com/advice/0/how-can-you-troubleshoot-query-caching-zbfoc)
- The "default configuration of 10ms for perf_event_mux_interval_ms is known to cause serious performance overhead for systems with large core counts" [(Source: How-To Geek)](https://www.howtogeek.com/monitor-linux-system-performance-from-the-terminal/)

**Consequences:**

- Search latency increases from <100ms to 200-500ms
- Index operations slow down due to stats writes blocking vector insertions
- User perception shifts from "instant" to "sluggish"
- Laptop battery drain increases from continuous monitoring

**Prevention:**

1. **Async metric collection**: Use background threads/tasks for stats writes
2. **In-memory aggregation**: Batch metrics in memory, flush periodically (every 10-100 operations)
3. **Separate stats database/schema**: Don't let stats tables lock vector tables
4. **Opt-in collection**: Stats collection OFF by default, enable with `--enable-stats` flag
5. **Minimal hot-path metrics**: Only track critical metrics (query count, total time) during search
6. **HTTP-only dashboard**: Stats dashboard runs as separate process, pulls from db (doesn't push during search)

**Detection:**

- Warning sign: Search latency increases after adding stats
- Warning sign: PostgreSQL queries show lock contention on stats tables
- Warning sign: CPU usage spikes when stats are enabled
- Test: Benchmark search with stats on/off, fail CI if >10% regression

**Which phase addresses this:**

- **Phase 2 (Stats Dashboard)**: Build with async collection from start
- **Phase 7 (Testing)**: Add performance regression tests

---

### Pitfall 2: MCP Skill Routing Becomes Unpredictable

**What goes wrong:**

Claude Code/OpenCode skill routing relies on LLM reasoning, not algorithmic dispatch. Poor skill descriptions or tool permission mistakes lead to:
- Skills not being invoked when needed
- Wrong skill invoked for task
- Security issues from over-permissioned tools

**Why it happens:**

Per official research: "The skill selection mechanism has no algorithmic routing or intent classification at the code level. Claude Code doesn't use embeddings, classifiers, or pattern matching to decide which skill to invoke. Instead, the system formats all available skills into a text description embedded in the Skill tool's prompt, and lets Claude's language model make the decision." [(Source: Lee Han Chung's Deep Dive)](https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/)

**Common mistakes (from 2026 research):**

1. **Overly generic skill names**: "Use gerund form (verb + -ing) for Skill names" but avoid vague names like "Searching Code"
2. **Tool permission bloat**: "A common mistake is listing every available tool, which creates a security risk" [(Source: Anthropic Skills Guide)](https://www.gend.co/blog/claude-skills-claude-md-guide)
3. **No failure documentation**: Every skill should include "Failed Attempts section — documentation of approaches that didn't work" [(Source: Medium - Elliot)](https://medium.com/@elliotJL/your-ai-has-infinite-knowledge-and-zero-habits-heres-the-fix-e279215d478d)
4. **Too many skills**: "The sweet spot in January 2026 is using about five skills regularly" [(Source: Medium - Best Practices)](https://medium.com/@rub1cc/how-claude-codes-creator-uses-it-10-best-practices-from-the-team-e43be312836f)

**Consequences:**

- User invokes "install cocosearch" -> skill routes to generic "installing packages" instead of CocoSearch-specific setup
- "Search this codebase" -> routes to web search instead of CocoSearch MCP tool
- Security: skill with Write permission when only Read needed

**Prevention:**

1. **Specific skill names**: "Installing CocoSearch" not "Installing Packages"
2. **Clear routing triggers**: List exact phrases in description that should trigger skill ("index a codebase", "semantic search")
3. **Minimal tool permissions**: Only grant tools actually needed (Read,Write not Read,Write,Bash,WebSearch)
4. **Test with ambiguous queries**: Validate routing with queries like "how do I search code?" before shipping
5. **Document non-triggers**: Add "This skill does NOT handle web search or grep" to prevent confusion

**Detection:**

- Warning sign: Users report skill isn't being invoked
- Warning sign: Wrong skill consistently chosen for task
- Test: Chat log analysis showing skill selection for test queries

**Which phase addresses this:**

- **Phase 3 (Claude Code Skill)**: Iterative testing with real Claude Code
- **Phase 4 (OpenCode Skill)**: Validate routing differs from Claude Code skill where needed

---

### Pitfall 3: Tree-sitter C/C++ Symbol Extraction Fails Silently

**What goes wrong:**

Expanding symbol extraction from 5 languages (Python, JS, TS, Go, Rust) to 10 by adding Java, C, C++, Ruby, PHP introduces language-specific parsing failures. C/C++ is especially problematic due to preprocessor macros and templates.

**Why it happens:**

Tree-sitter parsers have fundamental limitations with C/C++ preprocessor directives:

- "Macros cannot be 100% correctly parsed by a grammar that isn't contextually aware and doesn't run the preprocessor" [(Source: GitHub Issue #108)](https://github.com/tree-sitter/tree-sitter-c/issues/108)
- "Any preprocessor directive that modifies text (#if, #include) can appear in the middle of a grammatical rule and change it to something entirely different" [(Source: Habr Article)](https://habr.com/en/articles/835192/)
- "An imported macro prevented the correct parsing of the following class" [(Source: GitHub Issue #85)](https://github.com/tree-sitter/tree-sitter-cpp/issues/85)

**Real-world parsing issues:**

- Function definitions with macros: "Tree-sitter's C/C++ parser has inconsistently parsed function definitions using macros" [(Source: GitHub Issue #3973)](https://github.com/tree-sitter/tree-sitter/issues/3973)
- Error recovery: "Error recovery problems have been reproduced almost verbatim in Ruby and Java, and partially in most other tree-sitter parsers (C#, C++, Rust, etc.)" [(Source: Mastering Emacs)](https://www.masteringemacs.org/article/tree-sitter-complications-of-parsing-languages)
- Parse quality: "In bad parses, tree-sitter may produce a block with a list of elements instead of proper call nodes" [(Source: Hacker News)](https://news.ycombinator.com/item?id=29327424)

**Consequences:**

- Symbol extraction succeeds but returns incomplete results (missing 30-50% of symbols)
- Users filter by symbol and get zero results despite symbols existing in file
- No error/warning surfaced - silent degradation
- Definition boost (2x) doesn't apply because symbols not extracted

**Prevention:**

1. **Per-language extraction confidence**: Track which languages have high-quality symbol extraction
2. **Fallback to chunk-only**: If symbol extraction fails, still index file chunks normally
3. **Logging but not blocking**: Log "symbol extraction failed for file.cpp" at INFO level, don't fail indexing
4. **Test with real-world codebases**: Don't just test simple examples - test against Linux kernel, Chromium source
5. **Document limitations**: README explicitly states "C/C++ symbol extraction may miss macros and templates"
6. **Preprocessor handling**: For critical C/C++ projects, consider optional preprocessing step

**Language-specific considerations:**

| Language | Confidence | Known Issues |
|----------|-----------|--------------|
| Java | HIGH | Generally reliable, watch for annotation processing |
| Ruby | MEDIUM | Dynamic method definitions via metaprogramming |
| PHP | MEDIUM | Mixed HTML/PHP files, dynamic class loading |
| C | LOW | Preprocessor macros, conditional compilation |
| C++ | LOW | Templates, preprocessor, multiple inheritance |

**Detection:**

- Warning sign: Symbol count suddenly drops when adding new language support
- Warning sign: Symbol extraction takes >1s per file
- Test: Index known C++ codebase, verify symbol counts match expected ranges
- Monitor: Track symbol_extraction_errors metric per language

**Which phase addresses this:**

- **Phase 1 (Nested Symbol Hierarchy)**: Must handle missing symbols gracefully
- **Phase 5 (Expanded Symbol Extraction)**: Add per-language error handling from start
- **Phase 7 (Testing)**: Real-world codebase tests for C/C++

---

### Pitfall 4: Query Cache Invalidation Becomes Correctness Bug

**What goes wrong:**

Adding query caching to improve performance introduces cache invalidation complexity. In local-first tools, users expect immediate results after re-indexing - stale cache breaks this expectation.

**Why it happens:**

1. **Index updates don't invalidate cache**: User re-indexes codebase but searches return old results
2. **Memory unbounded growth**: LRU cache with no size limit consumes laptop RAM
3. **Multi-instance incoherence**: If running multiple MCP instances (Claude Desktop + Claude Code), cache not shared
4. **TTL too long**: 10-minute TTL means stale results for 10 minutes after index update

**Real-world evidence:**

- "MySQL Query Cache was deprecated due to cache invalidation overhead where any write to a table invalidated all cached queries for that table" [(Source: OneUpTime)](https://oneuptime.com/blog/post/2026-01-24-mysql-query-cache-deprecated/view)
- "When running multiple application instances, HybridCache doesn't automatically synchronize local L1 cache across nodes - if data is updated on Node A, Node B continues serving stale data from its in-memory cache until the entry expires" [(Source: Milan Jovanovic Blog)](https://www.milanjovanovic.tech/blog/solving-the-distributed-cache-invalidation-problem-with-redis-and-hybridcache)
- "Local caches don't scale horizontally - each instance maintains its own cache, leading to data inconsistencies and duplicated memory usage across nodes" [(Source: DragonflyDB)](https://www.dragonflydb.io/guides/in-memory-cache-how-it-works-and-top-solutions)

**Consequences:**

- User indexes new version of code, searches return old results
- Memory grows unbounded until laptop swap/crash
- Confusion: "I just added this function, why isn't search finding it?"

**Prevention:**

1. **Revision-based invalidation**: Track index version in cache key
   - Cache key: `{index_name}:{revision}:{query_hash}`
   - On re-index, increment revision counter
   - Old revision caches auto-invalidated
2. **Size-bounded cache**: `maxsize=1000` entries, not unlimited
3. **Short TTL for semantic cache**: 5-minute TTL for embedding results (embeddings don't change)
4. **No caching for search results**: Cache embeddings and tsvector preprocessing, NOT final search results
5. **Memory monitoring**: Log cache size every 100 operations, warn if >100MB

**Semantic caching strategy:**

For semantic code search specifically:
- "Set a similarity threshold (e.g., 0.85-0.95) to filter results. High thresholds reduce wrong cache hits but miss legitimate rephrases" [(Source: Redis Blog)](https://redis.io/blog/what-is-semantic-caching/)
- "Limit cache size to prevent memory issues and use time-to-live (TTL) to refresh outdated cache entries" [(Source: Meilisearch)](https://www.meilisearch.com/blog/how-to-cache-semantic-search)
- "MeanCache's embedding compression utility approximately reduces storage and memory needs by 83%" [(Source: ArXiv)](https://arxiv.org/html/2403.02694v3)

**Detection:**

- Warning sign: Search returns results not in current index
- Warning sign: Memory usage grows without bound
- Test: Re-index, verify search returns new results immediately
- Monitor: Cache hit rate, cache size, memory usage

**Which phase addresses this:**

- **Phase 6 (Query Caching/History)**: Build with revision-based invalidation from start
- **Phase 7 (Testing)**: Test re-index + cache invalidation explicitly

---

### Pitfall 5: Documentation Fragments into Maintenance Nightmare

**What goes wrong:**

Overhauling documentation for a tool that has grown from "semantic search" to "hybrid search + context expansion + symbol filtering + stats" creates maintenance burden:
- Multiple documentation locations (README, docs/, CLI help, MCP docstrings)
- Docs go stale as code evolves
- Content gaps where new features aren't documented
- Inconsistent terminology across docs

**Why it happens:**

Research shows this is a widespread 2026 problem:

- "About 69% of developers say they lose eight or more hours per week to inefficiencies, including: unclear navigation, fragmented tools, and repeated context rebuilding. 54% of respondents say they use 6 or more tools to get work done" [(Source: Xurrent Blog)](https://www.xurrent.com/blog/observability-tools)
- "Documentation tools in 2026 are best compared by use case, AI depth, and long-term maintenance effort, with fragmented tool stacks, outdated content, and higher long-term maintenance effort being common issues" [(Source: Documentation.ai)](https://documentation.ai/blog/ai-tools-for-documentation)
- "Confluence remains common for internal docs, but struggles with long-term accuracy and maintenance" [(Source: Medium - 2026 Shift)](https://medium.com/@EmiliaBiblioKit/the-2026-shift-bridging-the-gap-between-design-and-dev-eeefb781af30)

**Common gaps from 2026 research:**

1. **Onboarding docs go stale**: "Multi-page wiki documents explaining how to install dependencies, configure databases, set up environment variables, and troubleshoot common issues are being replaced by automated solutions" [(Source: ClickHelp)](https://clickhelp.com/clickhelp-technical-writing-blog/top-20-software-documentation-tools/)
2. **No single source of truth**: Multiple README files, docs/ directory, wiki, all with conflicting information
3. **Missing retrieval logic docs**: How hybrid search actually works, what RRF k=60 means - critical for debugging

**Consequences:**

- Users can't find documentation for advanced features
- GitHub issues asking questions already answered in (hidden) docs
- Maintainer burden answering same questions repeatedly
- New contributors can't contribute because architecture undocumented

**Prevention:**

1. **Single source of truth**: README for quickstart, docs/ for deep dives, NO wiki
2. **Documentation structure**:
   - README: Quick start, features overview, installation
   - docs/ARCHITECTURE.md: How retrieval works, component boundaries
   - docs/MCP_TOOLS.md: Tool reference with examples
   - CLI --help: Always generated from code (argparse help text)
3. **Inline docstrings drive MCP tool descriptions**: Don't duplicate - MCP tool descriptions FROM function docstrings
4. **Maintenance checklist**: PR template requires "Docs updated?" checkbox
5. **Content gap detection**: Track which features have no documentation (GitHub issue template asks "did you read docs on X?")
6. **Keep focused**: Don't document every internal function - focus on user-facing features and architecture decisions

**Documentation anti-patterns to avoid:**

From CLI Guidelines research:
- "Design for humans first" - write docs for humans, not just reference
- "Follow existing patterns" - use standard structure (like Keep a Changelog format) [(Source: clig.dev)](https://clig.dev/)

**Detection:**

- Warning sign: GitHub issues asking questions answered in docs
- Warning sign: README >500 lines (split into docs/)
- Warning sign: Multiple versions of same information
- Test: Search docs for feature name, verify found in <30 seconds

**Which phase addresses this:**

- **Phase 8 (README Rebrand)**: Restructure for new positioning
- **Phase 9 (Retrieval Logic Documentation)**: Add technical deep dive
- **Phase 10 (MCP Tools Reference)**: Tool reference with examples

---

## Moderate Pitfalls

### Pitfall 6: Hybrid + Symbol Filter Combination Complexity

**What goes wrong:**

v1.7 deferred the combination of hybrid search + symbol filtering, falling back to vector-only. Implementing this in v1.8 introduces SQL query complexity and performance considerations.

**Why it happens:**

- Hybrid search uses RRF (Reciprocal Rank Fusion) combining vector + keyword results
- Symbol filtering requires JOIN on symbols table
- Combining both means RRF must operate on pre-filtered result sets
- Query planner may choose inefficient join order

**Prevention:**

1. **Test with large indexes**: Verify performance with 100K+ chunks, 50K+ symbols
2. **Index strategy**: Ensure GIN index on symbols.symbol_name and vector index on chunks.embedding
3. **Query order matters**: Filter by symbols first (smaller result set), then RRF
4. **Explain analyze**: Run EXPLAIN ANALYZE on combined queries, optimize as needed

**Which phase addresses this:**

- **Phase 1 (Hybrid + Symbol Filter Combination)**

---

### Pitfall 7: Stats Dashboard HTTP API Security

**What goes wrong:**

Adding HTTP API for stats dashboard exposes CocoSearch to network attacks if not properly secured. Local-first tool shouldn't require authentication, but also shouldn't be exploitable.

**Why it happens:**

- HTTP server bound to 0.0.0.0 allows remote access
- No rate limiting on stats endpoints
- CORS misconfiguration allows malicious sites to query stats

**Prevention:**

1. **Bind to localhost only**: HTTP API on 127.0.0.1, not 0.0.0.0
2. **Read-only API**: Stats dashboard is GET only, no POST/PUT/DELETE
3. **No sensitive data**: Don't expose file contents in stats, only counts/metadata
4. **CORS whitelist**: Only allow localhost origins

**Which phase addresses this:**

- **Phase 2 (Stats Dashboard)**

---

### Pitfall 8: Incremental Feature Development Technical Debt

**What goes wrong:**

Adding 5 major feature categories (stats, skills, symbols, caching, docs) to existing 8,225 LOC codebase creates technical debt if not managed carefully.

**Why it happens:**

Research shows this is a critical 2026 concern:

- "75% of technology decision-makers anticipate that their technical debt will reach moderate to severe levels by 2026, partly due to accelerated AI adoption" [(Source: Monday.com)](https://monday.com/blog/rnd/technical-debt/)
- "Technical debt has recently doubled in scale, growing by approximately $6 trillion globally, according to a July 2024 report from Oliver Wyman" [(Source: IBM Think)](https://www.ibm.com/think/topics/technical-debt)
- "As developers add new features and make revisions, software quality can suffer. For instance, repeatedly adding lines to a class can turn it into a large, unwieldy codebase" [(Source: Qt Blog)](https://www.qt.io/quality-assurance/blog/how-to-tackle-technical-debt)

**Consequences:**

- Feature additions slow down as codebase becomes harder to understand
- Test suite becomes brittle and slow
- Bug fix in one feature breaks another

**Prevention:**

1. **Reserve 15-25% of effort for refactoring**: "Reserve 15-25% of each sprint for debt reduction and treat it as seriously as feature development" [(Source: Metamindz)](https://www.metamindz.co.uk/post/technical-debt-vs-feature-development-what-to-prioritize)
2. **Module boundaries**: Each feature has clear module (stats/, skills/, symbols/)
3. **Interface-driven design**: Features communicate through defined interfaces, not direct coupling
4. **Regression tests**: Add tests BEFORE implementing feature to catch breakage
5. **Code review checklist**: "Does this feature increase coupling?" "Is this testable?"

**Which phase addresses this:**

- **All phases**: Continuous vigilance during development

---

## Minor Pitfalls

### Pitfall 9: Skill YAML Frontmatter Errors

**What goes wrong:**

YAML syntax errors in skill frontmatter prevent skill from loading, with unclear error messages.

**Prevention:**

1. **Validate YAML in tests**: CI checks skills/ directory for valid YAML
2. **Schema validation**: Use yamllint or similar to catch common errors
3. **Required fields**: Ensure `name` and `description` always present

**Which phase addresses this:**

- **Phase 3 (Claude Code Skill)**, **Phase 4 (OpenCode Skill)**

---

### Pitfall 10: Symbol Hierarchy Display Truncation

**What goes wrong:**

Nested symbol hierarchy (Class.method.inner_function) becomes too long for terminal display or MCP responses.

**Prevention:**

1. **Configurable depth**: Default to 2 levels, allow --symbol-depth flag
2. **Truncation with ellipsis**: Display "LongClassName...method" if too long
3. **Full path in structured output**: JSON includes full path even if display truncated

**Which phase addresses this:**

- **Phase 1 (Nested Symbol Hierarchy)**

---

### Pitfall 11: Query History Disk Space Growth

**What goes wrong:**

Storing query history indefinitely consumes disk space, especially with embeddings.

**Prevention:**

1. **Don't store embeddings in history**: Only store query text, timestamp, result count
2. **Automatic pruning**: Keep last 1000 queries or 30 days, whichever is smaller
3. **Opt-in**: History collection OFF by default, enable with config flag

**Which phase addresses this:**

- **Phase 6 (Query Caching/History)**

---

## Phase-Specific Warnings

| Phase | Topic | Likely Pitfall | Mitigation |
|-------|-------|---------------|------------|
| 1 | Hybrid + Symbol Filter | Query performance on large indexes | Test with 100K+ chunks, EXPLAIN ANALYZE |
| 1 | Nested Symbol Hierarchy | Display truncation | Configurable depth, ellipsis truncation |
| 2 | Stats Dashboard | Performance overhead from sync collection | Async collection, batch writes, opt-in |
| 2 | Stats Dashboard | HTTP API security | Bind to localhost, read-only, CORS whitelist |
| 3 | Claude Code Skill | Routing unpredictability | Specific names, clear triggers, minimal permissions |
| 4 | OpenCode Skill | Duplicate routing with Claude Code skill | Test both independently |
| 5 | Expanded Symbol Extraction | C/C++ preprocessor failures | Fallback to chunk-only, document limitations |
| 6 | Query Caching | Cache invalidation on re-index | Revision-based cache keys |
| 6 | Query History | Disk space growth | Prune old entries, no embeddings in history |
| 7 | Testing | Test suite slowdown | Unit tests remain fast (<5s), integration opt-in |
| 8 | README Rebrand | Documentation fragmentation | Single source of truth, clear structure |
| 9 | Retrieval Logic Docs | Over-documentation of internals | Focus on user-facing behavior and architecture |
| 10 | MCP Tools Reference | Docs drift from code | Generate from docstrings where possible |

---

## Integration-Specific Warnings

Adding features to existing 8,225 LOC system introduces coupling risks:

### Database Schema Evolution

**Risk**: Adding stats tables, symbol hierarchy columns, cache tables

**Mitigation**:
- Additive schema only (no breaking changes to existing tables)
- Schema versioning in metadata table
- Graceful degradation if schema not upgraded

### Module Coupling

**Risk**: Stats collection code scattered throughout search/index modules

**Mitigation**:
- Stats as separate module with clear interface
- Decorator pattern for metric collection (doesn't modify core logic)
- Feature flags to disable entirely

### Configuration Complexity

**Risk**: Config file grows with stats options, cache options, skill paths

**Mitigation**:
- Nested config sections (stats: {}, cache: {})
- Sensible defaults (features OFF by default)
- Config validation with helpful error messages

### Testing Combinatorial Explosion

**Risk**: 5 new features = 2^5 = 32 combinations to test

**Mitigation**:
- Test features independently first
- Integration tests for common combinations only (hybrid + symbols, not all 32)
- Property-based testing for edge cases

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|----------|-------|
| Stats Dashboard | HIGH | Well-researched with 2026 MCP observability sources |
| Claude Code Skills | HIGH | Official Anthropic documentation and 2026 blog posts |
| Symbol Extraction (Java, Ruby, PHP) | MEDIUM | Tree-sitter issues documented but limited production data |
| Symbol Extraction (C/C++) | LOW | Known limitations but unclear severity in practice |
| Query Caching | HIGH | Extensive research on semantic caching and invalidation |
| Documentation | HIGH | 2026 developer tool documentation research |

---

## Research Sources

### High Confidence (Official/Technical)

1. [Anthropic Claude Code Skills Documentation](https://code.claude.com/docs/en/skills)
2. [Skill Authoring Best Practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
3. [MCP Observability Overview](https://www.merge.dev/blog/mcp-observability)
4. [MCP Best Practices: Architecture & Implementation](https://modelcontextprotocol.info/docs/best-practices/)
5. [Tree-sitter C Preprocessor Issues](https://github.com/tree-sitter/tree-sitter-c/issues/108)
6. [Redis Cache Invalidation](https://redis.io/glossary/cache-invalidation/)
7. [Semantic Caching Guide](https://redis.io/blog/what-is-semantic-caching/)
8. [CLI Guidelines](https://clig.dev/)

### Medium Confidence (2026 Industry Research)

9. [Google Gemini CLI Monitoring Dashboards 2026](https://cloud.google.com/blog/topics/developers-practitioners/instant-insights-gemini-clis-new-pre-configured-monitoring-dashboards)
10. [Top Infrastructure Monitoring Tools 2026](https://clickhouse.com/resources/engineering/top-infrastructure-monitoring-tools-comparison)
11. [MCP Performance Monitoring 2026](https://www.byteplus.com/en/topic/541572)
12. [MCP Server Best Practices 2026](https://www.cdata.com/blog/mcp-server-best-practices-2026)
13. [Technical Debt Strategic Guide 2026](https://monday.com/blog/rnd/technical-debt/)
14. [Developer Documentation Tools 2026](https://documentation.ai/blog/ai-tools-for-documentation)

### Medium Confidence (Technical Deep Dives)

15. [Claude Skills Deep Dive](https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/)
16. [Tree-sitter and Preprocessing](https://habr.com/en/articles/835192/)
17. [Mastering Emacs: Tree-sitter Complications](https://www.masteringemacs.org/article/tree-sitter-complications-of-parsing-languages)
18. [Distributed Cache Invalidation with Redis](https://www.milanjovanovic.tech/blog/solving-the-distributed-cache-invalidation-problem-with-redis-and-hybridcache)

### Low Confidence (Community/Blog Posts)

19. [Claude Code Best Practices Blog](https://medium.com/@rub1cc/how-claude-codes-creator-uses-it-10-best-practices-from-the-team-e43be312836f)
20. [Claude Skills and CLAUDE.md Practical Guide](https://www.gend.co/blog/claude-skills-claude-md-guide)

---

## Gaps to Address

### Areas Needing Phase-Specific Research

1. **Stats dashboard UI framework**: Which terminal UI library (rich, textual, blessed)? Needs evaluation in Phase 2
2. **HTTP framework for stats API**: FastAPI, Flask, or built-in http.server? Needs benchmarking
3. **Symbol hierarchy storage**: Nested arrays vs JSONB vs separate table? Database design decision in Phase 1
4. **Cache storage**: In-memory only vs SQLite vs PostgreSQL table? Performance tradeoff in Phase 6

### Known Unknowns

1. **Real-world C++ parsing failure rate**: We know it's problematic, but what % of files fail? Need production data
2. **Query cache hit rate**: What's realistic for code search? General semantic caching is 60-80%, but code queries may differ
3. **Stats collection overhead**: How many milliseconds does async write add? Need benchmarking with CocoSearch's stack

### Validation Needed

These pitfalls are based on research and analogous systems. Validation during implementation:
- [ ] Measure actual stats collection overhead in Phase 2
- [ ] Test C/C++ symbol extraction on 5+ real codebases in Phase 5
- [ ] Benchmark cache invalidation strategies in Phase 6
- [ ] User testing of skill routing with ambiguous queries in Phase 3/4

---

*Last updated: 2026-02-03 - Based on web search of 2026 sources and official documentation*
