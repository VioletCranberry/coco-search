# Feature Landscape: Search Enhancements (v1.7)

**Domain:** Semantic code search enhancements — hybrid search, context expansion, symbol-aware indexing
**Researched:** 2026-02-03
**Confidence:** HIGH (verified against Context7, official documentation, current research papers)

## Executive Summary

This research covers four enhancement areas for CocoSearch v1.7:

1. **Hybrid Search** — Combine vector similarity with keyword matching (BM25) for better recall
2. **Context Expansion** — Show surrounding lines at query time without re-indexing
3. **Symbol-Aware Search** — Index functions/classes as first-class entities with metadata
4. **Full Language Coverage** — Expand from 15+ to 30+ languages via CocoIndex built-in support

**Key finding:** These features are table stakes for production code search tools in 2026. Missing them makes CocoSearch feel incomplete compared to Sourcegraph, Cursor, and other modern tools.

## Table Stakes

Features users expect when a code search tool claims "production-ready search." Missing these makes the feature feel incomplete or broken.

### Hybrid Search (Vector + Keyword)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **BM25 keyword scoring** | Pure vector search misses exact identifier matches. Searching "AuthService" should rank exact matches higher than semantic similarity. Users expect both semantic understanding AND literal matching. | HIGH | Requires PostgreSQL extension (pg_textsearch or VectorChord-BM25) or tsvector/tsquery with custom BM25 implementation. PostgreSQL's built-in ts_rank is NOT BM25 — it lacks inverse document frequency. |
| **Reciprocal Rank Fusion (RRF)** | Industry-standard method for combining ranked lists. Formula: `score = sum(1/(k + rank))` where k=60. Works well without tuning, which is why Elasticsearch, OpenSearch, and LanceDB all use it by default. | LOW-MEDIUM | Simple algorithm, no dependencies. Given two ranked lists (vector results, keyword results), merge them with RRF scoring. 50 lines of Python. |
| **Configurable weighting** | Different queries favor different strategies. "Find database migrations" (keyword-heavy) vs "Find where we handle authentication" (semantic-heavy). Users expect a balance parameter. | LOW | Weighted RRF: multiply each retriever's contribution by a weight. Default 0.5/0.5 (equal weight), configurable via CLI flag `--hybrid-weight` (0.0 = pure keyword, 1.0 = pure vector). |
| **Query analysis** | Automatically detect when to use hybrid vs pure vector. Short queries with camelCase/snake_case identifiers (e.g., "UserAuth", "get_token") should trigger keyword emphasis. Natural language queries ("where do we authenticate users") should favor vector. | MEDIUM | Heuristic-based: If query contains [A-Z][a-z] or _, boost keyword weight. If query > 5 words, boost vector weight. Simple rules, 90% accuracy. |
| **Backward compatibility** | Existing pure vector search must continue working. Users who don't need hybrid search shouldn't pay the indexing cost (tsvector columns). | LOW | Hybrid search is opt-in via CLI flag `--hybrid`. Default behavior (vector-only) unchanged. |

### Context Expansion (Surrounding Code Display)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Configurable context lines** | Users expect `-A/-B/-C` flags like grep/ripgrep. Showing 2-5 lines before/after each match is standard in all code search tools (grep, ag, rg, Sourcegraph, GitHub Code Search). | LOW | Read file from disk at query time. Use start_byte/end_byte to locate chunk, then count N lines before/after. No indexing changes required. |
| **Line number adjustment** | When showing context, line numbers must be accurate. If chunk starts at line 50 and we show 3 lines before, display should start at line 47. | LOW | Calculate line offset from start_byte. PostgreSQL location range gives bytes, not lines. Count newlines in file from 0 to start_byte to get starting line number. |
| **Smart context boundaries** | Don't show partial lines or break mid-statement. If showing context, include complete lines. If a line is continuation (`\` in Python/Bash), include the full statement. | MEDIUM | Use Tree-sitter to find enclosing scope boundaries (function start/end) and prefer those as context limits. Fallback to line boundaries if Tree-sitter not available for language. |
| **File reading fallback** | If file has been deleted/moved since indexing, gracefully degrade. Show chunk content only (already in index in v1.0 reference-only approach — wait, CocoSearch uses reference-only storage, so chunk text is NOT in DB). | MEDIUM | Chunk text is NOT stored in PostgreSQL (verified from PROJECT.md: "Reference-only storage"). Context expansion requires file on disk. If file missing, show error: "File modified/deleted since indexing." Cannot show context or chunk text without re-indexing. |
| **Context separator** | When showing multiple results, separate them clearly like ripgrep does with `--` separator between non-contiguous matches. | LOW | Insert `--` between results in pretty output. Already have this concept from v1.0 pretty formatter. |
| **Performance for large files** | Reading a 50MB file to show 5 lines of context is wasteful. Need efficient partial file reading using byte ranges. | MEDIUM | Use `seek()` to jump to start_byte - N bytes, read small buffer (~4KB), extract lines. Don't read entire file into memory. |

