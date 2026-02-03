# Feature Landscape: v1.8 Capabilities

**Domain:** Stats dashboard, Claude Code/OpenCode skills, query caching, expanded symbol extraction
**Researched:** 2026-02-03
**Confidence:** MEDIUM-HIGH (WebSearch findings verified with multiple sources where possible, some areas remain LOW confidence and flagged)

## Executive Summary

This research covers four enhancement areas for CocoSearch v1.8:

1. **Stats Dashboard** — Visual/text metrics about index health, search performance, and usage patterns
2. **Claude Code / OpenCode Skills** — Agent Skills for integrating CocoSearch into AI coding workflows
3. **Query Caching** — Semantic and exact-match caching to speed up repeated searches
4. **Expanded Symbol Extraction** — Enhanced symbol types, cross-references, and definition lookup

**Key finding:** These features represent the evolution from "working code search" to "production code intelligence platform." Stats and skills improve developer experience, caching improves performance at scale, and enhanced symbols enable LSP-like navigation.

**Confidence breakdown:**
- Stats Dashboard: MEDIUM (community patterns, not domain-specific)
- Skills: HIGH (official documentation, clear patterns from Anthropic)
- Query Caching: HIGH (established patterns from vector DB vendors)
- Symbol Extraction: MEDIUM (Tree-sitter capabilities verified, LSP integration patterns less clear)

## Table Stakes

Features users expect when these capabilities are advertised. Missing these makes the feature feel incomplete or broken.

### Stats Dashboard

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Index health metrics** | Users expect to see: total files indexed, total chunks, total embedding vectors, index size on disk, last updated timestamp. This is standard in all search tools (Elasticsearch, Meilisearch, Typesense). | LOW | Query PostgreSQL for counts: `SELECT COUNT(*) FROM chunks`, `SELECT pg_database_size(current_database())` for disk size, `SELECT MAX(indexed_at) FROM files` for last update. All data already exists. |
| **Language breakdown** | Show files/chunks/lines per language: "Python: 450 files, 12K chunks, 85K lines; TypeScript: 320 files, 9K chunks, 62K lines." Essential for understanding codebase composition. | LOW | Already have `language_id` in chunks table from v1.2. `SELECT language_id, COUNT(*), SUM(end_byte - start_byte) FROM chunks GROUP BY language_id`. Convert bytes to lines estimate (bytes / 80 avg line length). |
| **Symbol statistics** | Count of symbols by type: "Functions: 1,234; Classes: 567; Methods: 2,890." Shows symbol-aware indexing is working. Expected once symbols are a first-class feature. | LOW | `SELECT symbol_type, COUNT(*) FROM chunks WHERE symbol_type IS NOT NULL GROUP BY symbol_type`. Already have symbol metadata from v1.7 enhancements. |
| **Text-based output** | CLI users expect plain text tables, not just JSON. `cocosearch stats <index>` should show human-readable output in terminal. | LOW | Use Rich tables (already dependency for pretty output). Format counts with thousands separators, sizes with human units (MB, GB). |
| **JSON output mode** | `--json` flag for programmatic access. MCP tools, scripts, dashboards need structured data. | LOW | `--json` already implemented in v1.0 for search. Extend to stats command. Return dict with all metrics. |
| **Index staleness warning** | If last update >7 days old, warn: "Index may be stale. Run 'cocosearch reindex' to update." Prevents confusion when search misses recent code changes. | LOW | Compare `MAX(indexed_at)` to current time. If diff > threshold (7d default, configurable), print warning to stderr. |

