# Phase 3: Search - Research

**Researched:** 2026-01-25
**Domain:** Semantic vector search with CocoIndex + pgvector
**Confidence:** HIGH

## Summary

This phase implements natural language search over indexed code using the existing CocoIndex + pgvector infrastructure from Phase 2. The primary approach is **direct PostgreSQL querying** with the pgvector `<=>` operator for cosine similarity, using the same `code_to_embedding` transform flow for query embedding consistency.

Key insight: CocoIndex provides `transform_flow.eval()` to compute embeddings at query time using the same model/configuration as indexing. Combined with `cocoindex.utils.get_target_default_name()` to resolve table names, we can query the database directly with psycopg3.

**Primary recommendation:** Query PostgreSQL directly using psycopg3 with the `<=>` cosine distance operator. Reuse the existing `code_to_embedding` transform flow via `.eval()` for query embedding. Store the extension field in the database to enable language filtering.

## Standard Stack

The established libraries/tools for this domain:

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| psycopg[pool] | 3.3.2+ | PostgreSQL connection pooling | Already in project, psycopg3 native |
| pgvector | 0.4.2+ | Vector type registration for psycopg | Already in project, enables `%s::vector` params |
| cocoindex | 0.3.28+ | Query embedding via `transform_flow.eval()` | Already in project, ensures embedding consistency |
| rich | 13.0.0+ | Pretty output formatting | Already in project |

### No New Dependencies Required

All required libraries are already installed via `pyproject.toml`:
- `psycopg[binary,pool]>=3.3.2` - connection pooling
- `pgvector>=0.4.2` - vector type support
- `cocoindex[embeddings]>=0.3.28` - embedding computation
- `rich>=13.0.0` - formatted output

**Installation:** No additional packages needed.

## Architecture Patterns

### Recommended Project Structure
```
src/cocosearch/
├── indexer/           # (existing) indexing flow
│   ├── embedder.py    # Contains code_to_embedding transform
│   └── ...
├── search/            # (new) search module
│   ├── __init__.py    # Exports: search(), SearchResult
│   ├── query.py       # Core search logic
│   ├── db.py          # Database connection pool management
│   └── formatter.py   # Output formatting (JSON, pretty)
└── cli.py             # (extend) add default search command
```

### Pattern 1: Shared Embedding Transform
**What:** Use the same `code_to_embedding` transform for both indexing and querying
**When to use:** Always - embedding consistency is critical for semantic search
**Example:**
```python
# Source: https://cocoindex.io/docs/query
from cocosearch.indexer.embedder import code_to_embedding

def get_query_embedding(query: str) -> list[float]:
    """Embed query text using same model as indexing."""
    return code_to_embedding.eval(query)
```

### Pattern 2: Direct pgvector Query
**What:** Query PostgreSQL directly using `<=>` cosine distance operator
**When to use:** For semantic similarity search with LIMIT
**Example:**
```python
# Source: https://github.com/pgvector/pgvector
# Cosine distance (lower = more similar)
SELECT filename, location, 1 - (embedding <=> %s::vector) AS score
FROM {table_name}
ORDER BY embedding <=> %s::vector
LIMIT %s
```

### Pattern 3: Connection Pool Configuration
**What:** Configure connection pool with pgvector type registration
**When to use:** Application startup for efficient connection reuse
**Example:**
```python
# Source: https://github.com/pgvector/pgvector-python
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

def configure(conn):
    register_vector(conn)

pool = ConnectionPool(
    conninfo=os.getenv("COCOINDEX_DATABASE_URL"),
    configure=configure,
)
```

### Pattern 4: Language Filtering via SQL WHERE
**What:** Filter by file extension using WHERE clause before vector search
**When to use:** When user specifies `--lang` or `lang:` filter
**Example:**
```python
# Note: Filter on a column with an index is applied efficiently
query = """
    SELECT filename, location, 1 - (embedding <=> %s::vector) AS score
    FROM {table_name}
    WHERE filename LIKE %s
    ORDER BY embedding <=> %s::vector
    LIMIT %s
"""
# For lang=python: filename pattern = '%.py'
```

