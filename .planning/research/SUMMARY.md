# Project Research Summary

**Project:** CocoSearch v1.7 Search Enhancement
**Domain:** Semantic code search with hybrid retrieval, context expansion, and symbol-aware indexing
**Researched:** 2026-02-03
**Confidence:** HIGH

## Executive Summary

CocoSearch v1.7 aims to enhance semantic code search with four integrated capabilities: hybrid search (vector + BM25), context expansion, symbol-aware indexing, and full language coverage (30+ languages). Research shows these are table stakes features for production code search tools in 2026. Missing them makes CocoSearch feel incomplete compared to Sourcegraph, Cursor, and GitHub Code Search.

The recommended approach is **incremental enhancement** using PostgreSQL-native features wherever possible. Use PostgreSQL's built-in `tsvector`/`tsquery` for keyword search rather than external BM25 extensions (avoids pre-release dependencies like pg_textsearch). Combine vector and keyword results using Reciprocal Rank Fusion (RRF) in the application layer (simple, proven, no score normalization issues). Context expansion is essentially free since CocoSearch already reads files on-demand for display — just extend existing utilities. Symbol extraction leverages Tree-sitter already used by CocoIndex for chunking, adding query-based symbol metadata extraction during indexing.

Key risks center on backward compatibility and performance. The reference-only storage architecture requires adding a `content_text` column for hybrid search (breaking change requiring re-indexing). Score normalization between BM25 and vector similarity is the most common hybrid search failure mode — mitigated by using RRF instead of linear score combination. File I/O for context expansion can thrash on slow disks if not batched by filename. Tree-sitter parser errors on malformed code can corrupt the symbol index if not validated. All risks are manageable with the prevention strategies documented in the pitfalls research.

## Key Findings

### Recommended Stack

PostgreSQL-native approach minimizes dependencies and maintains CocoSearch's local-first philosophy. The core decision is using PostgreSQL's built-in full-text search instead of external BM25 extensions.

**Core technologies:**
- **PostgreSQL `tsvector`/`tsquery` (built-in)**: Keyword/lexical search — Zero new dependencies, mature and stable, sufficient for code chunk search where BM25's advantage is marginal
- **PostgreSQL `pg_trgm` (built-in contrib)**: Trigram similarity fallback — Optional enhancement for fuzzy matching
- **RRF in Python application layer**: Score fusion algorithm — Simple formula, well-documented, avoids score normalization pitfalls
- **`tree-sitter-languages` (v1.10.2+)**: Pre-built Tree-sitter grammars for 50+ languages — Enables symbol extraction with zero-config language support
- **Python file I/O (stdlib)**: Context expansion — Zero dependencies, simple, fast enough (<1ms per file with seek)

**Storage impact:** Adding `content_text` and `content_tsv` columns increases storage by ~10-20% (13MB per 10K chunks). Symbol metadata columns (`symbol_type`, `symbol_name`, `symbol_signature`) add ~500KB per 10K chunks. Total increase from baseline: ~20-25%.

**Why NOT external BM25 extensions:**
- `pg_textsearch` (Timescale): Pre-release v0.5.0, GA Feb 2026, too new for production
- `pg_search` (ParadeDB): Requires Rust/Tantivy build, adds complexity
- Code chunks are short (1000 bytes avg), BM25's length normalization advantage is marginal

### Expected Features

Research shows hybrid search, context expansion, and symbol awareness are now table stakes for code search tools. Users expect grep-like context flags, identifier-aware search, and function/class filtering.

**Must have (table stakes):**
- **Hybrid search with RRF** — Pure vector search misses exact identifier matches; users expect both semantic understanding AND literal matching
- **Context expansion with configurable lines** — All code search tools (grep, ripgrep, Sourcegraph) show surrounding lines; `-A/-B/-C` flags are expected
- **Symbol metadata extraction** — Users think in functions and classes, not arbitrary chunks; "find the User class" should filter to class definitions
- **Symbol search filters** — `--symbol-type function` to narrow searches, complements existing `--language` filter
- **Full language coverage (30+ languages)** — Modern repos are 40% config/docs (YAML, JSON, Markdown), not just code

