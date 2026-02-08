# Phase 46: Parse Failure Tracking - Research

**Researched:** 2026-02-08
**Domain:** Tree-sitter parse error detection, PostgreSQL schema, stats aggregation
**Confidence:** HIGH

## Summary

This phase adds parse failure tracking to the indexing pipeline and surfaces results through all three stats endpoints (CLI, MCP, HTTP). The core challenge is that CocoIndex's `SplitRecursively` handles chunking internally in Rust, so parse status must be determined **outside** the CocoIndex flow -- as a separate step that runs during the `run_index` orchestration.

The approach requires: (1) a new `parse_results` table created via schema migration, (2) a standalone parse-status detection function that uses tree-sitter's `root_node.has_error` property, (3) aggregation queries for stats, and (4) integration with the existing stats display in CLI/MCP/HTTP.

**Primary recommendation:** Build parse-status detection as a standalone function invoked within `run_index()` (after `flow.update()`), iterating over indexed files directly. This keeps the CocoIndex flow unchanged and avoids fighting CocoIndex's Rust-based chunking pipeline.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tree-sitter | >=0.25.0,<0.26.0 | Parse source files and detect ERROR nodes | Already in use; `Node.has_error` property is the API for error detection |
| tree-sitter-language-pack | >=0.13.0 | Get parser for each language | Already in use via `pack_get_parser()` |
| psycopg | >=3.3.2 | Create table, insert rows, run aggregation queries | Already in use for schema migration pattern |
| psycopg_pool | (via psycopg[pool]) | Connection pooling for stats queries | Already in use via `get_connection_pool()` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| rich | >=13.0.0 | CLI stats formatting with tables | Already used in `stats_command` and `format_language_table` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Separate parse_results table | Column on chunks table | CONTEXT.md decided: separate table with per-file granularity (not per-chunk) |
| Post-flow file iteration | CocoIndex transform in flow | Fighting CocoIndex internals; parse status is per-file not per-chunk |

**Installation:**
No new dependencies needed. All libraries already in `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure
```
src/cocosearch/
  indexer/
    symbols.py           # MODIFY: add parse_status detection function
    schema_migration.py  # MODIFY: add ensure_parse_results_table()
    flow.py              # MODIFY: call parse tracking in run_index()
  management/
    stats.py             # MODIFY: add get_parse_stats(), update IndexStats, update get_comprehensive_stats()
  cli.py                 # MODIFY: add --show-failures flag, parse health display
  mcp/
    server.py            # MODIFY: update index_stats tool and /api/stats endpoint
```

### Pattern 1: Standalone Parse-Status Detection (runs outside CocoIndex flow)

**What:** After `flow.update()` completes, iterate over all files that were indexed (query the chunks table for distinct filenames), read each file, run tree-sitter parse, check `root_node.has_error`, and record results in `parse_results` table.

**When to use:** Always, during every index run.

**Why this approach:**
- CocoIndex's `SplitRecursively` is a Rust-based function -- we cannot intercept its internal tree-sitter parsing
- The `extract_symbol_metadata` function already uses tree-sitter but operates per-chunk, not per-file
- Parse status is inherently per-file (one tree-sitter parse per file), while chunks are per-file-segment
- The CONTEXT.md decided on per-file granularity in a separate table

**Example:**
```python
# In symbols.py or new parse_tracking.py
from tree_sitter import Parser
from tree_sitter_language_pack import get_parser as pack_get_parser

def detect_parse_status(file_content: str, language: str) -> tuple[str, str | None]:
    """Detect parse status for a file.

    Returns:
        Tuple of (status, error_message):
        - ("ok", None) - clean parse
        - ("partial", "ERROR nodes at lines 5, 12") - tree produced but with errors
        - ("error", "Exception: ...") - total failure
        - ("unsupported", None) - language not in LANGUAGE_MAP
    """
    from cocosearch.indexer.symbols import LANGUAGE_MAP

    ts_language = LANGUAGE_MAP.get(language)
    if ts_language is None:
        return ("unsupported", None)

    try:
        parser = pack_get_parser(ts_language)
        tree = parser.parse(bytes(file_content, "utf8"))

        if not tree.root_node.has_error:
            return ("ok", None)

        # Collect ERROR node locations for diagnostics
        error_lines = _collect_error_lines(tree.root_node)
        error_msg = f"ERROR nodes at lines: {', '.join(str(l) for l in error_lines[:10])}"
        if len(error_lines) > 10:
            error_msg += f" (+{len(error_lines) - 10} more)"

        return ("partial", error_msg)

    except Exception as e:
        return ("error", str(e))