### Anti-Patterns to Avoid
- **Storing full chunk text in search results:** The index uses reference-only storage. Read chunk content from source files at display time.
- **Creating new embedding model for queries:** Always use the shared `code_to_embedding` transform to ensure consistency.
- **Not using connection pool:** Single connections per query are inefficient; use `psycopg_pool.ConnectionPool`.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Query embedding | Custom Ollama API call | `code_to_embedding.eval(query)` | Must match indexing exactly |
| Table name resolution | Hardcode table names | `cocoindex.utils.get_target_default_name()` | Flow naming conventions |
| Vector type handling | Manual list→vector conversion | `pgvector.psycopg.register_vector()` | Handles serialization |
| Connection management | Manual open/close | `psycopg_pool.ConnectionPool` | Efficient reuse |
| Cosine similarity | Custom math | pgvector `<=>` operator | Optimized C implementation |

**Key insight:** CocoIndex provides utilities for the hard parts (embedding, table naming). pgvector provides efficient SQL operators. Don't rebuild these.

## Common Pitfalls

### Pitfall 1: Cosine Distance vs Cosine Similarity
**What goes wrong:** `<=>` returns distance (0=identical, 2=opposite), but users expect similarity (1=identical, 0=unrelated)
**Why it happens:** pgvector uses distance for ORDER BY efficiency (ascending sort)
**How to avoid:** Convert: `1 - (embedding <=> query_vector) AS score`
**Warning signs:** Scores between 0-2 instead of 0-1, or best results having lowest scores

### Pitfall 2: Location Field is Byte Offset Tuple
**What goes wrong:** Treating `location` as line numbers
**Why it happens:** CocoIndex `SplitRecursively` stores `location` as `(start_byte, end_byte)` tuple, not line numbers
**How to avoid:** Convert byte offsets to line numbers by counting newlines in source file up to offset
**Warning signs:** Line numbers in thousands for small files

### Pitfall 3: Chunk Text Not Stored
**What goes wrong:** Trying to SELECT chunk text from database
**Why it happens:** Phase 2 used reference-only storage (no `text` column)
**How to avoid:** Read chunk content from source file using filename + location
**Warning signs:** SQL errors about missing column, or modifying schema decisions

### Pitfall 4: Index Not Found After Restart
**What goes wrong:** Query fails with "relation does not exist"
**Why it happens:** CocoIndex needs `cocoindex.init()` before table name resolution works
**How to avoid:** Call `cocoindex.init()` at application startup before any queries
**Warning signs:** Errors about missing tables that definitely exist

### Pitfall 5: Filter After Index Scan
**What goes wrong:** Filtering by language returns fewer results than requested
**Why it happens:** With approximate indexes (HNSW), filtering happens after the index scan
**How to avoid:** For strict result counts, over-fetch then filter in Python, or use partial indexes
**Warning signs:** Requesting 10 results but getting 3

## Code Examples

Verified patterns from official sources:

### Query Embedding (CocoIndex)
```python
# Source: https://cocoindex.io/docs/query
# Reuse the shared transform from indexing
from cocosearch.indexer.embedder import code_to_embedding

def embed_query(query: str) -> list[float]:
    """Embed query using same model as indexing."""
    return code_to_embedding.eval(query)
```

### Table Name Resolution (CocoIndex)
```python
# Source: https://cocoindex.io/docs/examples/code_index
import cocoindex
from cocosearch.indexer.flow import create_code_index_flow

def get_table_name(index_name: str) -> str:
    """Get PostgreSQL table name for an index."""
    # Must call cocoindex.init() first
    flow = create_code_index_flow(
        index_name=index_name,
        codebase_path="/tmp",  # placeholder
        include_patterns=["*.py"],
        exclude_patterns=[],
    )
    return cocoindex.utils.get_target_default_name(flow, f"{index_name}_chunks")
```

### Vector Search Query (pgvector)
```python
# Source: https://github.com/pgvector/pgvector
def search(pool, query_vector: list[float], table_name: str, limit: int = 10):
    """Search for similar code chunks."""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT filename, location,
                       1 - (embedding <=> %s::vector) AS score
                FROM {table_name}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (query_vector, query_vector, limit))
            return cur.fetchall()
```

### Connection Pool Setup (pgvector-python)
```python
# Source: https://github.com/pgvector/pgvector-python
import os
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

def create_pool() -> ConnectionPool:
    """Create connection pool with vector support."""
    def configure(conn):
        register_vector(conn)

    return ConnectionPool(
        conninfo=os.getenv("COCOINDEX_DATABASE_URL"),
        configure=configure,
    )
```

### Byte Offset to Line Number
```python
# Source: Python standard library pattern
def byte_offset_to_line(filepath: str, byte_offset: int) -> int:
    """Convert byte offset to 1-based line number."""
    with open(filepath, 'rb') as f:
        content = f.read(byte_offset)
        return content.count(b'\n') + 1
```