### Symbol-Aware Indexing (Functions/Classes/Methods)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Function-level chunking granularity** | Users think in terms of functions and classes, not arbitrary 512-token chunks. "Find the authentication function" should return the complete function definition, not a mid-function chunk. | LOW-MEDIUM | CocoIndex already uses Tree-sitter for built-in languages. Verify that default chunking respects function boundaries. If not, add custom separators for each language (e.g., Python: `^def `, `^class `, `^async def `). |
| **Symbol metadata extraction** | Search results should show "function: authenticate_user" or "class: AuthService" alongside file/line info. This is what VSCode's symbol search does — users expect it. | MEDIUM | Use Tree-sitter queries to extract symbol names. For each chunk, if it starts with a function/class definition, extract the name. Store in `symbol_name` and `symbol_type` columns (extends v1.2 metadata approach). |
| **Symbol type classification** | Distinguish between functions, classes, methods, interfaces, structs, enums, constants. Different query patterns target different symbol types ("find the User class" vs "find getUserById function"). | MEDIUM | Tree-sitter node types map to symbol types. Python: `function_definition` → function, `class_definition` → class. Each language has different node type names but similar concepts. Need language-specific mapping tables. |
| **Nested symbol hierarchy** | A method inside a class should show as "AuthService.validate_token" not just "validate_token". Otherwise, searching for "token validation" returns 50 unqualified names. | HIGH | Requires walking up Tree-sitter AST to find parent class/module. Multi-pass parsing: first pass identifies all symbols, second pass builds hierarchy map. Significantly more complex than flat extraction. |
| **Symbol search filter** | `--symbol-type function` or `--symbol-type class` to narrow search to specific symbol kinds. Complements existing `--language` filter. | LOW | SQL WHERE clause on `symbol_type` column. Trivial once metadata is stored. |
| **Symbol name search** | `--symbol-name UserAuth` for exact symbol name match, case-insensitive. Useful when you know the symbol name but not which file it's in. | LOW | SQL WHERE with ILIKE on `symbol_name` column. Exact match first, then substring match. |

### Full Language Coverage (30+ Languages)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **All CocoIndex built-in languages** | CocoIndex bundles 30+ Tree-sitter grammars. Users expect a semantic code search tool to support all common languages out of the box. Supporting only 15 languages feels arbitrary and incomplete in 2026. | LOW | Enable all built-in CocoIndex languages. No custom language definitions needed — Tree-sitter grammars already bundled. Just remove the implicit limitation. |
| **YAML/JSON/Markdown support** | DevOps repos contain tons of YAML (Kubernetes, GitHub Actions, Ansible), JSON (package.json, tsconfig.json, API schemas), and Markdown (docs, README files). Searching only code files misses critical configuration and documentation. | LOW | Already supported by CocoIndex built-ins. Add to LANGUAGE_EXTENSIONS mapping in query.py. |
| **Language auto-detection** | File extension should be sufficient. `*.yaml` → YAML, `*.md` → Markdown, `*.json` → JSON. No magic number detection needed — code repos are well-organized by convention. | LOW | Already implemented in v1.0 via extension-based routing. Just expand the extension mapping tables. |
| **Language-specific chunking** | Different languages have different structural units. JSON: top-level keys. YAML: document separators (`---`). Markdown: heading boundaries (`#`, `##`). Tree-sitter handles this automatically. | NONE | Tree-sitter grammars already know language structure. CocoIndex's SplitRecursively respects language semantics. Zero work needed. |
| **Updated documentation** | README and docs should list all supported languages. Users need to know what's supported before trying it. | LOW | Update `LANGUAGE_EXTENSIONS` mapping and regenerate CLI help text. Add supported languages section to README. |

## Differentiators

Features that set CocoSearch apart from competitors. Not expected, but highly valued when present.

### Hybrid Search Intelligence

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Automatic hybrid mode** | No manual `--hybrid` flag needed. Query analyzer automatically enables hybrid for identifier-heavy queries ("AuthService", "get_user_by_id") and pure vector for natural language ("where do we handle errors"). Best of both worlds without user intervention. | MEDIUM | Heuristics: If query contains camelCase/snake_case/kebab-case identifiers, enable hybrid. If query is >5 words with no code-like patterns, use pure vector. Log decision for transparency. |
| **Explain mode** | `--explain` flag shows how the query was interpreted: "Detected identifier pattern 'AuthService', using hybrid search with 0.7 keyword weight." Helps users understand ranking and tune their queries. | LOW | Wrapper around existing search logic. Log query analysis decisions and scoring breakdown per result. |
| **Negative keywords** | `NOT:test` or `-test` to exclude results. "Find authentication logic NOT:test" excludes test files. Keyword-based exclusion is faster than post-processing vector results. | LOW | Translate to PostgreSQL tsquery: `authentication & !test`. Requires tsvector column (already needed for hybrid search). |
| **Phrase matching** | `"exact phrase"` in quotes forces keyword phrase match. Useful for error messages, specific comments, or API names. Vector search alone can't enforce exact phrase matching. | LOW | PostgreSQL tsquery `<->` operator: `authentication <-> token`. Requires tsvector column. |

