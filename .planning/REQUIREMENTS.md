# Requirements: CocoSearch

**Defined:** 2026-01-25
**Core Value:** Semantic code search that runs entirely locally — no data leaves your machine.

## v1.1 Requirements

Requirements for Docs & Tests milestone. Each maps to roadmap phases.

### Installation Documentation

- [ ] **INST-01**: User can follow guide to install Ollama via brew and pull nomic-embed-text model
- [ ] **INST-02**: User can follow guide to set up PostgreSQL with pgvector via Docker Compose
- [ ] **INST-03**: User can follow guide to set up Python environment with UV and install cocosearch

### MCP Setup Guides

- [ ] **MCP-01**: User can follow guide to configure CocoSearch as MCP server in Claude Code
- [ ] **MCP-02**: User can follow guide to configure CocoSearch in Claude Desktop (claude_desktop_config.json)
- [ ] **MCP-03**: User can follow guide to configure CocoSearch in OpenCode

### CLI Documentation

- [ ] **CLI-01**: User can reference all CLI commands with flags, options, and descriptions
- [ ] **CLI-02**: User can see usage examples for each CLI command

### README

- [ ] **README-01**: README has quick start showing CLI demo (index → search)
- [ ] **README-02**: README has quick start showing MCP setup path
- [ ] **README-03**: README links to detailed docs/ guides

### Test Infrastructure

- [ ] **INFRA-01**: pytest configured with proper test discovery and async support
- [ ] **INFRA-02**: Mocking infrastructure for PostgreSQL connections
- [ ] **INFRA-03**: Mocking infrastructure for Ollama API calls
- [ ] **INFRA-04**: pytest fixtures for common test scenarios

### Test Coverage - Indexer

- [ ] **TEST-IDX-01**: Tests for indexer/config.py (configuration loading/validation)
- [ ] **TEST-IDX-02**: Tests for indexer/flow.py (CocoIndex flow operations)
- [ ] **TEST-IDX-03**: Tests for indexer/file_filter.py (include/exclude patterns, gitignore)
- [ ] **TEST-IDX-04**: Tests for indexer/embedder.py (embedding generation)
- [ ] **TEST-IDX-05**: Tests for indexer/progress.py (progress tracking/display)

### Test Coverage - Search

- [ ] **TEST-SRC-01**: Tests for search/db.py (database operations)
- [ ] **TEST-SRC-02**: Tests for search/query.py (query execution, vector search)
- [ ] **TEST-SRC-03**: Tests for search/formatter.py (result formatting)
- [ ] **TEST-SRC-04**: Tests for search/utils.py (utility functions)

### Test Coverage - Management

- [ ] **TEST-MGT-01**: Tests for management/git.py (git root detection)
- [ ] **TEST-MGT-02**: Tests for management/clear.py (index clearing)
- [ ] **TEST-MGT-03**: Tests for management/discovery.py (index discovery)
- [ ] **TEST-MGT-04**: Tests for management/stats.py (statistics gathering)

### Test Coverage - CLI

- [ ] **TEST-CLI-01**: Tests for cli.py commands (index, search, clear, list, stats)
- [ ] **TEST-CLI-02**: Tests for CLI output formatting (JSON, pretty)
- [ ] **TEST-CLI-03**: Tests for CLI error handling

### Test Coverage - MCP

- [ ] **TEST-MCP-01**: Tests for mcp/server.py tool definitions
- [ ] **TEST-MCP-02**: Tests for MCP tool execution (index_codebase, search_code, etc.)
- [ ] **TEST-MCP-03**: Tests for MCP error handling and response formatting

## v2 Requirements

Deferred to future release.

### Extended Documentation

- **DOC-01**: Troubleshooting guide for common issues
- **DOC-02**: Architecture documentation for contributors
- **DOC-03**: API reference (generated from docstrings)

### Extended Testing

- **TEST-INT-01**: Integration tests with real PostgreSQL + Ollama
- **TEST-PERF-01**: Performance benchmarks for indexing and search

## Out of Scope

| Feature | Reason |
|---------|--------|
| Hosted documentation site | Markdown files sufficient for v1.1 |
| Test coverage metrics/badges | Focus on writing tests first |
| Automated doc generation | Manual docs provide better quality for v1.1 |
| REPL documentation | Commands + examples sufficient, REPL is discoverable |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INST-01 | Phase 7 | Pending |
| INST-02 | Phase 7 | Pending |
| INST-03 | Phase 7 | Pending |
| MCP-01 | Phase 7 | Pending |
| MCP-02 | Phase 7 | Pending |
| MCP-03 | Phase 7 | Pending |
| CLI-01 | Phase 7 | Pending |
| CLI-02 | Phase 7 | Pending |
| README-01 | Phase 7 | Pending |
| README-02 | Phase 7 | Pending |
| README-03 | Phase 7 | Pending |
| INFRA-01 | Phase 5 | Complete |
| INFRA-02 | Phase 5 | Complete |
| INFRA-03 | Phase 5 | Complete |
| INFRA-04 | Phase 5 | Complete |
| TEST-IDX-01 | Phase 6 | Pending |
| TEST-IDX-02 | Phase 6 | Pending |
| TEST-IDX-03 | Phase 6 | Pending |
| TEST-IDX-04 | Phase 6 | Pending |
| TEST-IDX-05 | Phase 6 | Pending |
| TEST-SRC-01 | Phase 6 | Pending |
| TEST-SRC-02 | Phase 6 | Pending |
| TEST-SRC-03 | Phase 6 | Pending |
| TEST-SRC-04 | Phase 6 | Pending |
| TEST-MGT-01 | Phase 6 | Pending |
| TEST-MGT-02 | Phase 6 | Pending |
| TEST-MGT-03 | Phase 6 | Pending |
| TEST-MGT-04 | Phase 6 | Pending |
| TEST-CLI-01 | Phase 6 | Pending |
| TEST-CLI-02 | Phase 6 | Pending |
| TEST-CLI-03 | Phase 6 | Pending |
| TEST-MCP-01 | Phase 6 | Pending |
| TEST-MCP-02 | Phase 6 | Pending |
| TEST-MCP-03 | Phase 6 | Pending |

**Coverage:**
- v1.1 requirements: 34 total
- Mapped to phases: 34
- Unmapped: 0

---
*Requirements defined: 2026-01-25*
*Last updated: 2026-01-25 after Phase 5 completion*