### Claude Code / OpenCode Skills

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **SKILL.md format compliance** | Skills must use YAML frontmatter with `name`, `version`, `trigger`, `description` fields, followed by markdown instructions. This is the Agent Skills standard used by Claude Code, OpenCode, Cursor, Gemini CLI. | LOW | Write `.claude/skills/cocosearch/SKILL.md` with proper structure. Reference official examples from anthropics/skills repo. |
| **Trigger patterns** | Skill should trigger on keywords: "search code", "find in codebase", "semantic search", "code search". Users expect skills to activate on natural language commands, not manual invocation. | LOW | Define in YAML frontmatter: `trigger: ["search code", "find in codebase", "semantic search"]`. Claude Code auto-activates skill when trigger phrase detected. |
| **MCP tool integration** | Skill instructions should reference MCP tools: "Use cocosearch_search tool with query parameter." Skills orchestrate MCP tools—they're complementary, not alternatives. | LOW | Document which MCP tools the skill calls (cocosearch_search, cocosearch_stats, etc.). Provide example prompts and expected workflows. |
| **Error handling guidance** | Tell agent what to do if search returns 0 results: "If no results, suggest broadening query or checking index freshness." Agent needs guidance for edge cases. | LOW | Include error handling section in SKILL.md: "When X happens, do Y." Helps agent recover gracefully. |
| **Progressive disclosure** | Don't load entire CocoSearch documentation into skill. Skill provides high-level workflow; agent uses MCP tools for details. Keep skill <500 tokens to avoid context bloat. | MEDIUM | Write concise instructions: "When user asks to search code, call cocosearch_search with natural language query." Link to docs for details. |
| **Multi-skill compatibility** | Skill should compose with git, file editing, code review skills. Example: "Use cocosearch to find auth logic, then use code review skill to analyze it." Skills aren't silos. | LOW | Test with common skill combinations. Ensure skill doesn't monopolize context or break when other skills are active. |

### Query Caching

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Exact match cache** | Identical queries return cached results instantly. "Find authentication logic" searched twice should hit cache on second attempt. This is baseline caching—every search tool does it. | LOW | Hash query string → cache key. Store results dict in Redis or local cache with 24h TTL. Check cache before embedding generation. |
| **Semantic similarity cache** | Similar queries reuse results: "authentication logic" and "auth code" should hit same cache. Uses embedding similarity to detect near-duplicate queries. | MEDIUM | Store query embedding in vector DB (Qdrant, Milvus, pgvector). For new query, search for similar cached queries (cosine similarity >0.95). If hit, return cached results. |
| **TTL expiration** | Cache entries expire after configured period (default 24h exact match, 7d semantic). Prevents stale results when codebase changes. | LOW | Redis TTL built-in. For local cache, store timestamp with each entry, check on retrieval. |
| **Cache invalidation on reindex** | When index is updated, clear cache for that index. Otherwise, cached results may reference deleted/moved files. | LOW | Maintain cache namespace per index: `cache:{index_name}:*`. On reindex, delete all keys in that namespace. Or simpler: include index update timestamp in cache key. |
| **Cache hit/miss metrics** | Track cache hit rate: "Cache hits: 847 (73%), misses: 314 (27%)." Essential for tuning cache parameters (TTL, similarity threshold). | LOW | Increment counters on hit/miss. Store in Redis or local SQLite. Expose via stats command: `cocosearch stats cache`. |
| **Disable cache flag** | `--no-cache` flag for users who want fresh results every time. Useful for benchmarking or testing. | LOW | Check flag before cache lookup. Skip cache and proceed to normal search. |

### Expanded Symbol Extraction

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Additional symbol types** | Beyond functions/classes, support: interfaces, enums, structs, type aliases, constants, global variables. TypeScript has interfaces; Rust/Go have structs; Python has module-level constants. Language-specific but expected. | MEDIUM | Extend Tree-sitter queries per language. TypeScript: `interface_declaration`, `enum_declaration`, `type_alias_declaration`. Python: `assignment` at module level for constants. Requires language-specific query files. |
| **Docstring extraction** | Store first line of docstring/comment with symbol: "Authenticates user with OAuth2 provider." Shown in search results for context. LSP hover tooltips show this—users expect it. | MEDIUM | Tree-sitter captures comments above function/class. Language-specific: Python docstrings are `expression_statement` with string; JSDoc is `comment` node. Extract and store in `symbol_docstring` column. |
| **Parameter/return type info** | For typed languages (TypeScript, Go, Rust), extract function signature: `fn authenticate(user: User, token: str) -> Result<Session>`. Helps users understand API without opening file. | HIGH | Tree-sitter provides type annotations. TypeScript: `type_annotation` nodes on parameters. Go: parameter/return types are sibling nodes to function name. Parse and store in `symbol_signature` column. Complex because types can be deeply nested. |
| **Symbol location precision** | Store line/column start and end, not just byte offsets. IDEs expect line:column format for navigation. | MEDIUM | Tree-sitter nodes provide start/end points as `(row, column)` tuples. Store in database, convert byte offsets to line/column on indexing. Requires counting newlines, already doing this for context expansion. |
| **Symbol scoping** | Nested symbols store parent scope: method `validate` in class `AuthService` → `AuthService.validate`. Prevents ambiguity when multiple classes have same method name. | MEDIUM | Walk up Tree-sitter AST to find enclosing class/module/namespace. Store fully qualified name in `symbol_full_name` column. Already identified as HIGH complexity in v1.7 research for hierarchy. |
| **Symbol kind metadata** | Tag symbols with kind: `async_function`, `static_method`, `abstract_class`, `readonly_property`. Provides semantic richness beyond basic type. | MEDIUM | Tree-sitter node types distinguish: Python `async` keyword → `async_function`, `@staticmethod` decorator → static method. Requires per-language mapping of node patterns to kinds. |