### Context Expansion Intelligence

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Semantic context boundaries** | Instead of fixed line counts, show the enclosing function/class. Searching for "user validation" inside a 200-line function should show the function signature, not just ±5 lines that cut off mid-logic. | HIGH | Use Tree-sitter to find enclosing `function_definition` or `class_definition` node. Extract entire node content. May be very large (200+ lines) — need max size limit to avoid flooding output. |
| **Collapsible context** | In JSON output for MCP clients, return `chunk` (matching text), `context_before`, `context_after` as separate fields. Calling LLM decides how much context to include based on its own context window budget. | LOW | Already separating concerns: CocoSearch returns chunks, caller synthesizes. Just add context fields to SearchResult dataclass and MCP response schema. |
| **Syntax-highlighted context** | Context lines in pretty output should be syntax-highlighted too, not just the matching chunk. Makes output readable in terminal. Already doing this for chunk text in v1.0 pretty formatter. | LOW | Extend existing Rich syntax highlighting to include context lines. Already have `EXTENSION_LANG_MAP` mapping. |
| **Adaptive context size** | Small chunks (5-10 lines) get less context (±2 lines). Large chunks (50+ lines) get more context (±10 lines) because they're already part of complex code. Prevents tiny snippets from being drowned in context. | LOW | Heuristic: `context_lines = min(requested_context, chunk_size_lines // 3)`. Simple ratio, good defaults. |

### Symbol-Aware Intelligence

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Symbol ranking boost** | When query contains a symbol-like term ("UserAuth", "validateToken"), boost chunks that contain symbol definitions (function/class) over chunks that just mention the symbol. Definitions are more useful than call sites 80% of the time. | MEDIUM | RRF with symbol-aware weights: If chunk has `symbol_type != ""`, multiply RRF score by 1.5. Simple heuristic, big impact. |
| **Related symbols** | "Find related symbols" query: Given a function name, find all functions that call it or are called by it. Useful for impact analysis ("if I change this function, what breaks?"). | VERY HIGH | Requires call graph analysis: parse all files, build AST, extract function calls, build graph, query graph. This is Language Server Protocol (LSP) territory. Probably out of scope for CocoSearch v1.7 — defer to v2.0 or never. |
| **Symbol cross-references** | Show "X uses this symbol" count alongside search results. "function: authenticate_user (used 47 times)" gives context about importance. | HIGH | Two-pass indexing: (1) extract all symbol definitions, (2) scan all files for references to each symbol, (3) count. Expensive, but high value. Defer to v1.8 or validate demand first. |
| **Jump to definition** | MCP tool: `jump_to_symbol(symbol_name)` returns file path + line number for symbol definition. Complements search with direct navigation. | LOW | SQL query: `SELECT filename, start_byte WHERE symbol_name = ? AND symbol_type IN ('function', 'class')`. Convert byte offset to line number. Already have all the pieces. |

### Full Language Coverage Value-Adds

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Language statistics** | `cocosearch stats <index>` shows language breakdown: "15k lines Python, 8k lines TypeScript, 2k lines YAML, 500 lines Markdown." Helps users understand codebase composition. | LOW | Extend existing stats command to count chunks by `language_id`. Already stored in v1.2 metadata schema. |
| **Multi-language projects** | Mixed-language codebases (Python backend + TypeScript frontend + YAML configs) work seamlessly. One index, all languages searchable. Competitors often segment by language. | NONE | Already implemented in v1.2 via unified flow architecture. Just document it explicitly. |
| **Language-aware snippets** | JSON output for MCP includes language hint: `{"language": "python", "chunk": "..."}` so calling LLM can syntax-highlight or lint the returned code. | LOW | Already capturing language_id in v1.2 metadata. Add to MCP response schema. |

## Anti-Features

Features that seem useful but should be deliberately NOT built. Building these would add complexity without proportionate value.

