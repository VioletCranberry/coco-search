# Project Research Summary

**Project:** CocoSearch v1.3 — Docker Integration Tests & Infrastructure
**Domain:** Docker-based integration testing for database+ML service application
**Researched:** 2026-01-30
**Confidence:** HIGH

## Executive Summary

CocoSearch v1.3 adds Docker-based integration tests to validate real PostgreSQL+pgvector and Ollama behavior beyond the existing 327 unit tests. Research shows Testcontainers-Python is the ecosystem standard for Python projects in 2026, providing programmatic container lifecycle management with automatic cleanup and built-in health checks. The recommended approach is to use session/module-scoped fixtures for container reuse (avoiding 30+ second Ollama startup on each test), function-scoped fixtures for database cleanup (ensuring test isolation), and explicit separation of unit tests (fast with mocks) from integration tests (slower with real services).

The critical architectural decision is separating test infrastructure: existing unit tests remain in `tests/unit/` with mocks, new integration tests live in `tests/integration/` with Testcontainers fixtures, and pytest markers (`@pytest.mark.integration`) enable selective execution. This preserves fast unit test feedback (<5 seconds) while adding comprehensive integration validation. The primary risk is fixture scope conflicts (module-scoped containers conflicting with function-scoped cleanup fixtures), which is mitigated by clear separation in conftest.py and explicit scope documentation.

Key implementation insight: Ollama model loading takes 30+ seconds on first request, causing test timeouts. This is addressed with warmup fixtures, `OLLAMA_KEEP_ALIVE=-1` to keep models loaded, and generous timeouts (60+ seconds). UV package manager requires `UV_LINK_MODE=copy` in Docker due to hardlink incompatibility with volume mounts. The test suite should categorize tests by speed: fast unit tests run on every save, integration tests run pre-commit, slow integration tests run in CI only.

## Key Findings

### Recommended Stack

**Core addition: Testcontainers-Python >=4.14.0** (released 2026-01-07, actively maintained)

The research strongly recommends Testcontainers over alternatives (pytest-docker-compose, raw docker-py) because:
1. Industry standard with cross-language consistency (Java, .NET, Python, Go, Rust, Node.js)
2. PostgreSQL module with pre-configured container and connection helpers
3. GenericContainer for Ollama with custom image support
4. Automatic cleanup with finalizers (prevents orphaned containers)
5. Dynamic port mapping (supports parallel execution without conflicts)
6. Simpler API than docker-compose plugins for CocoSearch's needs

**Core technologies:**
- **Testcontainers[postgres] >=4.14.0**: Programmatic Docker lifecycle management for tests — recommended over pytest-docker because it provides better control for dynamic container needs
- **Existing pytest >=9.0.2**: No changes needed — handles both unit tests (mocked) and integration tests (real containers) seamlessly
- **Existing pytest-asyncio >=1.3.0**: No changes needed — async fixtures work with sync container setup (different scopes)
- **pgvector/pgvector:pg17**: Real database testing — identical image for dev/test/prod to ensure test validity
- **ollama/ollama:latest**: Real embedding generation — required because embedding behavior cannot be accurately mocked

**What NOT to add:**
- pytest-docker plugins (less dynamic control than Testcontainers)
- docker-compose Python libraries (adds complexity for static configs)
- Separate test-specific container images (breaks dev/test/prod parity)

**Confidence:** HIGH — Testcontainers verified via PyPI, official docs, and cross-language ecosystem adoption

See: [STACK.md](STACK.md)

### Expected Features

Research identifies Docker integration testing as a well-established domain with clear table stakes and anti-patterns.

**Must have (table stakes):**
- Container lifecycle management (startup, health checks, teardown) — core value proposition of Testcontainers
- Real PostgreSQL+pgvector testing — vector similarity queries cannot be accurately mocked
- Real Ollama embedding generation — embedding dimensions, normalization require real models
- Test isolation (fresh state per test) — fundamental testing principle, prevents flaky tests
- End-to-end flow verification (index → search → verify) — validates complete system integration
- Automatic cleanup — prevents orphaned containers consuming resources
- Health checks before execution — prevents race conditions and connection errors
- Test data seeding — enables controlled test scenarios with known content
- Component-level tests — isolates PostgreSQL and Ollama for faster failure diagnosis