def _collect_error_lines(node) -> list[int]:
    """Recursively find all ERROR node line numbers."""
    lines = []
    if node.is_error or node.is_missing:
        lines.append(node.start_point[0] + 1)  # 1-indexed
    for child in node.children:
        lines.extend(_collect_error_lines(child))
    return lines
```

### Pattern 2: Schema Migration (same pattern as symbol columns)

**What:** Create `parse_results` table using the idempotent migration pattern from `schema_migration.py`.

**When to use:** Called from `run_index()` after `flow.setup()`, before `flow.update()`.

**Example:**
```python
def ensure_parse_results_table(conn: psycopg.Connection, index_name: str) -> dict:
    """Create parse_results table if it doesn't exist.

    Table: cocosearch_parse_results_{index_name}
    Columns:
    - file_path TEXT NOT NULL
    - language TEXT NOT NULL
    - parse_status TEXT NOT NULL CHECK (parse_status IN ('ok', 'partial', 'error', 'unsupported'))
    - error_message TEXT
    - PRIMARY KEY (file_path)
    """
    table_name = f"cocosearch_parse_results_{index_name}"

    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                file_path TEXT NOT NULL,
                language TEXT NOT NULL,
                parse_status TEXT NOT NULL,
                error_message TEXT,
                PRIMARY KEY (file_path)
            )
        """)
        # Index for fast aggregation by language and status
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_lang_status
            ON {table_name} (language, parse_status)
        """)
    conn.commit()
    return {"table_created": table_name}
```

### Pattern 3: Rebuild on Each Index Run

**What:** CONTEXT.md requires drop-and-recreate semantics -- always reflects current state.

**When to use:** At the start of each `run_index()` call.

**Example:**
```python
def rebuild_parse_results(conn: psycopg.Connection, index_name: str, results: list[dict]) -> None:
    """Drop and recreate parse results for an index.

    Args:
        conn: Database connection
        index_name: Index name
        results: List of {"file_path": str, "language": str, "parse_status": str, "error_message": str|None}
    """
    table_name = f"cocosearch_parse_results_{index_name}"

    with conn.cursor() as cur:
        # Truncate (faster than DROP+CREATE for schema preservation)
        cur.execute(f"TRUNCATE TABLE {table_name}")

        # Batch insert
        if results:
            from psycopg.sql import SQL, Identifier
            cur.executemany(
                f"INSERT INTO {table_name} (file_path, language, parse_status, error_message) VALUES (%s, %s, %s, %s)",
                [(r["file_path"], r["language"], r["parse_status"], r["error_message"]) for r in results]
            )
    conn.commit()