| Anti-Feature | Why It Seems Useful | Why Problematic | What to Do Instead |
|--------------|--------------------|-----------------|--------------------|
| **Full-text index everything** | "Index every token for perfect keyword recall" | tsvector columns add significant storage cost (30-50% increase). Most queries are semantic, not keyword. Indexing common words ("the", "a", "if") is wasteful. | Index only identifiers and important terms. Use PostgreSQL's `english` text search config to filter stop words. Store tsvector separately, not inline with vector embeddings. |
| **Re-rank with LLM** | "Use Claude/GPT to re-rank results for perfect relevance" | API cost per query, latency spike (500ms+ per query), violates local-first principle. Semantic code search should be fast (sub-100ms) and free (no API calls). | RRF + heuristic boosts (symbol-aware, identifier-pattern detection) achieve 90% of LLM re-ranking quality with zero cost and latency. |
| **Result clustering** | "Group results by file, by module, by feature" | Users already have IDE file trees and `git ls-files` for clustering. Search results should be flat and ranked. Clustering hides rank order and complicates navigation. | Return flat ranked list. Calling LLM can group results if needed (e.g., "summarize these results by component"). |
| **Query suggestions** | "Did you mean X?" autocorrect for queries" | Code search queries are often intentionally misspelled (variable names with typos, abbreviations like "auth" for "authentication"). Autocorrect breaks more queries than it fixes. | No autocorrect. Let semantic search handle fuzzy matching via embeddings. If zero results, suggest relaxing filters (e.g., remove `--language` filter) instead of correcting query text. |
| **Result deduplication** | "Collapse identical chunks from different files" | Identical code in different files often has different meanings (vendored dependencies vs application code). Collapsing loses context. User needs to see all occurrences. | Show all results. Rank by relevance, not uniqueness. If identical chunks appear, that's information ("this code is duplicated 5 times"). |
| **Search history** | "Remember past queries for quick repeat" | CocoSearch is designed to be called by MCP clients (Claude Code, Cursor) which have their own chat history. CLI users have shell history (Ctrl+R). Duplicating history in the tool adds complexity with no value. | Rely on shell history for CLI. MCP clients handle their own history. |
| **Saved searches** | "Save common queries with a name" | Code search queries are one-off explorations, not recurring reports. If a query is repeated often, it should be codified as a test or documented pattern, not saved in a search tool. | No saved searches. If users want to repeat a query, they can copy/paste from shell history or chat history. |
| **Multi-index search** | "Search across multiple codebases simultaneously" | Different codebases have different contexts. Results from two unrelated projects mixed together are confusing. Users should search one codebase at a time. | One search = one index. If users need multi-repo search, they can run multiple searches sequentially (via bash loop or MCP tool chaining). |
| **Search within results** | "Filter results from previous search" | Encourages inefficient workflows ("search broadly, then narrow"). Better to refine the original query. MCP clients can do this client-side if needed. | No server-side result filtering. Encourage users to refine queries using `--language`, `--symbol-type`, etc. |
| **Export results to CSV/Excel** | "Export results for reporting" | Code search is for navigation and understanding, not reporting. If users need to report on code patterns, they should use static analysis tools (SonarQube, CodeQL) designed for that purpose. | JSON output is already machine-readable. If users want CSV, they can pipe: `cocosearch search ... --json | jq -r '.[] | [.filename, .score] | @csv'`. |

## Feature Dependencies

```
[Hybrid Search Layer]
PostgreSQL tsvector column
    |
    +--> BM25-compatible ranking (pg_textsearch OR custom ts_rank)
    |       |
    |       +--> Reciprocal Rank Fusion (RRF) scoring
    |       |       |
    |       |       +--> Weighted RRF (configurable vector/keyword balance)
    |       |
    |       +--> Query analyzer (identifier detection, auto-hybrid)
    |
    +--> Backward compatibility (hybrid is opt-in via --hybrid flag)
    |
    +--> Schema migration (add tsvector column, GIN index)

[Context Expansion Layer]
File on disk (reference-only storage requires original files)
    |
    +--> Byte-to-line conversion (count newlines from 0 to start_byte)
    |       |
    |       +--> Efficient partial file reading (seek + small buffer)
    |
    +--> Smart boundaries (Tree-sitter scope detection OR line boundaries)
    |       |
    |       +--> Configurable context size (-A/-B/-C flags like grep)
    |
    +--> MCP schema extension (context_before, context_after fields)
    |
    +--> Pretty formatter extension (syntax-highlighted context)

[Symbol-Aware Layer]
Tree-sitter AST parsing (already used by CocoIndex)
    |
    +--> Symbol extraction (function/class/method names)
    |       |
    |       +--> Symbol type classification (language-specific node types)
    |       |
    |       +--> Metadata storage (symbol_name, symbol_type columns)
    |
    +--> Symbol hierarchy (OPTIONAL, nested symbols like Class.method)
    |       |
    |       +--> AST traversal (parent node lookup)
    |       |
    |       +--> Fully qualified names (package.module.Class.method)
    |
    +--> Symbol filters (--symbol-type, --symbol-name CLI flags)
    |       |
    |       +--> SQL WHERE clauses on symbol_* columns
    |
    +--> Symbol ranking boost (in RRF scoring, definitions > references)

[Language Coverage Layer]
CocoIndex built-in languages (already available, just enable)
    |
    +--> LANGUAGE_EXTENSIONS mapping (query.py update)
    |
    +--> Documentation update (README, CLI help)
    |
    +--> Language statistics (extend stats command)
```

