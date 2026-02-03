# Phase 32: Full Language Coverage + Documentation - Research

**Researched:** 2026-02-03
**Domain:** Language enablement, CLI statistics commands, technical documentation
**Confidence:** HIGH

## Summary

This phase enables all 30+ CocoIndex built-in languages, adds a `stats` command showing per-language metrics, creates a `languages` command to list supported languages, and comprehensively documents all v1.7 features (hybrid search, symbol filtering, context expansion) in README.md.

CocoIndex's `SplitRecursively` function provides native support for 31 languages through Tree-sitter integration (verified from official docs: https://cocoindex.io/docs/ops/functions). The codebase already has partial language support in `LANGUAGE_EXTENSIONS` (16 languages) and `DEVOPS_LANGUAGES` (3 languages), but needs expansion to match CocoIndex's full capabilities.

For the `stats` command, the database schema already tracks `filename` and `language_id` fields per chunk, enabling efficient per-language aggregation. Python's Rich library (already in use) provides excellent ASCII table formatting with unicode box characters.

Documentation best practices in 2026 emphasize use-case driven examples with before/after comparisons, showing command + expected output for each feature. The README is already 792 lines and well-structured, requiring expansion rather than reorganization.

**Primary recommendation:** Use CocoIndex's complete language list (31 languages), implement stats aggregation via SQL GROUP BY language_id, format output using Rich Table with ASCII styling for CLI consistency, and expand README with use-case driven examples showing real command output.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| CocoIndex | Current | Language detection and chunking | Built-in support for 31 languages via Tree-sitter, authoritative source for language capabilities |
| tree-sitter | Via CocoIndex | Syntax parsing for symbol extraction | Industry standard for language parsing, used by GitHub, Atom, and tree-sitter-languages |
| Rich | 14.1.0+ | Terminal table formatting | De facto standard for Python CLI formatting, provides ASCII tables matching git/docker style |
| psycopg | 3.x | PostgreSQL driver | Already in use, supports efficient GROUP BY queries for stats aggregation |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tree-sitter-languages | Current | Pre-built parsers | Already in use for symbol extraction, no additional setup needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Rich Table | PrettyTable, tabulate | Rich is already a dependency and matches CLI styling conventions |
| SQL aggregation | Python post-processing | SQL GROUP BY is orders of magnitude faster for large indexes |
| README expansion | Separate docs site | User decision (CONTEXT.md) requires single README.md file |

**Installation:**

No new dependencies required - all libraries already present in codebase.

## Architecture Patterns

### Recommended Project Structure

Existing structure is appropriate:
```
src/cocosearch/
├── cli.py                    # Add stats and languages subcommands
├── management/
│   └── stats.py              # Extend with per-language aggregation
└── indexer/
    └── languages.py          # Deprecate, point to CocoIndex
```

### Pattern 1: Language Registry (Single Source of Truth)

**What:** All language information comes from CocoIndex's SplitRecursively supported languages
**When to use:** Any feature requiring language lists, extensions, or capabilities

**Example:**

CocoIndex official documentation (verified 2026-01-09) lists 31 languages:

| Language | Aliases | Extensions | Symbol Support |
|----------|---------|------------|----------------|
| Python | — | .py | ✓ (5 langs) |
| JavaScript | js | .js | ✓ |
| TypeScript | ts | .ts, .tsx | ✓ |
| Go | golang | .go | ✓ |
| Rust | rs | .rs | ✓ |
| C | — | .c | ✗ |
| C++ | c++, cpp | .cpp, .cc, .cxx, .h, .hpp | ✗ |
| C# | cs, csharp | .cs | ✗ |
| Java | — | .java | ✗ |
| Ruby | — | .rb | ✗ |
| PHP | — | .php | ✗ |
| Swift | — | .swift | ✗ |
| Kotlin | — | .kt, .kts | ✗ |
| Scala | — | .scala | ✗ |
| Solidity | — | .sol | ✗ |
| R | — | .r | ✗ |
| Fortran | f, f90, f95, f03 | .f, .f90, .f95, .f03 | ✗ |
| Pascal | pas, dpr, delphi | .pas, .dpr | ✗ |
| CSS | — | .css, .scss | ✗ |
| HTML | — | .html, .htm | ✗ |
| XML | — | .xml | ✗ |
| JSON | — | .json | ✗ |
| YAML | — | .yaml, .yml | ✗ |
| TOML | — | .toml | ✗ |
| Markdown | md | .md, .mdx | ✗ |
| SQL | — | .sql | ✗ |
| DTD | — | .dtd | ✗ |
| TSX | — | .tsx | ✗ |