**Should have (competitive differentiators):**
- **Automatic hybrid mode** — Query analyzer detects identifier patterns ("AuthService") and enables hybrid automatically, no manual flag needed
- **Symbol ranking boost** — Boost function/class definitions over references in RRF scoring (definitions more useful 80% of the time)
- **Smart context boundaries** — Use Tree-sitter to expand to enclosing function/class rather than arbitrary line counts
- **Language statistics** — Show language breakdown in stats command (15k lines Python, 8k TypeScript, etc.)

**Defer to v1.8+ (validate demand first):**
- **Nested symbol hierarchy** — Fully qualified names (Class.method) requires AST traversal, complex
- **Explain mode** — `--explain` showing query analysis and scoring decisions, useful for power users
- **Phrase matching** — `"exact phrase"` keyword search, niche use case
- **Negative keywords** — `NOT:test` exclusion, nice-to-have but not essential
- **Symbol cross-references** — Count symbol usage ("used 47 times"), requires call graph analysis

### Architecture Approach

CocoSearch's existing reference-only storage architecture provides clean separation between indexing (store metadata) and display (read files on-demand). The enhancements integrate by extending the schema with new columns and adding parallel processing during indexing.

**Major components:**

1. **Hybrid Search Layer** — Adds `content_text` and `content_tsv` columns to chunks table, creates GIN index on tsvector, implements RRF fusion query combining vector similarity and keyword search results at query time
2. **Context Expansion Layer** — Already implemented via existing file reading utilities (`read_chunk_content`, `get_context_lines`), zero schema changes, batching file reads by filename prevents I/O thrashing
3. **Symbol-Aware Layer** — Adds symbol metadata columns (`symbol_type`, `symbol_name`, `symbol_signature`), extracts symbols during indexing using Tree-sitter queries (parallel to chunking), enables filtering searches by symbol type

**Integration pattern:** Same-table multi-index approach stores all data (embeddings, text, symbols) in one table with multiple indexes. This is the industry standard (ParadeDB, Timescale) because it simplifies RRF joins, ensures atomic updates, and has proven scalability to 1M+ chunks.

**Key architectural decision:** Store chunk text in database for hybrid search but keep file reading for context expansion. Hybrid search is a retrieval concern (which results to return) requiring stored text for BM25 indexing. Context expansion is a formatting concern (how to display results) that benefits from always-fresh file content and flexible line counts.

### Critical Pitfalls

Top pitfalls from research with prevention strategies:

1. **Score scale incompatibility between BM25 and vector search** — BM25 scores are unbounded (0-50+) while pgvector cosine similarity returns [0,2]. Naive linear combination makes BM25 always dominate. **Prevention:** Use RRF (reciprocal rank fusion) as default, not score combination. RRF formula `score = 1/(rank + k)` requires no normalization and is robust to score scale differences. Industry standard in Elasticsearch, OpenSearch, Azure AI Search.

2. **Tokenization preprocessing inconsistency** — BM25 uses lowercased/stemmed tokens while vector embeddings use original case/form. Query "getUserById" matches vector but not BM25 or vice versa. **Prevention:** Apply identical preprocessing to both paths. For code search, minimal preprocessing is better (preserve case, no stemming which breaks identifiers). Split on non-alphanumeric, handle special characters (`_`, `.`, `::`) consistently.

3. **Context expansion file I/O thrashing** — Showing context for 10 results requires reading 10 files from disk. On slow disks (HDD, network mount), latency jumps from 100ms to 5+ seconds. **Prevention:** Batch file reads when multiple chunks from same file (group results by filename before reading). Make context expansion opt-in with `--context N` flag, not default. Cache file contents during search session with LRU eviction.