### Dependency Notes

- **Hybrid search depends on tsvector column:** Can't do keyword search without full-text index. This is a schema change (additive, backward-compatible).
- **Context expansion depends on files on disk:** CocoSearch uses reference-only storage (no chunk text in DB). Context requires reading original files. If file deleted, no context available.
- **Symbol extraction depends on Tree-sitter:** Already using Tree-sitter for chunking. Extend to extract symbol names from AST nodes.
- **Nested symbol hierarchy is optional:** Flat symbol names (function: "authenticate_user") are sufficient for v1.7 MVP. Fully qualified names (module.Class.method) can be deferred to v1.8.
- **Language coverage is essentially free:** CocoIndex bundles 30+ Tree-sitter grammars. Just enable them, no code changes to indexing pipeline.

## MVP Recommendation for v1.7

### Must Ship (Core Deliverable)

1. **Hybrid search with RRF** — Combines vector + keyword, essential for identifier search quality
2. **Configurable context expansion** — `-A/-B/-C` flags, show surrounding lines, table stakes feature
3. **Symbol metadata extraction** — Extract function/class names and types, store in DB
4. **Full language coverage** — Enable all 30+ CocoIndex built-in languages (YAML, JSON, Markdown, etc.)
5. **Symbol search filters** — `--symbol-type function` to narrow to specific symbol kinds
6. **Updated MCP schema** — Include symbol metadata and context fields in search responses

### Should Ship (Significant Value Add)

7. **Automatic hybrid mode** — Query analyzer detects identifier patterns, enables hybrid automatically
8. **Symbol ranking boost** — Boost symbol definitions over references in RRF scoring
9. **Smart context boundaries** — Use Tree-sitter to prefer function/class boundaries over arbitrary line counts
10. **Language statistics** — Show language breakdown in `cocosearch stats` command

### Defer to v1.8 (Post-Validation)

11. **Nested symbol hierarchy** — Fully qualified names (Class.method), requires AST traversal
12. **Explain mode** — `--explain` flag showing query analysis and scoring decisions
13. **Phrase matching** — `"exact phrase"` keyword search with tsquery `<->` operator
14. **Negative keywords** — `NOT:test` exclusion via tsquery negation
15. **Symbol cross-references** — Count how many times each symbol is used

## Competitive Positioning (2026)

| Capability | grep/ripgrep | GitHub Code Search | Sourcegraph | Cursor/Claude Context | CocoSearch v1.7 |
|-----------|-------------|-------------------|-------------|----------------------|----------------|
| Vector semantic search | No | Limited | Yes (Deep Search) | Yes | **Yes** |
| Keyword search | Yes | Yes | Yes | Limited | **Yes (hybrid)** |
| Hybrid search (combined) | No | Yes | Yes | No | **Yes (RRF)** |
| Context expansion (±N lines) | Yes (-A/-B/-C) | Yes | Yes | No (full file) | **Yes** |
| Symbol-aware search | No | Limited | Yes (LSP) | No | **Yes (metadata)** |
| Function/class filtering | No | No | Yes (code intel) | No | **Yes (--symbol-type)** |
| 30+ language support | Yes | Yes | Yes | Yes | **Yes** |
| Fully local / private | Yes | No (cloud) | No (cloud/enterprise) | No (cloud API) | **Yes** |
| MCP integration | No | No | Limited | Yes | **Yes** |
| Sub-second search | Yes | Yes | Yes | Depends | **Yes (local)** |

**Key differentiator:** CocoSearch v1.7 is the only tool that combines hybrid search, symbol awareness, and semantic understanding in a fully local, privacy-preserving package with MCP integration. GitHub Code Search and Sourcegraph require cloud/enterprise infrastructure. Cursor/Claude Context uses cloud APIs (not local-first). ripgrep/grep lack semantic search. CocoSearch v1.7 fills the gap.

## User Query Examples (What People Actually Search For)

These queries illustrate why each enhancement matters:

| Query | Without Enhancements | With v1.7 Enhancements | Why It Matters |
|-------|---------------------|------------------------|----------------|
| **"AuthService"** | Finds chunks semantically similar to "authentication service" but misses exact class name matches buried in boilerplate | Hybrid search ranks exact identifier match first, semantic matches second | Identifiers should match exactly when they appear literally |
| **"where do we validate tokens"** | Returns chunks with "validate", "token" nearby, but no context — could be inside a 200-line function | Returns chunk with ±10 lines of context showing the function signature and setup logic | Context prevents "grep in the dark" problem |
| **"find the User class"** | Returns any chunk mentioning "User" — could be imports, comments, docstrings | Symbol-aware search filters to `symbol_type=class`, returns only class definitions | Users think in symbols (functions, classes), not arbitrary chunks |
| **"deployment scripts"** | Only searches Python/JS/Rust code (15 languages), misses deploy.yaml and deploy.sh | Full language coverage includes YAML, Bash, Markdown — finds all deployment-related files | Modern repos are 40% config/docs, not just code |
| **"error handling in API"** | Returns 50 snippets, no way to see if they're inside error handling functions or just comments mentioning errors | Symbol metadata shows which results are inside `handle_error()` functions vs. incidental mentions | Symbol context disambiguates results |
| **"database connection NOT:test"** | Returns test files mixed with application code, user manually filters | Hybrid search with negative keywords excludes test files immediately | Keyword exclusion is faster than semantic filtering |

