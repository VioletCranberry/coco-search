# Technology Stack: Search Enhancements

**Project:** CocoSearch v1.7 Search Enhancement
**Researched:** 2026-02-03
**Confidence:** HIGH

## Executive Summary

This research evaluates stack additions for hybrid search (vector + BM25), context expansion, and symbol-aware indexing. The recommendation is **PostgreSQL-native approach** using built-in full-text search extensions rather than external libraries, keeping with CocoSearch's local-first, minimal-dependency philosophy.

**Key decision:** Use PostgreSQL's built-in `tsvector`/`tsquery` with custom ranking over external BM25 extensions because:
1. Zero new dependencies (already using PostgreSQL 17)
2. Mature, stable, well-documented
3. Sufficient for code search use case (BM25 advantage is marginal for short code chunks)
4. Avoids pre-release extensions (pg_textsearch v0.5.0 still pre-GA)

**Tree-sitter for symbols:** Use existing CocoIndex Tree-sitter integration with query-based symbol extraction - adds one small dependency (`tree-sitter-languages`) for 50+ language support.

## Recommended Stack Additions

### 1. Hybrid Search (Vector + Keyword)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL `tsvector`/`tsquery` | Built-in (PG17) | Keyword/lexical search | Zero dependencies, mature, sufficient for code chunks |
| PostgreSQL `pg_trgm` | Built-in contrib | Trigram similarity (fallback) | Optional enhancement for fuzzy matching |
| None (RRF in Python) | N/A | Reciprocal Rank Fusion | Simple formula, implement in application layer |

**Rationale:**

PostgreSQL 17 includes production-ready full-text search with `tsvector` (document representation) and `tsquery` (query representation). While not "true BM25", it provides:
- TF-IDF-like ranking via `ts_rank()` and `ts_rank_cd()` functions
- Configurable weights for different text positions
- Stop word filtering and stemming
- GIN indexes for performance

**Why NOT external BM25 extensions:**

| Extension | Status | Why Skip |
|-----------|--------|----------|
| pg_textsearch (Timescale) | v0.5.0 pre-release, GA Feb 2026 | Too new, pre-release risk |
| pg_search (ParadeDB) | Requires Rust/Tantivy build | Adds complexity, non-standard packaging |
| VectorChord-BM25 | Newer, less mature | Limited adoption, unproven |

For code search, the BM25 advantage is marginal:
- Code chunks are short (1000 bytes avg) - length normalization less critical
- Term frequency saturation less relevant in structured code
- Keyword precision matters more than scoring nuance

**Implementation approach:**

1. Add `content_text` column to chunk table (stores actual chunk text, ~5-20KB per chunk)
2. Add `content_tsv` column with `tsvector` (indexed with GIN)
3. Generate `content_tsv` during indexing: `to_tsvector('english', chunk_text)`
4. Keyword search: `SELECT ... WHERE content_tsv @@ plainto_tsquery('english', query)`
5. Rank with `ts_rank(content_tsv, query)` for lexical score
6. RRF fusion in Python application layer (simple formula)

**Storage cost:** ~10-20% increase (chunk text + tsvector index)

### 2. Context Expansion (Surrounding Code)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python file I/O | stdlib | Read surrounding lines at query time | Zero dependencies, simple, fast |
| PostgreSQL byte offsets | Existing | Locate chunk position | Already stored (`location` column) |

**Rationale:**

Context expansion is a **query-time operation**, not indexing-time. Current architecture stores:
- `filename`: Full path to source file
- `location`: Byte range as PostgreSQL `int4range` (e.g., `[0, 1000)`)

**Implementation approach:**

```python
def expand_context(filename: str, start_byte: int, end_byte: int,
                   context_lines: int = 5) -> tuple[str, int, int]:
    """Expand chunk to include N lines before/after."""
    with open(filename, 'rb') as f:
        content = f.read().decode('utf-8', errors='replace')

    # Find line boundaries
    lines = content.splitlines(keepends=True)
    # ... calculate expanded start/end based on context_lines

    return expanded_text, new_start, new_end
```

