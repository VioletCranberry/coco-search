# Requirements: CocoSearch

**Defined:** 2026-01-24
**Core Value:** Semantic code search that runs entirely locally — no data leaves your machine.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Indexing

- [x] **INDEX-01**: Index codebase directory under named index
- [x] **INDEX-02**: Language-aware chunking via Tree-sitter (15+ languages)
- [x] **INDEX-03**: Respect .gitignore patterns
- [x] **INDEX-04**: File filtering with include/exclude patterns
- [x] **INDEX-05**: Incremental indexing (only re-index changed files)

### Search

- [x] **SRCH-01**: Semantic search with natural language queries
- [x] **SRCH-02**: Return file paths in results
- [x] **SRCH-03**: Return line numbers in results
- [x] **SRCH-04**: Return relevance scores (cosine similarity)
- [x] **SRCH-05**: Limit results to avoid overwhelming context
- [x] **SRCH-06**: Filter results by programming language

### Index Management

- [ ] **MGMT-01**: Support multiple named indexes simultaneously
- [ ] **MGMT-02**: Clear specific named index
- [ ] **MGMT-03**: List all existing indexes
- [ ] **MGMT-04**: Show index statistics (file count, chunk count, size)

### Infrastructure

- [x] **INFRA-01**: PostgreSQL via Docker for vector storage (pgvector)
- [x] **INFRA-02**: Ollama for local embeddings (nomic-embed-text)
- [x] **INFRA-03**: All processing local — no external API calls

### MCP Interface

- [ ] **MCP-01**: `index_codebase` tool
- [ ] **MCP-02**: `search_code` tool
- [ ] **MCP-03**: `clear_index` tool
- [ ] **MCP-04**: `list_indexes` tool
- [x] **MCP-05**: Progress feedback during indexing

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Search Enhancements

- **SRCH-07**: Chunk context expansion (show surrounding code)
- **SRCH-08**: Hybrid keyword + semantic search
- **SRCH-09**: Search result deduplication

### Advanced Features

- **ADV-01**: Symbol-aware indexing (functions, classes, methods)
- **ADV-02**: Configurable embedding model selection
- **ADV-03**: Cross-index search (search multiple indexes at once)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Answer synthesis inside MCP | Claude (caller) handles synthesis from returned chunks |
| Cloud storage / external APIs | Local-first is core value proposition |
| Real-time file watching | Manual index trigger for v1; complexity not justified |
| Web UI | MCP interface only per project constraints |
| Regex/keyword-only search | Focus on semantic search; hybrid deferred to v2 |
| Git history indexing | Scope creep; index current state only |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INDEX-01 | Phase 2 | Complete |
| INDEX-02 | Phase 2 | Complete |
| INDEX-03 | Phase 2 | Complete |
| INDEX-04 | Phase 2 | Complete |
| INDEX-05 | Phase 2 | Complete |
| SRCH-01 | Phase 3 | Complete |
| SRCH-02 | Phase 3 | Complete |
| SRCH-03 | Phase 3 | Complete |
| SRCH-04 | Phase 3 | Complete |
| SRCH-05 | Phase 3 | Complete |
| SRCH-06 | Phase 3 | Complete |
| MGMT-01 | Phase 4 | Pending |
| MGMT-02 | Phase 4 | Pending |
| MGMT-03 | Phase 4 | Pending |
| MGMT-04 | Phase 4 | Pending |
| INFRA-01 | Phase 1 | Complete |
| INFRA-02 | Phase 1 | Complete |
| INFRA-03 | Phase 1 | Complete |
| MCP-01 | Phase 4 | Pending |
| MCP-02 | Phase 4 | Pending |
| MCP-03 | Phase 4 | Pending |
| MCP-04 | Phase 4 | Pending |
| MCP-05 | Phase 2 | Complete |

**Coverage:**
- v1 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0

---
*Requirements defined: 2026-01-24*
*Last updated: 2026-01-25 — Phase 3 requirements complete*
