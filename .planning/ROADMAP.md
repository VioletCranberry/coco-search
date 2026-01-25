# Roadmap: CocoSearch

## Milestones

- [x] **v1.0 MVP** - Phases 1-4 (shipped 2026-01-25)
- [ ] **v1.1 Docs & Tests** - Phases 5-7 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-4) - SHIPPED 2026-01-25</summary>

### Phase 1: Foundation
**Goal**: PostgreSQL + pgvector + Ollama infrastructure operational
**Plans**: 3 plans (complete)

### Phase 2: Indexing
**Goal**: CocoIndex-based embedding pipeline with progress UI
**Plans**: 3 plans (complete)

### Phase 3: Search
**Goal**: Vector similarity search with Rich formatting and REPL
**Plans**: 3 plans (complete)

### Phase 4: Management
**Goal**: CLI commands + MCP server for LLM integration
**Plans**: 3 plans (complete)

</details>

## v1.1 Docs & Tests (In Progress)

**Milestone Goal:** Make CocoSearch approachable for new users and maintainable with comprehensive test coverage.

### Phase 5: Test Infrastructure
**Goal**: pytest configured with mocking infrastructure for isolated testing
**Depends on**: Phase 4 (v1.0 complete)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04
**Success Criteria** (what must be TRUE):
  1. pytest discovers and runs tests in tests/ directory with async support
  2. PostgreSQL connections can be mocked without real database
  3. Ollama API calls can be mocked without running Ollama
  4. Common fixtures available for typical test scenarios (mock db, mock embeddings, sample data)
**Plans**: 3 plans

Plans:
- [x] 05-01-PLAN.md — pytest configuration and test structure setup
- [x] 05-02-PLAN.md — PostgreSQL mocking infrastructure
- [x] 05-03-PLAN.md — Ollama mocking and data fixtures

### Phase 6: Test Coverage
**Goal**: Full test suite covering all modules with mocked dependencies
**Depends on**: Phase 5 (test infrastructure ready)
**Requirements**: TEST-IDX-01, TEST-IDX-02, TEST-IDX-03, TEST-IDX-04, TEST-IDX-05, TEST-SRC-01, TEST-SRC-02, TEST-SRC-03, TEST-SRC-04, TEST-MGT-01, TEST-MGT-02, TEST-MGT-03, TEST-MGT-04, TEST-CLI-01, TEST-CLI-02, TEST-CLI-03, TEST-MCP-01, TEST-MCP-02, TEST-MCP-03
**Success Criteria** (what must be TRUE):
  1. Indexer module tests pass (config, flow, file_filter, embedder, progress)
  2. Search module tests pass (db, query, formatter, utils)
  3. Management module tests pass (git, clear, discovery, stats)
  4. CLI tests pass (commands, output formatting, error handling)
  5. MCP server tests pass (tool definitions, execution, error handling)
**Plans**: 5 plans

Plans:
- [x] 06-01-PLAN.md — Indexer module tests (config, file_filter, embedder, progress, flow)
- [x] 06-02-PLAN.md — Search module tests (db, query, utils, formatter)
- [x] 06-03-PLAN.md — Management module tests (git, discovery, clear, stats)
- [x] 06-04-PLAN.md — CLI tests (commands, output, error handling)
- [x] 06-05-PLAN.md — MCP server tests (tools, execution, errors)

### Phase 7: Documentation
**Goal**: User documentation enabling new users to install, configure, and use CocoSearch
**Depends on**: Nothing (can run parallel to Phase 5-6)
**Requirements**: INST-01, INST-02, INST-03, MCP-01, MCP-02, MCP-03, CLI-01, CLI-02, README-01, README-02, README-03
**Success Criteria** (what must be TRUE):
  1. User can follow installation guide to set up Ollama, PostgreSQL, and cocosearch
  2. User can follow MCP guides to configure CocoSearch in Claude Code, Claude Desktop, or OpenCode
  3. User can reference CLI documentation for all commands with examples
  4. README provides quick start path from install to first search (CLI and MCP)
**Plans**: 3 plans

Plans:
- [ ] 07-01-PLAN.md — README structure, introduction, Quick Start, and Installation guide
- [ ] 07-02-PLAN.md — MCP configuration guides (Claude Code, Claude Desktop, OpenCode)
- [ ] 07-03-PLAN.md — CLI reference and configuration documentation

## Progress

**Execution Order:** Phases 5-7 (Phase 7 can parallel 5-6)

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 3/3 | Complete | 2026-01-25 |
| 2. Indexing | v1.0 | 3/3 | Complete | 2026-01-25 |
| 3. Search | v1.0 | 3/3 | Complete | 2026-01-25 |
| 4. Management | v1.0 | 3/3 | Complete | 2026-01-25 |
| 5. Test Infrastructure | v1.1 | 3/3 | Complete | 2026-01-25 |
| 6. Test Coverage | v1.1 | 5/5 | Complete | 2026-01-25 |
| 7. Documentation | v1.1 | 0/3 | Planned | - |

---
*Roadmap created: 2026-01-25 for v1.1 Docs & Tests milestone*