## Differentiators

Features that set CocoSearch apart from competitors. Not expected, but highly valued when present.

### Stats Dashboard Advanced Features

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Search performance metrics** | Track P50, P95, P99 query latency over time. "Median search: 45ms, 95th percentile: 180ms." Helps identify performance degradation as index grows. | MEDIUM | Store query execution times in time-series database (SQLite with timestamp) or append-only log. Calculate percentiles on-demand. Already have timing in search code—just need to persist. |
| **Top queries dashboard** | Show most common search queries: "authentication: 47 times, database migration: 23 times, error handling: 19 times." Reveals what users care about, informs roadmap. | MEDIUM | Store query strings in database with count. Privacy concern: queries may contain sensitive info. Make opt-in with `--telemetry` flag (default off for local-first tool). |
| **Index growth trends** | Graph of files/chunks/size over time: "Index grew 15% last week (120 new files)." Useful for understanding codebase evolution. | HIGH | Requires historical snapshots. On each reindex, store current metrics with timestamp. Query time-series data for trends. Needs stats persistence infrastructure. |
| **Dependency-free visualization** | Terminal-based graphs using Unicode box characters. No need for web server or separate dashboard app. `cocosearch stats --graph` shows sparklines in terminal. | MEDIUM | Use libraries like `plotille` (Unicode plots) or `rich` (already dependency). Lightweight, no additional runtime deps. |
| **Health check endpoint** | `cocosearch health <index>` returns exit code 0 if index is healthy, 1 if issues detected (missing files, corrupted data, outdated schema). Useful for monitoring scripts. | LOW | Check: (1) index exists in DB, (2) file count > 0, (3) schema version matches current, (4) sample query executes. Return status code. |
| **Export stats to JSON/CSV** | `cocosearch stats --export stats.json` for integration with external dashboards (Grafana, Datadog). Enables enterprise observability. | LOW | Serialize stats dict to JSON or CSV. Simple file output, no API server needed. |

### Claude Code / OpenCode Skills Advanced Features

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Multi-step workflow skill** | "Research unfamiliar codebase" skill: (1) stats for overview, (2) search for entry points (main, init), (3) search for tests, (4) summarize architecture. Orchestrates multiple searches into cohesive workflow. | MEDIUM | Skill provides step-by-step template. Agent executes each step with MCP tools. Skill doesn't execute logic—it guides agent's decision-making. |
| **Context-aware suggestions** | Skill detects when search returns too many/few results and suggests refinements: "Try narrowing to specific language with --language flag" or "Broaden query—try semantic terms instead of exact identifiers." | MEDIUM | Include decision tree in skill: "If results > 50, suggest filters. If results < 3, suggest broader query." Agent interprets and acts on suggestions. |
| **Integration with git workflow** | Skill combines search with git: "Find all files modified in last commit that mention 'database', then search for migration logic." Bridges CocoSearch with git MCP tools. | LOW | Skill orchestrates both tools: "Use git_diff to get changed files, filter by search term, then use cocosearch_search on those files." No code changes to CocoSearch—pure skill logic. |
| **Skill versioning** | Skill frontmatter includes version: `version: 1.0.0`. When CocoSearch adds new features (e.g., caching), skill can be updated independently. Users pull new skill versions without upgrading CLI. | LOW | Follow Agent Skills standard. Include `version` in YAML. Skill updates distributed via `.claude/skills/` repo updates, not CocoSearch releases. |
| **Skill discovery via MCP** | MCP tool `list_skills` returns available CocoSearch skills. Agent can discover and activate skills programmatically. | LOW | Add `cocosearch_list_skills` MCP tool that returns skill metadata (name, description, version, triggers). Reads from `.claude/skills/` directory. |
| **Domain-specific skills** | Separate skills for common workflows: "debugging" (find error logs + stack traces), "refactoring" (find all usages of symbol), "onboarding" (codebase overview). Each optimized for specific use case. | MEDIUM | Create multiple SKILL.md files, one per workflow. Each skill tailored to common developer tasks. Requires research into what workflows are most valuable. |