**Should have (differentiators):**
- Shared container fixtures (module/session scope) — dramatically faster test execution (amortizes 30s Ollama startup)
- Docker Compose integration — leverages existing docker-compose.yml from development
- CI/CD integration examples — reduces friction for contributors
- Parallel test execution — speeds up suite as it grows (pytest-xdist)

**Defer (v2+):**
- Performance benchmarking — valuable but not blocking MVP
- Test retry mechanisms — better to fix root causes than mask flakiness
- Minimal test-specific models — marginal value given nomic-embed-text is already fast

**Anti-patterns (deliberately NOT building):**
- Using `latest` tags for images — breaks test reproducibility
- Different images for test vs production — invalidates test results
- Hardcoded ports or configuration — causes conflicts and brittleness
- In-memory or mock alternatives for integration tests — defeats the purpose
- Including test dependencies in production images — bloats images unnecessarily

**Confidence:** HIGH — Patterns verified across official Docker/Testcontainers docs and recent 2025-2026 community resources

See: [FEATURES_DOCKER_TESTING.md](FEATURES_DOCKER_TESTING.md)

### Architecture Approach

Research recommends a three-layer test organization:

**Test directory structure:**
```
tests/
├── unit/              # Existing 327 tests with mocks (fast: <5s)
│   └── conftest.py    # Mock fixtures only
└── integration/       # New Docker-based tests (slower: 30-60s)
    ├── conftest.py    # Testcontainers fixtures only
    ├── test_postgres.py     # Component: database operations
    ├── test_ollama.py       # Component: embedding generation
    └── test_full_flow.py    # End-to-end: index → search → verify
```

**Major components:**
1. **Testcontainers Fixtures (session/module scope)** — Start containers once per test module, reuse across tests for performance. Return connection details (host, port, URL) not containers themselves.
2. **Database Cleanup Fixtures (function scope)** — Clean database state between tests while reusing same container. Truncate tables rather than recreating containers.
3. **Warmup Fixtures (session scope)** — Trigger Ollama model load before tests run, avoiding 30+ second timeout on first embedding request.
4. **pytest Markers** — Separate `@pytest.mark.unit` (fast, mocks) from `@pytest.mark.integration` (slower, real services) for selective execution.

**Build order recommendation:**
1. **Phase 1: Foundation** (2-4 hours) — Reorganize existing tests to `tests/unit/`, add pytest markers, create `tests/integration/` structure with conftest.py
2. **Phase 2: Infrastructure** (4-8 hours) — Add Testcontainers dependency, create Docker fixtures, verify container lifecycle
3. **Phase 3: PostgreSQL Tests** (8-12 hours) — Test database operations with real pgvector: schema, storage, vector search
4. **Phase 4: Ollama Tests** (6-10 hours) — Test embedding generation with real models, handle timeouts
5. **Phase 5: Full Flow Tests** (8-12 hours) — End-to-end validation of complete pipeline

**Confidence:** HIGH — Architecture verified against official pytest docs, Testcontainers guides, and multiple recent integration testing resources

See: [ARCHITECTURE.md](ARCHITECTURE.md)

### Critical Pitfalls

Research identified 18 pitfalls across critical/medium/low severity. Top 5 critical:

1. **Fixture Scope Mixing Causes Container Conflicts** — Using module-scoped containers with function-scoped fixtures for same service causes "service already exists" errors. **Prevention:** Use module scope for container lifecycle, function scope only for data cleanup within running containers. Separate conftest.py for unit vs integration tests.

2. **Ollama Model Loading Timeout on First Test Run** — First embedding request takes 30+ seconds (confirmed in Jan 2026 GitHub issue), causing test timeouts. Subsequent requests complete in ~3 seconds. **Prevention:** Set `OLLAMA_KEEP_ALIVE=-1`, add session-scoped warmup fixture, increase timeouts to 60+ seconds.

