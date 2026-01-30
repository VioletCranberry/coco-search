# Architecture Research: Docker Integration Testing

**Project:** CocoSearch
**Focus:** Integration test architecture alongside existing unit tests
**Researched:** 2026-01-30
**Overall Confidence:** HIGH

## Executive Summary

Docker integration tests should live in `tests/integration/` alongside existing `tests/unit/`, using pytest markers for selective execution and session-scoped fixtures for container lifecycle management. Docker Compose profiles enable a single compose file for dev, testing, and CI with different service combinations. This architecture preserves existing unit test isolation while adding real-environment validation.

**Key Recommendation:** Use pytest-docker plugin + Docker Compose profiles + pytest markers for clean separation without duplicating configuration.

## Recommended Test Organization

### Directory Structure

```
tests/
├── conftest.py                    # Root-level shared fixtures (existing)
├── fixtures/                      # Shared fixture modules (existing)
│   ├── __init__.py
│   ├── db.py                      # Mock DB fixtures (existing)
│   ├── ollama.py                  # Mock Ollama fixtures (existing)
│   └── data.py                    # Test data (existing)
├── mocks/                         # Mock implementations (existing)
│   ├── db.py
│   └── ollama.py
├── unit/                          # NEW: Unit tests with mocks (move existing)
│   ├── conftest.py                # Unit-specific fixtures
│   ├── indexer/
│   ├── search/
│   ├── management/
│   ├── mcp/
│   └── test_*.py
└── integration/                   # NEW: Integration tests with Docker
    ├── conftest.py                # Docker fixtures (pytest-docker integration)
    ├── docker-compose.yml         # Test-specific compose config
    ├── test_postgres_integration.py
    ├── test_ollama_integration.py
    └── test_full_flow_integration.py
```

**Rationale:**
- Clear separation enables running fast unit tests without Docker overhead
- Hierarchical conftest.py files allow shared and specialized fixtures
- Existing fixtures remain available throughout (pytest discovers parent conftest.py)
- Integration tests can import/reuse test data from `tests/fixtures/data.py`