**Symbol-aware languages** (from src/cocosearch/indexer/symbols.py):
- Python: functions, classes, methods
- JavaScript: functions, arrow functions, classes, methods
- TypeScript: functions, classes, methods, interfaces, type aliases
- Go: functions, methods, structs, interfaces
- Rust: functions, methods, structs, traits, enums

Plus 3 custom DevOps languages (HCL, Dockerfile, Bash) added via `get_custom_languages()`.

### Pattern 2: Stats Aggregation via SQL GROUP BY

**What:** Use database aggregation for per-language statistics
**When to use:** Any multi-language statistics (stats command, MCP index_stats)

**Example:**
```python
# Efficient aggregation at database level
stats_query = f"""
    SELECT
        COALESCE(language_id, 'unknown') as language,
        COUNT(*) as chunk_count,
        COUNT(DISTINCT filename) as file_count,
        -- Line count requires content_text column (v1.7+)
        SUM(array_length(string_to_array(content_text, E'\n'), 1)) as line_count
    FROM {table_name}
    GROUP BY language_id
    ORDER BY chunk_count DESC
"""
```

**Why not Python post-processing:** For large indexes (10k+ chunks), SQL aggregation is 10-100x faster and uses constant memory.

### Pattern 3: Rich Table Formatting (ASCII Style)

**What:** Use Rich library with minimal box style for CLI consistency
**When to use:** All pretty-printed table output (stats, languages, list commands)

**Example:**
```python
# Source: https://rich.readthedocs.io/en/stable/reference/table.html
from rich.table import Table
from rich.console import Console

table = Table(title="Language Statistics")
table.add_column("Language", style="cyan", no_wrap=True)
table.add_column("Files", justify="right")
table.add_column("Chunks", justify="right")
table.add_column("Lines", justify="right")

for lang_stats in stats:
    table.add_row(
        lang_stats["language"],
        str(lang_stats["file_count"]),
        str(lang_stats["chunk_count"]),
        str(lang_stats["line_count"]),
    )

# Add totals row
table.add_section()  # Divider line
table.add_row("TOTAL", str(total_files), str(total_chunks), str(total_lines), style="bold")

console = Console()
console.print(table)
```

**Styling options:**
- `box=box.MINIMAL_DOUBLE_HEAD` - Minimal borders with double header line (git-like)
- `box=box.ROUNDED` - Rounded corners (modern)
- `box=None` - No borders (most minimal)
- Row styles: `row_styles=["dim", ""]` for zebra striping

User decision (CONTEXT.md): "Exact ASCII table styling and column widths" left to Claude's discretion.

### Pattern 4: Use-Case Driven Documentation

**What:** Start each feature section with "When to use", show command + output
**When to use:** All README feature documentation (hybrid search, symbol filtering, context expansion)

**Example structure:**
```markdown
## Hybrid Search

**When to use:** Searching for specific identifiers (function names, class names) where exact matches matter alongside semantic similarity.

Without hybrid search (semantic only):
```bash
cocosearch search "getUserById"
# May return: getUserByEmail, fetchUser, getProfile
```

With hybrid search (semantic + keyword):
```bash
cocosearch search "getUserById" --hybrid
# Returns: getUserById (exact match boosted to top)
```

**How it works:** Combines vector similarity with PostgreSQL full-text search (tsvector). Results are ranked by combined score.

**CLI flag:** `--hybrid`
**MCP parameter:** `use_hybrid: true`
```

User decision (CONTEXT.md): "Include before/after comparison examples to highlight improvement"

### Anti-Patterns to Avoid