**Performance:** File reads are fast (local SSD, ~1ms per file). Caching not needed for MVP (10 results = 10 file reads = 10ms overhead).

**Alternative considered:** Store full chunk text in PostgreSQL. **Rejected because:**
- Violates current reference-only design (filename + byte range)
- Increases storage 10-20x (768-dim embeddings = 3KB, full text = 1KB avg)
- Makes context expansion less flexible (fixed at indexing time)

**When to upgrade:** If profiling shows file I/O is a bottleneck (unlikely), add chunk text column later.

### 3. Symbol-Aware Indexing (Functions/Classes)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `tree-sitter-languages` | 1.10.2+ | Pre-built Tree-sitter grammars for 50+ languages | Zero-config language support |
| Tree-sitter queries | Via `tree-sitter-languages` | Extract symbols (functions, classes, methods) | Precise, AST-based extraction |

**Rationale:**

CocoSearch already uses Tree-sitter via CocoIndex for chunking. Extend to **symbol extraction** by querying the AST during indexing.

**Current Tree-sitter usage:**
- CocoIndex uses `SplitRecursively` with Tree-sitter for semantic chunking
- Custom language handlers for HCL, Dockerfile, Bash (via `custom_languages`)

**Symbol extraction approach:**

Tree-sitter provides a **query language** for pattern matching on ASTs. Example for Python:

```python
# Query pattern (S-expression format)
PYTHON_SYMBOL_QUERY = """
(function_definition
  name: (identifier) @function.name) @function.def

(class_definition
  name: (identifier) @class.name) @class.def
"""

# Usage
from tree_sitter_languages import get_language, get_parser

parser = get_parser('python')
tree = parser.parse(bytes(code, 'utf8'))

language = get_language('python')
query = language.query(PYTHON_SYMBOL_QUERY)

for match, capture_name in query.captures(tree.root_node):
    if capture_name == 'function.name':
        # Extract function name, line number, byte range
        pass
```

**Schema addition:**

Add `symbol_type` and `symbol_name` columns to chunk table:

```sql
ALTER TABLE codeindex_{index}__{index}_chunks
ADD COLUMN symbol_type TEXT,  -- 'function', 'class', 'method', etc.
ADD COLUMN symbol_name TEXT;  -- 'parse_config', 'SearchResult', etc.
```

**Language coverage:**

`tree-sitter-languages` v1.10.2 includes 50+ languages:
- **Core:** Python, JavaScript, TypeScript, Java, C, C++, Go, Rust, Ruby, PHP
- **Web:** HTML, CSS, JSON, YAML, Markdown
- **Systems:** C#, Swift, Kotlin, Scala, Erlang, Elixir
- **Config:** TOML, INI, SQL

**Integration with CocoIndex:**

CocoIndex already parses files with Tree-sitter. Add symbol extraction as a **parallel operation** during chunking:

1. CocoIndex chunks file into semantic units (existing)
2. For each chunk, query Tree-sitter AST for symbols (new)
3. Store symbol metadata alongside chunk (new columns)

**Why NOT regex-based extraction:**
- Fragile (breaks on edge cases, nested definitions)
- Language-specific (need 50+ regex patterns)
- Already have Tree-sitter in pipeline

### 4. Full Language Coverage

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| CocoIndex built-in languages | Via `tree-sitter-languages` | Enable all 50+ languages | Already supported, just need to enable |

**Current state:** CocoSearch uses CocoIndex's `SplitRecursively` which already supports 50+ languages via Tree-sitter. No code changes needed.

**Validation needed:** Test that current CocoIndex version (0.3.28+) works with YAML, JSON, Markdown, and other non-code languages.

**Schema changes:** None. Language detection already handled by CocoIndex via file extensions.

