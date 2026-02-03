# Architecture Research: Search Enhancements

**Domain:** Semantic code search with hybrid retrieval
**Researched:** 2026-02-03
**Focus:** Integration of hybrid search, context expansion, and symbol-aware indexing into existing CocoIndex + PostgreSQL architecture

## Executive Summary

This research examines how three new capabilities integrate with CocoSearch's existing reference-only storage architecture:

1. **Hybrid search (BM25 + vector)** - Requires TEXT column for lexical indexing, BM25 extension, and RRF fusion at query time
2. **Context expansion** - Already supported via existing file reading utilities, requires zero schema changes
3. **Symbol-aware indexing** - Requires new extraction pipeline and additional metadata columns for symbol tracking

**Key finding:** Each enhancement has different integration complexity. Context expansion is essentially free (uses existing file I/O). Hybrid search requires schema changes and new PostgreSQL extensions. Symbol-aware indexing requires the most extensive changes (new extraction pipeline, schema additions, possibly separate index).

## Current Architecture Baseline

### Existing Pipeline

```
LocalFile source
    → SplitRecursively (Tree-sitter chunking)
        → EmbedText (Ollama embedding)
            → Extract DevOps metadata (block_type, hierarchy, language_id)
                → PostgreSQL storage (reference-only)
```

### Current Schema

```sql
-- Table: codeindex_{index_name}__{index_name}_chunks
CREATE TABLE ... (
    filename TEXT,
    location INT8RANGE,           -- [start_byte, end_byte)
    embedding VECTOR(768),        -- nomic-embed-text dimension
    block_type TEXT,              -- v1.2: DevOps metadata
    hierarchy TEXT,               -- v1.2: DevOps metadata
    language_id TEXT,             -- v1.2: DevOps metadata
    PRIMARY KEY (filename, location)
);

CREATE INDEX ... ON ... USING ivfflat (embedding vector_cosine_ops);
```

### Current Search Flow

```
Query string
    → Ollama embedding
        → pgvector cosine similarity (ORDER BY embedding <=> query_vector)
            → Post-filter by language (filename LIKE or language_id =)
                → Read file content at byte offsets (search/utils.py)
                    → Return with context_before/context_after lines
```

**Key characteristic:** Reference-only storage. Chunk text is NOT stored in database, only filename + byte range. File content is read on-demand during result formatting.

## Enhancement 1: Hybrid Search (BM25 + Vector)

### What Is Hybrid Search?

Combines two retrieval strategies:
- **Vector similarity** (semantic): "authentication logic" matches "login handler" even without shared keywords
- **BM25 lexical** (keyword): "JWT token" only matches exact/stemmed terms, boosting precision

Fusion via Reciprocal Rank Fusion (RRF) merges ranked results from both searches.

### PostgreSQL BM25 Extension Options

| Extension | Status | Approach | Confidence |
|-----------|--------|----------|------------|
| **pg_textsearch** (Timescale) | Pre-release v0.5.0-dev, GA Feb 2026 | Native BM25 with hybrid query support | HIGH |
| **VectorChord-BM25** (TensorChord) | Production-ready | Custom operator + index | HIGH |
| **ParadeDB pg_search** | Production-ready | Full-featured BM25 + vector | MEDIUM |
| **plpgsql_bm25** | Open-source | Pure PL/pgSQL implementation | LOW |

**Recommendation:** pg_textsearch (Timescale) for operational simplicity and hybrid search focus, or VectorChord-BM25 for performance. Both integrate cleanly with pgvector.

**Confidence:** HIGH - Multiple production-ready options exist, all documented for hybrid search with pgvector.

### Schema Changes Required

**Challenge:** Current architecture stores NO text content in database (reference-only). BM25 requires indexed text.

**Options:**

#### Option A: Add text column + BM25 index (RECOMMENDED)

```sql
ALTER TABLE codeindex_{index}__{index}_chunks
ADD COLUMN chunk_text TEXT;

-- Populate during indexing (modify CocoIndex export)
-- BM25 index creation (extension-specific)
CREATE INDEX idx_bm25 ON ... USING bm25(chunk_text);  -- pg_textsearch
-- OR
CREATE INDEX idx_bm25 ON ... USING vchord_bm25(chunk_text);  -- VectorChord
```

**Pros:**
- Single table, simple joins for RRF
- Same table structure as prior art (ParadeDB examples, Timescale docs)
- Atomic updates (text + embedding updated together)

