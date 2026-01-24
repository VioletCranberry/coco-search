# Pitfalls Research

**Domain:** Code Indexing and Semantic Search (CocoIndex + Ollama + pgvector + MCP)
**Researched:** 2026-01-24
**Confidence:** MEDIUM-HIGH (based on multiple verified sources, CocoIndex-specific details from official docs)

## Critical Pitfalls

### Pitfall 1: Embedding Dimension Mismatch After Model Change

**What goes wrong:**
Switching embedding models (e.g., from `nomic-embed-text` to `mxbai-embed-large`) silently creates vectors with different dimensions. The pgvector table rejects inserts with dimension errors like "Vector dimension 768 does not match the dimension of the index 1024." Entire index becomes unusable.

**Why it happens:**
- Different Ollama embedding models output different vector dimensions
- `nomic-embed-text`: 768 dimensions
- `mxbai-embed-large`: 1024 dimensions
- pgvector columns are created with fixed dimension at table creation
- No runtime warning when model changes; failure occurs at insert time

**How to avoid:**
- Store embedding model name and dimension in index metadata table
- On index creation, record: `{model: "nomic-embed-text", dimensions: 768}`
- Before any operation, validate current model matches stored metadata
- If mismatch detected, require explicit `clear_index` + re-index

**Warning signs:**
- Insert errors mentioning "dimension mismatch"
- Queries returning zero results after model update
- Ollama model pull/update without corresponding index update

**Phase to address:**
Phase 1 (Foundation) - Include model metadata tracking in schema design from day one.

---

### Pitfall 2: Code Chunking Destroys Semantic Meaning

**What goes wrong:**
Fixed-size chunking splits functions/classes mid-statement. Search returns fragments like `def process_data(self, items` without the closing `)` or function body. Retrieved chunks are useless for understanding code.

**Why it happens:**
- Naive chunking treats code as plain text
- Character/token limits ignore syntax boundaries
- Functions, classes, and imports have highly variable lengths
- The "right" chunk size for prose (512 tokens) fails for code

**How to avoid:**
- Use CocoIndex's `SplitRecursively` with Tree-sitter support for language-aware chunking
- Configure for your primary languages (Python, JS, etc.)
- Set `must_break_at_empty_line: true` for unknown file types
- Use overlapping chunks (10-15% overlap) to preserve boundary context
- Store parent context (file path, class name) as metadata with each chunk

**Warning signs:**
- Search returns syntactically incomplete code
- High retrieval volume but low user satisfaction
- Functions always split across multiple chunks

**Phase to address:**
Phase 1 (Foundation) - Chunking strategy is foundational; wrong choice requires full re-index.

---

### Pitfall 3: pgvector Query Performance Collapses at Scale

**What goes wrong:**
Search queries that took 50ms suddenly take 5+ seconds after adding more code. Memory usage spikes. Docker container becomes unresponsive. The index no longer fits in RAM.

**Why it happens:**
- pgvector stores index in memory by default
- Performance is excellent while index fits in RAM
- Beyond RAM capacity, queries hit disk constantly
- No gradual degradation; performance cliff is sudden
- HNSW indexes use ~3x memory of raw vectors

**How to avoid:**
- Calculate index size before deployment: `vectors * dimensions * 4 bytes * 3 (HNSW overhead)`
- For 100K chunks at 768 dimensions: ~900MB minimum
- Monitor PostgreSQL shared_buffers and work_mem
- Set appropriate Docker memory limits (at least 2x expected index size)
- Consider IVFFlat for memory-constrained environments (slower queries but smaller footprint)

**Warning signs:**
- Query latency increasing over time
- PostgreSQL logs showing disk I/O waits
- Docker memory warnings or OOM kills

**Phase to address:**
Phase 2 (Search) - Design index strategy with scale in mind; monitor from first deployment.

---

### Pitfall 4: MCP Tool Returns Overwhelm Context Window