**Sources:**
- [Pytest Good Integration Practices](https://docs.pytest.org/en/7.1.x/explanation/goodpractices.html) - Directory structure recommendations
- [5 Best Practices for Organizing Tests](https://pytest-with-eric.com/pytest-best-practices/pytest-organize-tests/) - Separation patterns
- [How to Keep Unit and Integration Tests Separate](https://www.pythontutorials.net/blog/how-to-keep-unit-tests-and-integrations-tests-separate-in-pytest/) - Marker and directory strategies

### Pytest Markers Configuration

Add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "unit: Fast unit tests with mocked dependencies (default)",
    "integration: Slower integration tests with Docker containers",
    "postgres: Integration tests requiring PostgreSQL",
    "ollama: Integration tests requiring Ollama embeddings",
    "slow: Tests that take >10 seconds (skip in pre-commit)",
]
```

**Usage patterns:**
```bash
# Fast feedback during development (unit tests only)
pytest -m unit                      # ~2-5 seconds

# Full validation before commit (unit + integration)
pytest                              # All tests, ~30-60 seconds

# Skip slow integration tests in pre-commit hooks
pytest -m "not slow"                # Unit + fast integration

# CI runs everything
pytest --verbose                    # Full suite with detailed output

# Specific integration test category
pytest -m postgres                  # Only PostgreSQL integration tests
```

**Rationale:**
- Markers provide flexibility beyond directory structure
- Can combine markers: `@pytest.mark.integration @pytest.mark.postgres @pytest.mark.slow`
- CI can run all, developers can skip slow tests during iteration
- Registration in pyproject.toml prevents warnings

**Sources:**
- [Ultimate Guide to Pytest Markers](https://pytest-with-eric.com/pytest-best-practices/pytest-markers/) - Marker patterns
- [Pytest Markers Documentation](https://docs.pytest.org/en/stable/how-to/skipping.html) - Skip and selection
- [pytest-skip-slow plugin](https://github.com/okken/pytest-skip-slow) - Skipping slow tests pattern

## Docker Compose Strategy

### Single File with Profiles (Recommended)

**Location:** Root `docker-compose.yml` (enhance existing)

```yaml
services:
  # Core service - always runs (dev + test + CI)
  db:
    image: pgvector/pgvector:pg17
    container_name: cocosearch-db
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: cocoindex
      POSTGRES_PASSWORD: cocoindex
      POSTGRES_DB: cocoindex
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cocoindex -d cocoindex"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  # Optional: Dockerized Ollama (test profile only)
  ollama:
    image: ollama/ollama:latest
    container_name: cocosearch-ollama
    profiles: [test, ollama-docker]  # Only start when profile active
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  ollama_data:
```

**Activation examples:**
```bash
# Development: PostgreSQL only (existing workflow)
docker compose up -d

# Integration tests: PostgreSQL + Ollama (if not using native)
docker compose --profile test up -d

# Explicit Ollama Docker usage
docker compose --profile ollama-docker up -d

# CI: Start containers, let pytest-docker manage lifecycle
# (CI just ensures Docker is available; pytest-docker handles up/down)
```

**Rationale:**
- Single source of truth prevents config drift
- Profiles avoid "separate file proliferation" (docker-compose.test.yml, docker-compose.dev.yml, etc.)
- Core services (db) always available for development
- Optional services (dockerized Ollama) only when needed
- Healthchecks ensure containers are ready before tests run
- pytest-docker respects existing compose files

**Alternative Approach (Not Recommended):**
Separate `tests/integration/docker-compose.yml` could be used if integration test containers differ significantly from dev environment. However, this creates duplication and configuration drift risk.

**Sources:**
- [Docker Compose Profiles Official Docs](https://docs.docker.com/compose/how-tos/profiles/) - Profile activation patterns
- [Leveraging Compose Profiles for Environments](https://collabnix.com/leveraging-compose-profiles-for-dev-prod-test-and-staging-environments/) - Multi-environment patterns
- [Managing Environment Configs with Profiles](https://oneuptime.com/blog/post/2025-11-27-manage-docker-compose-profiles/view) - Best practices

## Fixture Architecture

### Session-Scoped Docker Fixtures

**Pattern:** Use pytest-docker plugin for automatic lifecycle management

**Add to `tests/integration/conftest.py`:**

```python
"""Integration test fixtures for Docker containers."""

import pytest
from pathlib import Path

# pytest-docker configuration fixtures
@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    """Point to root docker-compose.yml."""
    return Path(pytestconfig.rootdir) / "docker-compose.yml"

@pytest.fixture(scope="session")
def docker_compose_project_name():
    """Use fixed name for easier debugging."""
    return "cocosearch-integration-tests"

@pytest.fixture(scope="session")
def docker_setup():
    """Start containers with --wait for healthchecks."""
    return ["up --build --wait"]

@pytest.fixture(scope="session")
def docker_cleanup():
    """Clean up containers and volumes after tests."""
    return ["down -v"]

# Service readiness fixtures
@pytest.fixture(scope="session")
def postgres_service(docker_ip, docker_services):
    """Ensure PostgreSQL is ready and return connection details."""
    port = docker_services.port_for("db", 5432)

    # Wait until PostgreSQL accepts connections
    docker_services.wait_until_responsive(
        timeout=30.0,
        pause=0.5,
        check=lambda: is_postgres_responsive(docker_ip, port),
    )

    return {
        "host": docker_ip,
        "port": port,
        "user": "cocoindex",
        "password": "cocoindex",
        "database": "cocoindex",
    }

@pytest.fixture(scope="session")
def ollama_service(docker_ip, docker_services):
    """Ensure Ollama is ready if using Docker profile."""
    # This fixture only runs for tests marked with @pytest.mark.ollama
    # If native Ollama is running, tests won't use this fixture
    port = docker_services.port_for("ollama", 11434)

    docker_services.wait_until_responsive(
        timeout=60.0,  # Ollama takes longer to start
        pause=1.0,
        check=lambda: is_ollama_responsive(docker_ip, port),
    )

    return {
        "host": docker_ip,
        "port": port,
        "base_url": f"http://{docker_ip}:{port}",
    }

def is_postgres_responsive(host, port):
    """Check if PostgreSQL accepts connections."""
    import psycopg
    try:
        conn = psycopg.connect(
            host=host, port=port,
            user="cocoindex", password="cocoindex",
            dbname="cocoindex",
            connect_timeout=3
        )
        conn.close()
        return True
    except Exception:
        return False

def is_ollama_responsive(host, port):
    """Check if Ollama API responds."""
    import httpx
    try:
        response = httpx.get(f"http://{host}:{port}/api/tags", timeout=3.0)
        return response.status_code == 200
    except Exception:
        return False
```

**Rationale:**
- Session scope minimizes container startup overhead (once per test run)
- pytest-docker handles lifecycle automatically (up before tests, down after)
- `wait_until_responsive` prevents test failures from race conditions
- `is_*_responsive` functions use actual connections, not just port checks
- Fixtures return connection details, not containers themselves
- Tests import these fixtures to ensure containers are ready

**Function-Scoped Cleanup Fixtures:**

For tests that modify database state:

```python
@pytest.fixture
def clean_postgres_db(postgres_service):
    """Clean database before each test."""
    # Setup: clear all data
    conn = psycopg.connect(**postgres_service)
    cursor = conn.cursor()
    cursor.execute("DROP SCHEMA IF EXISTS public CASCADE")
    cursor.execute("CREATE SCHEMA public")
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()
    conn.close()

    yield postgres_service

    # Teardown: could clean again if needed, but usually not necessary
```

**Sources:**
- [pytest-docker GitHub](https://github.com/avast/pytest-docker) - Plugin usage and fixture examples
- [Pytest Fixture Scopes Official Docs](https://docs.pytest.org/en/stable/how-to/fixtures.html) - Session vs function scope
- [Managing Containers with Pytest Fixtures](https://blog.oddbit.com/post/2023-07-15-pytest-and-containers/) - Lifecycle patterns

## Integration Points

### With Existing Unit Tests

**Preserved Isolation:**
- Unit tests continue using mocks (no Docker dependency)
- Unit tests remain fast (<5 seconds for full suite)
- Existing conftest.py fixtures remain available to all tests

**Shared Resources:**
- Test data fixtures in `tests/fixtures/data.py` used by both
- Utility functions can be shared
- Mocks still useful for integration test edge cases

**Migration Path:**
1. Move existing tests to `tests/unit/` directory (Phase 1)
2. Add pytest markers to existing tests: `@pytest.mark.unit` (Phase 1)
3. Create `tests/integration/` structure (Phase 2)
4. Add pytest-docker fixtures (Phase 2)
5. Write integration tests incrementally (Phase 3)

**No Breaking Changes:**
- `pytest` still runs all tests
- Existing test commands work unchanged
- CI can adopt integration tests gradually

### With CI/CD

**GitHub Actions Example:**

```yaml
name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Run unit tests
        run: |
          uv sync --all-groups
          uv run pytest -m unit --verbose

  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Start Docker containers
        run: docker compose up -d --wait
      - name: Run integration tests
        run: |
          uv sync --all-groups
          uv run pytest -m integration --verbose
      - name: Cleanup containers
        if: always()
        run: docker compose down -v
```

**Rationale:**
- Separate jobs allow parallel execution (faster CI)
- Unit tests run without Docker overhead
- Integration tests use Docker Compose (not pytest-docker in CI)
- `--wait` flag respects healthchecks (containers ready before pytest)
- `if: always()` ensures cleanup even if tests fail
- Can add test result caching, coverage reports later

**Alternative (Single Job):**
```yaml
integration-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: astral-sh/setup-uv@v5
    - name: Install pytest-docker
      run: uv add --dev pytest-docker
    - name: Run all tests
      run: uv run pytest --verbose  # pytest-docker manages containers
```

Simpler but slower (containers start/stop per test run).

**Sources:**
- [Pytest GitHub Actions Integration](https://pytest-with-eric.com/integrations/pytest-github-actions/) - CI patterns (edited 2026-01-22)
- [Setup Docker for Integration Testing in GitHub Actions](https://dev.to/sahanonp/setup-docker-for-integration-testing-in-github-action-39fn) - Workflow examples
- [pytest-docker-compose Actions](https://github.com/pytest-docker-compose/pytest-docker-compose/actions) - Real-world CI configs

## Comparison: pytest-docker vs testcontainers

### pytest-docker (Recommended for CocoSearch)

**Pros:**
- Leverages existing docker-compose.yml (no duplication)
- Simple pytest integration (just fixtures)
- Works with existing healthchecks
- Session scope minimizes overhead
- Team already familiar with Docker Compose

**Cons:**
- Less dynamic (can't easily create containers per test)
- Tied to Docker Compose (not just Docker API)

**Best for:** Projects with stable infrastructure needs where docker-compose already exists for development.

### testcontainers-python (Alternative)

**Pros:**
- Full control from Python code
- Can create containers dynamically per test
- Built-in wait strategies for many services
- Language-agnostic (Java, Python, Go, etc.)

**Cons:**
- Requires code changes beyond tests
- Longer test execution (containers per test or test class)
- Duplicates infrastructure config (not DRY)
- Another abstraction layer to learn

**Best for:** Projects needing dynamic test infrastructure or testing multiple DB versions.

### Decision for CocoSearch

**Use pytest-docker** because:
1. docker-compose.yml already exists and maintained
2. Infrastructure needs are stable (PostgreSQL + optional Ollama)
3. Session scope sufficient (don't need per-test isolation)
4. Team familiarity with Compose
5. Simpler mental model (compose file = all infrastructure)

**Sources:**
- [Python Integration Tests: docker-compose vs testcontainers](https://medium.com/codex/python-integration-tests-docker-compose-vs-testcontainers-94986d7547ce) - Detailed comparison
- [Testcontainers Python GitHub](https://github.com/testcontainers/testcontainers-python) - API and patterns

## Build Order

Recommended implementation sequence balancing risk and value.

### Phase 1: Reorganize Existing Tests (Low Risk)

**Goal:** Separate unit/integration without breaking anything

**Tasks:**
1. Create `tests/unit/` directory
2. Move existing test files to `tests/unit/` (preserve structure)
3. Add pytest markers to existing tests: `@pytest.mark.unit`
4. Update `pyproject.toml` to register markers
5. Verify `pytest` and `pytest -m unit` produce same results
6. Update CI to use markers (no functional change yet)

**Validation:**
- All existing tests pass
- No new dependencies
- CI passes unchanged

**Estimated effort:** 2-4 hours

**Risk:** LOW (mechanical refactoring)

### Phase 2: Add Docker Infrastructure (Medium Risk)

**Goal:** Enable Docker-based testing without writing integration tests yet

**Tasks:**
1. Add pytest-docker to dev dependencies: `uv add --dev pytest-docker`
2. Enhance root `docker-compose.yml` with Ollama service + test profile
3. Create `tests/integration/conftest.py` with Docker fixtures
4. Create empty `tests/integration/` directory structure
5. Write fixture test: `test_docker_fixtures.py` (validates containers start/stop)
6. Document Docker setup in development guide

**Validation:**
- `pytest tests/integration/test_docker_fixtures.py` passes
- Containers start with healthchecks
- Containers clean up after tests
- No interference with unit tests

**Estimated effort:** 4-8 hours

**Risk:** MEDIUM (new infrastructure, potential Docker issues)

**Dependencies:** Docker installed locally + in CI

### Phase 3: PostgreSQL Integration Tests (Medium Risk)

**Goal:** Validate database operations with real PostgreSQL

**Tasks:**
1. Write `test_postgres_integration.py`:
   - Test schema creation (extensions, tables)
   - Test index storage (write chunks, verify persistence)
   - Test vector search (insert, search, verify results)
   - Test index management (clear, stats)
2. Create `clean_postgres_db` fixture for test isolation
3. Add `@pytest.mark.postgres @pytest.mark.integration` to tests
4. Update CI to run PostgreSQL integration tests

**Validation:**
- Tests pass with real PostgreSQL
- Tests isolated (no state leakage)
- CI runs PostgreSQL tests successfully
- Unit tests still fast (unaffected)

**Estimated effort:** 8-12 hours

**Risk:** MEDIUM (real DB adds complexity, timing issues)

### Phase 4: Ollama Integration Tests (High Risk)

**Goal:** Validate embedding generation with real Ollama

**Tasks:**
1. Write `test_ollama_integration.py`:
   - Test embedding generation (text -> vector)
   - Test model availability checks
   - Test error handling (model not loaded, service down)
2. Add fixture to pull nomic-embed-text model if missing
3. Add `@pytest.mark.ollama @pytest.mark.slow` markers
4. Support both native and Docker Ollama (env var toggle)
5. Update CI to use Docker Ollama or skip Ollama tests

**Validation:**
- Tests pass with real embeddings
- Tests skip gracefully if Ollama unavailable
- CI strategy defined (Docker Ollama or skip)

**Estimated effort:** 6-10 hours

**Risk:** HIGH (Ollama slow to start, large model downloads, CI complexity)

**Note:** May decide to keep Ollama mocked in CI (download cost/time) while supporting local integration testing.

### Phase 5: Full Flow Integration Tests (Low-Medium Risk)

**Goal:** End-to-end validation of index -> search workflow

**Tasks:**
1. Write `test_full_flow_integration.py`:
   - Index a real codebase (tests/fixtures/sample_project/)
   - Search with natural language queries
   - Verify returned chunks match expected files
   - Test incremental indexing (add file, reindex, search)
   - Test DevOps file handling (Terraform, Dockerfile, Bash)
2. Add `@pytest.mark.integration @pytest.mark.slow` markers
3. Create fixture sample codebase with diverse languages

**Validation:**
- Full workflow works end-to-end
- Results match expected behavior
- Incremental indexing detected correctly
- DevOps metadata extracted properly

**Estimated effort:** 8-12 hours

**Risk:** MEDIUM (complex test, many moving parts, but builds on previous phases)

### Summary: Total Estimated Effort

**Total:** 28-46 hours (3.5-5.75 working days)

**Critical path:** Phase 1 → Phase 2 → Phase 3 → Phase 5 (PostgreSQL must work before full flow)

**Parallel work:** Phase 4 (Ollama) can be developed alongside Phase 3 or after Phase 5

**De-risk strategy:** Phases 1-2 establish foundation with minimal breaking changes. Phase 3 proves Docker integration works. Phases 4-5 add comprehensive coverage.

## Key Architectural Decisions Summary

| Decision | Rationale |
|----------|-----------|
| Separate `tests/unit/` and `tests/integration/` | Clear separation, enables fast unit tests without Docker |
| pytest markers in addition to directories | Flexible test selection, CI can combine filters |
| pytest-docker over testcontainers | Leverages existing docker-compose.yml, simpler model |
| Session-scoped fixtures | Minimize container overhead, tests share infrastructure |
| Docker Compose profiles over separate files | Single source of truth, prevents config drift |
| Root conftest.py + directory-specific conftest.py | Hierarchical fixture organization, shared + specialized |
| Healthchecks + wait_until_responsive | Prevent race conditions, reliable test startup |
| Optional Docker Ollama via profile | Supports both native and Docker workflows |
| CI runs unit and integration separately | Faster feedback, parallel execution |
| Incremental adoption (5 phases) | De-risk changes, validate at each step |

## Anti-Patterns to Avoid

### Don't: Mix Docker and Mocks in Same Test

**Why:** Confusing, defeats purpose of integration testing

**Instead:** Integration tests use real services, unit tests use mocks exclusively

### Don't: Function-Scoped Docker Fixtures by Default

**Why:** Slow (containers restart per test), unnecessary overhead

**Instead:** Session scope for containers, function scope only for data cleanup

### Don't: Skip Healthchecks

**Why:** Race conditions (tests start before services ready)

**Instead:** Always use healthchecks + wait_until_responsive

### Don't: Separate docker-compose.test.yml

**Why:** Configuration drift, duplication, maintenance burden

**Instead:** Use profiles in single docker-compose.yml

### Don't: Commit Running Containers in CI

**Why:** Resource leaks, port conflicts in subsequent runs

**Instead:** Always `docker compose down -v` in cleanup step with `if: always()`

### Don't: Rely on pytest-docker in CI (Debatable)

**Why:** Extra abstraction, harder to debug CI failures

**Instead:** Let CI start containers explicitly, pytest just runs tests

**Alternative view:** pytest-docker in CI is fine if it works reliably

## Confidence Assessment

| Area | Confidence | Source Quality |
|------|------------|----------------|
| Test directory structure | HIGH | Official pytest docs + multiple credible sources |
| Pytest markers | HIGH | Official pytest docs + community best practices |
| Docker Compose profiles | HIGH | Official Docker docs + 2025-2026 articles |
| pytest-docker vs testcontainers | MEDIUM | Community comparison articles (2020-2024) |
| Fixture scoping | HIGH | Official pytest docs + plugin docs |
| CI/CD patterns | MEDIUM | GitHub Actions examples + community articles |
| Build order | MEDIUM | Based on CocoSearch architecture + general best practices |

**Gaps identified:**
- No 2026-specific pytest-docker updates found (plugin stable since 2020)
- Limited examples of pytest + Docker Compose profiles together (pattern is new)
- Ollama Docker healthcheck reliability unknown (may need custom wait logic)

## Recommended Next Steps

1. **Review this architecture** with team/stakeholder
2. **Validate Docker setup** on development machine (docker-compose.yml enhancements)
3. **Start with Phase 1** (reorganize tests) - lowest risk, immediate clarity
4. **Prototype Phase 2** (Docker fixtures) in spike branch - validate pytest-docker works with existing setup
5. **Decide on Ollama strategy** - Docker vs native vs mocked in CI
6. **Create roadmap phases** based on this research

---

**Sources:**

*Test Organization:*
- [Pytest Good Integration Practices](https://docs.pytest.org/en/7.1.x/explanation/goodpractices.html)
- [5 Best Practices for Organizing Tests | Pytest with Eric](https://pytest-with-eric.com/pytest-best-practices/pytest-organize-tests/)
- [How to Keep Unit and Integration Tests Separate | Python Tutorials](https://www.pythontutorials.net/blog/how-to-keep-unit-tests-and-integrations-tests-separate-in-pytest/)
- [Pytest Conftest.py Hierarchy | Pytest with Eric](https://pytest-with-eric.com/pytest-best-practices/pytest-conftest/)

*Docker Integration:*
- [pytest-docker GitHub](https://github.com/avast/pytest-docker)
- [pytest-docker-compose GitHub](https://github.com/pytest-docker-compose/pytest-docker-compose)
- [Building Resilient API Test Automation: Pytest + Docker Integration | Medium](https://manishsaini74.medium.com/building-resilient-api-test-automation-pytest-docker-integration-guide-9710359b6d9b)
- [Integration Testing with Pytest & Docker Compose | Medium](https://xnuinside.medium.com/integration-testing-for-bunch-of-services-with-pytest-docker-compose-4892668f9cba)

*Docker Compose Patterns:*
- [Docker Compose Profiles Official Docs](https://docs.docker.com/compose/how-tos/profiles/)
- [Leveraging Compose Profiles for Environments | Collabnix](https://collabnix.com/leveraging-compose-profiles-for-dev-prod-test-and-staging-environments/)
- [Managing Environment Configs with Docker Compose Profiles | OneUptime](https://oneuptime.com/blog/post/2025-11-27-manage-docker-compose-profiles/view)

*Fixture Patterns:*
- [Pytest Fixture Scopes Official Docs](https://docs.pytest.org/en/stable/how-to/fixtures.html)
- [Managing Containers with Pytest Fixtures | blog.oddbit.com](https://blog.oddbit.com/post/2023-07-15-pytest-and-containers/)
- [Testcontainers in Python | Medium](https://medium.com/@kandemirozenc/testcontainers-in-python-for-integration-testing-with-mysql-63160a004fb5)

*CI/CD:*
- [Pytest GitHub Actions Integration | Pytest with Eric](https://pytest-with-eric.com/integrations/pytest-github-actions/)
- [Setup Docker for Integration Testing in GitHub Actions | DEV](https://dev.to/sahanonp/setup-docker-for-integration-testing-in-github-action-39fn)
- [Speed up pytest GitHub Actions with Docker | Towards Data Science](https://towardsdatascience.com/speed-up-your-pytest-github-actions-with-docker-6b3a85b943f/)

*Comparison & Strategy:*
- [Python Integration Tests: docker-compose vs testcontainers | Medium](https://medium.com/codex/python-integration-tests-docker-compose-vs-testcontainers-94986d7547ce)
- [Ultimate Guide to Pytest Markers | Pytest with Eric](https://pytest-with-eric.com/pytest-best-practices/pytest-markers/)
- [pytest-skip-slow plugin](https://github.com/okken/pytest-skip-slow)

---

*Researched: 2026-01-30*
