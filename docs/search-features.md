## Search Features

CocoSearch introduces advanced search capabilities: hybrid search for better identifier matching, symbol filtering for navigating code structure, and smart context expansion for understanding matches.

### Hybrid Search

**When to use:** Searching for specific identifiers (function names, class names, variables) where exact matches matter alongside semantic similarity.

**The problem:** Pure semantic search finds conceptually similar code but may miss exact identifier matches.

**Without hybrid search:**

```bash
uv run cocosearch search "getUserById" --pretty
# May return: getUserByEmail, fetchUser, getProfile (semantically similar but not exact)
```

**With hybrid search:**

```bash
uv run cocosearch search "getUserById" --hybrid --pretty
# Returns: getUserById exact match boosted to top, then semantically similar results
```

**How it works:** Combines vector similarity (semantic meaning) with PostgreSQL full-text search (keyword matching). Results are ranked using Reciprocal Rank Fusion (RRF) to balance both signals.

**Auto-detection:** Hybrid search automatically enables for queries containing identifier patterns (camelCase like `getUserById` or snake_case like `get_user_by_id`).

| Mode           | CLI Flag        | MCP Parameter       | Behavior                               |
| -------------- | --------------- | ------------------- | -------------------------------------- |
| Auto (default) | (none)          | (none)              | Enables hybrid for identifier patterns |
| Force on       | `--hybrid`      | `use_hybrid: true`  | Always use hybrid search               |
| Force off      | (not available) | `use_hybrid: false` | Vector-only search                     |

### Symbol Filtering

**When to use:** Finding specific types of code elements (functions, classes, methods) or searching for symbols by name pattern.

**Filter by type:**

```bash
# Find all functions matching "auth"
uv run cocosearch search "auth" --symbol-type function --pretty

# Find classes matching "User"
uv run cocosearch search "User" --symbol-type class --pretty

# Find both functions and methods (OR logic)
uv run cocosearch search "handler" --symbol-type function --symbol-type method --pretty
```

**Filter by name pattern:**

```bash
# Find symbols starting with "get"
uv run cocosearch search "database operations" --symbol-name "get*" --pretty

# Find symbols ending with "Handler"
uv run cocosearch search "request processing" --symbol-name "*Handler" --pretty

# Combine type and name filters (AND logic)
uv run cocosearch search "validation" --symbol-type function --symbol-name "validate*" --pretty
```

**Available symbol types:**

- `function` - Standalone functions
- `class` - Class definitions
- `method` - Methods within classes
- `interface` - Interfaces, traits, type aliases

**Symbol-aware languages:** Python, JavaScript, TypeScript, Go, Rust. Other languages are indexed but without symbol extraction.

| Filter | CLI Flag                  | MCP Parameter               |
| ------ | ------------------------- | --------------------------- |
| Type   | `--symbol-type <type>`    | `symbol_type: ["function"]` |
| Name   | `--symbol-name <pattern>` | `symbol_name: "get*"`       |

### Context Expansion

**When to use:** Understanding code in context - seeing the function or class containing a match.

**Fixed context lines:**

```bash
# Show 5 lines before and after each match
uv run cocosearch search "database connection" -C 5 --pretty

# Show 10 lines after (like grep -A)
uv run cocosearch search "error handling" -A 10 --pretty

# Show 3 lines before (like grep -B)
uv run cocosearch search "config parsing" -B 3 --pretty
```

**Smart context (default):**

By default, CocoSearch expands context to include the enclosing function or class boundary, up to 50 lines centered on the match.

```bash
# Smart context enabled by default
uv run cocosearch search "parse config" --pretty
# Shows entire function containing the match

# Disable smart context for fixed line counts only
uv run cocosearch search "parse config" -C 5 --no-smart --pretty
```

**How smart context works:**

1. Finds the enclosing function/class using tree-sitter parsing
2. Expands to include the full scope (up to 50 lines max)
3. Centers the expansion on the original match location
4. Falls back to fixed lines if no enclosing scope found

**Supported languages:** Python, JavaScript, TypeScript, Go, Rust, Scala, HCL/Terraform. For unsupported languages, smart context falls back to fixed-line expansion. Run `cocosearch languages` to see which languages have context support.

| Option       | CLI Flag     | MCP Parameter       | Behavior                          |
| ------------ | ------------ | ------------------- | --------------------------------- |
| Lines after  | `-A <n>`     | `context_after: n`  | Show n lines after match          |
| Lines before | `-B <n>`     | `context_before: n` | Show n lines before match         |
| Both         | `-C <n>`     | (set both)          | Show n lines before and after     |
| Smart expand | (default)    | (default)           | Expand to function/class boundary |
| No smart     | `--no-smart` | (explicit lines)    | Disable smart expansion           |

### Pipeline Analysis

**When to use:** Debugging why a query returns unexpected results, understanding how the search pipeline processes your query, or optimizing search parameters.

The `analyze` command runs the same pipeline as `search` but captures and displays diagnostics at each stage:

```bash
# See full pipeline breakdown for a query
uv run cocosearch analyze "getUserById"

# JSON output for programmatic inspection
uv run cocosearch analyze "getUserById" --json
```

**What it shows:**

- **Query Analysis** — identifier detection, normalized keyword form, search mode decision
- **Cache** — hit/miss status and cache key
- **Vector Search** — result count, score range, top results
- **Keyword Search** — whether executed, ts_rank scores, top results
- **RRF Fusion** — match type breakdown (both/semantic-only/keyword-only), fused scores
- **Definition Boost** — how many results were boosted and rank changes
- **Timings** — per-stage timing with visual bar chart

### Cross-Index Search

**When to use:** Searching across multiple related projects — monorepos, shared libraries, microservice codebases, or any set of independently indexed repositories.

**`linkedIndexes` config (automatic):**

Configure related indexes in `cocosearch.yaml` to automatically expand searches:

```yaml
indexName: my-api
linkedIndexes:
  - shared-libs
  - common-types
```

With this config, every search against `my-api` automatically includes `shared-libs` and `common-types`. Missing linked indexes are silently skipped.

**CLI usage:**

```bash
# Explicit cross-index search
uv run cocosearch search "auth middleware" --indexes api-server,shared-libs --pretty

# With linkedIndexes configured, just search normally — expansion is automatic
uv run cocosearch search "auth middleware" --pretty
```

**MCP usage:**

```json
{
  "query": "auth middleware",
  "index_names": ["api-server", "shared-libs", "auth-service"],
  "use_hybrid_search": true,
  "smart_context": true
}
```

Explicitly providing `index_names` in MCP (or `--indexes` in CLI) overrides the `linkedIndexes` config.

**How it works:**

1. The query embedding is computed **once** and reused across all indexes
2. Each index is searched **in parallel** (ThreadPoolExecutor)
3. Results are **merged by score** across all indexes
4. Each result is tagged with its source `index_name`
5. Partial failures are handled gracefully — if one index is unavailable, results from the others are still returned

**Note:** All indexes must use the same embedding provider and model for reliable cross-index relevance scoring.
