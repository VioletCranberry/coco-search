# Roadmap: CocoSearch

## Milestones

- v1.0 MVP - Phases 1-4 (shipped 2026-01-25)
- v1.1 Docs & Tests - Phases 5-7 (shipped 2026-01-26)
- v1.2 DevOps Language Support - Phases 8-10, 4-soi (shipped 2026-01-27)
- v1.3 Docker Integration Tests - Phases 11-15 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-4) - SHIPPED 2026-01-25</summary>

### Phase 1: Local Infrastructure
**Goal**: PostgreSQL + Ollama setup enabling local vector storage
**Plans**: 3 plans

Plans:
- [x] 01-01: PostgreSQL + pgvector container setup
- [x] 01-02: Ollama integration
- [x] 01-03: Connection management

### Phase 2: Core Indexing
**Goal**: Index codebases into vector database
**Plans**: 3 plans

Plans:
- [x] 02-01: File discovery and chunking
- [x] 02-02: Embedding and storage
- [x] 02-03: Incremental indexing

### Phase 3: Search & Management
**Goal**: Query indexes and manage multiple codebases
**Plans**: 3 plans

Plans:
- [x] 03-01: Vector search implementation
- [x] 03-02: Index management (list, clear, info)
- [x] 03-03: Result formatting and language filtering

### Phase 4: Interfaces
**Goal**: Expose via CLI and MCP
**Plans**: 3 plans

Plans:
- [x] 04-01: CLI with JSON/pretty output
- [x] 04-02: MCP server tools
- [x] 04-03: REPL interface

</details>

<details>
<summary>v1.1 Docs & Tests (Phases 5-7) - SHIPPED 2026-01-26</summary>

### Phase 5: Test Infrastructure
**Goal**: Mocked testing system for isolated unit tests
**Plans**: 4 plans

Plans:
- [x] 05-01: Test framework setup
- [x] 05-02: Mock system (PostgreSQL, Ollama)
- [x] 05-03: Core module tests
- [x] 05-04: Interface tests (CLI, MCP)

### Phase 6: User Documentation
**Goal**: Installation and usage guides
**Plans**: 3 plans

Plans:
- [x] 06-01: README with Quick Start
- [x] 06-02: MCP configuration guides
- [x] 06-03: Architecture documentation

### Phase 7: Reference Documentation
**Goal**: Complete CLI reference
**Plans**: 4 plans

Plans:
- [x] 07-01: Command reference
- [x] 07-02: Flag documentation
- [x] 07-03: Output format examples
- [x] 07-04: REPL reference

</details>

<details>
<summary>v1.2 DevOps Language Support (Phases 8-10, 4-soi) - SHIPPED 2026-01-27</summary>

### Phase 8: DevOps Chunking
**Goal**: Language-aware chunking for HCL, Dockerfile, Bash
**Plans**: 1 plan

Plans:
- [x] 08-01: CocoIndex custom language specs

### Phase 9: DevOps Metadata
**Goal**: Rich metadata extraction and storage
**Plans**: 2 plans

Plans:
- [x] 09-01: Metadata extraction pipeline
- [x] 09-02: Database schema extension

### Phase 10: DevOps Search & Output
**Goal**: DevOps filtering and metadata display
**Plans**: 2 plans

Plans:
- [x] 10-01: Language alias resolution and search filtering
- [x] 10-02: Output integration (JSON, pretty, MCP)

### Phase 4-soi: Search Output Integration (INSERTED)
**Goal**: Complete metadata integration across all output surfaces
**Plans**: 1 plan

Plans:
- [x] 4-soi-01: MCP metadata annotations with syntax highlighting

</details>

### v1.3 Docker Integration Tests (In Progress)

**Milestone Goal:** Add Docker-based integration tests validating real PostgreSQL+pgvector and Ollama behavior beyond existing 327 unit tests with mocked dependencies.

#### Phase 11: Test Reorganization
**Goal**: Separate unit tests from integration tests with clear execution boundaries
**Depends on**: Nothing (foundation phase)
**Requirements**: ORG-01, ORG-02, ORG-03, ORG-04, ORG-05
**Success Criteria** (what must be TRUE):
  1. Existing 327 unit tests run from tests/unit/ directory unchanged
  2. Integration test structure exists in tests/integration/ with conftest.py
  3. pytest markers enable selective execution (unit vs integration)
  4. Default test run executes only unit tests (fast feedback)
  5. Integration tests run only when explicitly requested or in CI