```

### Pattern 4: Stats Aggregation Query

**What:** Aggregate parse results per language for stats display.

**Example:**
```python
def get_parse_stats(index_name: str) -> dict:
    """Get parse failure stats per language.

    Returns:
        {
            "by_language": {
                "python": {"files": 142, "ok": 138, "partial": 3, "error": 1, "unsupported": 0},
                "javascript": {"files": 50, "ok": 50, "partial": 0, "error": 0, "unsupported": 0},
            },
            "parse_health_pct": 95.2,
            "total_files": 192,
            "total_ok": 188,
        }
    """
    table_name = f"cocosearch_parse_results_{index_name}"
    pool = get_connection_pool()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            # Check table exists first
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = %s
                )
            """, (table_name,))
            if not cur.fetchone()[0]:
                return {}  # Graceful degradation for pre-v46 indexes

            # Aggregate by language and status
            cur.execute(f"""
                SELECT language, parse_status, COUNT(*) as cnt
                FROM {table_name}
                GROUP BY language, parse_status
                ORDER BY language, parse_status
            """)
            rows = cur.fetchall()

    # Build response structure
    by_language = {}
    total_files = 0
    total_ok = 0

    for lang, status, count in rows:
        if lang not in by_language:
            by_language[lang] = {"files": 0, "ok": 0, "partial": 0, "error": 0, "unsupported": 0}
        by_language[lang][status] = count
        by_language[lang]["files"] += count
        total_files += count
        if status == "ok":
            total_ok += count

    parse_health_pct = round((total_ok / total_files * 100), 1) if total_files > 0 else 100.0

    return {
        "by_language": by_language,
        "parse_health_pct": parse_health_pct,
        "total_files": total_files,
        "total_ok": total_ok,
    }
```

### Pattern 5: Failure Detail Query

**What:** Get individual file failure details for `--show-failures` and MCP/HTTP.

**Example:**
```python
def get_parse_failures(index_name: str, status_filter: list[str] | None = None) -> list[dict]:
    """Get individual file parse failure details.

    Args:
        index_name: Index name
        status_filter: Optional filter, e.g. ["error", "partial"]. Default: non-ok statuses.

    Returns:
        List of {"file_path": str, "language": str, "parse_status": str, "error_message": str|None}
    """
    table_name = f"cocosearch_parse_results_{index_name}"
    if status_filter is None:
        status_filter = ["partial", "error", "unsupported"]

    pool = get_connection_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT file_path, language, parse_status, error_message
                FROM {table_name}
                WHERE parse_status = ANY(%s)
                ORDER BY language, parse_status, file_path
            """, (status_filter,))
            rows = cur.fetchall()

    return [
        {"file_path": r[0], "language": r[1], "parse_status": r[2], "error_message": r[3]}
        for r in rows
    ]