4. **Tree-sitter parser errors corrupt symbol index** — Parser encounters malformed code (syntax error, incomplete file) and returns ERROR nodes instead of symbols. Symbol index contains garbage entries. **Prevention:** Check `tree.root_node.has_error` before extracting symbols. Log warning and skip symbol extraction for files with parse errors. Test with malformed code samples in test suite.

5. **Backward incompatible schema migration** — Adding new columns as NOT NULL fails on existing indexes with data, forcing reindexing. **Prevention:** Use "expand, migrate, contract" pattern. Add columns as nullable with defaults (`DEFAULT ''`). Detect schema version at runtime and gracefully degrade if columns missing (like v1.2 metadata). Provide explicit `--upgrade-schema` command for reindexing.

## Implications for Roadmap

Based on research, suggested phase structure balances dependencies, risk, and user value:

### Phase 1: Hybrid Search Foundation (Storage + Indexing)
**Rationale:** Must come first because hybrid search requires schema changes and affects indexing pipeline. All other features depend on having the right data in the database. This phase is backward compatible (new columns are nullable, old indexes still work).

**Delivers:**
- Schema additions: `content_text TEXT`, `content_tsv tsvector` columns
- Modified indexing pipeline stores chunk text during CocoIndex flow
- GIN index on `content_tsv` for keyword search performance
- PostgreSQL extension setup: `CREATE EXTENSION IF NOT EXISTS pg_trgm`

**Addresses features:** Lays groundwork for hybrid search (FEATURES.md table stakes)

**Avoids pitfalls:** Backward incompatible schema migration (nullable columns + graceful degradation)

**Estimated complexity:** MEDIUM (150-200 LOC, schema changes, pipeline modification)

### Phase 2: Hybrid Search Query (RRF Implementation)
**Rationale:** Once data is in place, implement the query logic. RRF fusion is simple (50 lines of Python) and well-documented. Separate from Phase 1 to allow incremental testing and rollback if needed.

**Delivers:**
- RRF hybrid search query combining vector and keyword results
- CLI flag: `--hybrid` to enable hybrid search (default: vector-only for backward compat)
- MCP parameter: `use_hybrid_search: bool`
- Query analyzer detecting identifier patterns (camelCase, snake_case) for automatic hybrid mode

**Uses stack:** PostgreSQL `tsvector`/`tsquery` (from Phase 1), RRF algorithm in Python

**Addresses features:** Hybrid search with RRF (FEATURES.md table stakes), Automatic hybrid mode (differentiator)

**Avoids pitfalls:** Score scale incompatibility (use RRF not linear combination), Tokenization inconsistency (shared preprocessing function)

**Estimated complexity:** MEDIUM (150-200 LOC, RRF query logic, CLI integration)

### Phase 3: Symbol-Aware Indexing (Extraction + Storage)
**Rationale:** Parallel to hybrid search implementation since they don't depend on each other. Symbol extraction can proceed independently while hybrid search is being tested. Start with Python only to validate approach before expanding to other languages.

**Delivers:**
- Schema additions: `symbol_type TEXT`, `symbol_name TEXT`, `symbol_signature TEXT` columns
- Tree-sitter query loader for symbol extraction patterns
- Symbol extraction pipeline integrated into indexing (parallel to chunking)
- Initial language support: Python (validate approach)

**Implements architecture:** Symbol-Aware Layer component, Tree-sitter query-based extraction

**Addresses features:** Symbol metadata extraction (table stakes), Function-level chunking granularity

**Avoids pitfalls:** Tree-sitter parser errors (check `has_error` before extracting), Schema complexity (limit to 3-4 columns not JSONB for v1.7)

**Estimated complexity:** MEDIUM (200 LOC, Tree-sitter integration, per-language query files)

### Phase 4: Symbol Search Filters + Language Expansion
**Rationale:** Once symbol extraction works for Python, expand to top 5 languages and add search filtering. This validates symbol extraction quality before committing to all 30+ languages.

**Delivers:**
- Symbol extraction for JavaScript, TypeScript, Go, Rust (top 5 languages total)
- CLI flags: `--symbol-type function`, `--symbol-name AuthService`
- MCP parameters: `symbol_type` and `symbol_name` filters
- Symbol ranking boost in RRF scoring (definitions weighted 1.5x over references)