3. **CI vs Local Network Access Differences** — Tests access `localhost:5432` on dev machines but need `cocosearch-db:5432` in CI when running in Docker network. **Prevention:** Use environment variable `DB_HOST=${DB_HOST:-localhost}`, set `DB_HOST=cocosearch-db` in CI workflows.

4. **Database State Pollution Between Tests** — Tests share state causing "duplicate key" errors and wrong result counts. **Prevention:** Implement autouse cleanup fixture that truncates tables between tests, or use transaction rollback pattern.

5. **UV Package Manager Hardlink Mode Fails with Docker Volumes** — UV's default hardlinks break with volume mounts, causing "cross-device link" errors. **Prevention:** Set `UV_LINK_MODE=copy` environment variable in Docker/docker-compose.yml.

**Additional notable pitfalls:**
- **pgvector extension not enabled** — Must run `CREATE EXTENSION IF NOT EXISTS vector` in session fixture
- **GitHub Actions TTY requirement** — Use `docker-compose exec -T` (disable TTY) in CI
- **Mocked vs integration fixture name collisions** — Use distinct names (`mock_db_pool` vs `docker_db`) and separate conftest files

**Confidence:** MEDIUM-HIGH — Pitfalls verified from recent 2025-2026 issues, official docs, and community resources. Ollama timeout confirmed via Jan 2026 GitHub issue.

See: [PITFALLS-docker-integration-tests.md](PITFALLS-docker-integration-tests.md)

## Implications for Roadmap

Based on research, suggested phase structure prioritizes risk mitigation and incremental validation:

### Phase 1: Test Reorganization & Infrastructure Setup
**Rationale:** Lowest risk, establishes foundation without breaking existing tests. Separates unit/integration tests before adding Docker complexity.

**Delivers:**
- Existing 327 tests moved to `tests/unit/` with `@pytest.mark.unit` markers
- `tests/integration/` directory structure created
- pytest.ini configured with markers (unit, integration, slow)
- Testcontainers[postgres] dependency added
- Separate conftest.py for integration tests with clear naming

**Addresses:** Table stakes features — container lifecycle management, automatic cleanup
**Avoids:** Pitfall #1 (fixture scope mixing), Pitfall #7 (fixture name collisions)

**Research flags:** None — standard pytest reorganization pattern

### Phase 2: Docker Fixtures & PostgreSQL Component Tests
**Rationale:** Validates Docker infrastructure works before adding Ollama complexity. PostgreSQL faster to start than Ollama, provides quicker feedback loop.

**Delivers:**
- Session-scoped PostgreSQL container fixture with health checks
- Function-scoped database cleanup fixture
- pgvector extension initialization
- Component tests: schema creation, index storage, vector search

**Addresses:** Table stakes features — real PostgreSQL+pgvector testing, test isolation, health checks
**Avoids:** Pitfall #4 (database state pollution), Pitfall #9 (pgvector extension missing)

**Uses:** Testcontainers PostgreSQL module, pgvector/pgvector:pg17 image
**Implements:** Container lifecycle layer, database cleanup layer

**Research flags:** Standard patterns, skip phase-specific research

### Phase 3: Ollama Component Tests
**Rationale:** Adds Ollama separately from full flows, isolates model loading timeout issues.

**Delivers:**
- Session-scoped Ollama container fixture with extended health check
- Warmup fixture to pre-load model
- Component tests: embedding generation, model availability, error handling

**Addresses:** Table stakes features — real Ollama embedding generation
**Avoids:** Pitfall #2 (Ollama model loading timeout)

**Uses:** ollama/ollama:latest image, GenericContainer with custom wait strategy
**Implements:** Warmup layer, timeout handling

**Research flags:** May need research if Ollama health check proves unreliable (wait strategies)

### Phase 4: Full Flow Integration Tests
**Rationale:** Validates complete system works end-to-end now that components are proven separately.

