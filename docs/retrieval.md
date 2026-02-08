# Retrieval Logic

CocoSearch uses a hybrid retrieval approach combining vector similarity search with keyword matching to deliver highly relevant code search results. This document covers both the indexing pipeline (how code enters the database) and the search pipeline (how queries retrieve results), including actual formulas, parameters, and implementation details.

## Core Concepts

Before diving into the pipelines, here's a brief primer on the key technologies:

**Embeddings:** Dense numerical representations of text that capture semantic meaning. CocoSearch uses Ollama's nomic-embed-text model to convert code chunks into 768-dimensional vectors. Similar code produces similar vectors, enabling semantic search that understands meaning rather than just matching keywords.

**Vector Search:** Finding the most similar vectors using cosine similarity. Higher cosine similarity (range 0-1) indicates more relevant results. PostgreSQL's pgvector extension handles this natively with efficient indexing.

**Full-Text Search:** PostgreSQL's built-in text search using tsvector/tsquery for exact token matching after preprocessing. Uses the 'simple' configuration (no stemming) since code identifiers like `getUserById` shouldn't be stemmed into unrelated words.

**Reciprocal Rank Fusion (RRF):** Algorithm for merging two ranked lists into one. Uses rank positions (not scores) making it distribution-agnostic — important because cosine similarity and ts_rank have completely different distributions. Formula: `score = sum(1/(k + rank))` where k=60 (standard RRF constant).

## Indexing Pipeline

The indexing pipeline transforms raw code files into searchable chunks with embeddings and metadata. Here's the complete end-to-end flow:

### 1. File Discovery and Filtering

**What It Does:** Identifies which files to index from the codebase directory.

**How It Works:**
- CocoIndex LocalFile source reads from the codebase root directory
- Applies exclusion patterns in order of precedence:
  1. Built-in defaults (node_modules, .git, __pycache__, etc.)
  2. .gitignore patterns (if respect_gitignore=True)
  3. User-defined patterns from .cocosearch.yaml config
- Applies inclusion patterns (default: all supported file types — 31 languages worth of extensions)
- Files matching exclusions are skipped entirely before processing

**Implementation:** `src/cocosearch/indexer/file_filter.py` — `build_exclude_patterns()`

### 2. Language Detection

**What It Does:** Determines the programming language for each file to enable language-aware processing.

**How It Works:**
- Checks filename patterns first for extensionless files (e.g., `Dockerfile`, `Containerfile`)
- Falls back to extension mapping for standard files (`.py` → python, `.js` → javascript, `.rs` → rust)
- Supports 31 languages total:
  - 28 standard languages: Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, C#, Ruby, PHP, Swift, Kotlin, Scala, R, Solidity, Fortran, Pascal, SQL, HTML, CSS, YAML, JSON, TOML, XML, Markdown, MDX, DTD
  - 3 DevOps languages: HCL/Terraform, Dockerfile, Bash/Shell
- Language identifier used to route chunks to appropriate Tree-sitter parser

**Implementation:** `src/cocosearch/indexer/embedder.py` — `extract_language()`

### 3. Code Chunking

**What It Does:** Splits large files into smaller, semantically meaningful chunks for embedding.

**How It Works:**
- Uses CocoIndex's `SplitRecursively` with Tree-sitter parsing for language-aware boundaries
- Custom language definitions for DevOps files (HCL, Dockerfile, Bash) registered via handler system
- **Parameters:**
  - `chunk_size=1000` bytes (configurable in .cocosearch.yaml)
  - `chunk_overlap=300` bytes (configurable in .cocosearch.yaml)
- Tree-sitter ensures chunks break at semantic boundaries (function definitions, class boundaries, block boundaries) rather than arbitrary byte positions
- Overlap preserves context across chunk boundaries to avoid information loss

**Implementation:** `src/cocosearch/indexer/flow.py` — `create_code_index_flow()`, lines 76-83

### 4. Embedding Generation

**What It Does:** Converts each code chunk into a numerical vector representation for semantic search.