**Addresses features:** Symbol search filters (table stakes), Symbol ranking boost (differentiator)

**Avoids pitfalls:** Large file timeouts (size threshold + timeout on parsing), Inconsistent language detection (skip generated/minified files)

**Estimated complexity:** LOW-MEDIUM (100 LOC, add filters to search query, expand query files)

### Phase 5: Context Expansion Enhancement
**Rationale:** Can proceed in parallel with Phase 4 since it only touches display/formatting layer. Existing implementation already works, this phase adds optimizations and smart boundaries.

**Delivers:**
- Batched file reading (group results by filename before I/O)
- Smart context boundaries using Tree-sitter (expand to enclosing function)
- Syntax-highlighted context in `--pretty` mode (extend existing formatter)
- Performance optimization: LRU cache for frequently accessed files

**Uses:** Python file I/O (stdlib), existing `get_context_lines` utility, Tree-sitter for boundary detection

**Addresses features:** Context expansion with configurable lines (table stakes), Smart context boundaries (differentiator)

**Avoids pitfalls:** File I/O thrashing (batching by filename), No syntax highlighting (use Pygments in pretty mode)

**Estimated complexity:** LOW (100 LOC, optimize existing code, add caching)

### Phase 6: Full Language Coverage + Documentation
**Rationale:** Final phase adds remaining languages (essentially configuration, no code changes) and documents all features. Language coverage is lowest complexity because CocoIndex already supports 30+ languages.

**Delivers:**
- Enable all CocoIndex built-in languages (YAML, JSON, Markdown, 20+ more)
- Update `LANGUAGE_EXTENSIONS` mapping
- Language statistics in `cocosearch stats` command
- Documentation: hybrid search guide, symbol search guide, supported languages list

**Addresses features:** Full language coverage (table stakes), Language statistics (differentiator)

**Avoids pitfalls:** (No new pitfalls in this phase, purely configuration + docs)

**Estimated complexity:** LOW (50 LOC, mostly configuration and documentation)

### Phase Ordering Rationale

- **Phase 1 before Phase 2:** Schema changes must happen before query implementation. Incremental rollout allows testing storage without exposing hybrid search to users yet.
- **Phase 3 parallel to Phases 1-2:** Symbol extraction is independent of hybrid search. Can proceed on separate development track.
- **Phase 4 after Phase 3:** Validate symbol extraction quality with Python before expanding to more languages. Prevents wasted effort if approach needs adjustment.
- **Phase 5 parallel to Phase 4:** Context expansion is display/formatting concern, independent of retrieval logic. Can optimize while symbol expansion is ongoing.
- **Phase 6 last:** Language expansion and documentation come after core features are complete and validated.

**Dependency chain:**
```
Phase 1 (storage) → Phase 2 (query) → User-facing hybrid search
Phase 3 (symbol extraction) → Phase 4 (symbol filters) → User-facing symbol search
Phase 5 (context optimization) → Improved UX
Phase 6 (languages + docs) → Launch-ready
```

### Research Flags

**Phases with standard patterns (skip research-phase):**
- **Phase 1:** PostgreSQL schema changes are well-documented, CocoIndex pipeline is familiar
- **Phase 2:** RRF algorithm has extensive documentation and examples across multiple sources
- **Phase 5:** File I/O and caching are standard Python patterns
- **Phase 6:** Configuration and documentation, no technical research needed

**Phases likely needing deeper research during planning:**
- **Phase 3 (symbol extraction):** Tree-sitter query syntax is language-specific and poorly documented. May need to research AST node types for Python, examine existing query examples, and experiment with query patterns before finalizing extraction logic.
- **Phase 4 (language expansion):** Each language (JavaScript, TypeScript, Go, Rust) has different AST node types for symbols. Minimal research per language (1-2 hours each) to write correct query files.