**What goes wrong:**
`search_code` returns 50 chunks at 500 tokens each = 25,000 tokens. Claude's response quality degrades due to "lost in the middle" effect. User gets unhelpful answers because model couldn't process the volume.

**Why it happens:**
- MCP tools return all results by default
- No pagination in simple implementations
- Code chunks tend to be verbose
- Calling LLM has finite attention; more context often means worse results

**How to avoid:**
- Default to returning top 5-10 results maximum
- Include relevance scores with results
- Offer `limit` parameter in tool schema
- Consider two-stage retrieval: first return summaries, then full content on request
- Structure responses with clear delineation between chunks

**Warning signs:**
- Claude responses reference only first few results
- User complaints about missing relevant code
- Token usage spikes without quality improvement

**Phase to address:**
Phase 3 (MCP) - Design tool schemas with output volume limits from the start.

---

### Pitfall 5: Ollama Model Breaks After Upgrade

**What goes wrong:**
`ollama pull nomic-embed-text` updates the model. New version has different behavior or breaks embedding API. Error: "this model does not support embeddings" or silent dimension changes.

**Why it happens:**
- Ollama models are updated in-place without version pinning
- Backend changes (e.g., Ollama v0.12.6 changed Qwen model handling)
- No warning when model capabilities change
- Community models may disappear or change owners

**How to avoid:**
- Pin specific model versions where possible: `ollama pull nomic-embed-text:v1.5`
- Test embedding generation on startup; fail fast if broken
- Use well-established models (`nomic-embed-text`, `mxbai-embed-large`)
- Avoid community/unofficial model variants for production
- Log model version at index creation time

**Warning signs:**
- HTTP 500 errors from Ollama embedding endpoint
- "model does not support embeddings" errors
- Sudden search quality degradation after system update

**Phase to address:**
Phase 1 (Foundation) - Include model health check in initialization sequence.

---

### Pitfall 6: Pre-filter vs Post-filter Query Disaster

**What goes wrong:**
Query with filter (e.g., "search Python files only") scans all vectors first, then filters. With 1M vectors and a filter matching 1K, query takes 10 seconds instead of 50ms.

**Why it happens:**
- pgvector defaults to post-filtering: vector search runs, then filter applied
- Post-filter works when filter is permissive (matches most rows)
- Fails catastrophically when filter is selective (matches few rows)
- Query planner doesn't always choose optimal strategy

**How to avoid:**
- Use composite indexes: `CREATE INDEX ON embeddings USING hnsw (embedding vector_cosine_ops) WHERE language = 'python'`
- For named indexes: partition data by index_name column
- Use `EXPLAIN ANALYZE` to verify query plan
- Consider separate pgvector tables per named index for isolation

**Warning signs:**
- Filtered queries much slower than unfiltered
- Query plans showing full vector scan before filter
- Memory spikes during filtered searches

**Phase to address:**
Phase 2 (Search) - Schema design must anticipate common filter patterns.

---

### Pitfall 7: Docker Volume Data Loss

**What goes wrong:**
PostgreSQL container restarts. All indexed data is gone. User must re-index everything. Hours of indexing work lost.

**Why it happens:**
- Docker containers are ephemeral by default
- PostgreSQL data in `/var/lib/postgresql/data` disappears with container
- `docker-compose down` without `-v` still removes containers
- Volume mount syntax errors silently fail

**How to avoid:**
- Always use named volumes in docker-compose:
  ```yaml
  volumes:
    - postgres_data:/var/lib/postgresql/data
  volumes:
    postgres_data:  # Must declare at top level
  ```
- Never use anonymous volumes for databases
- Test data persistence: stop container, restart, verify data exists
- Include volume backup instructions in setup documentation

**Warning signs:**
- Empty database after container restart
- `docker volume ls` shows no named volumes
- Index operations succeed but data disappears