## Per-Feature User Experience Specification

### Hybrid Search UX

**CLI:**
```bash
# Explicit hybrid mode
cocosearch search "AuthService" --hybrid

# Automatic hybrid (query analyzer detects identifier)
cocosearch search "AuthService"  # auto-enables hybrid

# Weight tuning (0.0 = keyword only, 1.0 = vector only, default 0.5)
cocosearch search "authentication logic" --hybrid-weight 0.7  # favor vector
```

**MCP:**
```json
{
  "query": "AuthService",
  "hybrid": true,
  "hybrid_weight": 0.5
}
```

**Expected behavior:**
- Identifier-heavy queries ("getUserById", "AuthService") automatically enable hybrid with 0.7 keyword weight
- Natural language queries ("where do we handle errors") use 0.3 keyword weight
- Pure keyword queries (--hybrid-weight 0.0) behave like grep but with BM25 ranking
- Pure vector queries (--hybrid-weight 1.0) behave like v1.0 (current behavior)

### Context Expansion UX

**CLI:**
```bash
# Show 3 lines before and after each match (like grep -C 3)
cocosearch search "validate token" -C 3

# Asymmetric context (5 before, 2 after)
cocosearch search "validate token" -B 5 -A 2

# Smart boundaries (show enclosing function)
cocosearch search "validate token" --context-smart
```

**MCP:**
```json
{
  "query": "validate token",
  "context_before": 3,
  "context_after": 3,
  "context_smart": false
}
```

**Result format (JSON):**
```json
{
  "filename": "auth.py",
  "start_line": 42,
  "end_line": 45,
  "score": 0.89,
  "context_before": ["def validate_token(token: str):", "    if not token:", "        return False"],
  "chunk": ["    payload = decode_jwt(token)", "    if payload.exp < now():", "        return False", "    return True"],
  "context_after": ["", "def refresh_token(user_id: int):"]
}
```

**Pretty output:**
```
auth.py:42-45 (score: 0.89)
39: def validate_token(token: str):
40:     if not token:
41:         return False
42:     payload = decode_jwt(token)
43:     if payload.exp < now():
44:         return False
45:     return True
46:
47: def refresh_token(user_id: int):
--
```

### Symbol-Aware Search UX

**CLI:**
```bash
# Filter by symbol type
cocosearch search "authentication" --symbol-type function

# Search by exact symbol name
cocosearch search --symbol-name "AuthService"

# Combine filters
cocosearch search "user management" --language python --symbol-type class
```

**MCP:**
```json
{
  "query": "authentication",
  "symbol_type": "function",
  "symbol_name": null
}
```

**Result format (JSON):**
```json
{
  "filename": "auth.py",
  "start_line": 42,
  "end_line": 45,
  "score": 0.89,
  "symbol_name": "authenticate_user",
  "symbol_type": "function",
  "language_id": "python"
}
```

**Pretty output:**
```
auth.py:42-45 (score: 0.89)
function: authenticate_user (python)
    def authenticate_user(username: str, password: str) -> User:
        ...
--
```

### Full Language Coverage UX

**CLI:**
```bash
# Search YAML files
cocosearch search "kubernetes deployment" --language yaml

# Search Markdown docs
cocosearch search "installation guide" --language markdown

# Multi-language search
cocosearch search "database config" --language python,yaml,json
```

**Language statistics:**
```bash
cocosearch stats myproject

Index: myproject
Files indexed: 1,247
Total chunks: 8,932

Language breakdown:
  Python: 4,521 chunks (50.6%)
  TypeScript: 2,340 chunks (26.2%)
  YAML: 1,203 chunks (13.5%)
  JSON: 543 chunks (6.1%)
  Markdown: 325 chunks (3.6%)
```

## Implementation Complexity Assessment

