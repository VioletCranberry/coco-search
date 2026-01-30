# Features Research: Docker Integration Testing

**Project:** CocoSearch
**Domain:** Docker-based integration testing for database+ML service application
**Researched:** 2026-01-30

## Executive Summary

Docker integration testing for a semantic code search tool with PostgreSQL+pgvector and Ollama requires real service testing (no mocks), container lifecycle management, test isolation, and end-to-end flow verification. The research identifies Testcontainers-Python as the ecosystem standard for Python projects, with pytest fixtures providing the cleanest integration pattern.

**Key ecosystem insight:** Modern integration testing (2026) prioritizes testing against real services in isolated containers over mocks/in-memory alternatives, with Testcontainers emerging as the cross-language standard (Java, .NET, Python, Go, Rust, Node.js).

## Table Stakes (Must Have)

### Container Lifecycle Management

**Description:** Automatic startup, health checks, and teardown of Docker containers for each test or test module.

**Complexity:** Medium

**Why required:** Core capability of integration testing with Docker. Without this, tests either fail due to containers not being ready or leave orphaned containers consuming resources. This is the fundamental value proposition of Testcontainers and Docker-based testing.

**Implementation pattern:** Use pytest fixtures with Testcontainers-Python or pytest-docker-compose to manage PostgreSQL and Ollama containers. Module-scoped fixtures start containers once per test module; function-scoped fixtures create isolated containers per test.