### Query Caching Advanced Features

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Embedding cache reuse** | Cache query embeddings separately from results. If "authentication logic" and "auth code" have similar embeddings, skip embedding generation for second query. Saves 50-200ms per query. | MEDIUM | Two-layer cache: (1) query text → embedding (with semantic similarity lookup), (2) embedding → search results. Check both layers. Embedding cache has longer TTL (30d) since embeddings are expensive and rarely change. |
| **Adaptive cache TTL** | Frequently accessed queries get longer TTL (up to 30d). Rarely accessed queries expire sooner (1d). Balances freshness and hit rate. | MEDIUM | Track query frequency in cache metadata. Extend TTL on each hit: `new_ttl = min(current_ttl * 1.5, max_ttl)`. Decay over time if not accessed. |
| **Pre-warming common queries** | On index creation, cache results for common queries: "main", "test", "config", "error". First search is slow, subsequent are instant. | LOW | After reindex completes, execute predefined query list and populate cache. List is configurable (users add their common queries). Simple post-indexing step. |
| **Cache compression** | Compress cached results with zlib/gzip. Results are JSON-serializable dicts—compress well. Reduces memory/disk usage for large result sets. | LOW | Compress before storing in Redis/disk. Decompress on retrieval. Python `zlib` built-in. Transparent to caller. |
| **Distributed cache** | Use Redis for cache when CocoSearch is deployed on multiple machines (enterprise setup). Shared cache across developer team. | MEDIUM | Add Redis support alongside local cache. Configure via env var `COCOSEARCH_CACHE_REDIS_URL`. Falls back to local if not set. Most users don't need this (single developer), but high value for teams. |
| **Cache analytics** | `cocosearch cache stats` shows: hit rate, top cached queries, cache size, eviction rate, avg time saved per hit. Helps tune cache parameters. | LOW | Store cache metrics in SQLite or Redis. Expose via stats command. Provides visibility into cache effectiveness. |

### Expanded Symbol Extraction Advanced Features

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Symbol cross-references** | Show "Used by X files" count in search results: "function: authenticate (used in 23 files)." Indicates importance/centrality of symbol. | HIGH | Two-pass indexing: (1) extract all symbol definitions, (2) scan all files for references (imports, calls), (3) count. Expensive but high value. Requires full-codebase symbol resolution. |
| **Jump to definition** | MCP tool: `cocosearch_jump_to_definition(symbol_name)` returns file + line number. Enables IDE-like navigation. "Where is `authenticate_user` defined?" → instant answer. | LOW | SQL query: `SELECT file_path, start_line FROM chunks WHERE symbol_name = ? AND symbol_type IN ('function', 'class') ORDER BY symbol_kind = 'definition' DESC LIMIT 1`. Already have symbol metadata—just expose via MCP. |
| **Symbol search by signature** | Search for functions by signature pattern: "functions that take User and return Result". Uses type info from expanded extraction. | VERY HIGH | Requires type system understanding. Parse type signatures, normalize (e.g., `Result<Session>` ≈ `Result[Session]`), index in searchable format. Complex because types vary wildly across languages. Probably defer to v2.0 or specialized tool. |
| **Symbol usage examples** | Return code snippets showing how symbol is used: "authenticate is called with user object and token string." Helps understand API without reading docs. | HIGH | Extract call sites from AST: find function calls matching symbol name, extract surrounding context (parent statement). Requires call graph analysis. High complexity, medium value—defer unless clear demand. |
| **Deprecated symbol detection** | Mark symbols with deprecation warnings if docstring contains `@deprecated` or `Deprecated:`. Show warning in search results. | MEDIUM | Parse docstrings for deprecation markers (language-specific: Python `warnings.deprecated`, JSDoc `@deprecated`). Store `is_deprecated` flag in metadata. |
| **Symbol ranking boost** | When query contains symbol name, rank definition chunks 3x higher than usage chunks. "Find UserService" should show class definition first, not random usages. | LOW | Extend RRF scoring with symbol type weights: definition=3.0, method=2.0, usage=1.0. Simple multiplier on base score. |