```

### Anti-Patterns to Avoid
- **Modifying CocoIndex flow to capture parse status:** The flow's `SplitRecursively` is Rust-based. Trying to inject parse status tracking inside the flow would require CocoIndex source changes. Instead, run parse detection as a separate step.
- **Storing parse results as a column on the chunks table:** CONTEXT.md decided on a separate table with per-file granularity. Chunks are per-file-segment, not per-file.
- **Caching parse results across index runs:** CONTEXT.md requires rebuild on each run. Always drop and recreate.
- **Skipping unsupported language detection:** Files with extensions not in `LANGUAGE_MAP` should still get `unsupported` status, not be silently ignored.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tree-sitter error detection | Custom parser/regex for syntax errors | `tree.root_node.has_error` + recursive `is_error` walk | Tree-sitter already tracks this; reliable across all languages |
| SQL injection prevention | String formatting for table names | psycopg parameterized queries (for values) | Table names still need f-strings (parameterized queries don't support identifiers), but use `psycopg.sql.Identifier` where possible |
| Schema idempotency | Manual column checks | `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` | PostgreSQL handles idempotency natively |
| Percentage formatting | Manual string formatting | `round(x / total * 100, 1)` | Simple arithmetic, no library needed |

**Key insight:** The core detection mechanism is trivially simple (`has_error` on root node). The complexity is in the plumbing: getting file contents, mapping extensions to languages, persisting results, and surfacing through three different interfaces.

## Common Pitfalls

### Pitfall 1: File Content Access After Indexing
**What goes wrong:** After `flow.update()`, we need to read original file contents to run tree-sitter parse. But the CocoIndex flow reads files from `codebase_path` -- we need to do the same.
**Why it happens:** The chunks table stores chunk text (`content_text`), not full file content. Parse status is per-file, requiring full file content.
**How to avoid:** Query the chunks table for `DISTINCT filename`, then read each file from disk using the `codebase_path` passed to `run_index()`. Files are guaranteed to exist since they were just indexed.
**Warning signs:** If trying to reconstruct full file from chunks -- don't do this. Read from disk.

### Pitfall 2: Language Extension Mapping Mismatch
**What goes wrong:** The chunks table stores `language_id` (from `extract_language`), which is a file extension like "py", "ts", "go". But `LANGUAGE_MAP` in symbols.py maps extensions to tree-sitter language names. The `language` column in `parse_results` should use the human-readable tree-sitter name (e.g., "python"), not the extension (e.g., "py"), to match the stats display format.
**Why it happens:** Two different mapping systems exist -- `extract_language()` returns extensions, `LANGUAGE_MAP` maps extensions to tree-sitter names.
**How to avoid:** Use `LANGUAGE_MAP` to convert the file extension to a tree-sitter language name for both parsing and storage. Store the tree-sitter name (e.g., "python") in `parse_results.language` to match `get_language_stats()` output format which uses `language_id`.
**Warning signs:** If parse stats show "py" while language stats show "py", alignment is correct. But CONTEXT.md shows "Python" in CLI output -- the display layer should handle capitalization.

### Pitfall 3: Extensionless Files and DevOps Languages
**What goes wrong:** Files like `Dockerfile` have no extension. `extract_language()` returns "dockerfile" for these. `LANGUAGE_MAP` does not include "dockerfile" -- it maps to `None`, yielding "unsupported".
**Why it happens:** DevOps handlers (Dockerfile, Bash, HCL) use `SplitRecursively` with custom `CustomLanguageSpec`, not tree-sitter parsing.
**How to avoid:** For languages not in `LANGUAGE_MAP`, they are genuinely unsupported by tree-sitter parsing. Mark them as "unsupported" -- this is correct behavior. The chunking still works (via `SplitRecursively`), just not via tree-sitter.
**Warning signs:** High `unsupported` counts for DevOps-heavy repos. This is expected and accurate.

### Pitfall 4: Large File Performance
**What goes wrong:** Reading every indexed file from disk and parsing with tree-sitter could be slow for large repos.
**Why it happens:** Parse detection happens after indexing, adding wall-clock time.
**How to avoid:** This is inherent to the approach. Files were already read once by CocoIndex -- reading them again is I/O but tree-sitter parsing is very fast (microseconds per file). For a 10,000-file repo, expect ~1-2 seconds total. If performance becomes an issue, batch the tree-sitter parsing.
**Warning signs:** If parse detection takes longer than the actual indexing, something is wrong.

### Pitfall 5: Table Name Collisions
**What goes wrong:** Using a table name that conflicts with existing tables.
**Why it happens:** CocoIndex uses `codeindex_{name}__{name}_chunks` pattern. Our table uses `cocosearch_parse_results_{name}`.
**How to avoid:** Prefix with `cocosearch_` to stay in the application namespace (matching `cocosearch_index_metadata`). The naming convention is already established.
**Warning signs:** If `CREATE TABLE IF NOT EXISTS` silently succeeds but the table has wrong schema -- check for leftover tables from failed migrations.

### Pitfall 6: Graceful Degradation for Pre-Phase-46 Indexes
**What goes wrong:** `get_parse_stats()` fails because the `parse_results` table doesn't exist for indexes created before this phase.
**Why it happens:** Old indexes never had parse tracking.
**How to avoid:** Check table existence first (same pattern as `get_language_stats` checking for `content_text` column). Return empty dict or None for missing tables. Display "N/A" in stats for pre-phase-46 indexes.
**Warning signs:** `ValueError` or `UndefinedTable` errors when querying stats on old indexes.

### Pitfall 7: Determining File Path from Chunks Table
**What goes wrong:** The `filename` in the chunks table may be a relative or absolute path depending on how CocoIndex stores it.
**Why it happens:** CocoIndex's `LocalFile` source stores filenames relative to the source path.
**How to avoid:** Query `DISTINCT filename` from chunks table, then join with `codebase_path` to get the absolute path for reading from disk. Store the original `filename` (as-is from chunks table) in `parse_results.file_path` for consistency.
**Warning signs:** `FileNotFoundError` when trying to read files -- check path joining logic.

## Code Examples

### Tree-Sitter ERROR Node Detection
```python
# Source: py-tree-sitter 0.25.x documentation
# https://tree-sitter.github.io/py-tree-sitter/classes/tree_sitter.Node.html