**Cons:**
- Storage increase (currently ~768 floats = 3KB per chunk, adding text = ~1-5KB more)
- Breaks "reference-only" philosophy (but hybrid search fundamentally requires stored text)

**Storage impact:** For 10,000 chunks averaging 1KB text each = ~10MB additional. Embeddings already ~30MB (768 floats × 4 bytes × 10K). Total increase ~33%.

#### Option B: Separate BM25 table (NOT RECOMMENDED)

```sql
CREATE TABLE codeindex_{index}_bm25 (
    filename TEXT,
    location INT8RANGE,
    chunk_text TEXT,
    PRIMARY KEY (filename, location)
);
```

**Pros:**
- Preserves reference-only storage in main table

**Cons:**
- Complex RRF joins across tables (FULL OUTER JOIN on filename + location)
- Duplicate primary key maintenance
- No clear benefits over Option A

**Recommendation:** NOT RECOMMENDED. Industry patterns (ParadeDB, Timescale, VectorChord examples) use same-table approach.

**Confidence:** HIGH - All hybrid search documentation shows same-table pattern.

### Integration Points

#### 1. Indexing Pipeline

**Modified flow:**

```python
# In create_code_index_flow()
with file["chunks"].row() as chunk:
    chunk["embedding"] = chunk["text"].call(code_to_embedding)
    chunk["metadata"] = chunk["text"].transform(extract_devops_metadata, ...)

    # NEW: Store chunk text for BM25
    chunk["chunk_text"] = chunk["text"]  # Pass through unchanged

    code_embeddings.collect(
        filename=file["filename"],
        location=chunk["location"],
        embedding=chunk["embedding"],
        chunk_text=chunk["chunk_text"],  # NEW
        block_type=chunk["metadata"]["block_type"],
        hierarchy=chunk["metadata"]["hierarchy"],
        language_id=chunk["metadata"]["language_id"],
    )
```

**Impact:** Minimal code change. CocoIndex already has the text in `chunk["text"]`, just need to pass it through to storage.

#### 2. Search Query

**New hybrid search function:**

```python
def hybrid_search(
    query: str,
    index_name: str,
    limit: int = 10,
    bm25_weight: float = 0.5,  # RRF weighting
    vector_weight: float = 0.5,
    min_score: float = 0.0,
    language_filter: str | None = None,
) -> list[SearchResult]:
    """Hybrid search using RRF fusion of BM25 + vector results."""

    # Embed query for vector search
    query_embedding = code_to_embedding.eval(query)
    table_name = get_table_name(index_name)

    # RRF with CTEs (Reciprocal Rank Fusion)
    sql = f"""
        WITH bm25_results AS (
            SELECT filename, location,
                   ROW_NUMBER() OVER (ORDER BY chunk_text <@> to_bm25query(%s)) AS rank
            FROM {table_name}
            WHERE {build_language_filter_clause()}
            LIMIT %s
        ),
        vector_results AS (
            SELECT filename, location,
                   1 - (embedding <=> %s::vector) AS score,
                   ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) AS rank
            FROM {table_name}
            WHERE {build_language_filter_clause()}
            LIMIT %s
        )
        SELECT COALESCE(bm25.filename, vec.filename) AS filename,
               COALESCE(bm25.location, vec.location) AS location,
               vec.score,
               (COALESCE(%s / (60 + bm25.rank), 0) +
                COALESCE(%s / (60 + vec.rank), 0)) AS rrf_score
        FROM bm25_results bm25
        FULL OUTER JOIN vector_results vec USING (filename, location)
        ORDER BY rrf_score DESC
        LIMIT %s
    """

    # Execute and return results
    # ... (similar to current search() implementation)
```

**Key pattern:** RRF fusion with k=60 smoothing factor (industry standard per MongoDB/ParadeDB docs).

**Confidence:** HIGH - RRF implementation well-documented across multiple sources.

#### 3. Extension Installation

**New setup requirement:**

```python
# In management/setup.py or similar
def init_bm25_extension():
    """Initialize BM25 extension for hybrid search."""
    with get_connection_pool().connection() as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS pg_textsearch")  # Timescale
        # OR
        conn.execute("CREATE EXTENSION IF NOT EXISTS vchord_bm25")  # VectorChord
```

**Docker dependency:** Requires BM25 extension in PostgreSQL image. Current `pgvector/pgvector:pg17` image does NOT include BM25 extensions.