**Phase to address:**
Phase 1 (Foundation) - Volume configuration is part of initial Docker setup.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip embedding model validation | Faster startup | Silent failures, corrupted indexes | Never |
| Single pgvector table for all indexes | Simpler schema | Query performance degrades, no isolation | MVP only, plan migration |
| No chunk overlap | Faster indexing, less storage | Boundary context lost, poor retrieval | Never for code |
| Hardcoded chunk sizes | Less configuration | Different codebases need different sizes | MVP only |
| No pagination in MCP tools | Simpler implementation | Context window overflow, poor UX | Never |
| `docker run` instead of compose | Quick start | No reproducibility, volume issues | Development only |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| CocoIndex + PostgreSQL | Not setting `COCOINDEX_DATABASE_URL` env var | Export URL before running; CocoIndex fails silently otherwise |
| Ollama embeddings | Using chat model for embeddings | Only use embedding models (`nomic-embed-text`, `mxbai-embed-large`); chat models return errors |
| pgvector extension | Forgetting `CREATE EXTENSION vector` | Include in init script or docker-entrypoint-initdb.d |
| MCP + STDIO | Using `print()` for debugging | Logs contaminate protocol stream; use stderr or proper logging |
| Docker networking | Hardcoding `localhost` for PostgreSQL | Use service names (`postgres`) in Docker network; localhost doesn't work between containers |
| CocoIndex + Python | Using Python < 3.11 | CocoIndex requires Python 3.11+; fails with cryptic errors on older versions |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| No vector index | Queries slow from start | Create HNSW index after initial data load | > 1K vectors |
| HNSW on small data | Index build overhead exceeds benefit | Skip index for < 10K vectors; use exact search | N/A (premature optimization) |
| Indexing large files | Memory spikes, timeouts | Set max file size limit (e.g., 1MB), skip generated files | Files > 500KB |
| Re-indexing entire codebase | Hours of processing on any code change | Use CocoIndex incremental processing; only re-embed changed files | > 10K files |
| Embedding one file at a time | Network round-trip overhead | Batch embedding requests to Ollama | > 100 files |
| No connection pooling | PostgreSQL connection exhaustion | Use connection pool; CocoIndex handles this internally | Concurrent requests |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Exposing PostgreSQL port publicly | Database compromise, data exfiltration | Bind to 127.0.0.1 only; use Docker internal network |
| Hardcoded database credentials | Credentials in version control | Use environment variables; never commit .env files |
| MCP server without input validation | Command injection via tool parameters | Sanitize all inputs; use parameterized queries |
| Indexing sensitive files | API keys, passwords in vector store | Exclude `.env`, `secrets/`, credentials files from indexing |
| Running containers as root | Container escape risks | Use non-root user in Dockerfile |
| No rate limiting on MCP tools | Resource exhaustion attacks | Implement rate limiting on index/search operations |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No progress feedback during indexing | User thinks system is frozen | Stream progress: "Indexed 150/500 files..." |
| Cryptic error messages | User can't diagnose issues | Map common errors to actionable messages |
| Search returns full file paths only | User must open files to understand | Include code preview snippet with each result |
| No relevance scores | User can't gauge result quality | Show similarity score (0.0-1.0) per result |
| Case-sensitive search queries | Misses obvious matches | Normalize queries or support case-insensitive mode |
| No index status command | User unsure what's indexed | Provide `index_status` tool showing file count, last update |

---

## "Looks Done But Isn't" Checklist