from tree_sitter_language_pack import get_parser

parser = get_parser("python")
tree = parser.parse(b"def foo(:\n    pass")

# Check if tree has any errors (fast, O(1))
has_errors = tree.root_node.has_error  # True

# Check if a specific node is an error node
for child in tree.root_node.children:
    if child.is_error:
        print(f"Error at line {child.start_point[0] + 1}")
    if child.is_missing:
        print(f"Missing node at line {child.start_point[0] + 1}")
```

### Schema Migration Pattern (from existing code)
```python
# Source: src/cocosearch/indexer/schema_migration.py
# Pattern: idempotent CREATE TABLE/INDEX with existence checks

def ensure_parse_results_table(conn, index_name):
    table_name = f"cocosearch_parse_results_{index_name}"
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                file_path TEXT NOT NULL,
                language TEXT NOT NULL,
                parse_status TEXT NOT NULL,
                error_message TEXT,
                PRIMARY KEY (file_path)
            )
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_lang_status
            ON {table_name} (language, parse_status)
        """)
    conn.commit()
```

### Stats Query Pattern (from existing code)
```python
# Source: src/cocosearch/management/stats.py
# Pattern: check table exists -> aggregate with GROUP BY -> return dict

def get_parse_stats(index_name):
    table_name = f"cocosearch_parse_results_{index_name}"
    pool = get_connection_pool()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            # Existence check (same pattern as get_stats)
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = %s
                )
            """, (table_name,))
            if not cur.fetchone()[0]:
                return {}

            # Aggregation (same pattern as get_language_stats GROUP BY)
            cur.execute(f"""
                SELECT language, parse_status, COUNT(*)
                FROM {table_name}
                GROUP BY language, parse_status
                ORDER BY language
            """)
            return cur.fetchall()
```

### IndexStats Extension Pattern
```python
# Source: src/cocosearch/management/stats.py
# Extend existing IndexStats dataclass with parse_stats field

@dataclass
class IndexStats:
    # ... existing fields ...
    parse_stats: dict  # NEW: parse failure breakdown
    # parse_stats structure:
    # {
    #     "by_language": {"python": {"files": 10, "ok": 9, "partial": 1, "error": 0, "unsupported": 0}},
    #     "parse_health_pct": 90.0,
    #     "total_files": 10,
    #     "total_ok": 9,
    # }
```

### CLI Stats Display Pattern
```python
# In stats_command, after language table:
# Pattern follows format_language_table / format_symbol_table

def format_parse_health(parse_stats: dict, console: Console) -> None:
    """Display parse health summary and per-language breakdown."""
    if not parse_stats:
        return

    pct = parse_stats.get("parse_health_pct", 100.0)
    total = parse_stats.get("total_files", 0)
    ok = parse_stats.get("total_ok", 0)

    # Summary line
    color = "green" if pct >= 95 else "yellow" if pct >= 80 else "red"
    console.print(f"[{color}]Parse health: {pct}% clean ({ok}/{total} files)[/{color}]")

    # Per-language table
    table = Table(title="Parse Status by Language")
    table.add_column("Language", style="cyan")
    table.add_column("Files", justify="right")
    table.add_column("OK", justify="right", style="green")
    table.add_column("Partial", justify="right", style="yellow")
    table.add_column("Error", justify="right", style="red")
    table.add_column("Unsupported", justify="right", style="dim")

    for lang, counts in sorted(parse_stats.get("by_language", {}).items()):
        table.add_row(
            lang,
            str(counts["files"]),
            str(counts["ok"]),
            str(counts["partial"]),
            str(counts["error"]),
            str(counts["unsupported"]),
        )
    console.print(table)
```

### MCP/HTTP Response Extension
```python
# In IndexStats.to_dict(), parse_stats dict is already JSON-serializable
# MCP index_stats tool and /api/stats both use get_comprehensive_stats().to_dict()
# Adding parse_stats to IndexStats automatically surfaces it in both.