## Anti-Features

Features to explicitly NOT build. Common mistakes in this domain.

### Stats Dashboard Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Web-based dashboard** | CocoSearch is local-first, CLI-centric. Adding web server introduces dependencies (Flask/FastAPI), security concerns (auth, CORS), deployment complexity. Breaks simplicity. | Stick to terminal UI with Rich tables and Unicode plots. For external dashboards, export stats to JSON and let users import into their own tools (Grafana, Datadog). |
| **Real-time streaming stats** | Live-updating stats in terminal (top/htop style) is complexity for little value. CocoSearch searches are fast (<500ms)—real-time tracking not meaningful. | Batch stats: `cocosearch stats` runs once, shows snapshot. Users can run in watch loop if needed: `watch -n 5 cocosearch stats`. |
| **Telemetry by default** | Sending usage data to external servers violates local-first principle. Users chose CocoSearch because data stays on their machine. | Make telemetry explicit opt-in with `--telemetry` flag and clear documentation. Default: no data leaves the machine. |
| **Query logging without consent** | Logging search queries for "top queries" feature risks leaking sensitive info (API keys, internal names). Privacy violation. | Only log queries if user explicitly enables with config flag. Document privacy implications clearly. Better: don't log queries at all, only aggregate metrics (count, latency). |

### Skills Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Skills that execute code** | Skills should guide, not execute. Running code (e.g., auto-refactoring) is dangerous—agent might make unintended changes. Skills orchestrate tools, tools execute. | Skills provide instructions: "Use file_edit tool to refactor." Agent confirms with user before executing. Keep skills declarative, not imperative. |
| **Overly prescriptive workflows** | "Always search X, then Y, then Z" removes agent flexibility. Agent should adapt to user needs, not follow rigid script. | Provide workflow templates as guidance: "Consider searching for entry points, then tests." Use "may", "consider", "typically" language. |
| **Skills that depend on CocoSearch internals** | Skill that references "use hybrid search with 0.7 weight" breaks when we change implementation. Skills should be high-level, agnostic to internals. | Document user-facing features: "Search supports both semantic and keyword matching." Agent uses MCP tools, which abstract implementation. |
| **One mega-skill** | Giant skill covering all CocoSearch features (search, stats, reindex, caching) creates context bloat and confusion. Skills should be focused. | Multiple small skills: "search-workflow.md", "debugging-workflow.md", "onboarding-workflow.md". User/agent activates relevant skill for task. |

### Query Caching Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Cache file contents** | Caching file text alongside search results duplicates data and risks staleness. File may change between cache write and cache read. | Cache only search result metadata (file paths, line numbers, scores). Read actual file content on-demand from disk (already doing this with reference-only storage). |
| **Infinite cache TTL** | "Cache forever for performance" causes stale results when code changes. Cache invalidation is hard—TTL is easier. | Use reasonable TTLs (24h exact, 7d semantic) and invalidate on reindex. Favor correctness over performance. |
| **Complex cache eviction policies** | LRU, LFU, ARC are over-engineering for single-developer use case. Redis/SQLite already handle memory limits. | Use simple TTL-based expiration. Let Redis handle memory eviction with its built-in policies. For local cache, set max size and drop oldest entries when full. |
| **Caching embedding model outputs** | Embedding model outputs (vectors) are already cached by vector DB (pgvector). Redundant caching wastes space. | Only cache at application layer (query string → results). Let PostgreSQL handle vector storage and retrieval. |