- **Custom language list maintenance:** Don't maintain separate language lists. CocoIndex is authoritative source.
- **Python-side aggregation:** Don't fetch all chunks and aggregate in Python. Use SQL GROUP BY.
- **Complex ASCII art:** Don't hand-roll table formatting. Rich handles edge cases (overflow, wrapping, Unicode).
- **Separate CLI/MCP docs:** User decision requires inline documentation showing both flags and MCP parameters together.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Language detection | Extension-to-language mapping | CocoIndex `SplitRecursively` docs | CocoIndex handles 31+ languages with aliases, tree-sitter parsing, extensionless files (Dockerfile) |
| Table formatting | ASCII art generators, manual spacing | Rich Table | Handles overflow, wrapping, alignment, colors, Unicode, responsive width |
| Statistics aggregation | Fetching all rows and aggregating in Python | SQL GROUP BY with COUNT/SUM | Orders of magnitude faster, constant memory usage, leverages database indexes |
| Line counting | Reading files and counting newlines | `array_length(string_to_array(content_text, E'\n'), 1)` in SQL | Already stored in database, no file I/O, handles edge cases |

**Key insight:** This phase is about exposing existing capabilities (CocoIndex languages, database aggregation) rather than building new ones. Use authoritative sources and database features.

## Common Pitfalls

### Pitfall 1: Incomplete Language Coverage

**What goes wrong:** Only enabling the 16 languages in current `LANGUAGE_EXTENSIONS`, missing 15+ CocoIndex-supported languages (Fortran, Pascal, Solidity, R, etc.)

**Why it happens:** Developers may not realize CocoIndex's full language support, relying on existing mappings