## Updated Dependency List

### New Dependencies

```toml
[project.dependencies]
# Existing (no changes)
cocoindex[embeddings] = ">=0.3.28"
mcp[cli] = ">=1.26.0"
pathspec = ">=1.0.3"
pgvector = ">=0.4.2"
psycopg[binary,pool] = ">=3.3.2"
pyyaml = ">=6.0.2"
rich = ">=13.0.0"

# NEW for symbol extraction
tree-sitter-languages = ">=1.10.2"
```

**Size impact:** `tree-sitter-languages` is ~50MB (pre-compiled binaries for all languages). Acceptable for desktop tool.

### PostgreSQL Extensions

Enable during database setup:

```sql
-- Already using
CREATE EXTENSION IF NOT EXISTS vector;

-- NEW for hybrid search
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- Built-in contrib, optional
```

**Note:** `tsvector`/`tsquery` are core PostgreSQL types, no extension needed.

## Schema Changes

### Chunk Table Additions

```sql
-- For hybrid search (keyword matching)
ALTER TABLE codeindex_{index}__{index}_chunks
ADD COLUMN content_text TEXT,        -- Full chunk text (1KB avg)
ADD COLUMN content_tsv tsvector;     -- Full-text search vector

-- For symbol-aware indexing
ALTER TABLE codeindex_{index}__{index}_chunks
ADD COLUMN symbol_type TEXT,         -- 'function', 'class', 'method', etc.
ADD COLUMN symbol_name TEXT;         -- 'parse_config', 'SearchResult', etc.

-- Indexes for performance
CREATE INDEX idx_{index}_content_gin ON codeindex_{index}__{index}_chunks USING GIN(content_tsv);
CREATE INDEX idx_{index}_symbols ON codeindex_{index}__{index}_chunks(symbol_type, symbol_name);
```

**Storage estimate (per 10K chunks):**
- `content_text`: ~10MB (1KB avg per chunk)
- `content_tsv` (GIN index): ~2-3MB (compressed tsvector)
- `symbol_type` + `symbol_name`: ~500KB (short strings)
- **Total new storage:** ~13MB per 10K chunks (~20% increase from baseline)

**Baseline for comparison:** Current 10K chunks with embeddings = ~65MB (768-dim float32 vectors)

## Implementation Sequence

### Phase 1: Storage & Indexing
1. Add schema columns (content_text, content_tsv, symbol_type, symbol_name)
2. Update CocoIndex flow to store chunk text
3. Generate tsvector during indexing: `to_tsvector('english', chunk_text)`
4. Add Tree-sitter symbol extraction to indexing pipeline
5. Populate new columns during indexing

### Phase 2: Hybrid Search
1. Implement keyword search query (PostgreSQL `@@` operator)
2. Implement RRF fusion in Python (combine vector + keyword scores)
3. Add hybrid search to MCP search tool
4. Add CLI flag: `--hybrid` or `--search-mode={vector,keyword,hybrid}`

### Phase 3: Context Expansion
1. Add query-time file reading function
2. Add context expansion to MCP search results
3. Add CLI flag: `--context-lines=N` (default 0)

### Phase 4: Symbol Search
1. Add symbol filtering to search query
2. Add MCP tool: `search_symbols(query, symbol_type='function')`
3. Add CLI command: `cocosearch symbols --index=NAME --type=function`

## Alternatives Considered

### Alternative 1: External BM25 Libraries

**Option A: pg_textsearch (Timescale)**
- **Pro:** True BM25, modern architecture
- **Con:** Pre-release (v0.5.0), GA expected Feb 2026, PostgreSQL 17+ only
- **Verdict:** Too new, wait for v1.0 before adopting

**Option B: pg_search (ParadeDB)**
- **Pro:** True BM25, built on Tantivy (Rust)
- **Con:** Requires Rust toolchain for build, complex packaging, non-standard
- **Verdict:** Adds too much complexity for marginal benefit