### Symbol Extraction Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Build full call graph** | Call graph requires resolving all function calls across codebase, handling imports, aliasing, dynamic dispatch. This is LSP server territory—complex and error-prone. | Provide symbol definitions and basic metadata. For "what calls this function", users should use proper LSP (rust-analyzer, pyright). CocoSearch is search, not IDE. |
| **Type inference** | Inferring types for untyped languages (Python without hints, JavaScript) requires running type checker (mypy, TypeScript compiler). Out of scope for search tool. | Extract explicit type annotations only. For untyped code, store `symbol_type = None`. Don't try to infer—leave that to LSP. |
| **Runtime symbol analysis** | Some want to extract actual runtime behavior (profiling, code coverage) to weight symbols. Requires executing code—dangerous and complex. | Stick to static analysis (Tree-sitter, AST). No code execution. Symbol importance can be inferred from search frequency and cross-references (static). |
| **Language-agnostic symbol extraction** | Trying to extract "symbols" from languages without clear symbol concept (Bash scripts, Makefiles, config files) produces garbage. Not all files have symbols. | Only extract symbols from languages with well-defined symbol semantics (functions, classes). For config files, index as plain text chunks—no symbol metadata. |

## Feature Dependencies

```
Stats Dashboard
  ├─ Index metadata (already exists in v1.2)
  ├─ Symbol statistics → requires Expanded Symbol Extraction
  └─ Search performance metrics → requires Query Caching (optional)

Claude Code / OpenCode Skills
  ├─ MCP server (already exists in v1.0)
  ├─ Stats command → requires Stats Dashboard (for overview workflow)
  └─ Symbol search → requires Expanded Symbol Extraction (for navigation workflow)

Query Caching
  ├─ Embedding generation (already exists in v1.0)
  ├─ Search results format (already exists in v1.0)
  └─ Cache invalidation → requires tracking index update timestamp

Expanded Symbol Extraction
  ├─ Tree-sitter parsing (already exists via CocoIndex in v1.2)
  ├─ Symbol metadata storage → extends v1.7 symbol-aware indexing
  └─ Type annotation parsing → language-specific, may not be available for all languages
```

**Critical path:**
1. Stats Dashboard can be built independently (only depends on existing data)
2. Skills can be built independently (orchestrate existing MCP tools)
3. Query Caching can be built independently (wraps existing search)
4. Expanded Symbol Extraction extends v1.7 symbol work (incremental)

**No blockers—all features can proceed in parallel.**

## MVP Recommendation

For v1.8 MVP, prioritize features by user value and implementation risk:

### High Priority (Must Have for v1.8)

1. **Stats Dashboard (basic)** — Essential for users to understand index health
   - Index metrics (files, chunks, size, last update)
   - Language breakdown
   - Text + JSON output
   - **Complexity: LOW, Value: HIGH**

2. **Claude Code Skill (basic)** — High demand from AI-assisted dev community
   - Single skill: "search-codebase.md"
   - Trigger on "search code" phrases
   - Integrates with existing MCP tools
   - **Complexity: LOW, Value: HIGH**

3. **Query Caching (exact match only)** — Low-hanging fruit for performance
   - Hash-based exact match cache
   - 24h TTL, invalidate on reindex
   - `--no-cache` flag
   - **Complexity: LOW, Value: MEDIUM**

4. **Symbol Extraction (additional types)** — Extend v1.7 symbol work
   - Interfaces, enums, structs, type aliases
   - Docstring extraction (first line only)
   - **Complexity: MEDIUM, Value: MEDIUM**

### Medium Priority (Nice to Have for v1.8)

5. **Stats Dashboard (advanced)** — Deeper insights
   - Search performance metrics (P50, P95, P99)
   - Cache hit rate
   - Terminal graphs (sparklines)
   - **Complexity: MEDIUM, Value: MEDIUM**

6. **Query Caching (semantic)** — Requires vector storage
   - Semantic similarity cache (cosine >0.95)
   - Embedding cache reuse
   - Cache analytics
   - **Complexity: MEDIUM, Value: MEDIUM**

7. **Symbol Extraction (metadata)** — Richer context
   - Parameter/return types
   - Symbol scoping (fully qualified names)
   - Symbol kind (async, static, abstract)
   - **Complexity: MEDIUM-HIGH, Value: MEDIUM**

8. **Skills (workflow-oriented)** — Multiple specialized skills
   - debugging-workflow.md
   - onboarding-workflow.md
   - refactoring-workflow.md
   - **Complexity: MEDIUM, Value: MEDIUM**

