## Search Features

CocoSearch introduces advanced search capabilities: hybrid search for better identifier matching, symbol filtering for navigating code structure, and smart context expansion for understanding matches.

### Hybrid Search

**When to use:** Searching for specific identifiers (function names, class names, variables) where exact matches matter alongside semantic similarity.

**The problem:** Pure semantic search finds conceptually similar code but may miss exact identifier matches.

**Without hybrid search:**

```bash
uvx cocosearch search "getUserById" --pretty
# May return: getUserByEmail, fetchUser, getProfile (semantically similar but not exact)
```

**With hybrid search:**

```bash
uvx cocosearch search "getUserById" --hybrid --pretty
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
uvx cocosearch search "auth" --symbol-type function --pretty

# Find classes matching "User"
uvx cocosearch search "User" --symbol-type class --pretty

# Find both functions and methods (OR logic)
uvx cocosearch search "handler" --symbol-type function --symbol-type method --pretty
```

**Filter by name pattern:**

```bash
# Find symbols starting with "get"
uvx cocosearch search "database operations" --symbol-name "get*" --pretty

# Find symbols ending with "Handler"
uvx cocosearch search "request processing" --symbol-name "*Handler" --pretty

# Combine type and name filters (AND logic)
uvx cocosearch search "validation" --symbol-type function --symbol-name "validate*" --pretty
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
uvx cocosearch search "database connection" -C 5 --pretty

# Show 10 lines after (like grep -A)
uvx cocosearch search "error handling" -A 10 --pretty

# Show 3 lines before (like grep -B)
uvx cocosearch search "config parsing" -B 3 --pretty
```

**Smart context (default):**

By default, CocoSearch expands context to include the enclosing function or class boundary, up to 50 lines centered on the match.

```bash
# Smart context enabled by default
uvx cocosearch search "parse config" --pretty
# Shows entire function containing the match

# Disable smart context for fixed line counts only
uvx cocosearch search "parse config" -C 5 --no-smart --pretty
```

**How smart context works:**

1. Finds the enclosing function/class using tree-sitter parsing
2. Expands to include the full scope (up to 50 lines max)
3. Centers the expansion on the original match location
4. Falls back to fixed lines if no enclosing scope found

| Option       | CLI Flag     | MCP Parameter       | Behavior                          |
| ------------ | ------------ | ------------------- | --------------------------------- |
| Lines after  | `-A <n>`     | `context_after: n`  | Show n lines after match          |
| Lines before | `-B <n>`     | `context_before: n` | Show n lines before match         |
| Both         | `-C <n>`     | (set both)          | Show n lines before and after     |
| Smart expand | (default)    | (default)           | Expand to function/class boundary |
| No smart     | `--no-smart` | (explicit lines)    | Disable smart expansion           |