**Sources:**
- [Testcontainers-Python (PyPI)](https://pypi.org/project/testcontainers/)
- [Getting started with Testcontainers for Python](https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/)
- [Shift-Left Testing with Testcontainers](https://www.docker.com/blog/shift-left-testing-with-testcontainers/)

---

### Real PostgreSQL+pgvector Testing

**Description:** Run tests against actual PostgreSQL container with pgvector extension, not mocked database.

**Complexity:** Low (infrastructure already exists)

**Why required:** Vector similarity queries have complex behavior that cannot be accurately mocked. Mocking pgvector queries would require reimplementing distance metrics (cosine similarity, etc.), which defeats the purpose of integration testing. The project already has 327 unit tests with mocks; integration tests must verify real database behavior.

**Implementation pattern:** Use `pgvector/pgvector:pg17` image (already in docker-compose.yml). Configure container with test credentials. Use Testcontainers PostgreSQL module or pytest-docker-compose.

**Sources:**
- [Testcontainers pgvector Module](https://testcontainers.com/modules/pgvector/)
- [TestContainers in .NET with PostgreSQL and PgVector](https://dev.to/chsami/testcontainers-in-net-with-postgresql-and-pgvector-4m93)
- [Setting Up PostgreSQL with pgvector in Docker](https://medium.com/@adarsh.ajay/setting-up-postgresql-with-pgvector-in-docker-a-step-by-step-guide-d4203f6456bd)

---

### Real Ollama Embedding Generation

**Description:** Run tests against actual Ollama container to generate embeddings with real models.

**Complexity:** Medium (requires model pulling, slower than mocks)

**Why required:** Embedding dimensions, normalization, and model behavior cannot be accurately simulated. Real embeddings are required to test: (1) end-to-end indexing flow, (2) embedding storage in pgvector, (3) query embedding generation, (4) vector similarity search accuracy. Mocked embeddings would produce false confidence in search quality.

**Implementation pattern:** Use `ollama/ollama:latest` Docker image. Configure with `nomic-embed-text` model (project default). Implement health check that waits for model availability. Use Testcontainers Ollama module if available, or generic container with HTTP readiness probe.

**Sources:**
- [ollama/ollama Docker Image](https://hub.docker.com/r/ollama/ollama)
- [How to Run Hugging Face Models with Ollama and Testcontainers](https://www.docker.com/blog/how-to-run-hugging-face-models-programmatically-using-ollama-and-testcontainers/)
- [Ollama Embeddings Documentation](https://docs.ollama.com/capabilities/embeddings)

---

### Test Isolation (Fresh State Per Test)

**Description:** Each test starts with clean database and no residual state from previous tests.

**Complexity:** Low

**Why required:** Integration tests must be independent and deterministic. Shared state leads to flaky tests where execution order matters. Named indexes in CocoSearch could collide between tests without isolation. This is a fundamental testing principle emphasized across all Docker testing resources.

**Implementation pattern:** Two approaches: (1) Module-scoped containers with database cleanup between tests (faster), (2) Function-scoped containers creating fresh instances per test (slower but perfect isolation). For CocoSearch, module-scoped + database cleanup is sufficient since schema is simple.

**Sources:**
- [Testcontainers Best Practices for .NET](https://www.milanjovanovic.tech/blog/testcontainers-best-practices-dotnet-integration-testing)
- [How to Write Integration Tests for Rust APIs with Testcontainers](https://oneuptime.com/blog/post/2026-01-07-rust-testcontainers/view)
- [Using Testcontainers with Pytest: Isolate Data for Effective Testing](https://qxf2.com/blog/using-testcontainers-with-pytest/)

---

### End-to-End Flow Verification

**Description:** Test complete flows: files → chunks → embeddings → storage → search → results.

**Complexity:** Medium

**Why required:** Unit tests with mocks verify individual components. Integration tests must verify the complete system works together. For CocoSearch, this means: (1) indexing a codebase produces searchable chunks, (2) searching returns relevant results, (3) CLI commands work end-to-end, (4) MCP tools work end-to-end. This is the primary value of integration testing beyond unit tests.

**Implementation pattern:** Create test codebases with known content. Index them. Search with queries that should match specific chunks. Assert results contain expected files/chunks. Verify relevance scores are reasonable. Test failure cases (missing index, empty query).

**Sources:**
- [Write Maintainable Integration Tests with Docker](https://www.docker.com/blog/maintainable-integration-tests-with-docker/)
- [The Ultimate Guide to Integration Testing with Docker-Compose](https://medium.com/swlh/the-ultimate-guide-to-integration-testing-with-docker-compose-and-sql-f288f05032c9)

---

### Automatic Cleanup (No Orphaned Containers)

**Description:** Containers are stopped and removed after test execution, even when tests fail.

**Complexity:** Low

**Why required:** Orphaned containers consume resources (memory, disk, ports) and can interfere with future test runs. Port conflicts are common when containers aren't cleaned up. Testcontainers handles this automatically; pytest-docker-compose requires configuration. This is emphasized as critical in all Docker testing anti-patterns resources.

**Implementation pattern:** Use pytest yield fixtures with try/finally or Testcontainers' automatic cleanup. Ensure `docker-compose down -v` runs in pytest teardown if using docker-compose. Implement cleanup even when tests raise exceptions.

**Sources:**
- [pytest-docker · PyPI](https://pypi.org/project/pytest-docker/)
- [Integration Testing with Testcontainers](https://devblogs.microsoft.com/ise/testing-with-testcontainers/)
- [How to Write Integration Tests for Rust APIs (cleanup patterns)](https://oneuptime.com/blog/post/2026-01-07-rust-testcontainers/view)

---

### Health Checks Before Test Execution

**Description:** Wait for services (PostgreSQL, Ollama) to be ready before running tests.

**Complexity:** Low

**Why required:** Containers start asynchronously. PostgreSQL takes time to initialize. Ollama takes time to load models. Tests that run before services are ready will fail with connection errors, producing flaky tests. This is a standard pattern in all Docker testing resources.

**Implementation pattern:** Use Testcontainers' built-in wait strategies (wait for port, wait for HTTP endpoint, wait for log message). For PostgreSQL, wait for `pg_isready`. For Ollama, wait for HTTP `/` endpoint to return 200. Existing docker-compose.yml already has health check for PostgreSQL.

**Sources:**
- [Integration tests with docker-compose (health checks)](https://atlasgo.io/guides/testing/docker-compose)
- [Docker Compose for Integration Testing](https://medium.com/@alexandre.therrien3/docker-compose-for-integration-testing-a-practical-guide-for-any-project-49b361a52f8c)

---

### Test Data Seeding

**Description:** Ability to seed test database with known data for search verification tests.

**Complexity:** Low

**Why required:** To test search accuracy, tests need codebases with known content. To test edge cases (large indexes, specific file types, etc.), tests need specific data scenarios. Seeding allows controlled test scenarios rather than relying on random/generated data.

**Implementation pattern:** Create test fixture codebases in `tests/fixtures/codebases/`. Create helper functions to index these codebases. Store sample chunks/embeddings for verification. Use SQL scripts mounted via Docker volumes for complex scenarios (optional, probably not needed for CocoSearch).

**Sources:**
- [Integration Testing with Real Databases Using Testcontainers](https://dev.to/imdj/integration-testing-with-real-databases-using-testcontainers-2k62)
- [Automate test data management & database seeding with Liquibase](https://www.liquibase.com/blog/automate-test-data-management-database-seeding-by-integrating-liquibase-into-your-testing-framework)
- [The Ultimate Guide to Integration Testing With Docker-Compose and SQL](https://medium.com/swlh/the-ultimate-guide-to-integration-testing-with-docker-compose-and-sql-f288f05032c9)

---

### Component-Level Integration Tests

**Description:** Test individual components (PostgreSQL storage, Ollama embeddings) independently before full flows.

**Complexity:** Low

**Why required:** When full flow tests fail, component tests help isolate which service is broken. Faster feedback loop than running complete flows. Tests database migrations, schema creation, and pgvector extension availability separately from indexing logic. Tests Ollama model loading and embedding generation separately from storage.

**Implementation pattern:** Create separate test modules: `tests/integration/test_db.py` for PostgreSQL operations, `tests/integration/test_ollama.py` for embedding generation, `tests/integration/test_flows.py` for end-to-end. Each can have different container configurations and scopes.

**Sources:**
- [Integration Testing with Testcontainers](https://devblogs.microsoft.com/ise/testing-with-testcontainers/)
- [Testcontainers documentation (component testing)](https://testcontainers.com/guides/introducing-testcontainers/)

---

## Differentiators (Nice to Have)

### Parallel Test Execution

**Description:** Run multiple integration tests in parallel using different container instances or ports.

**Complexity:** High

**Why valuable:** Speeds up test suite execution. Integration tests with real services are slower than unit tests. Parallel execution can reduce CI/CD time significantly. pytest-xdist provides `-n auto` for parallel execution.

**Value add:** A test suite with 50 integration tests taking 2 minutes serially could run in 30 seconds with 4 parallel workers. This becomes increasingly valuable as test suite grows. However, requires careful management of port conflicts and container isolation.

**Implementation notes:** Testcontainers handles port randomization automatically. pytest-xdist provides worker ID for test isolation. May not be needed initially if test suite is small (<20 tests).

**Sources:**
- [Running Parallel Tests in Docker](https://dzone.com/articles/running-parallel-tests-in-docker-1)
- [Parallel Testing in Software Testing Guide 2026](https://www.accelq.com/blog/parallel-testing/)

---

### Shared Container Fixtures (Module/Session Scope)

**Description:** Reuse same container instance across multiple tests instead of recreating per test.

**Complexity:** Medium

**Why valuable:** Dramatically faster test execution. Starting PostgreSQL+Ollama for every test is slow. Module-scoped fixtures start containers once per test file. Session-scoped fixtures start containers once for entire test run.

**Value add:** Function-scoped containers might take 30-60 seconds per test (container startup + model loading). Module-scoped containers reduce this to once per module. For 10 tests in a module, this saves 5-9 minutes. Tradeoff is maintaining isolation through database cleanup rather than fresh containers.

**Implementation notes:** Requires careful cleanup between tests to maintain isolation. Good pattern: session-scoped containers + module-scoped schema setup + function-scoped data cleanup.

**Sources:**
- [Pytest and Testcontainers (module-scoped fixtures)](https://mariogarcia.github.io/blog/2019/10/pytest_fixtures.html)
- [Test-Driven Development with Python and Testcontainers](https://collabnix.com/test-driven-development-with-python-testcontainers-and-pytest/)

---

### Docker Compose Integration

**Description:** Leverage existing docker-compose.yml for test environment instead of Testcontainers.

**Complexity:** Low (CocoSearch already has docker-compose.yml)

**Why valuable:** Simpler for projects that already use Docker Compose. Users can test against the same configuration they use for development. pytest-docker-compose plugin provides pytest integration. Allows unified environment for dev + test.

**Value add:** Reduces duplication between dev environment (docker-compose.yml) and test environment. Users familiar with Docker Compose don't need to learn Testcontainers API. However, Testcontainers provides better programmatic control and cleanup.

**Implementation notes:** Can use pytest-docker-compose plugin. Existing docker-compose.yml would need test-specific overrides (different ports, ephemeral volumes). Testcontainers is generally preferred in 2026 ecosystem.

**Sources:**
- [pytest-docker-compose · PyPI](https://pypi.org/project/pytest-docker-compose/)
- [Integration tests with docker-compose](https://atlasgo.io/guides/testing/docker-compose)
- [Docker Compose for Integration Testing: A Practical Guide](https://medium.com/@alexandre.therrien3/docker-compose-for-integration-testing-a-practical-guide-for-any-project-49b361a52f8c)

---

### Test Retry Mechanisms

**Description:** Automatically retry flaky tests (timing issues, container startup variations).

**Complexity:** Low

**Why valuable:** Docker-based tests can have occasional timing issues despite health checks. Network conditions, resource contention, or CI environment variations can cause intermittent failures. Retrying flaky tests (with backoff) improves CI stability without masking real issues.

**Value add:** pytest-rerunfailures plugin provides `--reruns 2` flag. Reduces false negatives in CI. However, better test design (proper health checks, longer timeouts) is preferable to masking flakiness with retries.

**Implementation notes:** Use sparingly. Retries should be for genuine environmental issues, not bugs. Log warnings when retries are used to identify tests that need better stability.

**Sources:** General pytest best practices, not Docker-specific.

---

### CI/CD Integration Examples

**Description:** Documentation and configuration examples for running Docker integration tests in GitHub Actions, GitLab CI, etc.

**Complexity:** Low

**Why valuable:** Many CI systems require specific Docker configuration (Docker-in-Docker, service containers). Providing working examples reduces friction for contributors and users. GitHub Actions supports Docker out of the box, which is common for projects.

**Value add:** Lowers barrier to running tests in CI. Demonstrates that tests work in automated environments, not just locally. Can include matrix testing across Python versions or operating systems.

**Implementation notes:** GitHub Actions example is most relevant for open-source Python projects. Docker is supported by default. Testcontainers works without modification in GitHub Actions.

**Sources:**
- [Integration Testing with Testcontainers (CI/CD section)](https://devblogs.microsoft.com/ise/testing-with-testcontainers/)
- [E2E-Testing in CI Environment With Testcontainers](https://dev.to/kirekov/e2e-testing-in-ci-environment-with-testcontainers-1403)

---

### Performance Benchmarking

**Description:** Integration tests that measure and assert on performance metrics (indexing speed, search latency).

**Complexity:** Medium

**Why valuable:** Catch performance regressions. Verify that vector search meets latency requirements. Ensure indexing throughput is acceptable for large codebases. Can use pytest-benchmark plugin for structured benchmarking.

**Value add:** Provides quantitative data on system performance. Helps identify bottlenecks (is it database, embeddings, or parsing?). However, Docker introduces overhead vs production, so benchmarks are relative, not absolute.

**Implementation notes:** Use consistent hardware for benchmarks. Docker performance varies by host. Focus on relative changes (regression detection) rather than absolute numbers.

**Sources:** General testing best practices, not Docker-specific.

---

### Minimal Test-Specific Models

**Description:** Use smaller/faster Ollama models for tests instead of production models.

**Complexity:** Low

**Why valuable:** `nomic-embed-text` (default) is fast, but tests could use an even smaller model if one exists. Faster model loading reduces test execution time. Tests care about shape/behavior of embeddings, not quality.

**Value add:** Reduced test time if significantly faster models exist. However, `nomic-embed-text` is already optimized for speed. Switching models introduces risk that tests don't match production behavior.

**Implementation notes:** Research if Ollama has a "test mode" or minimal embedding model. May not provide significant value given nomic-embed-text is already fast. Prioritize test accuracy over speed.

**Sources:**
- [Ollama Embedded Models Guide](https://collabnix.com/ollama-embedded-models-the-complete-technical-guide-to-local-ai-embeddings-in-2025/)

---

## Anti-Features (Deliberately NOT Building)

### Using `latest` Tags for Docker Images

**Why not:** `latest` tag is mutable and can point to different image versions over time. This breaks test reproducibility. Tests that pass today might fail tomorrow if upstream image changes. This is explicitly called out as an anti-pattern in Docker testing best practices.

**What to do instead:** Pin specific image versions: `pgvector/pgvector:pg17`, `ollama/ollama:0.1.22` (check current version). Document version choices. Update versions deliberately with testing.

**Sources:**
- [Docker Anti Patterns](https://codefresh.io/blog/docker-anti-patterns/)
- [7 Docker Anti-Patterns You Need to Avoid](https://www.howtogeek.com/devops/7-docker-anti-patterns-you-need-to-avoid/)

---

### Different Container Images for Test vs Production

**Why not:** Integration tests should verify production behavior. Using different images (e.g., PostgreSQL in test, pgvector in production) means tests don't validate what ships. This is a critical Docker anti-pattern that leads to "works on my machine" but fails in production.

**What to do instead:** Use identical `pgvector/pgvector:pg17` image for development, testing, and production. Test environment should differ only in scale/data, not in service versions.

**Sources:**
- [Docker Anti-Patterns: Different Images Per Environment](https://codefresh.io/blog/docker-anti-patterns/)
- [Container Anti-Patterns: Common Docker Mistakes](https://dev.to/idsulik/container-anti-patterns-common-docker-mistakes-and-how-to-avoid-them-4129)

---

### Hardcoded Ports or Configuration

**Why not:** Hardcoded ports (e.g., always use 5432) cause conflicts when running tests in parallel or when ports are already in use. Testcontainers uses dynamic port assignment for this reason. Hardcoded configuration makes tests brittle and environment-dependent.

**What to do instead:** Use Testcontainers' dynamic port assignment. Retrieve actual host port from container after startup. Pass configuration to application via environment variables, not hardcoded values.

**Sources:**
- [Testcontainers Best Practices (dynamic ports)](https://www.milanjovanovic.tech/blog/testcontainers-best-practices-dotnet-integration-testing)
- [Docker Best Practices and Anti-Patterns](https://ubk.hashnode.dev/docker-best-practices-and-anti-patterns)

---

### In-Memory or Mock Alternatives for Integration Tests

**Why not:** Integration tests exist specifically to test against real services. Using in-memory SQLite instead of PostgreSQL+pgvector means tests don't validate actual vector search behavior. Mocking Ollama means tests don't catch embedding/model issues. This defeats the entire purpose of integration testing.

**What to do instead:** Reserve mocks for unit tests (already have 327 unit tests). Integration tests use real PostgreSQL+pgvector and real Ollama. Accept that integration tests are slower but more accurate.

**Sources:**
- [Write Maintainable Integration Tests with Docker (test real services)](https://www.docker.com/blog/maintainable-integration-tests-with-docker/)
- [What is Testcontainers, and why should you use it? (no mocks)](https://testcontainers.com/guides/introducing-testcontainers/)

---

### Wait-for Scripts in Dockerfile

**Why not:** Using wait-for-it.sh or similar scripts in Dockerfiles to manage startup dependencies is a Docker anti-pattern. It couples test logic to container build. Better handled at orchestration level (health checks, wait strategies).

**What to do instead:** Use Testcontainers wait strategies or Docker Compose health checks. Let test framework handle service readiness. Existing docker-compose.yml already has proper health check for PostgreSQL.

**Sources:**
- [Docker Container Anti-Patterns (wait-for scripts)](https://www.couchbase.com/blog/docker-container-anti-patterns/)
- [Docker Anti-Patterns: Startup Dependencies](https://codefresh.io/blog/docker-anti-patterns/)

---

### Including Test Dependencies in Production Images

**Why not:** Production Docker images (if CocoSearch creates them later) should not include pytest, testcontainers, or test files. This increases image size unnecessarily and creates security surface. Tests should run against production-like images, not from within them.

**What to do instead:** Use multi-stage Dockerfiles if building images. Test dependencies stay in dev/CI environments. Integration tests run externally and connect to containers, not from inside them.

**Sources:**
- [Dockerfile Anti-Patterns and How to Avoid Them](https://medium.com/@harnesha22/dockerfile-anti-patterns-and-how-to-avoid-them-61e2c9e289e8)
- [Anti-Patterns When Building Container Images](https://jpetazzo.github.io/2021/11/30/docker-build-container-images-antipatterns/)

---

### Shared Test State Across Tests

**Why not:** Reusing the same database/indexes across tests without cleanup causes tests to pass/fail based on execution order. This is a fundamental testing anti-pattern that Docker isolation specifically solves. Shared state makes debugging failures extremely difficult.

**What to do instead:** Either use function-scoped containers (fresh per test) or module-scoped containers with explicit cleanup between tests. CocoSearch should clear named indexes or drop/recreate schema between tests.

**Sources:**
- [How to Write Integration Tests for Rust APIs (test isolation)](https://oneuptime.com/blog/post/2026-01-07-rust-testcontainers/view)
- [Using Testcontainers with Pytest: Isolate Data](https://qxf2.com/blog/using-testcontainers-with-pytest/)

---

### Testing Against Non-Containerized Local Services

**Why not:** Running tests against a PostgreSQL instance installed locally or Ollama running natively creates environment dependency. Tests work on developer machines with correct setup but fail in CI or for new contributors. This is the problem Docker testing solves.

**What to do instead:** Always use containers for integration tests. Developers can continue using native Ollama for development (current PROJECT.md decision), but tests should use containers for reproducibility.

**Sources:**
- [7 Ways to Improve Your Test Suite with Docker](https://www.cloudbees.com/blog/7-ways-to-improve-your-test-suite-with-docker)

---

## Dependencies on Existing Infrastructure

### Existing Unit Test Suite (327 tests)

**Status:** ✅ Complete

**Impact:** Integration tests complement, not replace, unit tests. Can reuse test fixtures from `tests/fixtures/` for codebase seeding. Can reference existing mock patterns to understand what behaviors are already unit-tested vs need integration testing.

**Files:** `tests/conftest.py`, `tests/fixtures/`, `tests/mocks/`

---

### Existing docker-compose.yml

**Status:** ✅ Complete

**Impact:** PostgreSQL service already configured with health checks. Can be used as-is for integration tests or as reference for Testcontainers configuration. Credentials (cocoindex/cocoindex) should remain consistent.

**Files:** `docker-compose.yml`

---

### PostgreSQL Schema Migrations

**Status:** ✅ Complete (schema in db.py)

**Impact:** Integration tests need to run schema initialization. Existing `cocosearch/search/db.py` has `initialize_schema()`. Tests should call this to set up tables/extensions before indexing tests.

**Files:** `cocosearch/search/db.py`

---

### Pytest Configuration

**Status:** ⚠️ Partial (no pytest.ini yet)

**Impact:** Integration tests should be marked differently from unit tests for selective execution. Need pytest markers like `@pytest.mark.integration` and `@pytest.mark.slow`. May want separate `tests/integration/` directory.

**Future work:** Create pytest.ini with markers, configure integration test discovery.

---

### UV Package Manager

**Status:** ✅ Constraint from PROJECT.md

**Impact:** Test dependencies (testcontainers, pytest-docker-compose) must be added via `uv add --dev`. Cannot use pip.

**Files:** `pyproject.toml`

---

## MVP Feature Prioritization

For minimal viable Docker integration test suite:

### Phase 1: Foundation (Must Have)
1. Container lifecycle management (Testcontainers-Python or pytest-docker-compose)
2. Real PostgreSQL+pgvector testing
3. Automatic cleanup
4. Health checks before test execution

### Phase 2: Basic Flows (Must Have)
5. Real Ollama embedding generation
6. Component-level integration tests (DB, Ollama separately)
7. Test isolation (fresh state per test)
8. Test data seeding

### Phase 3: Complete Coverage (Must Have)
9. End-to-end flow verification (index → search → verify)

### Phase 4: Optimization (Nice to Have)
10. Shared container fixtures (module scope)
11. CI/CD integration examples
12. Docker Compose integration (if preferred over Testcontainers)

### Defer to Post-MVP
- Parallel test execution (complex, only needed if suite grows large)
- Performance benchmarking (valuable but not blocking)
- Test retry mechanisms (band-aid, fix root cause instead)
- Minimal test-specific models (marginal value)

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Testcontainers-Python | HIGH | Official library, actively maintained (released Jan 7, 2026), comprehensive documentation |
| pgvector Docker testing | HIGH | Official Testcontainers module exists, multiple verified examples |
| Ollama Docker testing | MEDIUM | Docker image official, Testcontainers support exists but less documented than DB |
| pytest integration patterns | HIGH | Mature ecosystem, extensive examples across languages |
| Best practices | HIGH | Consistent patterns across 2025-2026 sources from official Docker/Testcontainers docs |
| Anti-patterns | HIGH | Well-documented in official Docker resources |

---

## Sources

### Testcontainers & Core Patterns
- [Testcontainers-Python (PyPI)](https://pypi.org/project/testcontainers/)
- [Getting started with Testcontainers for Python](https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/)
- [Testcontainers Documentation](https://testcontainers.com/guides/introducing-testcontainers/)
- [Shift-Left Testing with Testcontainers](https://www.docker.com/blog/shift-left-testing-with-testcontainers/)
- [Write Maintainable Integration Tests with Docker](https://www.docker.com/blog/maintainable-integration-tests-with-docker/)

### PostgreSQL & pgvector
- [Testcontainers pgvector Module](https://testcontainers.com/modules/pgvector/)
- [TestContainers in .NET with PostgreSQL and PgVector](https://dev.to/chsami/testcontainers-in-net-with-postgresql-and-pgvector-4m93)
- [Setting Up PostgreSQL with pgvector in Docker](https://medium.com/@adarsh.ajay/setting-up-postgresql-with-pgvector-in-docker-a-step-by-step-guide-d4203f6456bd)

### Ollama
- [ollama/ollama Docker Image](https://hub.docker.com/r/ollama/ollama)
- [How to Run Hugging Face Models with Ollama and Testcontainers](https://www.docker.com/blog/how-to-run-hugging-face-models-programmatically-using-ollama-and-testcontainers/)
- [Ollama Embeddings Documentation](https://docs.ollama.com/capabilities/embeddings)
- [Ollama Embedded Models Guide 2025](https://collabnix.com/ollama-embedded-models-the-complete-technical-guide-to-local-ai-embeddings-in-2025/)

### Python/pytest Integration
- [Test-Driven Development with Python and Testcontainers](https://collabnix.com/test-driven-development-with-python-testcontainers-and-pytest/)
- [Pytest and Testcontainers](https://mariogarcia.github.io/blog/2019/10/pytest_fixtures.html)
- [Using Testcontainers with Pytest: Isolate Data](https://qxf2.com/blog/using-testcontainers-with-pytest/)
- [pytest-docker-compose · PyPI](https://pypi.org/project/pytest-docker-compose/)

### Best Practices & Patterns
- [Testcontainers Best Practices for .NET](https://www.milanjovanovic.tech/blog/testcontainers-best-practices-dotnet-integration-testing)
- [How to Write Integration Tests for Rust APIs with Testcontainers](https://oneuptime.com/blog/post/2026-01-07-rust-testcontainers/view)
- [Integration Testing with Testcontainers](https://devblogs.microsoft.com/ise/testing-with-testcontainers/)
- [The Ultimate Guide to Integration Testing with Docker-Compose](https://medium.com/swlh/the-ultimate-guide-to-integration-testing-with-docker-compose-and-sql-f288f05032c9)
- [Docker Compose for Integration Testing: A Practical Guide](https://medium.com/@alexandre.therrien3/docker-compose-for-integration-testing-a-practical-guide-for-any-project-49b361a52f8c)

### Test Data & Cleanup
- [Integration Testing with Real Databases Using Testcontainers](https://dev.to/imdj/integration-testing-with-real-databases-using-testcontainers-2k62)
- [Integration tests with docker-compose](https://atlasgo.io/guides/testing/docker-compose)
- [pytest-docker · PyPI](https://pypi.org/project/pytest-docker/)

### Anti-Patterns
- [Docker Anti Patterns](https://codefresh.io/blog/docker-anti-patterns/)
- [7 Docker Anti-Patterns You Need to Avoid](https://www.howtogeek.com/devops/7-docker-anti-patterns-you-need-to-avoid/)
- [Container Anti-Patterns: Common Docker Mistakes](https://dev.to/idsulik/container-anti-patterns-common-docker-mistakes-and-how-to-avoid-them-4129)
- [Docker Container Anti-Patterns](https://www.couchbase.com/blog/docker-container-anti-patterns/)
- [Dockerfile Anti-Patterns and How to Avoid Them](https://medium.com/@harnesha22/dockerfile-anti-patterns-and-how-to-avoid-them-61e2c9e289e8)

### Performance & CI/CD
- [Running Parallel Tests in Docker](https://dzone.com/articles/running-parallel-tests-in-docker-1)
- [Parallel Testing in Software Testing Guide 2026](https://www.accelq.com/blog/parallel-testing/)
- [E2E-Testing in CI Environment With Testcontainers](https://dev.to/kirekov/e2e-testing-in-ci-environment-with-testcontainers-1403)
- [7 Ways to Improve Your Test Suite with Docker](https://www.cloudbees.com/blog/7-ways-to-improve-your-test-suite-with-docker)

---

*Researched: 2026-01-30*
*Confidence: HIGH (ecosystem standard patterns, multiple authoritative sources, recent 2025-2026 documentation)*