**Plans**: 2 plans

Plans:
- [ ] 11-01-PLAN.md - Create test directory structure and pytest marker configuration
- [ ] 11-02-PLAN.md - Migrate all 327 unit tests to tests/unit/

#### Phase 12: Container Infrastructure & PostgreSQL
**Goal**: Docker-based PostgreSQL testing with session-scoped containers and function-scoped cleanup
**Depends on**: Phase 11
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, PG-01, PG-02, PG-03, PG-04, PG-05
**Success Criteria** (what must be TRUE):
  1. Integration tests connect to real PostgreSQL+pgvector container
  2. Containers start with health checks before tests execute
  3. pgvector extension initializes automatically in test database
  4. Database state cleans between tests without container recreation
  5. Vector similarity search returns correct results with real pgvector
**Plans**: TBD

Plans:
- [ ] 12-01: TBD

#### Phase 13: Ollama Integration
**Goal**: Real Ollama embedding generation with warmup handling for 30-second first-request timeout
**Depends on**: Phase 12
**Requirements**: OLLAMA-01, OLLAMA-02, OLLAMA-03, OLLAMA-04, OLLAMA-05
**Success Criteria** (what must be TRUE):
  1. Integration tests generate embeddings with real Ollama container
  2. Warmup fixture prevents 30-second timeout on first embedding request
  3. Embeddings match expected dimensions (768 for nomic-embed-text)
  4. Tests detect native Ollama availability and fallback to Docker
  5. Optional dockerized Ollama works alongside native installation
**Plans**: TBD

Plans:
- [ ] 13-01: TBD

#### Phase 14: End-to-End Flows
**Goal**: Full-flow integration tests validating complete index and search pipelines
**Depends on**: Phase 13
**Requirements**: E2E-01, E2E-02, E2E-03, E2E-04, E2E-05, E2E-06
**Success Criteria** (what must be TRUE):
  1. Full indexing flow works end-to-end (files -> chunks -> embeddings -> storage)
  2. Full search flow works end-to-end (query -> embedding -> vector search -> results)
  3. CLI index command successfully indexes test codebase with real services
  4. CLI search command returns correct results with file paths and line numbers
  5. DevOps files (Terraform, Dockerfile, Bash) index correctly with metadata
**Plans**: TBD

Plans:
- [ ] 14-01: TBD

#### Phase 15: CI/CD Integration
**Goal**: GitHub Actions workflow running integration tests with Docker services
**Depends on**: Phase 14
**Requirements**: CI-01, CI-02, CI-03, CI-04
**Success Criteria** (what must be TRUE):
  1. GitHub Actions workflow runs integration tests on every push
  2. CI uses Docker services for PostgreSQL and Ollama containers
  3. Environment-based hostname detection works (localhost vs container names)
  4. Integration tests skip locally via pytest marker when Docker unavailable
**Plans**: TBD

Plans:
- [ ] 15-01: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Local Infrastructure | v1.0 | 3/3 | Complete | 2026-01-25 |
| 2. Core Indexing | v1.0 | 3/3 | Complete | 2026-01-25 |
| 3. Search & Management | v1.0 | 3/3 | Complete | 2026-01-25 |
| 4. Interfaces | v1.0 | 3/3 | Complete | 2026-01-25 |
| 5. Test Infrastructure | v1.1 | 4/4 | Complete | 2026-01-26 |
| 6. User Documentation | v1.1 | 3/3 | Complete | 2026-01-26 |
| 7. Reference Documentation | v1.1 | 4/4 | Complete | 2026-01-26 |
| 8. DevOps Chunking | v1.2 | 1/1 | Complete | 2026-01-27 |
| 9. DevOps Metadata | v1.2 | 2/2 | Complete | 2026-01-27 |
| 10. DevOps Search & Output | v1.2 | 2/2 | Complete | 2026-01-27 |
| 4-soi. Search Output Integration | v1.2 | 1/1 | Complete | 2026-01-27 |
| 11. Test Reorganization | v1.3 | 0/2 | Planned | - |
| 12. Container Infrastructure & PostgreSQL | v1.3 | 0/TBD | Not started | - |
| 13. Ollama Integration | v1.3 | 0/TBD | Not started | - |
| 14. End-to-End Flows | v1.3 | 0/TBD | Not started | - |
| 15. CI/CD Integration | v1.3 | 0/TBD | Not started | - |
