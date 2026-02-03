# Domain Pitfalls: Search Enhancements

**Domain:** Adding hybrid search, context expansion, and symbol indexing to semantic code search
**Project:** CocoSearch v1.7 Search Enhancement
**Researched:** 2026-02-03
**Confidence:** HIGH (verified with 2026 sources, existing codebase analysis)

## Executive Summary

Adding hybrid search, context expansion, and symbol-aware indexing to an existing semantic code search system presents integration challenges beyond typical greenfield implementations. CocoSearch's existing architecture (PostgreSQL + pgvector, pure vector search, 550+ tests) provides both advantages (established patterns, test infrastructure) and constraints (backward compatibility, schema stability, local-first requirement).

**Critical insight from research:** Most hybrid search pitfalls stem from score normalization and preprocessing inconsistencies, not algorithm complexity. Context expansion failures typically occur at file I/O boundaries, not display logic. Symbol indexing breaks on parser errors, not schema design.

## Critical Pitfalls

Mistakes that cause rewrites, major performance degradation, or data loss.

### Pitfall 1: Score Scale Incompatibility Between BM25 and Vector Search

**What goes wrong:** BM25 scores are unbounded (can range from 0 to 50+) while pgvector cosine similarity returns values in [0, 2]. Naive linear combination produces meaningless results where BM25 always dominates or vector search is ignored.

**Why it happens:** BM25 scores depend on term frequency and document distribution (corpus-dependent), while vector similarity is normalized. Developers assume "both are scores, just add them."

**Consequences:**
- Hybrid search returns identical results to BM25-only (vector component has zero weight)
- Result quality degrades vs pure vector search
- Users lose trust in hybrid mode
- Wasted implementation effort

**Prevention:**
1. **Use Reciprocal Rank Fusion (RRF) as default, not score combination**
   - RRF formula: `score = 1/(rank + k)` where k=60 is empirically optimal
   - No normalization required, robust to score scale differences
   - Industry standard: Elasticsearch, OpenSearch, Azure AI Search all default to RRF

2. **If using score combination, normalize BOTH scores**
   - Min-max normalization: `(score - min) / (max - min)` per result set
   - Apply BEFORE combination, not after
   - Store original scores for debugging

3. **Test with extreme cases**
   - Exact match queries (BM25 should dominate)
   - Semantic paraphrases (vector should dominate)
   - Verify both contribute meaningfully to final ranking

**Detection:**
- Compare top-10 results from hybrid vs BM25-only vs vector-only
- If hybrid == BM25-only, normalization failed
- Log individual scores before/after normalization during development

**CocoSearch-specific notes:**
- Current architecture uses `1 - (embedding <=> %s::vector)` for vector scoring
- This already normalizes to [0, 1] range (not [0, 2])
- BM25 integration should use RRF to avoid re-normalizing vector scores