### Language Filter Mapping
```python
# Common extension-to-language mapping for filtering
LANGUAGE_EXTENSIONS = {
    "python": [".py", ".pyw", ".pyi"],
    "javascript": [".js", ".mjs", ".cjs"],
    "typescript": [".ts", ".tsx", ".mts", ".cts"],
    "rust": [".rs"],
    "go": [".go"],
    "java": [".java"],
    "ruby": [".rb"],
    "php": [".php"],
    "c": [".c", ".h"],
    "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".h"],
}

def get_extension_patterns(language: str) -> list[str]:
    """Get file extension patterns for a language."""
    exts = LANGUAGE_EXTENSIONS.get(language.lower(), [])
    return [f"%{ext}" for ext in exts]  # For SQL LIKE
```

## Database Schema

Based on the Phase 2 flow definition, the table structure is:

```sql
-- Table name: CodeIndex_{index_name}__{index_name}_chunks
-- (CocoIndex naming convention: flow_name__target_name)

CREATE TABLE codeindex_myproject__myproject_chunks (
    filename TEXT,           -- Full file path
    location INT4RANGE,      -- (start_byte, end_byte) as Postgres int4range
    embedding VECTOR(768),   -- 768-dim from nomic-embed-text
    PRIMARY KEY (filename, location)
);

-- Vector index (created by CocoIndex)
CREATE INDEX ON codeindex_myproject__myproject_chunks
    USING hnsw (embedding vector_cosine_ops);
```

**Note:** The `location` field is stored as PostgreSQL `int4range` type, representing byte offsets `[start, end)`. Access as `lower(location)` and `upper(location)` in SQL.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Keyword search (grep) | Vector semantic search | Mainstream 2023+ | Finds conceptually related code |
| Full text in DB | Reference-only + file read | Project decision | Smaller DB, fresh content |
| Separate query models | Shared transform_flow | CocoIndex design | Guaranteed consistency |

**Current best practices:**
- Use approximate nearest neighbor (HNSW) for large indexes
- Convert distance to similarity for user-facing scores
- Pool database connections
- Compute embeddings on-demand, don't cache

## Open Questions

Things that couldn't be fully resolved:

1. **Location field exact format**
   - What we know: It's a tuple of byte offsets, stored as int4range
   - What's unclear: Exact PostgreSQL representation (need to verify with running instance)
   - Recommendation: Query actual table to confirm format, adapt code accordingly

2. **Index auto-detection from cwd**
   - What we know: CONTEXT.md specifies auto-detect from cwd
   - What's unclear: How to map cwd to index name reliably
   - Recommendation: Look for `.cocosearch.yaml` or use directory name derivation (same as CLI)

3. **REPL mode implementation details**
   - What we know: `--interactive` flag for REPL mode
   - What's unclear: Exact UX (prompt style, history, readline)
   - Recommendation: Use Python `cmd` module or simple input loop with readline

## Sources

### Primary (HIGH confidence)
- [CocoIndex Query Support](https://cocoindex.io/docs/query) - transform_flow.eval(), query handlers
- [CocoIndex Code Index Example](https://cocoindex.io/docs/examples/code_index) - complete search implementation
- [pgvector GitHub](https://github.com/pgvector/pgvector) - <=> operator, index types
- [pgvector-python GitHub](https://github.com/pgvector/pgvector-python) - register_vector, psycopg3 integration
- Project source: `src/cocosearch/indexer/flow.py` - actual schema, field names
- Project source: `src/cocosearch/indexer/embedder.py` - code_to_embedding transform

### Secondary (MEDIUM confidence)
- [CocoIndex Medium Article](https://medium.com/@cocoindex.io/building-intelligent-codebase-indexing-with-cocoindex-a-deep-dive-into-semantic-code-search-e93ae28519c5) - patterns and examples
- [pgvector Cosine Similarity Guide](https://www.sarahglasmacher.com/how-to-use-cosine-similarity-in-pgvector/) - distance to similarity conversion

### Tertiary (LOW confidence)
- Python mailing list discussion - byte offset to line number conversion pattern

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in project
- Architecture: HIGH - follows CocoIndex official examples
- Pitfalls: HIGH - verified from official docs and project code
- Database schema: MEDIUM - inferred from flow.py, needs runtime verification

**Research date:** 2026-01-25
**Valid until:** 2026-02-25 (30 days - stable domain)