### Low Priority (Defer to v1.9+)

9. **Symbol cross-references** — Two-pass indexing, expensive
   - Defer until user demand validated
   - **Complexity: HIGH, Value: MEDIUM**

10. **Index growth trends** — Requires time-series storage
    - Defer until stats persistence infrastructure exists
    - **Complexity: HIGH, Value: LOW**

11. **Distributed cache** — Enterprise feature, low single-dev value
    - Defer until team usage patterns emerge
    - **Complexity: MEDIUM, Value: LOW for target users**

## Gaps to Address in Phase-Specific Research

Areas where this research was inconclusive or needs deeper investigation:

### Stats Dashboard

- **LOW confidence:** Optimal metrics for code search vs general DevOps tools. Most research is about build/deployment metrics, not search-specific KPIs.
- **Need to research:** What metrics do users of Sourcegraph, Hound, or similar tools find most valuable? Survey or interview users.
- **Gap:** Terminal visualization libraries—which render best in various terminal emulators? Need to test `rich`, `plotille`, `termgraph`.

### Claude Code / OpenCode Skills

- **MEDIUM confidence:** Skill effectiveness patterns. Official docs are clear, but best practices for search-oriented skills are unclear.
- **Need to research:** What makes a good "code search" skill vs generic "use this tool" skill? Requires prototyping and user testing.
- **Gap:** Skill discoverability—how do users find skills for installed tools? Is listing in MCP sufficient or do skills need a registry?

### Query Caching

- **HIGH confidence:** Caching strategies are well-documented by vector DB vendors (Redis, Milvus, Qdrant). But...
- **Need to research:** Semantic cache similarity threshold—0.95 is cited frequently, but is it optimal for code search queries? May need experimentation.
- **Gap:** Cache size estimation—how much memory/disk does caching consume for typical codebases? Need benchmarks.

### Expanded Symbol Extraction

- **MEDIUM confidence:** Tree-sitter capabilities are clear, but integration patterns vary wildly across projects.
- **Need to research:** Language-specific symbol extraction quirks. Each language has edge cases (Python decorators, TypeScript type guards, Rust macros).
- **Gap:** Symbol cross-reference performance—how expensive is two-pass indexing on large codebases (100k+ files)? Need profiling.
- **Gap:** Definition vs declaration—some languages distinguish (C header vs implementation). How to prioritize in search results?

## Sources