**Options:**
- Build custom Docker image with pgvector + pg_textsearch/vchord_bm25
- Use ParadeDB image (includes both pg_search for BM25 and pgvector)
- Document manual extension installation for native PostgreSQL setups

### Build Order Recommendation

1. **Phase 1:** Add chunk_text column, modify indexing pipeline to store text
2. **Phase 2:** Install BM25 extension (document Docker image requirements)
3. **Phase 3:** Implement RRF hybrid search query
4. **Phase 4:** Add CLI flag `--hybrid` to enable hybrid vs pure vector search

**Rationale:** Incremental rollout. Phase 1 is backward compatible (pure vector search still works). Phase 2 handles infrastructure. Phase 3 adds new capability. Phase 4 exposes to users.

## Enhancement 2: Context Expansion

### What Is Context Expansion?

Retrieving surrounding lines of code beyond the matched chunk to provide fuller context for understanding.

**Example:**
- Matched chunk: Lines 45-47 (function body)
- Context expansion: Lines 40-52 (include function signature, docstring, closing brace)

### Current Implementation

**Already exists!** See `src/cocosearch/search/formatter.py`:

```python
def get_context_lines(
    filepath: str,
    start_line: int,
    end_line: int,
    context: int = 5,  # Default: 5 lines before/after
) -> tuple[list[str], list[str]]:
    """Get lines before and after a code chunk."""
    # Reads file, returns (lines_before, lines_after)
```

**Used in:**
- JSON output: `context_before`, `context_after` fields
- CLI `--context` flag: `cocosearch search "query" --context 10`
- MCP response: Optional context inclusion

### Schema Changes Required

**NONE.** Context expansion happens at **query time** by reading the source file. No database storage needed.

### Integration Points

**No changes needed!** Current architecture already supports context expansion:

1. Search returns `(filename, start_byte, end_byte, score)`
2. Formatter converts bytes to lines: `byte_to_line(filename, start_byte)`
3. Context reader fetches surrounding lines: `get_context_lines(filename, start_line, end_line, context=N)`

**Existing capabilities:**
- CLI: `--context N` flag
- MCP: `include_context` parameter
- JSON: `context_before` / `context_after` fields

### Potential Enhancement: Smart Context Expansion

Instead of fixed N-line context, expand to **semantic boundaries** using Tree-sitter.

**Example:**
- Matched chunk: Middle of function body
- Smart expansion: Entire function definition (from `def` to closing brace)

**Implementation:**

```python
def get_semantic_context(
    filepath: str,
    start_byte: int,
    end_byte: int,
    language: str,
) -> tuple[int, int]:
    """Expand byte range to nearest semantic boundary using Tree-sitter."""
    # Parse file with Tree-sitter
    # Find enclosing node (function_definition, class_definition, etc.)
    # Return (node.start_byte, node.end_byte)
```

**Benefits:**
- More meaningful context (full function instead of partial)
- Language-aware (different boundaries for Python vs Go)

**Challenges:**
- Requires Tree-sitter dependency at search time (currently only used during indexing)
- File may have changed since indexing (stale boundaries)

**Recommendation:** Defer to post-enhancement phase. Fixed-line context works well and is simpler.

**Confidence:** HIGH for current implementation (already exists), MEDIUM for smart expansion (requires validation that Tree-sitter overhead is acceptable at query time).

### Build Order Recommendation

**No build needed!** Context expansion is already implemented and working.

**Potential Phase (optional):**
- Smart semantic boundary expansion (Tree-sitter at query time)

## Enhancement 3: Symbol-Aware Indexing

### What Is Symbol-Aware Indexing?

Tracking code symbols (functions, classes, methods, types) as first-class entities with searchable metadata.

**Use case:**
- Search: "login function" → Find all function definitions related to authentication
- Filter: "show me all class definitions" → Skip function bodies, only return classes
- Navigate: "find callers of authenticate_user" → Requires call graph (out of scope for this phase)

### Symbol Extraction Options

#### Option A: Tree-sitter Queries (RECOMMENDED)

Tree-sitter provides a query language for extracting structured information from ASTs.

**Example query (Python functions):**

```scheme
(function_definition
  name: (identifier) @function.name
  parameters: (parameters) @function.params
  return_type: (type)? @function.return_type
  body: (block) @function.body
) @function.definition
```

