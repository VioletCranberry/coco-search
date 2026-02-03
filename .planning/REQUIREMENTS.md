# Requirements: CocoSearch v1.7

**Defined:** 2026-02-03
**Core Value:** Semantic code search that runs entirely locally — no data leaves your machine.

## v1.7 Requirements

Requirements for Search Enhancement milestone. Each maps to roadmap phases.

### Hybrid Search

- [x] **HYBR-01**: Search combines vector similarity and keyword matching via RRF fusion
- [x] **HYBR-02**: CLI flag `--hybrid` enables hybrid search mode
- [x] **HYBR-03**: MCP parameter `use_hybrid_search` enables hybrid search
- [x] **HYBR-04**: Query analyzer detects identifier patterns (camelCase, snake_case) for auto-hybrid
- [ ] **HYBR-05**: Schema adds `content_text` and `content_tsv` columns for keyword search
- [ ] **HYBR-06**: GIN index on `content_tsv` for keyword search performance
- [ ] **HYBR-07**: Existing indexes gracefully degrade (hybrid unavailable, vector-only works)

### Context Expansion

- [ ] **CTXT-01**: CLI flags `-A/-B/-C` show N lines before/after/around matches
- [ ] **CTXT-02**: MCP parameters `context_before`, `context_after` for context lines
- [ ] **CTXT-03**: File reads batched by filename to prevent I/O thrashing
- [ ] **CTXT-04**: Smart context boundaries expand to enclosing function/class via Tree-sitter
- [ ] **CTXT-05**: LRU cache for frequently accessed files during search session
- [ ] **CTXT-06**: Context included in both JSON and pretty output formats

### Symbol-Aware Search

- [ ] **SYMB-01**: Schema adds `symbol_type`, `symbol_name`, `symbol_signature` columns
- [ ] **SYMB-02**: Tree-sitter query-based symbol extraction during indexing
- [ ] **SYMB-03**: Symbol extraction for Python (validate approach)
- [ ] **SYMB-04**: Symbol extraction for JavaScript, TypeScript, Go, Rust
- [ ] **SYMB-05**: CLI flag `--symbol-type` filters by symbol type (function, class, method)
- [ ] **SYMB-06**: CLI flag `--symbol-name` filters by symbol name pattern
- [ ] **SYMB-07**: MCP parameters `symbol_type`, `symbol_name` for symbol filtering
- [ ] **SYMB-08**: Symbol ranking boost in RRF (definitions weighted 1.5x)
- [ ] **SYMB-09**: Unified symbol filters work with DevOps metadata (block_type, hierarchy)
- [ ] **SYMB-10**: Existing indexes gracefully degrade (symbol filters unavailable)

### Language Coverage

- [ ] **LANG-01**: Enable all 30+ CocoIndex built-in languages (YAML, JSON, Markdown, etc.)
- [ ] **LANG-02**: Update LANGUAGE_EXTENSIONS mapping with all supported extensions
- [ ] **LANG-03**: Language statistics in `cocosearch stats` command (lines per language)
- [ ] **LANG-04**: Documentation lists all supported languages with file extensions

## v1.8+ Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Query

- **ADVQ-01**: Nested symbol hierarchy (fully qualified names: Class.method)
- **ADVQ-02**: Explain mode (`--explain`) showing query analysis and scoring
- **ADVQ-03**: Phrase matching (`"exact phrase"` keyword search)
- **ADVQ-04**: Negative keywords (`NOT:test` exclusion)
- **ADVQ-05**: Symbol cross-references (count usage: "used 47 times")

### Additional Languages

- **ADDL-01**: Kubernetes YAML handler with resource kind extraction
- **ADDL-02**: Ansible handler with task/role metadata
- **ADDL-03**: Makefile handler with target extraction
- **ADDL-04**: CloudFormation handler with resource type extraction

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| External BM25 extensions (pg_textsearch) | Pre-release v0.5.0, too new for production |
| Full AST storage | Storage bloat, not needed for search |
| Real-time file watching | Manual index trigger only (existing constraint) |
| Web UI for search results | MCP and CLI interface only (existing constraint) |
| Cross-index unified search | Complexity, validate demand first |
| Query caching/history | Nice-to-have, defer to v1.8 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| HYBR-01 | Phase 28 | Complete |
| HYBR-02 | Phase 28 | Complete |
| HYBR-03 | Phase 28 | Complete |
| HYBR-04 | Phase 28 | Complete |
| HYBR-05 | Phase 27 | Complete |
| HYBR-06 | Phase 27 | Complete |
| HYBR-07 | Phase 27 | Complete |
| CTXT-01 | Phase 31 | Pending |
| CTXT-02 | Phase 31 | Pending |
| CTXT-03 | Phase 31 | Pending |
| CTXT-04 | Phase 31 | Pending |
| CTXT-05 | Phase 31 | Pending |
| CTXT-06 | Phase 31 | Pending |
| SYMB-01 | Phase 29 | Pending |
| SYMB-02 | Phase 29 | Pending |
| SYMB-03 | Phase 29 | Pending |
| SYMB-04 | Phase 30 | Pending |
| SYMB-05 | Phase 30 | Pending |
| SYMB-06 | Phase 30 | Pending |
| SYMB-07 | Phase 30 | Pending |
| SYMB-08 | Phase 30 | Pending |
| SYMB-09 | Phase 30 | Pending |
| SYMB-10 | Phase 29 | Pending |
| LANG-01 | Phase 32 | Pending |
| LANG-02 | Phase 32 | Pending |
| LANG-03 | Phase 32 | Pending |
| LANG-04 | Phase 32 | Pending |

**Coverage:**
- v1.7 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0

---
*Requirements defined: 2026-02-03*
*Last updated: 2026-02-03 after Phase 28 completion*