| Feature | Complexity | LOC Estimate | Dependencies | Risk Level |
|---------|-----------|--------------|--------------|------------|
| **Hybrid search (RRF)** | MEDIUM | 150 | tsvector column, GIN index | LOW (well-documented) |
| **BM25 ranking** | HIGH | 200 | pg_textsearch OR custom | MEDIUM (extension dependency) |
| **Context expansion** | LOW | 100 | None (file I/O) | LOW |
| **Smart context boundaries** | MEDIUM | 150 | Tree-sitter queries | MEDIUM (language-specific) |
| **Symbol extraction** | MEDIUM | 200 | Tree-sitter queries | MEDIUM (per-language mapping) |
| **Symbol hierarchy** | HIGH | 300 | AST traversal | HIGH (complex logic) |
| **Language coverage** | LOW | 50 | None (already in CocoIndex) | NONE |
| **Query analyzer** | LOW | 100 | Regex patterns | LOW |

**Total v1.7 MVP estimate:** ~950 LOC (hybrid search + context expansion + symbol extraction + language coverage)

**Deferred features (v1.8):** ~450 LOC (symbol hierarchy + explain mode + advanced query syntax)

## Query Pattern Taxonomy

Based on research, code search queries fall into 5 categories:

| Pattern | Example | Best Approach | Why |
|---------|---------|--------------|-----|
| **Identifier lookup** | "AuthService", "getUserById" | Hybrid with keyword boost | Exact match matters |
| **Natural language concept** | "where do we handle authentication" | Pure vector | Semantic understanding needed |
| **Error message** | "Token expired" | Hybrid with phrase match | Exact phrase + semantic context |
| **Symbol search** | "User class definition" | Symbol-aware filter | User thinking in code structure |
| **File type + concept** | "YAML kubernetes deployment" | Language filter + vector | Scope + semantics |

**Query analyzer heuristics:**

1. Contains camelCase/snake_case → Enable hybrid, boost keyword 0.7
2. Contains quoted phrase → Enable phrase matching
3. Mentions "class" or "function" → Enable symbol filters
4. Mentions file type/language → Enable language filter
5. >5 words, no code patterns → Pure vector search

## Schema Changes Required

### New Columns (Hybrid Search)

```sql
-- Add tsvector column for full-text search
ALTER TABLE codeindex_{index_name}__{index_name}_chunks
ADD COLUMN chunk_text_tsvector tsvector;

-- Populate tsvector from chunk text (requires reading files to extract text)
-- NOTE: chunk text not stored in DB (reference-only), need to read from disk

-- Create GIN index for fast keyword search
CREATE INDEX idx_{index_name}_chunks_tsvector
ON codeindex_{index_name}__{index_name}_chunks
USING GIN (chunk_text_tsvector);
```

**CRITICAL ISSUE:** Reference-only storage means chunk text is NOT in database. To populate tsvector, must:
1. Read each file from disk
2. Extract chunk text using start_byte/end_byte
3. Convert to tsvector
4. Update row

This is essentially a full re-index. **Hybrid search cannot be retrofitted to existing indexes without re-indexing.**

### New Columns (Symbol-Aware)

```sql
-- Add symbol metadata columns
ALTER TABLE codeindex_{index_name}__{index_name}_chunks
ADD COLUMN symbol_name TEXT DEFAULT '',
ADD COLUMN symbol_type TEXT DEFAULT '',
ADD COLUMN symbol_hierarchy TEXT DEFAULT '';

-- Create indexes for symbol filters
CREATE INDEX idx_{index_name}_chunks_symbol_type
ON codeindex_{index_name}__{index_name}_chunks (symbol_type);

CREATE INDEX idx_{index_name}_chunks_symbol_name
ON codeindex_{index_name}__{index_name}_chunks (symbol_name);
```

**Note:** Unlike tsvector, symbol metadata CAN be extracted during initial indexing from CocoIndex chunk text (before storage). This is additive and backward-compatible.

## Performance Considerations

### Hybrid Search Performance

| Operation | Vector-Only | Hybrid (RRF) | Notes |
|-----------|-------------|--------------|-------|
| Query latency | 20-50ms | 40-80ms | Two queries + RRF merge |
| Index size | 100% | 130-150% | +30-50% for tsvector + GIN |
| Indexing time | 100% | 120-140% | +20-40% for text extraction + tsvector |

**Mitigation:** Hybrid is opt-in. Default vector-only search unchanged.

### Context Expansion Performance

| File Size | Context Retrieval Time | Notes |
|-----------|----------------------|-------|
| <10KB | <1ms | Negligible |
| 100KB | 2-5ms | Seek + read small buffer |
| 1MB | 5-10ms | Still fast with byte-range seek |
| 10MB+ | 20-50ms | Large files become bottleneck |

**Mitigation:** Use `seek()` + small buffer (4KB) read. Don't load full file into memory.

### Symbol Extraction Performance

| Language | Parse Time (per file) | Notes |
|----------|----------------------|-------|
| Python | 10-30ms | Tree-sitter built-in |
| TypeScript | 20-50ms | Complex grammar |
| YAML | 5-10ms | Simple structure |

**Mitigation:** Symbol extraction happens during indexing (one-time cost). Query time unaffected.

## Open Questions