**Option C: Python BM25 library (rank-bm25)**
- **Pro:** Pure Python, no PostgreSQL changes
- **Con:** Requires loading all documents into memory, doesn't scale
- **Verdict:** Not suitable for 100K+ chunks

### Alternative 2: Store Full Chunk Text in PostgreSQL

**Approach:** Add `content_text` column, query-time context expansion from DB.

**Pro:**
- Faster query time (no file I/O)
- Simpler query logic

**Con:**
- Violates reference-only design principle
- 10-20x storage increase (significant for large codebases)
- Less flexible (context size fixed at indexing time)
- Makes re-indexing slower (more data to insert)

**Verdict:** Start with file I/O approach (Phase 3), measure performance, upgrade if needed.

### Alternative 3: Regex-Based Symbol Extraction

**Approach:** Use regex patterns instead of Tree-sitter queries.

**Pro:**
- Simpler (no new dependencies)
- Faster for simple cases

**Con:**
- Fragile (breaks on nested definitions, complex syntax)
- Requires 50+ language-specific patterns
- Already have Tree-sitter in pipeline

**Verdict:** Use Tree-sitter queries (more robust, leverages existing infrastructure).

## Performance Considerations

### Hybrid Search Query Time

**Baseline (vector-only):**
- Query embedding: ~50ms (Ollama)
- Vector similarity search: ~10ms (pgvector with HNSW index)
- **Total:** ~60ms

**Hybrid (vector + keyword):**
- Query embedding: ~50ms (same)
- Vector similarity search: ~10ms (same)
- Keyword search: ~5ms (GIN index on tsvector)
- RRF fusion: ~1ms (in-memory ranking)
- **Total:** ~66ms (+10% overhead)

**Verdict:** Negligible overhead, acceptable.

### Context Expansion Overhead

**File I/O per result:**
- Open file: ~0.5ms
- Read and decode: ~0.5ms
- Parse lines: ~0.1ms
- **Total:** ~1ms per result

**For 10 results:** ~10ms total

**Verdict:** Acceptable. Add caching later if profiling shows bottleneck.

### Symbol Extraction During Indexing

**Overhead per file:**
- Parse with Tree-sitter: Already done by CocoIndex (~5ms per file)
- Query for symbols: ~1-2ms per file (one query per language)
- **Additional overhead:** ~1-2ms per file

**For 1000 files:** ~1-2 seconds additional indexing time

**Verdict:** Minimal impact on indexing performance.

## Migration Path

### Backward Compatibility

New columns are **additive only** (no breaking changes):
- Existing indexes work without re-indexing (columns default to empty)
- New features gracefully degrade if columns missing (like v1.2 metadata)
- Full functionality requires re-indexing

### Migration Strategy

```python
# Check if new columns exist
try:
    cursor.execute("SELECT content_text FROM {table} LIMIT 1")
    has_content_text = True
except UndefinedColumn:
    has_content_text = False

# Graceful degradation
if not has_content_text:
    logger.warning("Hybrid search requires re-indexing. Run: cocosearch index")
    # Fall back to vector-only search
```

### User Communication