**Capabilities:**
- Extract: Function names, parameters, return types, docstrings
- Extract: Class names, base classes, methods
- Works for 30+ languages (all Tree-sitter grammars)

**CocoIndex integration:** Tree-sitter is already used in `SplitRecursively`. Could extend custom_languages handlers to include symbol extraction.

**Pros:**
- Reuses existing Tree-sitter dependency
- Language-agnostic (write queries once per language)
- Fast (Tree-sitter is highly optimized)

**Cons:**
- Requires writing/maintaining query files for each language
- Tree-sitter doesn't provide queries out-of-box (unlike some AST libraries)

**Confidence:** HIGH - Tree-sitter is battle-tested for symbol extraction (used by GitHub code navigation, many IDEs).

#### Option B: Language-Specific AST Parsers

Use Python's `ast` module for Python, `tree-sitter-go` for Go, etc.

**Pros:**
- More detailed metadata (e.g., Python's `ast` includes decorators, annotations)

**Cons:**
- Separate parser per language (higher maintenance)
- Not all languages have good Python bindings (e.g., Rust, Kotlin)

**Recommendation:** NOT RECOMMENDED. Tree-sitter already in use, adding language-specific parsers increases complexity.

#### Option C: CocoIndex Built-in Functions

**Finding:** CocoIndex does NOT provide built-in symbol extraction functions. `SplitRecursively` chunks at semantic boundaries but doesn't extract symbol metadata.

**Implication:** Must implement custom extraction logic.

### Schema Changes Required

#### Option A: Same Table with Symbol Metadata (RECOMMENDED)

Add columns to existing chunks table:

```sql
ALTER TABLE codeindex_{index}__{index}_chunks
ADD COLUMN symbol_type TEXT,      -- 'function', 'class', 'method', 'type', NULL for non-symbols
ADD COLUMN symbol_name TEXT,      -- 'authenticate_user', 'User', etc.
ADD COLUMN symbol_signature TEXT, -- 'def authenticate_user(username: str, password: str) -> User'
ADD COLUMN symbol_parent TEXT;    -- For methods: parent class name

-- Index for symbol searches
CREATE INDEX idx_symbol_type ON ... (symbol_type);
CREATE INDEX idx_symbol_name ON ... (symbol_name);
```

**Pros:**
- Unified storage (symbols and regular chunks in same table)
- Simple queries (single table scan)
- Reuse existing vector similarity for semantic symbol search

**Cons:**
- Most chunks are NOT symbols (NULL values for symbol_* columns)
- Schema gets wider (more columns)

**Recommendation:** RECOMMENDED for v1.7. Simple, works with existing architecture.

#### Option B: Separate Symbols Table

```sql
CREATE TABLE codeindex_{index}_symbols (
    filename TEXT,
    location INT8RANGE,
    symbol_type TEXT,      -- 'function', 'class', 'method'
    symbol_name TEXT,
    symbol_signature TEXT,
    embedding VECTOR(768), -- Same embedding as chunk
    PRIMARY KEY (filename, location)
);

CREATE INDEX ... ON ... USING ivfflat (embedding vector_cosine_ops);
```

**Pros:**
- Cleaner schema (only symbols, no NULL columns)
- Faster symbol-only queries (smaller table scan)
- Could use different embedding strategy (e.g., embed signature instead of full code)

**Cons:**
- Separate indexing pipeline or dual-export from CocoIndex
- Separate search code path
- More complexity (two tables to maintain)

**Recommendation:** Consider for FUTURE if symbol search becomes primary use case. Premature optimization for v1.7.

**Confidence:** MEDIUM - No clear industry standard for symbol storage in semantic code search. Most tools (Sourcegraph Cody, Cursor) don't publicly document their schema.

### Integration Points

#### 1. Indexing Pipeline

**New symbol extraction transform:**

```python
# In handlers/ directory
def extract_symbol_metadata(
    text: str,
    language: str,
    start_byte: int,
    end_byte: int,
    filepath: str,
) -> dict:
    """Extract symbol metadata using Tree-sitter queries.

    Returns:
        dict with keys: symbol_type, symbol_name, symbol_signature, symbol_parent
        All values are empty strings if chunk is not a symbol.
    """
    if language not in SYMBOL_AWARE_LANGUAGES:
        return {"symbol_type": "", "symbol_name": "", "symbol_signature": "", "symbol_parent": ""}

    # Parse file with Tree-sitter (cache parsed tree per file)
    tree = parse_file_cached(filepath, language)

    # Find node at byte range
    node = tree.root_node.descendant_for_byte_range(start_byte, end_byte)

    # Run language-specific query
    query = get_symbol_query(language)  # Load from queries/{language}.scm
    captures = query.captures(node)

    # Extract metadata from captures
    # ... (language-specific logic)

    return {
        "symbol_type": "function",  # or 'class', 'method', etc.
        "symbol_name": "authenticate_user",
        "symbol_signature": "def authenticate_user(username: str, password: str) -> User",
        "symbol_parent": "",  # Empty for top-level functions
    }
```

**Pipeline modification:**

```python
# In create_code_index_flow()
with file["chunks"].row() as chunk:
    chunk["embedding"] = chunk["text"].call(code_to_embedding)
    chunk["devops_metadata"] = chunk["text"].transform(extract_devops_metadata, ...)

    # NEW: Extract symbol metadata
    chunk["symbol_metadata"] = chunk["text"].transform(
        extract_symbol_metadata,
        language=file["extension"],
        start_byte=chunk["location"]["start"],
        end_byte=chunk["location"]["end"],
        filepath=file["filename"],
    )

    code_embeddings.collect(
        filename=file["filename"],
        location=chunk["location"],
        embedding=chunk["embedding"],
        # DevOps metadata
        block_type=chunk["devops_metadata"]["block_type"],
        hierarchy=chunk["devops_metadata"]["hierarchy"],
        language_id=chunk["devops_metadata"]["language_id"],
        # Symbol metadata (NEW)
        symbol_type=chunk["symbol_metadata"]["symbol_type"],
        symbol_name=chunk["symbol_metadata"]["symbol_name"],
        symbol_signature=chunk["symbol_metadata"]["symbol_signature"],
        symbol_parent=chunk["symbol_metadata"]["symbol_parent"],
    )
```

**Challenges:**
- Tree-sitter parsing at indexing time (currently only used for chunking inside SplitRecursively)
- Need to parse full file to find symbols, not just chunk text
- File parsing could be slow (mitigate with caching: one parse per file, multiple chunks)

#### 2. Search Query

**Symbol-filtered search:**

```python
def search(
    query: str,
    index_name: str,
    symbol_type: str | None = None,  # NEW: 'function', 'class', 'method'
    symbol_name_filter: str | None = None,  # NEW: SQL LIKE pattern
    limit: int = 10,
    ...
) -> list[SearchResult]:
    """Search with optional symbol filtering."""

    # Build WHERE clause
    where_parts = []
    if symbol_type:
        where_parts.append(f"symbol_type = %s")
    if symbol_name_filter:
        where_parts.append(f"symbol_name LIKE %s")

    # ... rest of query
```

**CLI integration:**

```bash
# Find all functions related to authentication
cocosearch search "authentication" --symbol function

# Find specific function by name
cocosearch search "login" --symbol-name "authenticate_user"

# List all class definitions
cocosearch search "" --symbol class --limit 100
```

#### 3. Tree-sitter Query Files

**New directory structure:**

```
src/cocosearch/queries/
    python.scm        # Python symbol extraction queries
    javascript.scm
    typescript.scm
    go.scm
    rust.scm
    ...
```

**Example `python.scm`:**

```scheme
; Functions
(function_definition
  name: (identifier) @function.name
  parameters: (parameters) @function.params
  return_type: (type)? @function.return
) @function.definition

; Classes
(class_definition
  name: (identifier) @class.name
  superclasses: (argument_list)? @class.bases
) @class.definition

; Methods (functions inside classes)
(class_definition
  body: (block
    (function_definition
      name: (identifier) @method.name
    ) @method.definition
  )
) @method.context
```

**Maintenance:** One query file per supported language. Start with top 5-10 languages (Python, JavaScript, TypeScript, Go, Rust).

### Build Order Recommendation

1. **Phase 1:** Add symbol_* columns to schema (nullable, defaults to empty strings)
2. **Phase 2:** Implement Tree-sitter symbol extraction for Python only (validate approach)
3. **Phase 3:** Add Tree-sitter queries for JavaScript, TypeScript, Go, Rust
4. **Phase 4:** Add symbol filtering to search query (--symbol, --symbol-name flags)
5. **Phase 5:** Document symbol extraction coverage per language

**Rationale:** Incremental rollout by language. Python first (most common in ML/AI codebases), then expand. Symbol extraction is optional (existing chunks still work), so no breaking changes.

## Comparison: Three Enhancements

| Enhancement | Schema Changes | Pipeline Changes | Query Changes | Complexity | Dependency |
|-------------|----------------|------------------|---------------|------------|------------|
| **Context Expansion** | None | None | None (already exists) | LOW | None |
| **Hybrid Search** | Add chunk_text column | Store text in collect() | RRF CTE query | MEDIUM | BM25 extension (pg_textsearch or vchord_bm25) |
| **Symbol-Aware** | Add 4 symbol columns | Add symbol extraction transform | Add symbol filters | HIGH | Tree-sitter queries (new files) |

## Recommended Build Order (Across All Enhancements)

### Phase 1: Hybrid Search Foundation
1. Add `chunk_text TEXT` column
2. Modify indexing pipeline to store chunk text
3. Test backward compatibility (old indexes still work)

### Phase 2: BM25 Infrastructure
1. Document BM25 extension installation (pg_textsearch or VectorChord-BM25)
2. Add extension to Docker image (custom build from pgvector base)
3. Create BM25 index on chunk_text column

### Phase 3: Hybrid Search Query
1. Implement RRF hybrid search function
2. Add CLI flag `--hybrid` (default: vector-only for backward compat)
3. Add MCP parameter `use_hybrid_search: bool`

### Phase 4: Symbol-Aware Foundation (Parallel to Phase 3)
1. Add symbol_type, symbol_name, symbol_signature, symbol_parent columns
2. Implement Tree-sitter query loader
3. Test symbol extraction on Python files

### Phase 5: Symbol Extraction Rollout
1. Add symbol extraction for top 5 languages (Python, JS, TS, Go, Rust)
2. Add symbol filtering to search query
3. Add CLI flags `--symbol`, `--symbol-name`

### Phase 6: Documentation & Polish
1. Document hybrid search vs pure vector tradeoffs
2. Document symbol coverage per language
3. Document context expansion (already works, just needs docs)

**Rationale:** Hybrid search is lower risk (text storage is straightforward). Symbol extraction is higher complexity (Tree-sitter query maintenance). Parallelizing Phase 3 and Phase 4 allows independent development tracks.

## Architecture Patterns

### Pattern 1: Same-Table Multi-Index

**Pattern:** Store all data (embeddings, text, symbols) in same table, create multiple indexes for different search strategies.

```sql
CREATE TABLE chunks (
    -- Primary key
    filename TEXT,
    location INT8RANGE,

    -- Vector search
    embedding VECTOR(768),

    -- BM25 search
    chunk_text TEXT,

    -- Symbol search
    symbol_type TEXT,
    symbol_name TEXT,

    -- Metadata
    block_type TEXT,
    language_id TEXT,
    ...

    PRIMARY KEY (filename, location)
);

CREATE INDEX idx_vector ON chunks USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_bm25 ON chunks USING bm25 (chunk_text);  -- Extension-specific
CREATE INDEX idx_symbol_type ON chunks (symbol_type);
CREATE INDEX idx_symbol_name ON chunks (symbol_name);
```

**Benefits:**
- Single source of truth
- Atomic updates (all data updated together)
- Simple RRF joins (no FULL OUTER JOIN across tables)
- Proven pattern (ParadeDB, Timescale docs)

**Tradeoffs:**
- Wider table (more columns)
- Some NULL values (e.g., symbol_type for non-symbols)

**Recommendation:** RECOMMENDED. Industry standard for hybrid search.

### Pattern 2: Lazy File Reading for Context

**Pattern:** Store only references (filename + byte range), read file content on-demand during result formatting.

**Current implementation:**
- Indexing: Store filename, start_byte, end_byte (reference-only)
- Search: Return references + metadata
- Formatting: Read file, extract content, add context lines

**Benefits:**
- Smaller database (no duplicate content storage)
- Always fresh (file changes reflected in reads)
- Works for large files (no storage limit)

**Tradeoffs:**
- File must exist at search time (deleted files = empty results)
- File I/O at query time (slower than DB-only query)
- No content for remote files (Docker container needs mount)

**Recommendation:** KEEP for context expansion (already works well). CHANGE for hybrid search (BM25 requires stored text).

**Rationale:** Context expansion is a formatting concern (how to display results). Hybrid search is a retrieval concern (which results to return). Different requirements.

### Pattern 3: Incremental Schema Evolution

**Pattern:** Add columns with default values, maintain backward compatibility.

```sql
-- v1.2: Added DevOps metadata
ALTER TABLE ... ADD COLUMN block_type TEXT DEFAULT '';
ALTER TABLE ... ADD COLUMN hierarchy TEXT DEFAULT '';
ALTER TABLE ... ADD COLUMN language_id TEXT DEFAULT '';

-- v1.7: Add hybrid search + symbols
ALTER TABLE ... ADD COLUMN chunk_text TEXT DEFAULT '';
ALTER TABLE ... ADD COLUMN symbol_type TEXT DEFAULT '';
ALTER TABLE ... ADD COLUMN symbol_name TEXT DEFAULT '';
```

**Benefits:**
- Old indexes still work (empty strings for new columns)
- No migration required (optional re-indexing for new features)
- Graceful degradation (search code checks for column existence)

**Current precedent:** v1.2 DevOps metadata used this pattern successfully (see query.py graceful degradation).

**Recommendation:** CONTINUE this pattern for v1.7 schema changes.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Separate Table Per Search Type

**What:** Create separate tables for vector search, BM25 search, symbol search.

**Why bad:**
- Complex RRF joins (FULL OUTER JOIN across 3 tables)
- Duplicate primary key maintenance
- Update skew (tables get out of sync)

**Industry evidence:** No hybrid search implementation uses this pattern. All use same-table approach.

### Anti-Pattern 2: Storing Context Lines in Database

**What:** Pre-compute context_before/context_after lines during indexing, store in database.

**Why bad:**
- Duplicate storage (context lines overlap between chunks)
- Stale data (file changes not reflected)
- Storage explosion (5 lines before + 5 after = 2-3x storage per chunk)

**Current approach is better:** Read files on-demand during formatting. Minimal storage, always fresh.

### Anti-Pattern 3: Full AST Storage

**What:** Store full Abstract Syntax Tree in database for each file.

**Why bad:**
- Enormous storage (ASTs are 10-100x larger than source)
- Stale data (file changes invalidate AST)
- Query complexity (traversing AST in SQL is impractical)

**Better approach:** Store extracted metadata only (symbol_type, symbol_name). Re-parse file if deeper AST traversal needed (rare).

## Scalability Considerations

### At Current Scale (10K-100K chunks)

| Concern | Approach | Notes |
|---------|----------|-------|
| Vector index | ivfflat (current) | Sufficient for <1M vectors |
| BM25 index | Native extension index | Fast for <100K documents per pg_textsearch docs |
| Symbol queries | B-tree index on symbol_name | Standard PostgreSQL indexing |
| Storage | Single table | ~10-50 MB per 10K chunks |

### At 1M+ Chunks

| Concern | Approach | Notes |
|---------|----------|-------|
| Vector index | Consider HNSW (pgvector 0.5.0+) | Better recall than ivfflat at scale |
| BM25 index | Partition tables | BM25 extensions support partitioned tables |
| Storage | Compression | PostgreSQL TOAST handles large text columns |
| Query speed | Parallel workers | Enable parallel query for table scans |

**Recommendation:** Current approach scales to 1M chunks. Defer optimizations until proven bottleneck.

## Migration Strategy

### Backward Compatibility

**Requirement:** Existing indexes (pre-v1.7) must continue to work without re-indexing.

**Approach:**

1. **Schema migration:** ALTER TABLE with DEFAULT values (empty strings)
2. **Graceful degradation:** Search code checks for column existence (like v1.2 DevOps metadata)
3. **Optional re-index:** Users can re-index to populate new columns (chunk_text, symbol_*)

**Precedent:** v1.2 DevOps metadata used this successfully. Pre-v1.2 indexes still work with empty metadata.

### Re-indexing Trigger

**When to re-index:**
- User explicitly runs `cocosearch index <path> --name <index>`
- Existing index name triggers update (CocoIndex incremental processing)

**What gets updated:**
- New files: Full processing with v1.7 features
- Changed files: Re-processed with v1.7 features
- Unchanged files: Keep existing data (may lack chunk_text if from pre-v1.7)

**Implication:** Hybrid search only works on re-indexed chunks. Symbol filtering only works on re-indexed chunks. Vector search works on all chunks.

**User communication:**
```
$ cocosearch search "query" --hybrid --index myproject
Warning: 45% of chunks lack text content (pre-v1.7 index).
Re-run 'cocosearch index' to enable full hybrid search.

Results (hybrid search on 3,847 chunks, vector-only on 3,153 chunks):
...
```

## Tool & Dependency Analysis

### Required Dependencies

| Feature | Dependency | Version | Status |
|---------|------------|---------|--------|
| Current | pgvector | Latest (0.5.0+) | ✓ In use |
| Hybrid search | pg_textsearch OR vchord_bm25 | v0.5.0-dev / Latest | NEW |
| Symbol extraction | tree-sitter | Via CocoIndex | ✓ In use (for chunking) |
| Symbol queries | (files: queries/*.scm) | N/A | NEW |

### PostgreSQL Extension Matrix

| Extension | Provider | License | Docker Support | Hybrid Search Docs | Confidence |
|-----------|----------|---------|----------------|-------------------|------------|
| **pg_textsearch** | Timescale | OSS (PostgreSQL) | Timescale images | ✓ Excellent | HIGH |
| **vchord_bm25** | TensorChord | OSS | VectorChord images | ✓ Good | HIGH |
| **pg_search** | ParadeDB | OSS (AGPL) | ParadeDB images | ✓ Excellent | MEDIUM (license) |

**Recommendation:** pg_textsearch (Timescale) for simplicity and OSS license, OR vchord_bm25 (TensorChord) for performance focus.

**Docker impact:** Current `pgvector/pgvector:pg17` image does NOT include BM25 extensions. Must either:
1. Build custom image: `FROM pgvector/pgvector:pg17` + install pg_textsearch
2. Use provider image: `FROM timescale/timescaledb:latest-pg17` (includes pgvector + pg_textsearch)
3. Document manual installation for native PostgreSQL

**Confidence:** HIGH - Multiple production-ready options with good documentation.

## Sources

### Hybrid Search & BM25
- [Hybrid Search in PostgreSQL: The Missing Manual | ParadeDB](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual)
- [True BM25 Ranking and Hybrid Retrieval Inside Postgres | Tiger Data](https://www.tigerdata.com/blog/introducing-pg_textsearch-true-bm25-ranking-hybrid-retrieval-postgres)
- [GitHub - timescale/pg_textsearch](https://github.com/timescale/pg_textsearch)
- [GitHub - tensorchord/VectorChord-bm25](https://github.com/tensorchord/VectorChord-bm25)
- [Hybrid search with Postgres Native BM25 and VectorChord](https://blog.vectorchord.ai/hybrid-search-with-postgres-native-bm25-and-vectorchord)
- [Reciprocal Rank Fusion (RRF) for Hybrid Search](https://apxml.com/courses/advanced-vector-search-llms/chapter-3-hybrid-search-approaches/rrf-fusion-algorithms)

### Symbol Extraction & Code Navigation
- [Code Navigation - Tree-sitter](https://tree-sitter.github.io/tree-sitter/4-code-navigation.html)
- [Tree-sitter MCP Server | PulseMCP](https://www.pulsemcp.com/servers/wrale-tree-sitter)
- [@squirrelsoft/code-index - npm](https://www.npmjs.com/package/@squirrelsoft/code-index)
- [Semantic Code Indexing with AST and Tree-sitter for AI Agents | Medium](https://medium.com/@email2dineshkuppan/semantic-code-indexing-with-ast-and-tree-sitter-for-ai-agents-part-1-of-3-eb5237ba687a)

### Context Expansion & Semantic Search
- [GitHub - zilliztech/claude-context](https://github.com/zilliztech/claude-context)
- [Code Context (Semantic Code Search) MCP Server | PulseMCP](https://www.pulsemcp.com/servers/code-context)
- [CodeGrok MCP: Semantic Code Search | HackerNoon](https://hackernoon.com/codegrok-mcp-semantic-code-search-that-saves-ai-agents-10x-in-context-usage)

### CocoIndex
- [Building Intelligent Codebase Indexing with CocoIndex | Medium](https://medium.com/@cocoindex.io/building-intelligent-codebase-indexing-with-cocoindex-a-deep-dive-into-semantic-code-search-e93ae28519c5)
- [Real-time Codebase Indexing | CocoIndex](https://cocoindex.io/docs/examples/code_index)
- [GitHub - cocoindex-io/cocoindex](https://github.com/cocoindex-io/cocoindex)