**How to avoid:**
1. Fetch complete language list from CocoIndex official docs (https://cocoindex.io/docs/ops/functions)
2. Update `LANGUAGE_EXTENSIONS` to match all 31 CocoIndex languages
3. Test with files from all language extensions
4. Document that "unsupported" languages fall back to plain text (CocoIndex behavior)

**Warning signs:**
- `cocosearch languages` output doesn't match CocoIndex docs
- Fortran/Pascal/Solidity files indexed as plain text
- Missing extensions like .f90, .pas, .sol in LANGUAGE_EXTENSIONS

### Pitfall 2: Inefficient Stats Implementation

**What goes wrong:** Fetching all chunks into Python and aggregating with collections.Counter or pandas, causing memory exhaustion on large indexes

**Why it happens:** Familiarity with Python data processing tools, not recognizing database aggregation capabilities

**How to avoid:**
1. Use SQL GROUP BY for all aggregation
2. Let database count rows, files, lines
3. Only fetch aggregated results (one row per language)
4. Test with large index (10k+ chunks) to verify memory usage

**Warning signs:**
- Stats command slow (>1 second) on medium indexes
- Memory usage scales with index size
- Python process consumes 100+ MB for stats

### Pitfall 3: Symbol Column Missing from Stats

**What goes wrong:** Per-language stats query assumes all chunks have `content_text` column for line counting, but column was added in v1.7 (hybrid search phase)

**Why it happens:** Schema migration awareness gap between phases

**How to avoid:**
1. Use conditional column checks (already done for metadata columns in search.py)
2. Fall back gracefully if column missing (show "N/A" for line count)
3. Schema migration ensures column exists for new indexes
4. Document line count requires v1.7+ index

**Warning signs:**
- SQL error "column content_text does not exist" on old indexes
- Stats command crashes instead of degrading gracefully

### Pitfall 4: README Bloat

**What goes wrong:** README becomes 2000+ lines, difficult to navigate, loses focus

**Why it happens:** Adding comprehensive examples without pruning existing content

**How to avoid:**
1. Use collapsible sections (`<details>`) for verbose examples
2. Link to external docs for deep dives (even if internal docs like examples/)
3. Keep Quick Start section under 50 lines (5-minute goal)
4. Use Table of Contents to make navigation clear
5. Remove redundant examples (consolidate similar use cases)

**Warning signs:**
- README > 1500 lines
- Users complaining about "can't find X in docs"
- Multiple examples showing same concept

### Pitfall 5: Inconsistent Language Naming

**What goes wrong:** CocoIndex uses "c++" and "cpp" aliases, but stats command outputs "cpp", languages command outputs "C++", causing user confusion

**Why it happens:** Multiple sources of truth for canonical names

**How to avoid:**
1. Choose single display format (e.g., "C++" for display, "cpp" for filters)
2. Document aliases clearly in languages command
3. Accept all aliases in CLI flags (already done via LANGUAGE_ALIASES)
4. Normalize language_id in database to canonical form
5. Show canonical name in stats/languages output

**Warning signs:**
- Users asking "is it C++ or cpp?"
- Stats show both "c++" and "cpp" as separate languages
- Filter `--lang cpp` works but `--lang c++` doesn't (or vice versa)

## Code Examples

### Stats Command Implementation

```python
# Source: Adapted from existing stats.py + SQL patterns in codebase
def get_language_stats(index_name: str) -> list[dict]:
    """Get per-language statistics for an index.

    Returns:
        List of dicts with keys: language, file_count, chunk_count, line_count
        Sorted by chunk_count descending
    """
    pool = get_connection_pool()
    table_name = get_table_name(index_name)

    # Check if table exists
    check_query = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(check_query, (table_name,))
            (exists,) = cur.fetchone()

            if not exists:
                raise ValueError(f"Index '{index_name}' not found")

            # Check if content_text column exists (v1.7+)
            col_check = """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'content_text'
            """
            cur.execute(col_check, (table_name,))
            has_content_text = cur.fetchone() is not None

            # Build query with conditional line count
            if has_content_text:
                stats_query = f"""
                    SELECT
                        COALESCE(language_id, 'unknown') as language,
                        COUNT(DISTINCT filename) as file_count,
                        COUNT(*) as chunk_count,
                        SUM(array_length(string_to_array(content_text, E'\n'), 1)) as line_count
                    FROM {table_name}
                    GROUP BY language_id
                    ORDER BY chunk_count DESC
                """
            else:
                # Graceful degradation for pre-v1.7 indexes
                stats_query = f"""
                    SELECT
                        COALESCE(language_id, 'unknown') as language,
                        COUNT(DISTINCT filename) as file_count,
                        COUNT(*) as chunk_count,
                        NULL as line_count
                    FROM {table_name}
                    GROUP BY language_id
                    ORDER BY chunk_count DESC
                """

            cur.execute(stats_query)
            rows = cur.fetchall()

            return [
                {
                    "language": row[0],
                    "file_count": row[1],
                    "chunk_count": row[2],
                    "line_count": row[3],
                }
                for row in rows
            ]
```

### Languages Command Implementation

```python
# Source: Based on CocoIndex language list + existing CLI patterns
def languages_command(args: argparse.Namespace) -> int:
    """Execute the languages command.

    Shows all supported languages with extensions and symbol support.
    """
    console = Console()

    # Language data (from CocoIndex docs + symbols.py)
    # In real implementation, this would be generated from CocoIndex API
    # or stored as constant derived from official docs
    languages = [
        {"name": "Python", "extensions": ".py", "symbols": True},
        {"name": "JavaScript", "extensions": ".js, .mjs, .cjs", "symbols": True},
        {"name": "TypeScript", "extensions": ".ts, .tsx", "symbols": True},
        {"name": "Go", "extensions": ".go", "symbols": True},
        {"name": "Rust", "extensions": ".rs", "symbols": True},
        {"name": "Java", "extensions": ".java", "symbols": False},
        # ... (all 31 languages)
    ]

    if args.pretty:
        table = Table(title="Supported Languages")
        table.add_column("Language", style="cyan")
        table.add_column("Extensions", style="dim")
        table.add_column("Symbols", justify="center")

        for lang in languages:
            symbol_mark = "✓" if lang["symbols"] else "✗"
            table.add_row(lang["name"], lang["extensions"], symbol_mark)

        console.print(table)
        console.print("\n[dim]Symbol-aware languages support function/class/method extraction[/dim]")
    else:
        # JSON output for scripting
        print(json.dumps(languages, indent=2))

    return 0
```

### README Documentation Pattern

```markdown
## Supported Languages

CocoSearch indexes 30+ programming languages using CocoIndex's Tree-sitter integration.

**View all languages:**
```bash
cocosearch languages --pretty
```

**Output:**
```
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Language   ┃ Extensions        ┃ Symbols ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ Python     │ .py               │    ✓    │
│ JavaScript │ .js, .mjs, .cjs   │    ✓    │
│ TypeScript │ .ts, .tsx         │    ✓    │
...
└────────────┴───────────────────┴─────────┘
```

**Symbol-aware languages** (✓) support extraction of functions, classes, methods for filtering with `--symbol-type` and `--symbol-name`.

### Language Statistics

**Per-language breakdown:**
```bash
cocosearch stats myproject --pretty
```

**Output:**
```
┏━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃ Language   ┃  Files ┃ Chunks ┃  Lines ┃
┡━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ python     │     42 │    287 │  3,521 │
│ typescript │     18 │    156 │  2,103 │
│ markdown   │      8 │     45 │    892 │
├────────────┼────────┼────────┼────────┤
│ TOTAL      │     68 │    488 │  6,516 │
└────────────┴────────┴────────┴────────┘
```

**JSON output** (for scripting):
```bash
cocosearch stats myproject --json
```
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hard-coded language list (16 langs) | CocoIndex-sourced (31 langs) | Phase 32 | Full language coverage matches indexing capabilities |
| Index-level stats only | Per-language stats | Phase 32 | Visibility into codebase composition |
| Prose language list in README | `cocosearch languages` command | Phase 32 | Machine-readable, always current |
| Separate CLI/MCP docs | Inline documentation | Phase 32 | Single source of truth, no sync issues |

**Deprecated/outdated:**
- `src/cocosearch/indexer/languages.py`: Module now just re-exports from handlers. Direct language enumeration should use CocoIndex docs as source.
- Partial LANGUAGE_EXTENSIONS: Phase 32 expands to full CocoIndex language set.

## Open Questions

1. **Line count accuracy for mixed-format files**
   - What we know: SQL counts newlines in `content_text` column
   - What's unclear: How chunks spanning multiple files are counted (edge case)
   - Recommendation: Document as "approximate line count" since chunks may overlap

2. **Language naming canonical form**
   - What we know: CocoIndex uses lowercase (python, javascript), symbol extractor uses lowercase
   - What's unclear: User preference for display names (Python vs python, C++ vs cpp)
   - Recommendation: Use Title Case for display (Python, JavaScript, C++), lowercase for filters

3. **Symbol support for future languages**
   - What we know: Currently 5 languages have symbol extraction (Python, JS, TS, Go, Rust)
   - What's unclear: Plan for adding Java, C++, Ruby symbol support
   - Recommendation: Mark as "future work", keep symbol column nullable in database

## Sources

### Primary (HIGH confidence)

- **CocoIndex functions documentation** - https://cocoindex.io/docs/ops/functions
  - Complete list of 31 supported languages with extensions (verified 2026-01-09)
  - Authoritative source for language capabilities

- **CocoSearch codebase** - /Users/fedorzhdanov/GIT/personal/coco-s/src/
  - Symbol extractor (symbols.py): 5 languages with tree-sitter parsing
  - Query module (query.py): LANGUAGE_EXTENSIONS and DEVOPS_LANGUAGES mappings
  - Stats module (stats.py): Existing aggregation patterns
  - CLI module (cli.py): Command structure and Rich table usage

- **Rich library documentation** - https://rich.readthedocs.io/en/stable/reference/table.html
  - Table formatting API and styling options
  - Used extensively in codebase for pretty output

### Secondary (MEDIUM confidence)

- **CLI Guidelines** - https://clig.dev/
  - Best practices for command-line interfaces (2026)
  - Conventions for table output and examples

- **Google Developer Documentation Style Guide** - https://developers.google.com/style/code-syntax
  - Command-line syntax documentation standards
  - Before/after comparison patterns

- **README Best Practices** - https://github.com/jehna/readme-best-practices
  - Use-case driven documentation approach
  - Example structuring and quick start patterns

### Tertiary (LOW confidence)

- **WebSearch: CocoIndex Twitter post** - https://x.com/cocoindex_io/status/1932108144047800472
  - Social media mention of supported languages
  - Cross-referenced with official docs for verification

## Metadata

**Confidence breakdown:**
- Language list: HIGH - Verified from official CocoIndex docs (2026-01-09)
- Stats implementation: HIGH - Based on existing database schema and SQL patterns in codebase
- Documentation patterns: MEDIUM - Best practices from multiple sources, user decisions constrain approach
- Symbol extraction: HIGH - Directly from codebase (symbols.py) with 5 language implementations

**Research date:** 2026-02-03
**Valid until:** 2026-03-03 (30 days - CocoIndex language list is stable, CLI patterns are established)

**Key assumptions:**
1. Database schema has `language_id` column (added in Phase 28)
2. `content_text` column exists for line counting (added in Phase 28 v1.7)
3. Rich library already available (verified in pyproject.toml dependencies)
4. User decision to keep all docs in README.md (from CONTEXT.md)