**Delivers:**
- Test codebases with known content (fixture data)
- End-to-end tests: index → embed → store → search → verify results
- DevOps file handling verification (Terraform, Dockerfile, Bash)
- Incremental indexing tests

**Addresses:** Table stakes features — end-to-end flow verification, test data seeding
**Avoids:** Pitfall #11 (floating-point similarity score assertions) via pytest.approx()

**Implements:** Complete pipeline validation

**Research flags:** None — builds on validated components

### Phase 5: CI Integration & Optimization
**Rationale:** Adds CI workflow once tests proven locally. Optimizes for speed after correctness validated.

**Delivers:**
- GitHub Actions workflow with Docker support
- Environment-based hostname detection (localhost vs container names)
- TTY handling for docker-compose exec in CI
- Test execution categorization (fast/slow markers)
- Module-scoped fixtures for performance

**Addresses:** Nice-to-have features — CI/CD integration, shared container fixtures
**Avoids:** Pitfall #3 (CI network differences), Pitfall #5 (GitHub Actions TTY), Pitfall #13 (slow test execution)

**Uses:** GitHub Actions with Docker, pytest-xdist for parallel execution

**Research flags:** None — standard CI patterns

### Phase Ordering Rationale

- **Phase 1 first** because reorganization is non-breaking and establishes test separation patterns
- **PostgreSQL before Ollama** because it's faster to start (2-5s vs 30s), providing quicker validation of Docker patterns
- **Component tests before full flows** to isolate failure modes and validate individual services work
- **CI last** because it requires working local tests first, and optimization can be done incrementally
- **No phase dependencies on external research** — all patterns well-documented, can proceed directly to roadmap

### Research Flags

**No phases need deeper research during planning:**
- Phase 1: Standard pytest reorganization
- Phase 2: Testcontainers PostgreSQL module is well-documented
- Phase 3: Ollama patterns established from community resources
- Phase 4: Builds on proven components
- Phase 5: Standard CI patterns

**All phases have clear implementation patterns:**
- Testcontainers usage verified via official guides
- Pytest fixture patterns verified via official docs
- Docker integration verified via recent 2025-2026 resources

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Testcontainers verified via PyPI (v4.14.0, 2026-01-07), official docs, cross-language ecosystem adoption |
| Features | HIGH | Table stakes and anti-patterns consistent across official Docker/Testcontainers documentation and 2025-2026 community resources |
| Architecture | HIGH | Test organization patterns verified against official pytest docs, fixture scoping verified via Testcontainers guides |
| Pitfalls | MEDIUM-HIGH | Most pitfalls verified from official sources; Ollama timeout confirmed via recent GitHub issue (Jan 2026); tree-sitter Docker issue is LOW confidence inference |

**Overall confidence:** HIGH

### Gaps to Address

**Minor gaps (low risk, handle during implementation):**

1. **Ollama health check reliability** — Research shows HTTP endpoint check pattern but CocoSearch-specific reliability unknown. **Mitigation:** Use extended timeout (60s) in wait strategy, verify in Phase 3 component tests, adjust if needed.

2. **pytest-xdist database isolation** — Parallel test execution with shared PostgreSQL requires separate test databases per worker. **Mitigation:** Defer parallelization to Phase 5 after correctness validated, use pytest-xdist's worker ID for isolation if implemented.

3. **Tree-sitter parsers in Docker** — CocoIndex uses tree-sitter for 15+ languages; unclear if parsers work automatically in Docker containers with different architecture (macOS host, Linux container). **Mitigation:** Test explicitly in Phase 4 full flow tests, compile parsers in Docker if needed (LOW confidence gap).

4. **UV lockfile caching in Docker** — UV's caching behavior with Docker build cache may require extra configuration. **Mitigation:** Document `docker-compose build` requirement after pyproject.toml changes, use `--no-cache` in CI.

**No critical gaps** — all core patterns verified from official sources. Minor gaps are implementation details that can be resolved during coding.

## Sources

### Primary (HIGH confidence)