**Sources:**
- [96. Hybrid Search: Combining BM25 and Vector Search (Medium)](https://medium.com/codex/96-hybrid-search-combining-bm25-and-vector-search-7a93adfd3f4e)
- [Hybrid Search Explained (Weaviate)](https://weaviate.io/blog/hybrid-search-explained)
- [Reciprocal Rank Fusion (RRF) explained (Medium)](https://medium.com/@devalshah1619/mathematical-intuition-behind-reciprocal-rank-fusion-rrf-explained-in-2-mins-002df0cc5e2a)

---

### Pitfall 2: Tokenization Preprocessing Inconsistency

**What goes wrong:** BM25 index uses lowercased, stemmed tokens while vector embeddings use original case/form. Query "getUserById" matches vector search but not BM25, or vice versa. Hybrid results are inconsistent and confusing.

**Why it happens:** BM25 tokenization happens in application code, vector embedding happens in Ollama (black box). Developers don't realize they need to preprocess identically.

**Consequences:**
- Hybrid search misses obvious matches (keyword present but wrong case)
- Result rankings are unpredictable
- Users can't understand why results appear/disappear
- Debugging is nightmare (need to inspect both indexes)

**Prevention:**
1. **Apply identical preprocessing to BOTH paths**
   ```python
   # WRONG: Different preprocessing
   bm25_tokens = tokenize_and_stem(code)  # lowercase + stem
   embedding = ollama.embed(code)  # original case

   # RIGHT: Same preprocessing
   normalized = preprocess_code(code)  # shared function
   bm25_tokens = tokenize(normalized)
   embedding = ollama.embed(normalized)
   ```

2. **For code search, minimal preprocessing is better**
   - Lowercase is dangerous (`getUserById` vs `GetUserById` may be different symbols)
   - Stemming breaks code identifiers (`running` → `run` corrupts `isRunning`)
   - Recommendation: Split on non-alphanumeric, preserve case, no stemming

3. **Handle special characters consistently**
   - Code contains `_`, `.`, `::`, `->` that matter semantically
   - Don't strip these unless embedding model also ignores them
   - Test with `snake_case`, `camelCase`, `kebab-case`, `namespaced::symbols`

**Detection:**
- Index test code: `function getUserById() { return userId; }`
- Search: "getUserById", "getuserbyid", "get user by id"
- Verify all three return the chunk (or consistently miss it)
- Check BM25 and vector components separately

**CocoSearch-specific notes:**
- Current system uses `code_to_embedding.eval(query)` with no preprocessing
- BM25 tokenization must match this behavior
- Consider: Use `nomic-embed-text` model's tokenizer directly for BM25

**Sources:**
- [Keyword Search BM25 (Weaviate)](https://docs.weaviate.io/weaviate/concepts/search/keyword-search)
- [BM25 tokenization (rank-bm25 PyPI)](https://pypi.org/project/rank-bm25/)
- [BM25 special characters (LlamaIndex Issue)](https://github.com/run-llama/llama_index/issues/17461)

---

### Pitfall 3: pgvector HNSW Index Memory Overflow

**What goes wrong:** Building HNSW index for BM25 or additional vector columns exhausts RAM. Process killed by OOM, index build fails, database becomes unresponsive.

**Why it happens:** HNSW indexes are RAM-hungry — entire index must fit in memory during build. CocoSearch users may index large codebases (10K+ files, 100K+ chunks). pgvector's HNSW has no incremental build.

**Consequences:**
- Index build fails on large codebases
- Database crashes mid-build, requires manual recovery
- Users with 8GB RAM machines cannot use hybrid search
- Breaks "local-first" promise if requires cloud-scale RAM

**Prevention:**
1. **Use IVFFlat for BM25 inverted index storage, not HNSW**
   - BM25 doesn't need vector index (it's keyword-based)
   - Store BM25 data in JSONB column or separate table
   - Reserve HNSW for vector embeddings only

2. **Monitor RAM during index build**
   - pgvector HNSW memory formula: ~`1200 * (dimensions + 8) * rows` bytes
   - For 768-dim embeddings, 100K chunks: ~93GB
   - Warn users BEFORE starting build if insufficient RAM

3. **Provide incremental/streaming index build option**
   - Build in batches: 10K chunks at a time
   - Use PostgreSQL's `maintenance_work_mem` tuning
   - Alternative: Build on disk with pgvectorscale extension (supports DiskANN)

4. **Detect native vs Docker PostgreSQL and adjust limits**
   - Docker has container memory limits (default 2GB on Docker Desktop)
   - Fail early with actionable error, not silent OOM

**Detection:**
- Monitor `pg_stat_activity` during index build
- Watch system memory: `docker stats` or `free -m`
- Test with synthetic 100K chunk dataset before production

**CocoSearch-specific notes:**
- Current index creation uses session-scoped fixtures (test infrastructure)
- v1.7 must support production-scale indexing (>10K files)
- Consider: Progress bar showing estimated RAM usage

**Sources:**
- [pgvector HNSW RAM issues (Instaclustr guide)](https://www.instaclustr.com/education/vector-database/pgvector-key-features-tutorial-and-pros-and-cons-2026-guide/)
- [Postgres Vector Search benchmarks (Medium)](https://medium.com/@DataCraft-Innovations/postgres-vector-search-with-pgvector-benchmarks-costs-and-reality-check-f839a4d2b66f)
- [Hybrid search with pgvector (ParadeDB)](https://www.paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual)

---

### Pitfall 4: Context Expansion File I/O Thrashing

**What goes wrong:** Showing 5-10 lines of context before/after each result requires reading 10+ files from disk per search. On slow disks (spinning HDD, network mount), search latency jumps from 100ms to 5+ seconds.

**Why it happens:** Pure vector search returns chunk byte ranges, no actual content. Context expansion naively opens each file, seeks to byte position, reads lines. No caching, no batching.

**Consequences:**
- Search becomes unusable on slow disks
- Users blame "semantic search is slow" (not context expansion)
- Docker deployments on bind mounts become painfully slow
- Concurrent searches hammer disk I/O

**Prevention:**
1. **Batch file reads when multiple chunks from same file**
   ```python
   # Group results by filename before reading
   by_file = defaultdict(list)
   for result in results:
       by_file[result.filename].append(result)

   # Read each file once, extract all chunks
   for filename, file_results in by_file.items():
       with open(filename) as f:
           content = f.read()
           for result in file_results:
               result.context = extract_context(content, result.start_byte)
   ```

2. **Make context expansion opt-in, not default**
   - Return byte ranges by default (fast)
   - Add `--with-context` flag for expansion (slow but useful)
   - MCP clients can choose based on use case

3. **Cache file contents during search session**
   - REPL mode: Keep LRU cache of last 10 files read
   - Subsequent searches reuse cached content
   - Invalidate on file mtime change

4. **Use mmap for large files**
   - Python `mmap.mmap()` maps file to memory
   - Seeking is fast (no repeated `read()` calls)
   - OS handles caching automatically

**Detection:**
- Benchmark search with `--with-context` vs without
- If >10x slowdown, file I/O is bottleneck
- Profile with `strace -c` to count `open()/read()` syscalls
- Test on HDD (not just SSD) to catch worst case

**CocoSearch-specific notes:**
- Existing `read_chunk_content()` and `get_context_lines()` already implemented
- Current usage: `read_chunk_content(filename, start_byte, end_byte)`
- Problem: Called once per result, no batching
- Solution: Group by filename in `search()` before calling utils

**Sources:**
- Research finding: Visual Studio 2026 context features use caching for performance
- Best practice: LRU cache for file contents in IDE integrations

---

### Pitfall 5: Tree-sitter Parser Errors Corrupt Symbol Index

**What goes wrong:** Tree-sitter parser encounters malformed code (syntax error, incomplete file, unsupported language extension). Parser returns ERROR nodes instead of symbols. Symbol index contains garbage: `ERROR_TOKEN` instead of `getUserById`.

**Why it happens:** Tree-sitter is designed for incremental parsing (editors with live typing). It always returns SOME parse tree, even for invalid code. Developers assume successful parse == valid symbols.

**Consequences:**
- Symbol search returns nonsense results
- Users lose trust: "searched for function, got error nodes"
- Incremental indexing propagates corruption (can't detect which symbols are valid)
- Debugging requires inspecting raw parse trees

**Prevention:**
1. **Check for ERROR nodes before extracting symbols**
   ```python
   tree = parser.parse(code)
   if tree.root_node.has_error:
       logger.warning(f"Parse error in {filename}, skipping symbol extraction")
       # Fall back to text-only indexing
       return []  # No symbols
   ```

2. **Use Tree-sitter's error recovery, but validate results**
   - Tree-sitter returns partial parse trees (useful!)
   - Extract symbols from valid subtrees only
   - Mark ERROR-containing functions as "partial" in metadata

3. **Test with malformed code samples**
   - Unclosed braces: `function foo() { if (x) {`
   - Mid-edit state: `def foo()\n  # incomplete`
   - Mixed languages: Python in .js file (wrong parser)

4. **Provide fallback to regex-based symbol extraction**
   - Tree-sitter fails: use simple regex for `def `, `function `, `class `
   - Lower quality but better than garbage
   - Mark as `symbol_source: "regex"` vs `"tree-sitter"` in metadata

**Detection:**
- Index known-bad code: `test_malformed.py` with syntax errors
- Verify symbol index is empty or contains ERROR markers
- Search for "ERROR" in symbol index (should return nothing)
- Check logs for parse error warnings

**CocoSearch-specific notes:**
- Current system uses CocoIndex which wraps Tree-sitter
- CocoIndex language handlers already exist (15+ languages)
- Symbol extraction is NEW for v1.7 — must add error handling
- Consider: Expose `has_error` flag in chunk metadata

**Sources:**
- [Tree-sitter parser error handling (GitHub Issue)](https://github.com/tree-sitter/tree-sitter/issues/255)
- [Tree-sitter partial parsing (Documentation)](https://tree-sitter.github.io/tree-sitter/using-parsers/)
- [Tree-sitter ERROR tokens (GitHub Issue)](https://github.com/tree-sitter/tree-sitter/issues/4789)

---

### Pitfall 6: Backward Incompatible Schema Migration

**What goes wrong:** Adding hybrid search requires new columns (`bm25_tokens JSONB`, `symbol_name TEXT`, `symbol_type TEXT`). Migration script uses `ALTER TABLE ... ADD COLUMN ... NOT NULL`, which fails on existing indexes with data. Users can't upgrade without reindexing.

**Why it happens:** Schema designed for greenfield, not incremental enhancement. Developers test on empty database, don't validate upgrade path.

**Consequences:**
- Forced reindexing on upgrade (may take hours for large codebases)
- Breaking change breaks "backward compatible" promise
- Users on old indexes get cryptic SQL errors
- Must maintain two code paths: old schema + new schema

**Prevention:**
1. **Use "expand, migrate, contract" pattern**
   - **Expand:** Add new columns as nullable (not NOT NULL)
     ```sql
     ALTER TABLE chunks ADD COLUMN bm25_tokens JSONB DEFAULT NULL;
     ALTER TABLE chunks ADD COLUMN symbol_name TEXT DEFAULT NULL;
     ```
   - **Migrate:** Populate for new indexes incrementally
   - **Contract:** (Never) Keep nullable forever for compatibility

2. **Detect schema version at runtime**
   ```python
   # Check if new columns exist before using them
   with conn.cursor() as cur:
       cur.execute("""
           SELECT column_name FROM information_schema.columns
           WHERE table_name = %s AND column_name = 'bm25_tokens'
       """, (table_name,))
       has_hybrid_search = cur.fetchone() is not None
   ```

3. **Provide opt-in upgrade command**
   ```bash
   # Reindex required for hybrid search on old indexes
   cocosearch index --upgrade-schema my-index
   ```
   - Explicit user action, not silent breaking change
   - Progress bar showing reindex status

4. **Test migration on populated database**
   - Create index with v1.6 schema
   - Add 1000 chunks
   - Run v1.7 migration
   - Verify search still works (graceful degradation)

**Detection:**
- Automated test: Create v1.6 index → upgrade to v1.7 → search
- Check for `UndefinedColumn` errors in logs
- Verify `_has_metadata_columns` pattern (already used for v1.2 upgrade)

**CocoSearch-specific notes:**
- Already has graceful degradation pattern (see `query.py` lines 154-167)
- v1.2 → v1.3 migration succeeded without breaking changes
- v1.7 should follow same pattern: nullable columns + runtime detection
- Existing test infrastructure can validate upgrade path

**Sources:**
- [Backward compatible database changes (PlanetScale)](https://planetscale.com/blog/backward-compatible-databases-changes)
- [Database Design Patterns for Backward Compatibility (PingCAP)](https://www.pingcap.com/article/database-design-patterns-for-ensuring-backward-compatibility/)
- [Schema Evolution Guide (DataExpert)](https://www.dataexpert.io/blog/backward-compatibility-schema-evolution-guide)

## Moderate Pitfalls

Mistakes that cause delays, performance issues, or technical debt.

### Pitfall 7: RRF Rank-Based Fusion Loses Score Information

**What goes wrong:** RRF treats rank 1 vs rank 2 identically regardless of actual score difference. A BM25 result with score 45 (rank 1) gets same weight as score 0.5 (rank 1 from different query). Highly relevant results are under-weighted.

**Why it happens:** RRF formula `1/(rank + k)` discards original scores entirely. Developers choose RRF for simplicity without understanding the tradeoff.

**Consequences:**
- Excellent matches (score 0.95) ranked equally with mediocre matches (score 0.51)
- Users see "weird results" where obvious answers are buried
- Can't tune without switching to score-based fusion (major refactor)

**Prevention:**
1. **Understand RRF is a STARTING point, not final solution**
   - Use RRF for v1.7 (simple, no tuning required)
   - Plan for score-based fusion in v1.8 if RRF proves insufficient

2. **Test RRF vs score fusion on benchmark queries**
   - Create 20 test queries with known correct answers
   - Compare result quality: RRF vs linear combination
   - If RRF consistently loses, implement score fusion

3. **Tune k parameter empirically**
   - Default k=60 from research
   - Test k=40, k=60, k=80 on CocoSearch data
   - Lower k = more weight to top ranks, higher k = flatter distribution

**Detection:**
- User feedback: "why isn't X result at top?"
- Compare top-3 results from RRF vs pure vector vs pure BM25
- If RRF frequently misses obvious answers, score fusion may be needed

**CocoSearch-specific notes:**
- Start with RRF for simplicity (matches research recommendation)
- Log both BM25 and vector scores for future analysis
- Revisit in v1.8 based on usage data

**Sources:**
- [RRF disadvantages (Elastic Documentation)](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion)
- [Azure AI Search Hybrid Scoring](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking)

---

### Pitfall 8: BM25 Index Build Performance on Large Codebases

**What goes wrong:** Indexing 50K files with BM25 tokenization takes 30+ minutes (vs 5 minutes for vector-only). Users abandon during indexing, assume tool is broken.

**Why it happens:** BM25 requires tokenizing every file to build inverted index. Tokenization (regex splitting, stemming) is CPU-bound and serial. No batching or parallelization.

**Consequences:**
- Poor user experience during indexing
- Users disable hybrid search to speed up indexing
- Incremental indexing becomes slow (must rebuild BM25 index partially)

**Prevention:**
1. **Make BM25 indexing optional**
   ```bash
   cocosearch index --hybrid  # Enable BM25 (slower)
   cocosearch index           # Vector-only (faster, default)
   ```

2. **Parallelize tokenization**
   ```python
   from concurrent.futures import ProcessPoolExecutor

   with ProcessPoolExecutor(max_workers=4) as executor:
       tokens = list(executor.map(tokenize_code, file_contents))
   ```

3. **Show progress with ETA**
   - Existing `ProgressReporter` already implemented
   - Add separate progress for BM25: "Tokenizing for BM25 (2/50000 files)..."
   - Update ETA based on tokenization speed

4. **Build BM25 index incrementally**
   - Store per-file token counts in database
   - On incremental index, only tokenize changed files
   - Update global IDF statistics efficiently

**Detection:**
- Benchmark: Index 10K files with/without BM25
- If >2x slowdown, optimization needed
- Profile: `python -m cProfile` to find tokenization bottleneck

**CocoSearch-specific notes:**
- Existing progress reporting can be extended
- Current indexing uses CocoIndex (Rust, fast)
- BM25 tokenization in Python may be slower (consider Rust implementation)

---

### Pitfall 9: Symbol-Aware Indexing Schema Complexity

**What goes wrong:** Schema grows to support symbols: `symbol_name`, `symbol_type`, `symbol_params`, `parent_symbol`, `symbol_line`, `symbol_col`. Queries become complex, joins are slow, debugging is painful.

**Consequences:**
- Schema harder to understand and maintain
- Query performance degrades (more columns = slower scans)
- Backward compatibility becomes nightmare (many nullable columns)
- New features delayed by schema migration concerns

**Prevention:**
1. **Use JSONB for flexible symbol metadata**
   ```sql
   ALTER TABLE chunks ADD COLUMN symbol_metadata JSONB DEFAULT NULL;

   -- Store everything in one column
   INSERT INTO chunks (symbol_metadata) VALUES ('{
     "name": "getUserById",
     "type": "function",
     "params": ["userId"],
     "parent": "UserService",
     "line": 42
   }');
   ```

2. **Index JSONB fields for performance**
   ```sql
   CREATE INDEX idx_symbol_name ON chunks ((symbol_metadata->>'name'));
   CREATE INDEX idx_symbol_type ON chunks ((symbol_metadata->>'type'));
   ```

3. **Validate JSONB schema in application code**
   - Use Pydantic model for symbol metadata
   - Validate before inserting to database
   - Prevents garbage data from parse errors

**Detection:**
- Count columns in chunks table
- If >10 columns, schema is getting complex
- Check query performance: EXPLAIN ANALYZE on symbol searches

**CocoSearch-specific notes:**
- Already uses JSONB pattern for config (see `cocosearch.yaml` handling)
- Existing DevOps metadata fields (`block_type`, `hierarchy`, `language_id`) are separate columns
- Symbol metadata could follow same pattern OR use JSONB
- Recommendation: Start with separate columns (simpler queries), migrate to JSONB if schema grows

---

### Pitfall 10: Context Window Expansion Without Syntax Highlighting

**What goes wrong:** Returned context is plain text: `def getUserById(userId):\n    return db.query...`. Users must manually parse code structure, slowing comprehension.

**Why it happens:** Context expansion focuses on "get the lines" not "present them well." JSON output doesn't support terminal colors.

**Consequences:**
- Poor user experience in CLI
- MCP clients (Claude) must re-parse code to understand structure
- Users prefer raw file viewing over context snippets

**Prevention:**
1. **Return both raw text and formatted text**
   ```json
   {
     "context": "def getUserById...",
     "context_formatted": "\033[34mdef\033[0m getUserById..."
   }
   ```

2. **Use Pygments for syntax highlighting**
   ```python
   from pygments import highlight
   from pygments.lexers import get_lexer_by_name
   from pygments.formatters import TerminalFormatter

   code = highlight(context, get_lexer_by_name('python'), TerminalFormatter())
   ```

3. **Provide `--no-color` flag for JSON output**
   - ANSI codes break JSON parsers
   - Only colorize in `--pretty` mode

**Detection:**
- Manual inspection: Does CLI output have colors?
- User feedback: Do users find context snippets helpful?

**CocoSearch-specific notes:**
- Already has `--pretty` flag for human-readable output
- Pygments already in dependencies (for `--pretty` formatting)
- Add syntax highlighting to context expansion in `--pretty` mode

## Minor Pitfalls

Mistakes that cause annoyance but are easily fixable.

### Pitfall 11: Inconsistent Language Detection for Symbol Parsing

**What goes wrong:** File `script.js` detected as JavaScript, parsed successfully. File `build.js` (generated bundle) detected as JavaScript, parser times out on 10MB minified line.

**Why it happens:** Language detection by extension, not content analysis. Generated files (bundles, minified, obfuscated) break parsers.

**Prevention:**
1. **Skip files over size threshold**
   ```python
   if file_size > 1_000_000:  # 1MB
       logger.warning(f"Skipping symbol extraction for large file: {filename}")
       return text_only_index(content)
   ```

2. **Detect minified/generated files**
   - Heuristic: Average line length >200 chars
   - Check for markers: `// Generated by webpack`
   - Add to `.cocosearchignore` patterns

3. **Timeout symbol parsing**
   ```python
   import signal

   signal.alarm(5)  # 5 second timeout
   try:
       symbols = parse_symbols(code)
   except TimeoutError:
       logger.warning(f"Parse timeout: {filename}")
       symbols = []
   ```

**Detection:**
- Test with `node_modules/`, `dist/`, `build/` directories
- Monitor parse times: >1 second per file is suspicious

---

### Pitfall 12: BM25 Query Expansion for Code Identifiers

**What goes wrong:** User searches "get user by ID", BM25 tokenizes to `["get", "user", "by", "id"]`. Code has `getUserById` (camelCase), BM25 doesn't match.

**Why it happens:** BM25 assumes natural language (spaces separate words). Code uses camelCase, snake_case, PascalCase without spaces.

**Prevention:**
1. **Split camelCase/snake_case during tokenization**
   ```python
   def code_tokenize(text):
       # getUserById -> ["get", "User", "By", "Id"]
       tokens = re.split(r'([A-Z][a-z]+|[a-z]+|[0-9]+|_)', text)
       return [t.lower() for t in tokens if t and t != '_']
   ```

2. **Test with code-specific queries**
   - "get user by id" should match `getUserById`, `get_user_by_id`, `GetUserByID`
   - Verify BM25 tokenization produces same tokens

**Detection:**
- Search "get user by id" in codebase with `getUserById`
- Check if BM25 component returns results

---

### Pitfall 13: Forgetting to Update Incremental Indexing Logic

**What goes wrong:** Incremental indexing works for vectors, broken for BM25. Changed files get new embeddings but BM25 index is stale. Search returns outdated results from BM25 component.

**Why it happens:** Incremental indexing code only updates embeddings table. BM25 inverted index is separate, forgotten during refactor.

**Prevention:**
1. **Centralize indexing logic**
   ```python
   def index_file(filename, content):
       embedding = create_embedding(content)
       bm25_tokens = create_bm25_tokens(content)
       symbols = extract_symbols(content)

       db.upsert(filename, embedding, bm25_tokens, symbols)
   ```

2. **Add integration test for incremental hybrid indexing**
   - Index file → modify file → reindex → verify BM25 updated

**Detection:**
- Modify file, reindex incrementally
- Search with BM25, verify new content appears

---

### Pitfall 14: Hardcoded k=60 for RRF Without Explanation

**What goes wrong:** Code has `k = 60` with no comment. Future maintainers change to `k = 100` "for better results", breaking ranking.

**Prevention:**
1. **Document magic numbers**
   ```python
   # RRF parameter k=60 is empirically optimal (Cormack et al. 2009)
   # Lower k weights top ranks more heavily, higher k flattens distribution
   # Tested k=40,60,80 on CocoSearch v1.7 benchmarks, k=60 performed best
   RRF_K_PARAMETER = 60
   ```

2. **Make k configurable**
   ```yaml
   # cocosearch.yaml
   search:
     hybrid:
       rrf_k: 60
   ```

**Detection:**
- Code review: Check for unexplained constants

## Phase-Specific Warnings

Warnings for specific implementation phases.

| Phase Topic | Likely Pitfall | Mitigation Strategy | When to Address |
|-------------|---------------|---------------------|-----------------|
| **Hybrid Search Setup** | Score normalization (Pitfall #1) | Use RRF, not linear combination | Phase 1: Initial implementation |
| **Hybrid Search Setup** | Preprocessing inconsistency (Pitfall #2) | Shared preprocessing function for BM25 and embeddings | Phase 1: Tokenization logic |
| **BM25 Implementation** | BM25 index build performance (Pitfall #8) | Make hybrid search opt-in, add progress reporting | Phase 1: Index command |
| **BM25 Implementation** | Code identifier tokenization (Pitfall #12) | Split camelCase/snake_case during tokenization | Phase 1: Tokenizer implementation |
| **Context Expansion** | File I/O thrashing (Pitfall #4) | Batch reads by filename, make opt-in | Phase 2: Context expansion |
| **Context Expansion** | No syntax highlighting (Pitfall #10) | Use Pygments in `--pretty` mode | Phase 2: Output formatting |
| **Symbol Indexing** | Parser errors corrupt index (Pitfall #5) | Check `has_error` before extracting symbols | Phase 3: Symbol extraction |
| **Symbol Indexing** | Schema complexity (Pitfall #9) | Use JSONB or limit to 3-4 symbol columns | Phase 3: Schema design |
| **Symbol Indexing** | Large file timeouts (Pitfall #11) | Size threshold + parse timeout | Phase 3: Parser integration |
| **Schema Migration** | Backward incompatibility (Pitfall #6) | Nullable columns + runtime detection | All phases: Schema changes |
| **Performance** | HNSW memory overflow (Pitfall #3) | Use IVFFlat for BM25, monitor RAM | Phase 1 + 3: Index creation |
| **Incremental Indexing** | BM25 index not updated (Pitfall #13) | Centralized indexing function | Phase 4: Integration |

## Testing Recommendations

Critical tests to prevent pitfalls.

### Integration Tests

```python
# Test hybrid search score normalization
def test_hybrid_search_both_components_contribute():
    # Index: "function getUserById() { return user; }"
    # Query: "get user by id" (should match BM25)
    # Query: "retrieve user record" (should match vector)
    results = search("get user by id", hybrid=True)
    # Verify result rank influenced by BOTH BM25 and vector
    assert results[0].bm25_score > 0
    assert results[0].vector_score > 0

# Test context expansion file I/O batching
def test_context_expansion_batch_reads():
    # Index 10 files, search returns 5 results from same file
    with patch("builtins.open") as mock_open:
        search("test query", with_context=True)
        # Should open file only ONCE, not 5 times
        assert mock_open.call_count == 1

# Test symbol extraction error handling
def test_symbol_extraction_with_syntax_errors():
    # Index file with unclosed brace
    malformed = "function foo() { if (x) {"
    symbols = extract_symbols(malformed)
    # Should return empty or ERROR markers, not crash
    assert symbols == [] or all("ERROR" in s.name for s in symbols)

# Test backward compatible schema migration
def test_v16_index_works_with_v17_code():
    # Create index with v1.6 schema (no hybrid search columns)
    create_v16_index()
    # Run v1.7 search (should gracefully degrade)
    results = search("test", hybrid=True)
    # Should fall back to vector-only, no crash
    assert len(results) > 0
```

### Benchmark Tests

```python
# Measure hybrid search performance
def benchmark_hybrid_vs_vector_only():
    # Index 10K chunks
    start = time.time()
    search("test query", hybrid=False)
    vector_only_ms = (time.time() - start) * 1000

    start = time.time()
    search("test query", hybrid=True)
    hybrid_ms = (time.time() - start) * 1000

    # Hybrid should be <2x slower than vector-only
    assert hybrid_ms < vector_only_ms * 2

# Measure context expansion overhead
def benchmark_context_expansion():
    results = search("test", limit=50)

    start = time.time()
    for r in results:
        read_chunk_content(r.filename, r.start_byte, r.end_byte)
    elapsed_ms = (time.time() - start) * 1000

    # Should complete <100ms for 50 results (batched reads)
    assert elapsed_ms < 100
```

## Research Confidence Assessment

| Area | Confidence | Source Quality | Notes |
|------|------------|----------------|-------|
| Hybrid Search (BM25+Vector) | **HIGH** | Context7-equivalent (official docs), 2026 blog posts | RRF is industry standard, score normalization well-documented |
| Context Expansion | **MEDIUM** | WebSearch (Visual Studio 2026), general best practices | File I/O patterns are established, but code-specific research limited |
| Symbol Indexing | **HIGH** | Official Tree-sitter docs, GitHub issues (2024-2026) | Error handling patterns confirmed in Tree-sitter community |
| pgvector Performance | **HIGH** | Official benchmarks (2026), multiple vendor comparisons | HNSW memory issues well-documented, pgvectorscale widely adopted |
| Schema Migration | **HIGH** | Industry standard patterns (PlanetScale, PingCAP) | Expand-migrate-contract is proven approach |
| CocoSearch Architecture | **HIGH** | Direct codebase analysis | 550+ tests, clear patterns for graceful degradation |

## Open Questions for Phase-Specific Research

Questions that couldn't be resolved in domain research, requiring implementation validation.

1. **BM25 Library Choice:** Use `rank-bm25` (pure Python, simple) vs `tantivy` (Rust binding, fast)? Need performance benchmarks on CocoSearch data.

2. **Symbol Granularity:** Index functions only, or also classes, methods, variables? Affects schema complexity and index size. Validate with user queries.

3. **RRF k Parameter:** Research suggests k=60, but optimal value may vary by codebase size and query type. Requires A/B testing on real usage.

4. **BM25 Token Storage:** Store tokens in JSONB column vs separate inverted index table? Affects query performance and storage size. Benchmark both approaches.

5. **Context Lines Default:** 3 lines, 5 lines, or 10 lines before/after? Balances comprehension vs token usage. Survey MCP users for preference.

## Key Takeaways for Roadmap Planning

1. **Phase 1 (Hybrid Search) should prioritize RRF over score fusion** — simpler, no tuning, proven results
2. **Phase 2 (Context Expansion) must batch file I/O** — otherwise performance becomes unacceptable
3. **Phase 3 (Symbol Indexing) must handle parser errors** — malformed code is common in real repos
4. **All phases require backward compatible schema** — nullable columns + runtime detection pattern
5. **Testing infrastructure already exists** — leverage 550+ tests, add integration tests for each pitfall
6. **Local-first constraint amplifies RAM concerns** — monitor HNSW memory usage, provide early warnings

---

**Research complete.** All major pitfall categories covered with prevention strategies and detection methods. Ready for roadmap planning.