- [ ] **Embedding API:** Often missing error handling for Ollama connection failures - verify graceful degradation when Ollama is down
- [ ] **Vector index:** Often missing from initial deployment - verify `\di` in psql shows HNSW index exists
- [ ] **Data persistence:** Often broken in dev setups - verify Docker restart preserves data
- [ ] **Named indexes:** Often share resources causing collisions - verify index A operations don't affect index B
- [ ] **Large files:** Often cause OOM or timeouts - verify indexing of 10MB generated file doesn't crash
- [ ] **Unicode handling:** Often breaks on non-ASCII code - verify search works with CJK, emoji, special chars
- [ ] **Concurrent access:** Often assumes single user - verify simultaneous index + search doesn't corrupt state
- [ ] **Empty codebase:** Often errors on edge case - verify indexing empty directory returns graceful message

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Dimension mismatch | MEDIUM | Drop table, recreate with correct dimensions, re-index all data |
| Corrupted index | MEDIUM | `REINDEX INDEX idx_name;` or drop/recreate index |
| Data loss (no backup) | HIGH | Re-index from source; no shortcut |
| Ollama model disappeared | LOW | `ollama pull <model>` to reinstall |
| Docker volume deleted | HIGH | Re-index from source; consider backup automation |
| Slow queries | LOW | Create/tune HNSW index; adjust `ef_search` parameter |
| MCP protocol contamination | LOW | Fix logging to stderr; restart MCP server |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Embedding dimension mismatch | Phase 1 (Foundation) | Schema includes model metadata; mismatch detected at startup |
| Code chunking destroys meaning | Phase 1 (Foundation) | Sample chunks are syntactically complete functions |
| pgvector performance collapse | Phase 2 (Search) | Load test with 50K+ vectors; p99 latency < 200ms |
| MCP tool overwhelms context | Phase 3 (MCP) | Default result limit in tool schema; tested with Claude |
| Ollama model breaks | Phase 1 (Foundation) | Health check on startup; known-good model version documented |
| Pre-filter vs post-filter | Phase 2 (Search) | `EXPLAIN ANALYZE` on filtered query shows index usage |
| Docker volume data loss | Phase 1 (Foundation) | Container restart test passes; data persists |

---

## Sources

- [Databricks: Mastering Chunking Strategies for RAG](https://community.databricks.com/t5/technical-blog/the-ultimate-guide-to-chunking-strategies-for-rag-applications/ba-p/113089)
- [Firecrawl: Best Chunking Strategies for RAG in 2025](https://www.firecrawl.dev/blog/best-chunking-strategies-rag-2025)
- [The Case Against pgvector](https://alex-jacobs.com/posts/the-case-against-pgvector/)
- [Debunking 6 common pgvector myths](https://www.thenile.dev/blog/pgvector_myth_debunking)
- [Medium: pgvector HNSW vs IVFFlat](https://medium.com/@bavalpreetsinghh/pgvector-hnsw-vs-ivfflat-a-comprehensive-study-21ce0aaab931)
- [AWS: pgvector indexing deep dive](https://aws.amazon.com/blogs/database/optimize-generative-ai-applications-with-pgvector-indexing-a-deep-dive-into-ivfflat-and-hnsw-techniques/)
- [Nearform: MCP Implementation Pitfalls](https://nearform.com/digital-community/implementing-model-context-protocol-mcp-tips-tricks-and-pitfalls/)
- [Red Hat: MCP Security Risks](https://www.redhat.com/en/blog/model-context-protocol-mcp-understanding-security-risks-and-controls)
- [CocoIndex GitHub](https://github.com/cocoindex-io/cocoindex)
- [CocoIndex: Building Intelligent Codebase Indexing](https://medium.com/@cocoindex.io/building-intelligent-codebase-indexing-with-cocoindex-a-deep-dive-into-semantic-code-search-e93ae28519c5)
- [Ollama Embeddings Issues #12757](https://github.com/ollama/ollama/issues/12757)
- [Modal: 6 Best Code Embedding Models](https://modal.com/blog/6-best-code-embedding-models-compared)
- [Tree-sitter Large Files Issue #1277](https://github.com/tree-sitter/tree-sitter/issues/1277)
- [GitHub: Embedding Dimension Mismatch Issues](https://github.com/RooCodeInc/Roo-Code/issues/5616)
- [freeCodeCamp: 5 Common RAG Failures](https://www.freecodecamp.org/news/how-to-solve-5-common-rag-failures-with-knowledge-graphs/)
- [Docker PostgreSQL Persistence](https://dev.to/iamrj846/how-to-persist-data-in-a-dockerized-postgres-database-using-volumes-15f0)

---
*Pitfalls research for: CocoSearch (Code Indexing + Semantic Search)*
*Researched: 2026-01-24*