# API response structure:
{
    "name": "myproject",
    "file_count": 142,
    # ... existing fields ...
    "parse_stats": {
        "by_language": {
            "python": {"files": 142, "ok": 138, "partial": 3, "error": 1, "unsupported": 0}
        },
        "parse_health_pct": 97.2,
        "total_files": 142,
        "total_ok": 138
    },
    "parse_failures": [  # Optional, included when requested
        {"file_path": "src/broken.py", "language": "python", "parse_status": "error", "error_message": "..."}
    ]
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No parse tracking | Parse status per file with 4 statuses | Phase 46 | Users can diagnose indexing quality |
| Symbol extraction only | Symbol extraction + parse health | Phase 46 | Complementary metrics |

**Dependencies on prior work:**
- Phase 43: Working indexing pipeline (flow.py, run_index) -- REQUIRED, already in place
- Symbol extraction (symbols.py) -- provides `LANGUAGE_MAP` and tree-sitter infrastructure

## Open Questions

1. **File path format in chunks table**
   - What we know: CocoIndex's `LocalFile` source produces filenames relative to the source directory
   - What's unclear: Exact format (e.g., "src/main.py" vs "/absolute/path/src/main.py")
   - Recommendation: Query a real chunks table during implementation to verify. Store whatever format is in the chunks table. Join with `codebase_path` for disk reads.

2. **Performance on very large repositories (50k+ files)**
   - What we know: Tree-sitter parsing is fast (microseconds per file). File I/O is the bottleneck.
   - What's unclear: Whether reading all files again adds noticeable time
   - Recommendation: Implement simple first. Add progress indicator if it takes >5 seconds. Consider batching with executemany (already planned).

3. **Cleanup of parse_results when index is cleared**
   - What we know: `clear_index()` in `management/clear.py` drops the chunks table
   - What's unclear: Whether it should also drop `cocosearch_parse_results_{index_name}`
   - Recommendation: YES -- extend `clear_index()` to also drop the parse_results table. Same lifecycle as the index.

4. **MCP/HTTP optional failure detail inclusion**
   - What we know: CONTEXT.md says "include failure details in response (or as optional parameter)"
   - What's unclear: Whether to use a query parameter or always include
   - Recommendation: Always include `parse_stats` aggregate in response. Add `include_failures=true` query parameter for `/api/stats` and an optional boolean parameter on the `index_stats` MCP tool to include the individual file failure list.

## Sources

### Primary (HIGH confidence)
- [py-tree-sitter Node documentation](https://tree-sitter.github.io/py-tree-sitter/classes/tree_sitter.Node.html) - `has_error`, `is_error`, `is_missing` properties verified
- Codebase inspection: `src/cocosearch/indexer/symbols.py` - LANGUAGE_MAP, tree-sitter usage patterns
- Codebase inspection: `src/cocosearch/indexer/schema_migration.py` - idempotent migration pattern
- Codebase inspection: `src/cocosearch/management/stats.py` - stats query patterns, IndexStats dataclass
- Codebase inspection: `src/cocosearch/indexer/flow.py` - `run_index()` orchestration, CocoIndex flow structure
- Codebase inspection: `src/cocosearch/mcp/server.py` - index_stats tool, /api/stats endpoint
- Codebase inspection: `src/cocosearch/cli.py` - stats_command, format_language_table, format_symbol_table
- Codebase inspection: `tests/unit/management/test_stats.py` - mock_db_pool test pattern
- Codebase inspection: `tests/mocks/db.py` - MockCursor, MockConnection, MockConnectionPool

### Secondary (MEDIUM confidence)
- [py-tree-sitter GitHub](https://github.com/tree-sitter/py-tree-sitter) - API overview and README

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in use; no new dependencies
- Architecture: HIGH - patterns directly derived from existing codebase (schema_migration.py, stats.py)
- Tree-sitter error detection: HIGH - verified via official documentation
- Pitfalls: HIGH - derived from direct codebase inspection of path handling, language mapping, etc.

**Research date:** 2026-02-08
**Valid until:** 2026-03-08 (stable domain, no fast-moving dependencies)