**Low research needs overall:** 4 out of 6 phases follow established patterns. Only symbol extraction requires domain-specific investigation, and even that is straightforward (documented Tree-sitter query syntax, community examples exist).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | PostgreSQL built-in features verified via official docs, Tree-sitter libraries verified via PyPI and GitHub (current versions), RRF algorithm verified via multiple sources with SQL examples |
| Features | HIGH | Table stakes features verified against Sourcegraph, GitHub Code Search, Cursor, and other modern tools (2026 feature sets). Competitive analysis based on official documentation and product research. |
| Architecture | HIGH | Same-table multi-index pattern is industry standard (ParadeDB, Timescale docs). Reference-only storage pattern proven in CocoSearch v1.0-v1.6. Hybrid search integration patterns well-documented across multiple vendors. |
| Pitfalls | HIGH | Score normalization, tokenization inconsistency, and parser error pitfalls confirmed across multiple sources (Weaviate, Elasticsearch, Tree-sitter GitHub issues). File I/O performance patterns are established best practices. |

**Overall confidence:** HIGH

### Gaps to Address

Areas where research was inconclusive or needs validation during implementation:

- **BM25 vs tsvector quality tradeoff:** Research suggests PostgreSQL's `ts_rank` is "good enough" for code search, but doesn't provide quantitative comparison. During Phase 2 implementation, benchmark hybrid search quality against known-good queries. If quality is insufficient, document upgrade path to pg_textsearch in v1.8.

- **RRF k parameter tuning:** Default k=60 is empirically optimal across multiple domains, but optimal value may vary by codebase characteristics (size, language distribution, query patterns). During Phase 2, log k=40, k=60, k=80 results for sample queries. Validate k=60 is best or adjust default.

- **Symbol extraction coverage:** Tree-sitter query syntax is straightforward, but symbol extraction quality depends on handling edge cases (nested functions, decorators, async functions, etc.). During Phase 3, test with real codebases containing complex structures. Iterate query patterns based on extraction failures.

- **Context expansion default lines:** Research shows tools vary (grep default 2, ripgrep default 0, Sourcegraph shows variable context). During Phase 5, survey MCP users for preference. Recommendation: default 0 (explicit is better than implicit) with documentation suggesting 3-5 lines for typical use.

- **Storage impact on large codebases:** Estimated 20-25% storage increase, but varies by codebase characteristics (average chunk size, comment density, language distribution). During Phase 1, monitor storage on test indexes of varying sizes. Document expected storage requirements in user guide.

## Sources

### Primary (HIGH confidence)
- PostgreSQL 17 official documentation: Full-text search (`tsvector`, `tsquery`, `ts_rank`)
- pgvector documentation: HNSW indexes, performance benchmarks, hybrid search patterns
- Tree-sitter official documentation: Parser error handling, query syntax, code navigation
- PyPI verified packages: `tree-sitter-languages` v1.10.2, `py-tree-sitter` v0.25.2
- Industry vendor documentation: ParadeDB hybrid search guide, Timescale pg_textsearch, VectorChord-BM25

### Secondary (MEDIUM confidence)
- Research papers: Reciprocal Rank Fusion algorithm (Cormack et al. 2009), BM25 in code search
- Blog posts from established vendors: Weaviate hybrid search explained (2026), Redis hybrid search (2026), OpenSearch semantic search tutorial (2026)
- Community resources: Medium articles on BM25 tokenization, GitHub issues on Tree-sitter error handling (2024-2026)
- CocoIndex documentation: Semantic code indexing, Tree-sitter integration, real-time indexing

### Tertiary (validation recommended)
- Performance estimates: File I/O timing (<1ms per file), Tree-sitter parsing overhead (1-2ms per file), HNSW memory formula — all extrapolated from vendor documentation, should be benchmarked on actual CocoSearch workload
- User preferences: Context line defaults, hybrid search auto-enable heuristics — inferred from tool comparisons, should be validated with user surveys

---
*Research completed: 2026-02-03*
*Ready for roadmap: yes*