**How It Works:**
- Sends chunk text to Ollama API with model `nomic-embed-text`
- Receives 768-dimensional float vector (embedding)
- Uses CocoIndex's shared transform — embedding function evaluated once and reused across all chunks in the flow
- Same embedding function used during search queries to ensure consistency
- Ollama server address configured via `COCOSEARCH_OLLAMA_URL` environment variable (defaults to http://localhost:11434)

**Implementation:** `src/cocosearch/indexer/embedder.py` — `code_to_embedding`

### 5. Metadata Extraction

**What It Does:** Extracts structured metadata from code chunks for filtering and context.

**How It Works:**

**DevOps Metadata** (all files):
- `block_type`: Type of code block (e.g., "resource", "FROM", "function")
- `hierarchy`: Nested path representation (e.g., "resource.aws_s3_bucket.data")
- `language_id`: Language identifier (e.g., "hcl", "dockerfile", "bash", "python")

**Symbol Metadata** (supported languages only):
- `symbol_type`: Function, class, method, interface, or None
- `symbol_name`: Identifier name (e.g., "UserService.get_user")
- `symbol_signature`: Full signature (e.g., "def get_user(user_id: int) -> User")
- Symbol extraction uses Tree-sitter queries defined in `.scm` files
- Supported for 10 languages: Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, Ruby, PHP
- Signature truncation: 200 characters maximum to prevent oversized database entries

**Implementation:**
- DevOps metadata: `src/cocosearch/handlers/` (language-specific handlers)
- Symbol metadata: `src/cocosearch/indexer/symbols.py` — `extract_symbol_metadata()`

### 6. Text Preprocessing for Keyword Search

**What It Does:** Prepares chunk text for PostgreSQL full-text search by splitting code identifiers into searchable tokens.

**How It Works:**
- Raw chunk text stored in `content_text` column (used for hybrid search and context expansion)
- Preprocessed text generated for `content_tsv_input` column
- Preprocessing splits camelCase, PascalCase, and snake_case identifiers:
  - `getUserById` → `"get user by id getuserbyid"` (both split tokens AND original preserved)
  - `user_repository` → `"user repository user_repository"`
  - `HttpClient` → `"http client httpclient"`
- PostgreSQL generates `content_tsv` tsvector column using `to_tsvector('simple', content_tsv_input)`
- 'simple' configuration means no stemming (preserves exact code tokens)
- GIN index created on `content_tsv` column for fast keyword search

**Implementation:** `src/cocosearch/indexer/tsvector.py` — `text_to_tsvector_sql()`

### 7. Storage

**What It Does:** Persists chunks, embeddings, and metadata to PostgreSQL for querying.

**How It Works:**
- CocoIndex exports to PostgreSQL table following naming convention: `codeindex_{name}__{name}_chunks`
- Primary key: `(filename, location)` where location is a byte range (start:end)
- Indexes created:
  - **Vector index** on embedding column using pgvector extension with cosine similarity metric
  - **GIN index** on content_tsv column for full-text search
- Schema migration (`ensure_symbol_columns`) adds symbol columns if not present (for indexes created before v1.7)
- **Cache invalidation:** Before reindexing starts, all cached queries for this index are invalidated to prevent stale results

**Implementation:**
- Export configuration: `src/cocosearch/indexer/flow.py` — `create_code_index_flow()`, lines 123-133
- Schema migration: `src/cocosearch/indexer/schema_migration.py`
- Cache invalidation: `src/cocosearch/indexer/flow.py` — `run_index()`, lines 165-172

### 8. Parse Tracking

**What It Does:** Records tree-sitter parse health for each unique file in the index, providing observability into how well source files were parsed.

**How It Works:**
- After CocoIndex completes the indexing flow, CocoSearch runs a post-flow parse tracking pass
- For each unique file in the index (queried from the chunks table via DISTINCT filenames), tree-sitter attempts to parse the file content read from disk
- Each file receives a parse status:
  - `ok` — Clean parse with no errors
  - `partial` — Parse completed but with error nodes in the tree
  - `error` — Parse failed completely
  - `unsupported` — No tree-sitter grammar available for the file's language
- Results are stored in a per-index `parse_results` table (`cocosearch_parse_results_{index_name}`) with columns: file_path, language, parse_status, error_count, error_message, created_at
- This tracking is non-fatal — parse failures do not block indexing
- The parse results table is dropped when an index is cleared via `clear_index`

**Implementation:** `src/cocosearch/management/parse_tracking.py`

## Search Pipeline

The search pipeline retrieves relevant code chunks for a query through vector similarity, keyword matching, and intelligent fusion. Here's the complete end-to-end flow:

### 1. Query Cache Lookup

**What It Does:** Checks if this query (or a semantically similar one) has been run recently to avoid redundant work.

**How It Works:**

**Two-level cache architecture:**

**Level 1 — Exact Match:**
- Cache key: SHA256 hash of all search parameters (query, index_name, limit, min_score, language_filter, use_hybrid, symbol_type, symbol_name)
- Identical parameters → instant cache hit
- No embedding generation needed on exact hit

**Level 2 — Semantic Match:**
- Query embedding compared against cached query embeddings using cosine similarity
- Threshold: **>= 0.95** cosine similarity
- Purpose: Cache hits for paraphrased queries ("find auth logic" vs "authentication handler")
- Falls back to Level 2 only if Level 1 misses

**Cache behavior:**
- TTL: **24 hours** (86400 seconds)
- Eviction: Time-based expiry, entries removed on next access after TTL
- Invalidation: All entries for an index removed on reindex via `invalidate_index_cache()`
- Storage: In-memory dict (session-scoped singleton)

**Why cache BEFORE embedding:** Exact cache hits avoid the Ollama API call entirely, saving latency.

**Implementation:** `src/cocosearch/search/cache.py` — `QueryCache` class

### 2. Query Analysis

**What It Does:** Analyzes the query to determine if hybrid search would improve results.

**How It Works:**

**Identifier pattern detection:**
- Checks for camelCase: `getUserById` (lowercase followed by uppercase)
- Checks for PascalCase: `UserRepository` (uppercase followed by lowercase, then uppercase)
- Checks for snake_case: `get_user_by_id` (alphanumeric parts separated by underscores)

**Hybrid mode auto-detection:**
- `use_hybrid=None` (default): Auto-detect based on identifier patterns
  - If identifier patterns found AND `content_tsv` column exists → hybrid search
  - Otherwise → vector-only search
- `use_hybrid=True`: Force hybrid search (falls back to vector-only if tsvector column missing)
- `use_hybrid=False`: Force vector-only search

**Rationale:** Plain English queries ("find database connection") benefit from semantic search alone. Queries with identifiers ("find getUserById") benefit from keyword matching in addition to semantic search.

**Implementation:** `src/cocosearch/search/query_analyzer.py` — `has_identifier_pattern()`

### 3. Language and Symbol Filter Validation

**What It Does:** Validates and normalizes filter parameters before building SQL queries.

**How It Works:**

**Language filter:**
- Resolves aliases: `terraform` → `hcl`, `shell` → `bash`, `sh` → `bash`
- Validates against known languages (31 total)
- Converts to filename LIKE patterns (e.g., `python` → `%.py`)
- Applied as SQL WHERE clause BEFORE fusion (not post-filtering)

**Symbol filter:**
- Validates `symbol_type` values: function, class, method, interface
- Supports glob patterns in `symbol_name`: `User*` catches `User`, `UserProfile`, `UserService`
- Requires v1.7+ index with symbol columns (gracefully skips if unavailable)
- Applied as SQL WHERE clause BEFORE fusion

**Why filter before fusion:** Ensures RRF scores are computed only on eligible results, preventing ineligible results from affecting rank calculations.

**Implementation:**
- Language validation: `src/cocosearch/search/query.py` — `validate_language_filter()`
- Symbol filter SQL: `src/cocosearch/search/filters.py` — `build_symbol_where_clause()`

### 4. Vector Similarity Search

**What It Does:** Finds code chunks semantically similar to the query using vector embeddings.

**How It Works:**
- Query text → Ollama embedding (same function as indexing) → 768-dimensional vector
- SQL query using pgvector's cosine distance operator:
  ```sql
  SELECT filename, location,
         1 - (embedding <=> %s::vector) AS score,
         block_type, hierarchy, language_id,
         symbol_type, symbol_name, symbol_signature
  FROM {table_name}
  WHERE {filters}
  ORDER BY embedding <=> %s::vector
  LIMIT %s
  ```
- `<=>` operator computes cosine distance, subtracted from 1 to get similarity score (0-1 range)
- Limit: `min(limit * 2, 100)` to provide better fusion coverage (more results to merge)
- Returns metadata columns for filtering and display

**Implementation:** `src/cocosearch/search/hybrid.py` — `execute_vector_search()`

### 5. Keyword Search (Hybrid Mode Only)

**What It Does:** Finds code chunks with exact token matches using PostgreSQL full-text search.

**How It Works:**
- Query normalized using same identifier splitting logic as indexing:
  - `getUserById` → `"getUserById get User By Id"`
  - This ensures queries match both the original identifier AND its constituent tokens
- PostgreSQL `plainto_tsquery('simple', normalized_query)` generates tsquery
- SQL query:
  ```sql
  SELECT filename, location,
         ts_rank(content_tsv, plainto_tsquery('simple', %s)) AS rank
  FROM {table_name}
  WHERE content_tsv @@ plainto_tsquery('simple', %s) AND {filters}
  ORDER BY rank DESC
  LIMIT %s
  ```
- `@@` operator matches tsvector against tsquery using GIN index
- `ts_rank` scores relevance (higher = better match)
- Limit: `min(limit * 2, 100)` for fusion coverage
- **Graceful fallback:** If `content_tsv` column doesn't exist (pre-v1.7 index), returns empty list and falls back to vector-only results

**Implementation:** `src/cocosearch/search/hybrid.py` — `execute_keyword_search()`

### 6. RRF Fusion (Hybrid Mode Only)

**What It Does:** Merges vector and keyword search results into a single ranked list using Reciprocal Rank Fusion.

**How It Works:**

**RRF Formula:**
```
RRF_score = sum(1 / (k + rank)) for each result list where result appears

where k = 60 (standard RRF constant)
```

**Example calculation:**

Result appearing in both lists (rank 3 in vector, rank 1 in keyword):
```
RRF_score = 1/(60+3) + 1/(60+1) = 0.0159 + 0.0164 = 0.0323
```

Result appearing in vector list only (rank 1):
```
RRF_score = 1/(60+1) = 0.0164
```

The result in both lists scores nearly **2x higher**, naturally boosting double-matched results.

**Fusion process:**
1. Results identified by unique key: `filename:start_byte:end_byte`
2. For each unique result, compute RRF score contributions from each list where it appears
3. Sum contributions to get final RRF score
4. Assign match type: "semantic" (vector only), "keyword" (keyword only), or "both" (appeared in both)
5. Sort by RRF score descending
6. Tiebreaker: Keyword matches preferred over semantic-only matches

**Why RRF over score normalization:** Vector cosine similarity (0-1) and ts_rank scores have completely different distributions. RRF uses rank positions only, making it distribution-agnostic and robust.

**Implementation:** `src/cocosearch/search/hybrid.py` — `rrf_fusion()`, lines 329-439

### 7. Definition Boost

**What It Does:** Applies a score multiplier to code chunks that contain definitions (functions, classes, etc.) to prioritize them over usage sites.

**How It Works:**
- Applied AFTER RRF fusion to preserve rank-based algorithm semantics
- Heuristic: Checks if chunk content starts with definition keywords:
  - Python: `def`, `class`, `async def`
  - JavaScript/TypeScript: `function`, `const`, `let`, `var`, `interface`, `type`
  - Go: `func`, `type`
  - Rust: `fn`, `struct`, `trait`, `enum`, `impl`
- **Boost multiplier: 2.0x** (doubles the RRF score for definition chunks)
- Re-sorts results after boost application
- Requires v1.7+ index with symbol columns (skipped gracefully if unavailable)
- Reads chunk content from disk to check for definition keywords

**Rationale:** When searching for `UserService`, users typically want the class definition, not every file that imports it. Definition boost ensures definitions rank higher than usage sites.

**Implementation:** `src/cocosearch/search/hybrid.py` — `apply_definition_boost()`, lines 442-519

### 8. Score Filtering and Result Assembly

**What It Does:** Applies final score threshold, limits results, caches for future queries, and converts to uniform SearchResult format.

**How It Works:**
- `min_score` threshold applied (default 0.0 — no filtering)
- Results limited to requested count (after boost and filtering)
- HybridSearchResult objects converted to SearchResult objects (uniform interface regardless of search mode)
- Results cached in QueryCache for future identical/similar queries
- Vector search embedding included in cache entry for L2 semantic matching

**Implementation:** `src/cocosearch/search/query.py` — `search()`

### 9. Context Expansion (MCP/Output Layer)

**What It Does:** Expands the matched chunk to include surrounding code for better readability and understanding.

**How It Works:**

**Smart expansion (default):**
- Uses Tree-sitter to find enclosing function or class boundaries
- Expands to include the entire definition containing the matched chunk
- Supported languages: Python, JavaScript, TypeScript, Go, Rust
- Falls back to byte-range-only if Tree-sitter parsing fails or language unsupported

**Explicit expansion (override):**
- `context_before` and `context_after` parameters specify exact line counts
- Used when caller wants precise control over context size

**Constraints:**
- **50-line hard limit** enforced on all results (prevents unbounded growth)
- Lines longer than 200 characters truncated with '...' suffix
- Instance-level LRU cache (128 files) for file I/O during search session
- Cache cleared after each search to avoid stale file content

**Rationale:** A 3-line matched chunk is often unreadable without surrounding context. Smart expansion shows the full function or class, making results immediately useful.

**Implementation:** `src/cocosearch/search/context_expander.py` — `ContextExpander` class

## Summary

CocoSearch's retrieval logic combines semantic understanding (vector search) with exact matching (keyword search) to deliver highly relevant code search results:

- **Indexing:** 8-stage pipeline transforms code into searchable chunks with embeddings, metadata, full-text indexes, and parse tracking
- **Search:** 9-stage pipeline retrieves results through caching, vector similarity, keyword matching, RRF fusion, definition boosting, and smart context expansion
- **Key parameters:** chunk_size=1000, chunk_overlap=300, RRF k=60, definition boost=2.0x, cache TTL=24h, semantic threshold=0.95

For implementation details, see the referenced source files throughout this document.
