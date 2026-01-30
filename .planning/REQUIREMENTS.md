# Requirements: CocoSearch v1.3

**Defined:** 2026-01-30
**Core Value:** Semantic code search that runs entirely locally — no data leaves your machine.

## v1.3 Requirements

Requirements for Docker Integration Tests & Infrastructure milestone.

### Container Infrastructure

- [ ] **INFRA-01**: Integration tests use real Docker containers (not mocks)
- [ ] **INFRA-02**: Containers start with health checks before tests execute
- [ ] **INFRA-03**: Containers automatically cleaned up after test session
- [ ] **INFRA-04**: Test isolation via database state cleanup between tests
- [ ] **INFRA-05**: Session-scoped container fixtures for performance (reuse across tests)

### PostgreSQL Integration

- [ ] **PG-01**: Integration tests connect to real PostgreSQL+pgvector container
- [ ] **PG-02**: pgvector extension initialized automatically in test database
- [ ] **PG-03**: Database schema created correctly in test container
- [ ] **PG-04**: Database state cleaned between tests (truncate, not drop/recreate)
- [ ] **PG-05**: Vector similarity search works correctly with real pgvector

### Ollama Integration

- [ ] **OLLAMA-01**: Integration tests use real Ollama for embedding generation
- [ ] **OLLAMA-02**: Warmup fixture mitigates 30s first-request timeout
- [ ] **OLLAMA-03**: Embedding generation produces correct vector dimensions
- [ ] **OLLAMA-04**: Optional dockerized Ollama (users can choose native or Docker)
- [ ] **OLLAMA-05**: Tests detect native Ollama availability, fallback to Docker

### End-to-End Flows

- [ ] **E2E-01**: Full indexing flow tested (files → chunks → embeddings → storage)
- [ ] **E2E-02**: Full search flow tested (query → embedding → vector search → results)
- [ ] **E2E-03**: CLI index command works end-to-end with real services
- [ ] **E2E-04**: CLI search command works end-to-end with real services
- [ ] **E2E-05**: Search results contain correct file paths and line numbers
- [ ] **E2E-06**: DevOps files (Terraform, Dockerfile, Bash) indexed correctly

### CI/CD Integration

- [ ] **CI-01**: GitHub Actions workflow runs integration tests
- [ ] **CI-02**: CI uses Docker services for PostgreSQL and Ollama
- [ ] **CI-03**: Environment-based hostname detection (localhost vs container names)
- [ ] **CI-04**: Integration tests can be skipped locally via pytest marker

### Test Organization

- [ ] **ORG-01**: Unit tests separated into tests/unit/ directory
- [ ] **ORG-02**: Integration tests in tests/integration/ directory
- [ ] **ORG-03**: pytest markers distinguish unit vs integration tests
- [ ] **ORG-04**: Default test run executes unit tests only (fast)
- [ ] **ORG-05**: Integration tests run via explicit marker or CI

## Future Requirements

Deferred to later milestones.

### Performance Optimization

- **PERF-01**: Parallel integration test execution with pytest-xdist
- **PERF-02**: Per-worker database isolation for parallel tests
- **PERF-03**: Test execution time benchmarking

### Extended Coverage

- **EXT-01**: MCP server tools tested end-to-end
- **EXT-02**: REPL commands tested end-to-end
- **EXT-03**: Multiple concurrent index operations tested

## Out of Scope

Explicitly excluded from this milestone.

| Feature | Reason |
|---------|--------|
| Kubernetes testing | Docker sufficient for local/CI integration tests |
| Remote Docker hosts | Local Docker only for v1.3 |
| Custom Ollama models | nomic-embed-text only; model flexibility is v2+ |
| Windows container support | Linux containers only; Windows adds complexity |
| Test coverage reporting | Focus on correctness first, metrics later |

## Traceability

Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ORG-01 | Phase 11 | Complete |
| ORG-02 | Phase 11 | Complete |
| ORG-03 | Phase 11 | Complete |
| ORG-04 | Phase 11 | Complete |
| ORG-05 | Phase 11 | Complete |
| INFRA-01 | Phase 12 | Pending |
| INFRA-02 | Phase 12 | Pending |
| INFRA-03 | Phase 12 | Pending |
| INFRA-04 | Phase 12 | Pending |
| INFRA-05 | Phase 12 | Pending |
| PG-01 | Phase 12 | Pending |
| PG-02 | Phase 12 | Pending |
| PG-03 | Phase 12 | Pending |
| PG-04 | Phase 12 | Pending |
| PG-05 | Phase 12 | Pending |
| OLLAMA-01 | Phase 13 | Pending |
| OLLAMA-02 | Phase 13 | Pending |
| OLLAMA-03 | Phase 13 | Pending |
| OLLAMA-04 | Phase 13 | Pending |
| OLLAMA-05 | Phase 13 | Pending |
| E2E-01 | Phase 14 | Pending |
| E2E-02 | Phase 14 | Pending |
| E2E-03 | Phase 14 | Pending |
| E2E-04 | Phase 14 | Pending |
| E2E-05 | Phase 14 | Pending |
| E2E-06 | Phase 14 | Pending |
| CI-01 | Phase 15 | Pending |
| CI-02 | Phase 15 | Pending |
| CI-03 | Phase 15 | Pending |
| CI-04 | Phase 15 | Pending |

**Coverage:**
- v1.3 requirements: 30 total
- Mapped to phases: 30
- Unmapped: 0

---
*Requirements defined: 2026-01-30*
*Last updated: 2026-01-30 after roadmap creation*