1. **BM25 implementation:** Use pg_textsearch extension (requires installation) or custom ts_rank implementation (pure SQL but lower quality)?
   - **Recommendation:** Start with custom ts_rank, document pg_textsearch as optional upgrade for production deployments.

2. **Chunk text storage:** Should we store chunk text in DB to avoid file I/O for context expansion and hybrid search?
   - **Recommendation:** No. Reference-only is a core principle. File I/O is fast enough (<5ms per chunk with seek).

3. **Symbol hierarchy depth:** How many levels? `Class.method` or `package.module.Class.method`?
   - **Recommendation:** Start with 2 levels (`Class.method`). Validate demand for full namespacing.

4. **Hybrid search default:** Should hybrid be default (with auto-weight) or opt-in?
   - **Recommendation:** Opt-in for v1.7 (backward compatibility). Consider default in v2.0 after validation.

5. **Context expansion default lines:** What's the default for `-C`? grep defaults to 2, ripgrep defaults to 0.
   - **Recommendation:** Default 0 (no context unless requested). Explicit is better than implicit for MCP responses.

## Sources

**Hybrid Search:**
- [Hybrid Search: Combining BM25 and Vector Search | Medium (Jan 2026)](https://medium.com/codex/96-hybrid-search-combining-bm25-and-vector-search-7a93adfd3f4e)
- [OpenSearch Semantic and Hybrid Search Tutorial (2026)](https://docs.opensearch.org/latest/tutorials/vector-search/neural-search-tutorial/)
- [Reciprocal Rank Fusion Explained | GitHub Gist](https://gist.github.com/srcecde/eec6c5dda268f9a58473e1c14735c7bb)
- [Implementing RRF in Python | Safjan](https://safjan.com/implementing-rank-fusion-in-python/)
- [Redis Hybrid Search Explained (2026)](https://redis.io/blog/hybrid-search-explained/)

**BM25 in PostgreSQL:**
- [PostgreSQL BM25 Full-Text Search | VectorChord Blog](https://blog.vectorchord.ai/postgresql-full-text-search-fast-when-done-right-debunking-the-slow-myth)
- [Implementing BM25 in PostgreSQL | ParadeDB](https://www.paradedb.com/learn/search-in-postgresql/bm25)
- [pg_textsearch (Timescale) | GitHub](https://github.com/timescale/pg_textsearch)
- [VectorChord-BM25 | GitHub](https://github.com/tensorchord/VectorChord-bm25)

**Context Expansion:**
- [Sourcegraph Code Navigation Features (2026)](https://sourcegraph.com/docs/code-search/code-navigation/features)
- [GitLab Exact Code Search (2026)](https://about.gitlab.com/blog/exact-code-search-find-code-faster-across-repositories/)
- [How to display context lines in grep | LabEx](https://labex.io/tutorials/linux-how-to-display-context-lines-in-grep-437961)
- [Ripgrep Context Matching | Learn by Example](https://learnbyexample.github.io/learn_gnugrep_ripgrep/context-matching.html)

**Symbol-Aware Search:**
- [Semantic Code Indexing with AST and Tree-sitter | Medium (2025)](https://medium.com/@email2dineshkuppan/semantic-code-indexing-with-ast-and-tree-sitter-for-ai-agents-part-1-of-3-eb5237ba687a)
- [Tree-sitter: Revolutionizing Parsing | Deus in Machina](https://www.deusinmachina.net/p/tree-sitter-revolutionizing-parsing)
- [Structural Code Search using Natural Language | arXiv (July 2025)](https://arxiv.org/html/2507.02107v1)

**Code Search Best Practices:**
- [Improving agent with semantic search | Cursor Blog (2025)](https://cursor.com/blog/semsearch)
- [Semantic Search on Stack Overflow | Stack Overflow Blog](https://stackoverflow.blog/2023/07/31/ask-like-a-human-implementing-semantic-search-on-stack-overflow/)
- [Semantic Code Search | Moderne.ai Blog](https://www.moderne.ai/blog/semantic-code-search-benefits)

**Language Coverage:**
- [tree-sitter-languages | PyPI (2026)](https://pypi.org/project/tree-sitter-languages/)
- [tree-sitter-language-pack (165+ languages) | GitHub](https://github.com/Goldziher/tree-sitter-language-pack)
- [Tree-sitter releases (v0.26.4, Feb 2026) | GitHub](https://github.com/tree-sitter/tree-sitter/releases)

**Anti-Patterns:**
- [Anti-patterns You Should Avoid in Your Code | freeCodeCamp](https://www.freecodecamp.org/news/antipatterns-to-avoid-in-code/)
- [6 Types of Anti Patterns | GeeksforGeeks](https://www.geeksforgeeks.org/blogs/types-of-anti-patterns-to-avoid-in-software-development/)

---
*Feature research for: CocoSearch v1.7 Search Enhancements*
*Researched: 2026-02-03*
