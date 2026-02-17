## CLI Reference

CocoSearch provides a command-line interface for indexing and searching code. Output is JSON by default (for scripting/MCP); use `--pretty` for human-readable output.

### Indexing Commands

`uv run cocosearch index <path> [options]`

Index a codebase for semantic search.

| Flag             | Description                        | Default                |
| ---------------- | ---------------------------------- | ---------------------- |
| `-n, --name`     | Index name                         | Derived from directory |
| `-i, --include`  | Include file patterns (repeatable) | See defaults below     |
| `-e, --exclude`  | Exclude file patterns (repeatable) | None                   |
| `--no-gitignore` | Ignore .gitignore patterns         | Respects .gitignore    |

**Example:**

```bash
uv run cocosearch index ./my-project --name myproject
```

### Searching Commands

`uv run cocosearch search <query> [options]`
`uv run cocosearch search --interactive`

Search indexed code using natural language.

| Flag                   | Description                        | Default              |
| ---------------------- | ---------------------------------- | -------------------- |
| `-n, --index`          | Index to search                    | Auto-detect from cwd |
| `-l, --limit`          | Max results                        | 10                   |
| `--lang`               | Filter by language                 | None                 |
| `--min-score`          | Minimum similarity (0-1)           | 0.3                  |
| `-A, --after-context`  | Lines to show after match          | Smart expand         |
| `-B, --before-context` | Lines to show before match         | Smart expand         |
| `-C, --context`        | Lines before and after             | Smart expand         |
| `--no-smart`           | Disable smart context expansion    | Off                  |
| `--hybrid`             | Force hybrid search                | Auto-detect          |
| `--symbol-type`        | Filter by symbol type (repeatable) | None                 |
| `--symbol-name`        | Filter by symbol name pattern      | None                 |
| `--no-cache`           | Bypass query cache (for debugging) | Off                  |
| `-i, --interactive`    | Enter REPL mode                    | Off                  |
| `--pretty`             | Human-readable output              | JSON                 |

**Examples:**

```bash
# Basic search
uv run cocosearch search "authentication logic" --pretty

# Filter by language
uv run cocosearch search "error handling" --lang python

# Inline language filter
uv run cocosearch search "database connection lang:go"

# Interactive mode
uv run cocosearch search --interactive
```

### Pipeline Analysis

`uv run cocosearch analyze <query> [options]`

Run the search pipeline with stage-by-stage diagnostics. Shows query analysis, mode selection, cache status, vector search results, keyword search results, RRF fusion breakdown, definition boost effects, filtering, and timing.

| Flag              | Description                        | Default              |
| ----------------- | ---------------------------------- | -------------------- |
| `-n, --index`     | Index to search                    | Auto-detect from cwd |
| `-l, --limit`     | Max results                        | 10                   |
| `--lang`          | Filter by language                 | None                 |
| `--min-score`     | Minimum similarity (0-1)           | 0.3                  |
| `--hybrid`        | Force hybrid search                | Auto-detect          |
| `--symbol-type`   | Filter by symbol type (repeatable) | None                 |
| `--symbol-name`   | Filter by symbol name pattern      | None                 |
| `--no-cache`      | Bypass query cache                 | Off                  |
| `--json`          | Output as JSON (default: Rich)     | Off                  |

**Examples:**

```bash
# Analyze why a query returns specific results
uv run cocosearch analyze "getUserById"

# JSON output for scripting
uv run cocosearch analyze "database connection pool" --json

# Analyze with language filter
uv run cocosearch analyze "error handling" --lang python
```

### Managing Indexes

**List indexes:** `uv run cocosearch list [--pretty]`

Show all available indexes.

```bash
uv run cocosearch list --pretty
```

**Index statistics:** `uv run cocosearch stats [index] [--pretty]`

Show statistics for one or all indexes. Includes file count, chunk count, size, language distribution, and parse health.

```bash
uv run cocosearch stats myproject --pretty
```

| Flag                    | Description                                | Default |
| ----------------------- | ------------------------------------------ | ------- |
| `--pretty`              | Human-readable output                      | JSON    |
| `--json`                | Machine-readable JSON output               | Off     |
| `-v, --verbose`         | Show symbol type breakdown                 | Off     |
| `--all`                 | Show stats for all indexes                 | Off     |
| `--show-failures`       | Show individual file parse failure details | Off     |
| `--staleness-threshold` | Days before staleness warning              | 7       |
| `--live`                | Terminal dashboard (multi-pane layout)     | Off     |
| `--watch`               | Auto-refresh dashboard (requires --live)   | Off     |
| `--refresh-interval`    | Refresh interval in seconds for --watch    | 1.0     |

**Parse health** is shown by default when available. It displays a percentage of files that parsed cleanly along with a per-language breakdown (ok, partial, error, no grammar).

To see individual file failure details (file paths and error types), use the `--show-failures` flag:

```bash
uv run cocosearch stats myproject --pretty --show-failures
```

**Clear index:** `uv run cocosearch clear <index> [--force] [--pretty]`

Delete an index and all its data (including the associated parse results table). Prompts for confirmation unless `--force`.

```bash
uv run cocosearch clear myproject --force
```

**List supported languages:** `uv run cocosearch languages [--json]`

Show all languages CocoSearch can index with extensions and symbol support.

```bash
uv run cocosearch languages
```

**Start MCP server:** `uv run cocosearch mcp`

Start the MCP server for LLM integration. Typically invoked by MCP clients, not directly.

```bash
uv run cocosearch mcp  # Runs until killed, used by Claude/OpenCode
```

### Configuration Commands

**Check configuration and connectivity:** `uv run cocosearch config check`

Validates environment variables and checks connectivity to PostgreSQL, Ollama, and the embedding model. Returns exit code 0 if all checks pass, 1 if any fail.

```bash
uv run cocosearch config check
```

Output includes an environment variable table and a connectivity table:

| Service              | Status          | Details                        |
| -------------------- | --------------- | ------------------------------ |
| PostgreSQL           | ✓ connected     |                                |
| Ollama               | ✓ connected     |                                |
| Model (nomic-embed-text) | ✓ available |                                |

If a service is unreachable, the status shows `✗ unreachable` with a remediation hint (e.g., `Run: docker compose up -d`). The model check is skipped if Ollama is unreachable.

**Show resolved configuration:** `uv run cocosearch config show`

Display the fully resolved configuration with all sources and precedence levels.

**Show config file path:** `uv run cocosearch config path`

Display the path to the config file, or indicate if none is found.

## Observability

Monitor index health, language distribution, symbol breakdown, and parse health.

### Index Statistics

```bash
uv run cocosearch stats myproject --pretty
```

Shows file count, chunk count, size, staleness warnings, language distribution with bar charts, and parse health summary.

### Parse Health

Parse health tracks how well tree-sitter parsed each indexed file. It is displayed by default in the stats output:

```bash
uv run cocosearch stats myproject --pretty
```

For detailed failure information including file paths and error types:

```bash
uv run cocosearch stats myproject --pretty --show-failures
```

### JSON Output

Machine-readable stats for automation:

```bash
uv run cocosearch stats myproject --json
```

### Dashboard

Web-based stats visualization:

```bash
uv run cocosearch dashboard
# Opens browser to http://localhost:8080
```

The dashboard displays real-time index health with language distribution charts.