### Stats Dashboard
- [Claude Code Analytics Dashboard](https://code.claude.com/docs/en/analytics) - Usage and contribution metrics for developer tools
- [How to Build a Developer Productivity Dashboard](https://jellyfish.co/library/developer-productivity/dashboard/) - DORA metrics and KPIs
- [11 DevOps Metrics You Should Be Monitoring in 2026](https://middleware.io/blog/devops-metrics-you-should-be-monitoring/) - Performance and workflow metrics
- [.NET Aspire dashboard for local development](https://anthonysimmon.com/dotnet-aspire-dashboard-best-tool-visualize-opentelemetry-local-dev/) - Local-first dashboard patterns
- [Open Source Dashboards: 9 Best Tools (2026)](https://www.metricfire.com/blog/top-8-open-source-dashboards/) - Grafana and alternatives

### Claude Code / OpenCode Skills
- [The Complete Claude Code Guide: Skills, MCP & Tool Integration](https://mrzacsmith.medium.com/the-complete-claude-code-guide-skills-mcp-tool-integration-part-2-20dcf2fb8877) - Integration patterns
- [Claude Skills vs MCP: The 2026 Guide to Agentic Architecture](https://www.cometapi.com/claude-skills-vs-mcp-the-2026-guide-to-agentic-architecture/) - Complementary relationship
- [Skills explained: How Skills compares to prompts, Projects, MCP, and subagents](https://claude.com/blog/skills-explained) - Official Anthropic documentation
- [Extending Claude's capabilities with skills and MCP](https://claude.com/blog/extending-claude-capabilities-with-skills-mcp-servers) - Official Anthropic documentation
- [Writing OpenCode Agent Skills: A Practical Guide](https://blog.devgenius.io/writing-opencode-agent-skills-a-practical-guide-with-examples-870ff24eec66) - Implementation examples
- [Agent Skills | OpenCode](https://opencode.ai/docs/skills) - OpenCode official documentation
- [Progressive Disclosure in AI Coding Tools](https://alexop.dev/posts/stop-bloating-your-claude-md-progressive-disclosure-ai-coding-tools/) - Context management best practices

### Query Caching
- [Semantic Caching: What We Measured, Why It Matters](https://www.catchpoint.com/blog/semantic-caching-what-we-measured-why-it-matters) - Performance benchmarks
- [How to Build LLM Caching Strategies](https://oneuptime.com/blog/post/2026-01-30-llm-caching-strategies/view) - Exact match, semantic, and provider caching
- [How to cache semantic search: a complete guide](https://www.meilisearch.com/blog/how-to-cache-semantic-search) - Implementation patterns
- [Semantic Caching and Memory Patterns for Vector Databases](https://www.dataquest.io/blog/semantic-caching-and-memory-patterns-for-vector-databases/) - Configuration and best practices
- [Redis Semantic Caching: Cut Your LLM Costs by 80%](https://medium.com/@srajsonu/redis-semantic-caching-cut-your-llm-costs-by-80-with-smarter-cache-hits-8512cdcbb7be) - Two-tier caching patterns
- [Caching Embeddings | RedisVL](https://redis.io/docs/latest/develop/ai/redisvl/user_guide/embeddings_cache/) - Embedding reuse strategies
- [10 techniques to optimize your semantic cache with Redis](https://redis.io/blog/10-techniques-for-semantic-cache-optimization/) - TTL and eviction policies
- [Vector search result caching with ElastiCache](https://aws.amazon.com/blogs/database/announcing-vector-search-for-amazon-elasticache/) - Real-time cache updates

### Symbol Extraction
- [Explainer: Tree-sitter vs. LSP](https://lambdaland.org/posts/2026-01-21_tree-sitter_vs_lsp/) - Complementary capabilities
- [Tree-sitter vs LSP: Why Hybrid IDE Architecture Wins](https://byteiota.com/tree-sitter-vs-lsp-why-hybrid-ide-architecture-wins/) - Architecture patterns
- [Code intelligence | GitLab Docs](https://docs.gitlab.com/user/project/code_intelligence/) - LSIF and SCIP formats
- [MCP Server Code Extractor](https://github.com/ctoth/mcp_server_code_extractor) - Tree-sitter symbol extraction for 30+ languages
- [TreeSitter Code Structure MCP Server](https://glama.ai/mcp/servers/@DarkEden-coding/CodeStructureMCP) - Symbol extraction implementation
- [Code intelligence with Granite Code Models](https://adasci.org/exploring-granite-code-models-in-multi-language-code-intelligence/) - Multi-language symbol extraction best practices

### MCP Server Design Patterns
- [MCP Server Best Practices for 2026](https://www.cdata.com/blog/mcp-server-best-practices-2026) - Architecture and implementation guide
- [Less is More: 4 design patterns for building better MCP servers](https://www.klavis.ai/blog/less-is-more-mcp-design-patterns-for-ai-agents) - Workflow-based tools, focused design
- [Building Scalable MCP Servers with Domain-Driven Design](https://medium.com/@chris.p.hughes10/building-scalable-mcp-servers-with-domain-driven-design-fb9454d4c726) - DDD patterns
- [MCP Best Practices: Architecture & Implementation Guide](https://modelcontextprotocol.info/docs/best-practices/) - Official MCP documentation
- [Top 5 MCP Server Best Practices | Docker](https://www.docker.com/blog/mcp-server-best-practices/) - Focused, stateless architecture

### Progressive Disclosure & CLI Design
- [6 things developer tools must have in 2026](https://evilmartians.com/chronicles/six-things-developer-tools-must-have-to-earn-trust-and-adoption) - Trust and adoption patterns
- [Progressive Disclosure Matters: Applying 90s UX Wisdom to 2026 AI Agents](https://aipositive.substack.com/p/progressive-disclosure-matters) - Context management
- [Codex Skills Deep Dive: Progressive Disclosure, Triggers, and Best Practices](https://habr.com/en/articles/984916/) - Implementation details