**Official Documentation:**
- [Testcontainers-Python PyPI](https://pypi.org/project/testcontainers/) — Version 4.14.0 (2026-01-07), Python >=3.10, Apache 2.0 license
- [Getting started with Testcontainers for Python](https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/) — Fixture patterns, container lifecycle, best practices
- [pytest fixtures documentation](https://docs.pytest.org/en/stable/how-to/fixtures.html) — Fixture scopes, autouse, cleanup patterns
- [pytest markers documentation](https://docs.pytest.org/en/stable/how-to/skipping.html) — Test selection and categorization
- [Using uv in Docker - Official Guide](https://docs.astral.sh/uv/guides/integration/docker/) — UV_LINK_MODE=copy requirement
- [Docker Compose documentation](https://docs.docker.com/compose/) — Service configuration, volume management
- [pgvector GitHub repository](https://github.com/pgvector/pgvector) — Extension installation, Docker usage

**Official Docker Resources:**
- [Shift-Left Testing with Testcontainers](https://www.docker.com/blog/shift-left-testing-with-testcontainers/) — Testcontainers value proposition
- [Write Maintainable Integration Tests with Docker](https://www.docker.com/blog/maintainable-integration-tests-with-docker/) — Best practices and anti-patterns
- [How to Run Hugging Face Models with Ollama and Testcontainers](https://www.docker.com/blog/how-to-run-hugging-face-models-programmatically-using-ollama-and-testcontainers/) — Ollama Docker patterns

**Recent Issues (2026):**
- [Ollama Docker slow startup Issue #13627](https://github.com/ollama/ollama/issues/13627) (Jan 2026) — Confirmed 30s first load, 3s subsequent on RTX 6000

### Secondary (MEDIUM confidence)

**Community Resources (2024-2026):**
- [Testcontainers Best Practices for .NET](https://www.milanjovanovic.tech/blog/testcontainers-best-practices-dotnet-integration-testing) — Cross-language patterns, module scoping
- [How to Write Integration Tests for Rust APIs with Testcontainers](https://oneuptime.com/blog/post/2026-01-07-rust-testcontainers/view) — Cleanup patterns, test isolation (2026-01-07)
- [Using Testcontainers with Pytest: Isolate Data](https://qxf2.com/blog/using-testcontainers-with-pytest/) — Database cleanup strategies
- [Integration testing with pytest & Docker compose](https://xnuinside.medium.com/integration-testing-for-bunch-of-services-with-pytest-docker-compose-4892668f9cba) — pytest-docker-compose comparison
- [Cleaning PostgreSQL DB between Integration Tests](https://carbonhealth.com/blog-post/cleaning-postgresql-db-between-integration-tests-efficiently) — TRUNCATE CASCADE pattern
- [pytest approx for accurate numeric testing](https://pytest-with-eric.com/pytest-advanced/pytest-approx/) — Floating-point assertion patterns
- [UV package management in Docker](https://medium.com/@shaliamekh/python-package-management-with-uv-for-dockerized-environments-f3d727795044) — UV_LINK_MODE issue
- [GitHub Actions Service Containers and Docker Compose](https://medium.com/@sreeprad99/from-ci-chaos-to-orchestration-deep-dive-into-github-actions-service-containers-and-docker-compose-7cb2ff335864) — CI network patterns

**Tool Documentation:**
- [pytest-docker GitHub](https://github.com/avast/pytest-docker) — Alternative approach comparison
- [pytest-docker-compose GitHub](https://github.com/pytest-docker-compose/pytest-docker-compose) — docker-compose.yml integration
- [Testcontainers pgvector module](https://testcontainers.com/modules/pgvector/) — Pre-configured PostgreSQL container

### Tertiary (LOW confidence)

**Inferred Patterns:**
- [tree-sitter Docker compilation issues](https://github.com/tree-sitter/py-tree-sitter/issues/99) — Cross-platform parser compilation (needs verification with CocoIndex)
- [Docker postgres for testing with tmpfs](https://github.com/labianchin/docker-postgres-for-testing) — tmpfs optimization pattern (standard but not verified for CocoSearch)

---
*Research completed: 2026-01-30*
*Ready for roadmap: yes*