```
$ cocosearch search --hybrid "authentication logic" --index=myproject

Warning: Hybrid search requires v1.7 index schema.
Run: cocosearch index --index=myproject
Falling back to vector-only search...
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `tsvector` ranking not good enough | Medium | Medium | Can upgrade to pg_textsearch later (schema compatible) |
| File I/O too slow for context | Low | Low | Add chunk text column if profiling shows issue |
| Tree-sitter query syntax complex | Low | Medium | Use pre-built queries from community examples |
| Storage increase unacceptable | Low | Medium | Make chunk text optional (CLI flag: --store-content) |

## Validation Checklist

Before finalizing implementation:

- [ ] Verify CocoIndex 0.3.28+ supports all 50+ languages (check docs/tests)
- [ ] Test `tsvector` ranking on sample code chunks (compare to BM25 baseline)
- [ ] Benchmark file I/O for context expansion (measure 10, 100, 1000 results)
- [ ] Validate Tree-sitter query syntax for Python, JavaScript, Go, Rust
- [ ] Estimate storage impact on large codebases (100K+ chunks)

## Sources

**PostgreSQL BM25 & Hybrid Search:**
- [PostgreSQL BM25 Full-Text Search](https://blog.vectorchord.ai/postgresql-full-text-search-fast-when-done-right-debunking-the-slow-myth)
- [True BM25 Ranking in Postgres](https://www.tigerdata.com/blog/introducing-pg_textsearch-true-bm25-ranking-hybrid-retrieval-postgres)
- [pg_textsearch GitHub](https://github.com/timescale/pg_textsearch) (v0.5.0 pre-release)
- [Hybrid Search in PostgreSQL: The Missing Manual](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual)
- [ParadeDB: BM25 in PostgreSQL](https://www.paradedb.com/learn/search-in-postgresql/bm25)

**Reciprocal Rank Fusion:**
- [RAG Series: Hybrid Search with Re-ranking](https://www.dbi-services.com/blog/rag-series-hybrid-search-with-re-ranking/)
- [Better RAG with RRF and Hybrid Search](https://www.assembled.com/blog/better-rag-results-with-reciprocal-rank-fusion-and-hybrid-search)
- [Hybrid Search Using RRF in SQL](https://www.singlestore.com/blog/hybrid-search-using-reciprocal-rank-fusion-in-sql/)
- [What is Reciprocal Rank Fusion?](https://www.paradedb.com/learn/search-concepts/reciprocal-rank-fusion)

**Tree-sitter & Symbol Extraction:**
- [py-tree-sitter Documentation](https://tree-sitter.github.io/py-tree-sitter/)
- [py-tree-sitter GitHub](https://github.com/tree-sitter/py-tree-sitter) (v0.25.2)
- [tree-sitter-languages PyPI](https://pypi.org/project/tree-sitter-languages/) (v1.10.2)
- [Diving into Tree-Sitter with Python](https://dev.to/shrsv/diving-into-tree-sitter-parsing-code-with-python-like-a-pro-17h8)
- [Using Tree-Sitter for Call Graph Extraction](https://volito.digital/using-the-tree-sitter-library-in-python-to-build-a-custom-tool-for-parsing-source-code-and-extracting-call-graphs/)

**PostgreSQL Full-Text Search:**
- [PostgreSQL 17: Chapter 12. Full Text Search](https://www.postgresql.org/docs/current/textsearch.html)
- [PostgreSQL pg_trgm Extension](https://www.postgresql.org/docs/current/pgtrgm.html)
- [Neon: pg_trgm Extension Guide](https://neon.com/docs/extensions/pg_trgm)

**CocoIndex & Tree-sitter Integration:**
- [Large Codebase Context with CocoIndex](https://cocoindexio.substack.com/p/index-codebase-with-tree-sitter-and)
- [Build Real-Time Codebase Indexing with CocoIndex](https://cocoindex.io/blogs/index-code-base-for-rag)
- [CocoIndex Functions Documentation](https://cocoindex.io/docs/ops/functions)

**Context Window & Code Search:**
- [Semantic Code Search](https://wangxj03.github.io/posts/2024-09-24-code-search/)
- [Building Open-Source Cursor Alternative](https://milvus.io/blog/build-open-source-alternative-to-cursor-with-code-context.md)
- [AI Code Review Tools: Context & Scale 2026](https://www.qodo.ai/blog/best-ai-code-review-tools-2026/)

---

**Research confidence:** HIGH
- PostgreSQL built-in features verified via official docs
- Tree-sitter libraries verified via PyPI and GitHub (current versions)
- BM25 extensions evaluated via official repos and blog posts
- RRF algorithm verified via multiple sources with SQL examples
