# Roadmap: CocoSearch

## Milestones

- v1.0 MVP - Phases 1-4 (shipped 2026-01-25)
- v1.1 Docs & Tests - Phases 5-7 (shipped 2026-01-26)
- v1.2 DevOps Language Support - Phases 8-10, 4-soi (shipped 2026-01-27)
- v1.3 Docker Integration Tests - Phases 11-14 (shipped 2026-01-30)
- v1.4 Dogfooding Infrastructure - Phases 15-18 (in progress)

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

<details>
<summary>v1.3 Docker Integration Tests (Phases 11-14) - SHIPPED 2026-01-30</summary>

### Phase 11: Test Reorganization
**Goal**: Separate unit tests from integration tests with clear execution boundaries
**Plans**: 3 plans

Plans:
- [x] 11-01: Test directory structure and pytest marker configuration
- [x] 11-02: Migrate all 327 unit tests to tests/unit/
- [x] 11-03: Fix default execution to unit-only

### Phase 12: Container Infrastructure & PostgreSQL
**Goal**: Docker-based PostgreSQL testing with session-scoped containers
**Plans**: 3 plans

Plans:
- [x] 12-01: Docker container infrastructure
- [x] 12-02: Database initialization and cleanup
- [x] 12-03: PostgreSQL integration tests

### Phase 13: Ollama Integration
**Goal**: Real Ollama embedding generation with warmup handling
**Plans**: 2 plans

Plans:
- [x] 13-01: Ollama fixture infrastructure
- [x] 13-02: Ollama integration tests

### Phase 14: End-to-End Flows
**Goal**: Full-flow integration tests for index and search
**Plans**: 3 plans

Plans:
- [x] 14-01: E2E test infrastructure and indexing flow
- [x] 14-02: E2E search and CLI validation
- [x] 14-03: DevOps file validation

</details>

<details open>
<summary>v1.4 Dogfooding Infrastructure (Phases 15-18) - IN PROGRESS</summary>

### Phase 15: Configuration System
**Goal**: Users can configure CocoSearch behavior via YAML config file
**Dependencies**: None (builds on existing CLI)
**Requirements**: CONF-01, CONF-02, CONF-03, CONF-04, CONF-05, CONF-06, CONF-07, CONF-08

**Success Criteria:**
1. User can create `cocosearch.yaml` in project root and CLI automatically loads it
2. User can specify index name, file patterns, languages, embedding model, and limits in config
3. User receives clear error message when config has invalid YAML syntax or unsupported fields
4. CLI works without config file (uses defaults) and with partial config (merges with defaults)

**Plans:** 3 plans

Plans:
- [x] 15-01: Config schema and loader
- [x] 15-02: Validation and error formatting
- [x] 15-03: CLI init command and integration

### Phase 16: CLI Config Integration
**Goal**: CLI flags take precedence over config file settings with env var support
**Dependencies**: Phase 15
**Requirements**: CONF-09

**Success Criteria:**
1. User can override any config setting via CLI flag (e.g., `--name` overrides `indexName` in YAML)
2. CLI help shows which flags have config file equivalents
3. Precedence is clear: CLI flag > env var > config file > default

**Plans:** 2 plans

Plans:
- [ ] 16-01-PLAN.md - ConfigResolver with TDD (precedence logic)
- [ ] 16-02-PLAN.md - Config subcommands and CLI integration

### Phase 17: Developer Setup Script
**Goal**: One-command setup for new developers working on CocoSearch
**Dependencies**: Phase 16
**Requirements**: DEVS-01, DEVS-02, DEVS-03, DEVS-04, DEVS-05, DEVS-06, DEVS-07, DEVS-08

**Success Criteria:**
1. New developer runs `./dev-setup.sh` and gets fully working CocoSearch environment
2. Script detects native Ollama and uses it; falls back to Docker if not found
3. Script shows colored progress output so user knows what is happening
4. Running script multiple times is safe (idempotent)
5. Script completes with indexed codebase ready for search

Plans:
- [ ] 17-01: TBD
- [ ] 17-02: TBD

### Phase 18: Dogfooding Validation
**Goal**: CocoSearch repository uses CocoSearch with documented example
**Dependencies**: Phase 17
**Requirements**: DOGF-01, DOGF-02

**Success Criteria:**
1. Repository contains `cocosearch.yaml` configured for indexing CocoSearch source code
2. README includes dogfooding section showing how to search CocoSearch with CocoSearch
3. New contributor can follow README to set up and search the codebase

Plans:
- [ ] 18-01: TBD

</details>

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
| 11. Test Reorganization | v1.3 | 3/3 | Complete | 2026-01-30 |
| 12. Container Infrastructure & PostgreSQL | v1.3 | 3/3 | Complete | 2026-01-30 |
| 13. Ollama Integration | v1.3 | 2/2 | Complete | 2026-01-30 |
| 14. End-to-End Flows | v1.3 | 3/3 | Complete | 2026-01-30 |
| 15. Configuration System | v1.4 | 3/3 | Complete | 2026-01-31 |
| 16. CLI Config Integration | v1.4 | 0/2 | Planned | - |
| 17. Developer Setup Script | v1.4 | 0/? | Pending | - |
| 18. Dogfooding Validation | v1.4 | 0/? | Pending | - |
