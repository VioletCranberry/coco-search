# Pitfalls Research: Docker Integration Testing

**Domain:** Adding Docker-based integration tests to Python pytest project
**Project Context:** CocoSearch (PostgreSQL+pgvector, Ollama, UV package manager, existing mocked tests)
**Researched:** 2026-01-30
**Milestone:** v1.3 -- Docker Integration Tests & Infrastructure
**Confidence:** MEDIUM-HIGH

---

## Critical Pitfalls

These mistakes cause test failures, rewrites, or major integration issues.

### Pitfall 1: Fixture Scope Mixing Causes Container Conflicts

**What goes wrong:**
Using module-scoped and function-scoped Docker fixtures in the same test file causes Docker Compose to fail. The module-scoped fixture spins up containers once, then function-scoped fixtures attempt to spin up the same containers again, which Docker Compose does not allow.

**Why it happens:**
- Different fixture scopes try to manage the same Docker Compose services simultaneously
- Developers often create function-scoped database cleanup fixtures without realizing the underlying containers are module-scoped
- pytest-docker-compose and similar plugins enforce exclusive container ownership per scope
- Module scope starts containers once per test file, function scope expects to start/stop per test

**Warning signs:**
- Error: "service already exists" from Docker Compose
- Containers fail to start on second test in a module
- Test failures only occur when running multiple tests together, not in isolation
- Docker ps shows multiple containers with similar names

**Prevention:**
- Use session or module scope for container lifecycle (startup/teardown)
- Use function scope only for data cleanup within already-running containers
- Document fixture scope decisions in conftest.py comments
- Never mix fixture scopes for the same Docker Compose service
- Create separate conftest.py for unit (mocks) vs integration (containers)

**Phase:** Phase 1 (Test infrastructure setup)

**CocoSearch specific:**
Project has 327 existing unit tests with mocks in `tests/fixtures/db.py` and `tests/fixtures/ollama.py`. New Docker fixtures must use distinct names and live in separate conftest.

**Sources:**
- [pytest-docker-compose scope management](https://github.com/pytest-docker-compose/pytest-docker-compose)
- [Integration testing with Docker compose](https://xnuinside.medium.com/integration-testing-for-bunch-of-services-with-pytest-docker-compose-4892668f9cba)

---

### Pitfall 2: Ollama Model Loading Timeout on First Test Run

**What goes wrong:**
First Ollama embedding request in Docker takes 30+ seconds, causing test timeouts. Subsequent requests complete in ~3 seconds once the model is loaded into memory. Tests fail with timeout errors on first run, then pass on re-run.

**Why it happens:**
- Ollama needs to load the embedding model (nomic-embed-text) into GPU/system memory on first use
- In Docker containers, this is compounded by container initialization overhead
- Default test timeouts (often 5-10 seconds) are too short for model loading
- Issue confirmed in recent GitHub issue (Jan 2026): 30s first load, 3s subsequent on RTX 6000

**Warning signs:**
- First test in suite times out, subsequent tests pass
- Tests pass when run individually, fail in full suite
- Logs show "loading model..." message just before timeout
- Tests work locally but timeout in CI with shorter timeouts

**Prevention:**
- Set `OLLAMA_KEEP_ALIVE=-1` environment variable to keep model loaded indefinitely
- Increase test timeout for embedding operations (60+ seconds minimum)
- Add warmup fixture that loads model once before tests run:
  ```python
  @pytest.fixture(scope="session")
  def warmup_ollama(docker_ollama):
      # Trigger model load before any tests
      generate_embedding("warmup query")
  ```
- Use module/session scope for Ollama container to prevent restarts
- Consider pre-pulling Ollama model in Docker image build stage
- Document expected first-run delay in test README

**Phase:** Phase 2 (Ollama integration tests)

**CocoSearch specific:**
Project uses Ollama for nomic-embed-text embeddings. Every integration test will hit this. Critical for CI/CD pipeline where timeouts are strict.

**Sources:**
- [Ollama Docker slow startup Issue #13627](https://github.com/ollama/ollama/issues/13627) (Jan 2026)
- [Integration Testing with Ollama and TestContainers](https://dzone.com/articles/ai-prompt-testing-ollama-spring-testcontainers)
- [Ollama Docker performance optimization](https://www.databasemart.com/kb/how-to-speed-up-ollama-performance)

---

### Pitfall 3: CI vs Local Network Access Differences

**What goes wrong:**
Tests access `localhost:5432` successfully on developer machines but fail in CI with "connection refused." In CI, tests may run inside Docker network and need to access containers by name (`cocosearch-db:5432`) instead of localhost.

**Why it happens:**
- On dev machines, tests run on host and connect to port-mapped containers via localhost
- In CI (GitHub Actions, etc.), tests may run in a container on the same Docker network
- Port mappings only work from host → container, not container → container
- Container-to-container communication requires using service names, not localhost
- Different environments require different connection strings

**Warning signs:**
- Tests pass locally, fail in CI with network/connection errors
- Error messages show "localhost refused connection" in CI logs
- Switching to container name fixes CI but breaks local tests
- Environment-specific connection string hacks scattered in test code
- `docker network inspect` shows tests on different network than services

**Prevention:**
- Detect environment (CI vs local) and use appropriate hostname:
  ```python
  def get_test_db_host():
      return os.getenv("DB_HOST", "localhost")
  ```
- Use environment variable for database host: `DB_HOST=${DB_HOST:-localhost}`
- In CI workflow, set: `DB_HOST=cocosearch-db` and `OLLAMA_HOST=http://ollama:11434`
- Document in README: "Set DB_HOST=cocosearch-db in CI environment"
- Consider using pytest-docker-tools' `get_addr()` helper for automatic resolution
- Test both modes locally using Docker-in-Docker

**Phase:** Phase 1 (Test infrastructure setup) and Phase 3 (CI integration)

**CocoSearch specific:**
Affects both PostgreSQL connection (port 5432) and Ollama connection (port 11434). UV package manager doesn't change this behavior.

**Sources:**
- [pytest-docker-tools get_addr helper](https://github.com/Jc2k/pytest-docker-tools)
- [Docker container port binding in GitHub Actions](https://community.latenode.com/t/docker-container-port-binding-issues-in-github-actions-but-works-locally/26221)
- [pytest-docker network handling](https://github.com/avast/pytest-docker)

---

### Pitfall 4: Database State Pollution Between Tests

**What goes wrong:**
Tests share database state across runs. One test creates chunks and embeddings, subsequent tests see those records and fail with unexpected data, duplicate key violations, or wrong result counts. Tests pass individually but fail when run together.

**Why it happens:**
- Containers persist between tests for performance (avoiding slow startup)
- Database isn't automatically cleaned between tests
- Developers assume fresh state without implementing cleanup
- PostgreSQL with persistent volume retains all data
- Connection pool singleton persists state across tests

**Warning signs:**
- Test order matters - tests pass in isolation, fail in suite
- "Duplicate key" or "already exists" errors in later tests
- Unexpected row counts or query results (e.g., expected 3 chunks, got 47)
- Tests fail on second run but pass on first run after container restart
- `SELECT count(*) FROM chunks` shows accumulating rows

**Prevention:**
- Implement database cleanup fixture (function scope):
  ```python
  @pytest.fixture(autouse=True)
  def cleanup_database(db_connection):
      yield
      # Teardown: clean all tables
      db_connection.execute("TRUNCATE chunks CASCADE;")
      db_connection.execute("DELETE FROM cocoindex_internal_state;")
  ```
- Use transaction rollback pattern for isolation
- Create new database per test (slower but complete isolation)
- Use factory functions for test data, not shared fixtures
- Document cleanup strategy in conftest.py
- Add assertion to verify clean state at test start

**Phase:** Phase 1 (Test infrastructure setup)

**CocoSearch specific:**
PostgreSQL+pgvector tables include chunks table with vector column and CocoIndex internal state tables. Must handle both application tables and CocoIndex metadata.

**Sources:**
- [Cleaning PostgreSQL DB between Integration Tests](https://carbonhealth.com/blog-post/cleaning-postgresql-db-between-integration-tests-efficiently)
- [Testcontainers data pollution discussion](https://github.com/testcontainers/testcontainers-java/discussions/4845)
- [Database testing with fixtures and seeding](https://neon.com/blog/database-testing-with-fixtures-and-seeding)

---

### Pitfall 5: GitHub Actions TTY Requirement Breaks Docker Exec

**What goes wrong:**
Running `docker-compose exec app pytest` works locally but fails in GitHub Actions with "the input device is not a TTY" error. Tests don't run at all in CI - Docker Compose starts successfully but pytest never executes.

**Why it happens:**
- `docker-compose exec` by default allocates a pseudo-TTY for interactive sessions
- TTY is available in local terminals but not in CI environments
- GitHub Actions runners don't provide TTY for exec commands
- The `-T` flag (disable TTY allocation) is required but non-obvious

**Warning signs:**
- Error message: "the input device is not a TTY"
- Tests run fine locally, completely fail to execute in CI
- CI logs show Docker Compose starts successfully but pytest never runs
- No test output or pytest summary appears in CI logs

**Prevention:**
- Always use `-T` flag in CI: `docker-compose exec -T app pytest`
- Create separate commands in Makefile:
  ```makefile
  test-local:
      docker-compose exec app pytest
  test-ci:
      docker-compose exec -T app pytest
  ```
- Or detect CI environment in scripts:
  ```bash
  if [ -n "$CI" ]; then
      docker-compose exec -T app pytest
  else
      docker-compose exec app pytest
  fi
  ```
- Document this in CI workflow comments
- Add to GitHub Actions workflow:
  ```yaml
  - name: Run integration tests
    run: docker-compose exec -T app pytest tests/integration
  ```

**Phase:** Phase 3 (CI integration)

**CocoSearch specific:**
Applies to running pytest inside containers. UV package manager doesn't affect this - it's purely a Docker exec issue.

**Sources:**
- [Running pytest in docker-compose with GitHub Actions](https://github.com/orgs/community/discussions/31737)
- [GitHub Actions Docker Compose orchestration](https://medium.com/@sreeprad99/from-ci-chaos-to-orchestration-deep-dive-into-github-actions-service-containers-and-docker-compose-7cb2ff335864)

---

### Pitfall 6: UV Package Manager Hardlink Mode Fails with Docker Volumes

**What goes wrong:**
`uv install` inside Docker container fails with errors about filesystem links or "cross-device link" when using volume mounts. Dependencies don't install correctly or appear missing despite successful install logs.

**Why it happens:**
- UV uses hardlinks by default for efficiency (shares files across installations)
- Docker volume mounts don't support hardlinks across host/container filesystem boundaries
- Attempting hardlink from container to host volume triggers EXDEV error
- UV defaults break in this scenario without explicit configuration
- The `.venv` directory mounted as volume is the trigger

**Warning signs:**
- Error messages about "cross-device link" or "operation not permitted" during install
- `uv install` fails in container but works on host
- `.venv` directory is mounted as volume in docker-compose.yml
- Dependencies appear missing despite successful install logs
- Import errors for packages that should be installed

**Prevention:**
- Set `UV_LINK_MODE=copy` environment variable in Docker:
  ```dockerfile
  ENV UV_LINK_MODE=copy
  ```
- Add to docker-compose.yml:
  ```yaml
  environment:
    - UV_LINK_MODE=copy
  ```
- OR exclude `.venv` from volume mounts entirely (let container create its own)
- Document this requirement in docker-compose.yml comments
- Consider multi-stage build: install deps in build stage with copy mode, copy to runtime
- Test dependency installation explicitly in Docker environment

**Phase:** Phase 1 (Test infrastructure setup)

**CocoSearch specific:**
Project uses UV package manager (not pip). This is critical for Docker-based testing to work at all. Must be configured before any tests can run.

**Sources:**
- [UV package management in Docker](https://medium.com/@shaliamekh/python-package-management-with-uv-for-dockerized-environments-f3d727795044)
- [Using uv in Docker - Official Docs](https://docs.astral.sh/uv/guides/integration/docker/)
- [UV Deep Dive](https://betterstack.com/community/guides/scaling-python/uv-explained/)

---

### Pitfall 7: Mocked vs Integration Fixture Name Collisions

**What goes wrong:**
Existing unit test mocks (`mock_db_pool`, `mock_ollama`) conflict with integration test fixtures that create real connections. Tests import wrong fixture and fail mysteriously, or worse, pass incorrectly using mocks when real services were intended.

**Why it happens:**
- pytest fixture discovery searches local scope first, then parent conftest.py files
- If unit and integration tests share conftest.py or use same fixture names, pytest picks the wrong one based on test file location
- CocoSearch has comprehensive mocking infrastructure in `tests/fixtures/db.py` and `tests/fixtures/ollama.py`
- Adding Docker fixtures with similar names creates ambiguity
- Fixture precedence rules are subtle and easy to misunderstand

**Warning signs:**
- Integration tests appear to succeed instantly (actually using mocks, not real services)
- Unit tests fail with "connection refused" (actually hitting real Docker services)
- Fixture behavior changes based on test file location
- Test results change when moving test files between directories
- Database queries in integration tests don't persist to real database

**Prevention:**
- Separate conftest.py by test type:
  - `tests/unit/conftest.py` - mock fixtures only
  - `tests/integration/conftest.py` - Docker container fixtures only
- Use distinct fixture names with clear prefixes:
  - Unit: `mock_db_pool`, `mock_ollama_client`
  - Integration: `real_db_pool`, `docker_db`, `docker_ollama`
- Document fixture scope and purpose in docstrings:
  ```python
  @pytest.fixture
  def docker_db():
      """INTEGRATION TEST ONLY: Real PostgreSQL in Docker."""
  ```
- Add pytest markers: `@pytest.mark.unit` vs `@pytest.mark.integration`
- Configure pytest.ini to separate test discovery paths
- Audit all fixtures for naming conflicts before adding Docker fixtures

**Phase:** Phase 1 (Test infrastructure setup)

**CocoSearch specific:**
Project has 327 existing unit tests with comprehensive mocks in `tests/fixtures/`. Must coexist with new integration tests without collision.

**Sources:**
- [Pytest conftest fixture conflicts](https://github.com/pytest-dev/pytest/issues/7053)
- [Modularizing pytest fixtures](https://gist.github.com/peterhurford/09f7dcda0ab04b95c026c60fa49c2a68)
- [Fixture discovery and organization](https://docs.pytest.org/en/stable/how-to/fixtures.html)

---

## Medium Priority Pitfalls

These cause delays, debugging pain, or technical debt.

### Pitfall 8: Connection Pool Not Closed Between Tests

**What goes wrong:**
Database connection pool accumulates connections across tests. Eventually hits PostgreSQL connection limit (default 100), causing "too many connections" errors late in test suite. Tests fail non-deterministically based on execution order.

**Why it happens:**
- Integration tests create real connection pools using psycopg ConnectionPool
- Without proper cleanup, pools persist between tests
- Connection pool singleton in application code (`_pool` in `cocosearch/search/db.py`) isn't reset
- Each test may create a new pool without closing the old one
- PostgreSQL's `max_connections` limit is eventually exhausted

**Warning signs:**
- Early tests pass, later tests fail with "too many connections"
- `SELECT count(*) FROM pg_stat_activity WHERE datname='cocoindex'` shows many IDLE connections
- Test suite failures are non-deterministic (depends on test count/order)
- Restarting PostgreSQL "fixes" the issue temporarily
- Connection count grows linearly with test count

**Prevention:**
- Add autouse fixture to close pools after each test:
  ```python
  @pytest.fixture(autouse=True)
  def cleanup_db_pool():
      yield
      from cocosearch.search.db import _pool
      if _pool:
          _pool.close()
          cocosearch.search.db._pool = None
  ```
- Explicitly call `pool.close()` in teardown
- Monitor connection count in tests: `SELECT count(*) FROM pg_stat_activity`
- Use smaller `max_connections` for test database to surface issues early
- Configure pool with `max_size=5` for tests (vs production values)

**Phase:** Phase 1 (Test infrastructure setup)

**CocoSearch specific:**
Project uses psycopg3 connection pool in `cocosearch/search/db.py`. Existing unit tests mock this with `reset_db_pool` fixture. Integration tests need real pool cleanup.

**Sources:**
- [Pytest mock resources connection management](https://pytest-mock-resources.readthedocs.io/en/latest/quickstart.html)
- [Testcontainers connection cleanup](https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/)

---

### Pitfall 9: pgvector Extension Not Enabled in Test Database

**What goes wrong:**
Integration tests fail with "type 'vector' does not exist" or "extension pgvector not found" errors. Vector similarity queries don't work. CocoIndex flow fails during setup phase.

**Why it happens:**
- pgvector extension must be explicitly enabled per database with `CREATE EXTENSION`
- The `pgvector/pgvector:pg17` Docker image includes the extension but doesn't enable it automatically
- CocoIndex expects the extension to already be enabled
- Default PostgreSQL initialization doesn't run extension creation

**Warning signs:**
- Error: `type "vector" does not exist` during table creation
- Error: `extension "pgvector" is not available`
- Vector queries fail but regular SQL queries work
- Manual `CREATE EXTENSION pgvector` in psql fixes it temporarily
- Tests fail immediately on first vector operation

**Prevention:**
- Add initialization script mounted to `/docker-entrypoint-initdb.d/`:
  ```sql
  -- init-pgvector.sql
  CREATE EXTENSION IF NOT EXISTS vector;
  ```
- Mount in docker-compose.yml:
  ```yaml
  volumes:
    - ./init-pgvector.sql:/docker-entrypoint-initdb.d/init-pgvector.sql
  ```
- OR run in test setup fixture (session scope):
  ```python
  @pytest.fixture(scope="session")
  def enable_pgvector(db_connection):
      db_connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
      db_connection.commit()
  ```
- Verify in test: `SELECT * FROM pg_extension WHERE extname='vector'`
- Document in docker-compose.yml comments and README

**Phase:** Phase 1 (Test infrastructure setup)

**CocoSearch specific:**
Project uses pgvector for 768-dimensional embeddings. Critical for all search-related integration tests. CocoIndex flow will fail immediately without this.

**Sources:**
- [Testcontainers pgvector module](https://testcontainers.com/modules/pgvector/)
- [Setting up PostgreSQL with pgvector in Docker](https://medium.com/@adarsh.ajay/setting-up-postgresql-with-pgvector-in-docker-a-step-by-step-guide-d4203f6456bd)
- [pgvector Docker Hub documentation](https://hub.docker.com/r/pgvector/pgvector)

---

### Pitfall 10: Test Data Schema Drift from Production

**What goes wrong:**
Integration tests create database schema manually in fixtures. Schema differs from application's actual schema over time. Tests pass but production queries fail, or vice versa. New columns added to production code aren't reflected in test setup.

**Why it happens:**
- No single source of truth for schema
- Tests recreate schema independently from application code
- Schema changes in CocoIndex or application code don't propagate to test setup
- Manual SQL in test fixtures gets out of sync with CocoIndex flow
- v1.2 added metadata columns (resource_type, block_type, hierarchy) that tests might miss

**Warning signs:**
- Tests pass but application fails with "column doesn't exist"
- New features break because test schema is outdated
- Manual schema sync required before writing new tests
- Multiple schema definitions scattered across codebase
- Integration test schema missing v1.2 metadata columns

**Prevention:**
- Use single schema source: CocoIndex flow initialization
- Initialize test database using same code path as production:
  ```python
  @pytest.fixture(scope="session")
  def test_db_schema(db_connection):
      # Use actual CocoIndex flow to create schema
      flow.setup()
  ```
- Version control schema initialization scripts if used
- Add schema verification test:
  ```python
  def test_schema_matches_production():
      # Verify all expected columns exist
      result = db.execute("""
          SELECT column_name FROM information_schema.columns
          WHERE table_name = 'chunks'
      """)
      assert 'resource_type' in columns  # v1.2 metadata
  ```
- Never create tables manually in tests - use CocoIndex flow

**Phase:** Phase 1 (Test infrastructure setup)

**CocoSearch specific:**
Schema includes vector column types (vector(768)) and v1.2 metadata columns. Must match CocoIndex expectations exactly. Let CocoIndex manage schema.

**Sources:**
- [pgvector schema migration limitations](https://docs.langchain.com/oss/python/integrations/vectorstores/pgvector)
- [Database testing with fixtures and seeding](https://neon.com/blog/database-testing-with-fixtures-and-seeding)

---

### Pitfall 11: Floating Point Similarity Score Assertions Fail Intermittently

**What goes wrong:**
Tests assert exact similarity scores (`assert score == 0.92`) but get values like `0.9199999...` or `0.920001`. Tests fail intermittently due to floating-point precision differences across systems or embedding runs.

**Why it happens:**
- Vector similarity calculations (cosine similarity, L2 distance) involve floating-point math
- Results aren't precisely reproducible across systems with different CPU architectures
- Ollama embeddings may have minor variance across runs
- Exact equality comparisons fail on tiny differences (0.0001)
- Different hardware (CI vs local) produces slightly different results

**Warning signs:**
- Test failures with score differences like 0.00001 or 0.0000001
- Failures more common in CI than locally (different CPU/architecture)
- Same test fails intermittently without code changes
- Error messages show values "almost equal" but not exactly: `0.92 != 0.9199999...`
- Tests fail after system upgrades or on different machines

**Prevention:**
- Use `pytest.approx()` for all floating-point comparisons:
  ```python
  assert score == pytest.approx(0.92, abs=0.01)  # tolerance of ±0.01
  ```
- Define acceptable tolerance based on use case:
  - Similarity scores: ±0.01 (1% tolerance)
  - Distance metrics: ±0.001
- Test score *ranges* not exact values:
  ```python
  assert 0.90 <= score <= 0.95
  ```
- Document expected precision in test docstrings
- Never use exact equality for floating-point: `score == 0.92` is wrong
- For embedding vectors, use `pytest.approx()` for array comparisons

**Phase:** Phase 2 (Search integration tests)

**CocoSearch specific:**
All search tests return similarity scores from pgvector cosine distance. Critical for result ranking tests and relevance assertions.

**Sources:**
- [Pytest approx for accurate numeric testing](https://pytest-with-eric.com/pytest-advanced/pytest-approx/)
- [Pytest approx for vectors and arrays](https://www.scivision.dev/pytest-approx-equal-assert-allclose/)
- [Measuring similarity in embeddings](https://www.dataquest.io/blog/measuring-similarity-and-distance-between-embeddings/)

---

### Pitfall 12: Docker Compose Build Cache Hides Dependency Changes

**What goes wrong:**
Developer updates `pyproject.toml` to add/update dependencies. Runs `docker-compose up`, tests fail with `ModuleNotFoundError` for the new dependency. Dependencies weren't actually updated in container because Docker cached the old layer.

**Why it happens:**
- Docker build cache persists layers to speed up builds
- If dependency installation layer is cached, new dependencies don't install
- `docker-compose up` doesn't rebuild by default (uses existing images)
- `pyproject.toml` changes don't automatically trigger rebuild
- UV caching adds another layer of complexity

**Warning signs:**
- "ModuleNotFoundError" for recently added dependencies
- Dependencies work after `docker-compose build --no-cache`
- Different behavior between "works on my machine" (older cache) and CI (fresh build)
- Deleting containers doesn't fix it (image still cached)
- `docker images` shows old image timestamp despite recent code changes

**Prevention:**
- Document rebuild requirement: "Run `docker-compose build` after dependency changes"
- Add to development workflow documentation
- Use `docker-compose up --build` to rebuild on startup
- In CI, always build fresh: `docker-compose build --no-cache`
- Add Makefile targets:
  ```makefile
  rebuild:
      docker-compose build --no-cache
  rebuild-fast:
      docker-compose build
  ```
- Watch for pyproject.toml changes in pre-commit hooks
- Add comment in pyproject.toml: "# After changes: run docker-compose build"

**Phase:** Phase 1 (Test infrastructure setup) and ongoing

**CocoSearch specific:**
Uses UV which has different caching than pip. Watch UV_LINK_MODE=copy layer caching. UV lockfile changes also require rebuild.

**Sources:**
- [Docker Compose build caching](https://docs.docker.com/compose/)
- [UV in Docker official guide](https://docs.astral.sh/uv/guides/integration/docker/)

---

### Pitfall 13: Test Execution Time Explodes Without Optimization

**What goes wrong:**
Integration test suite takes 10+ minutes to run sequentially. Each test waits for Docker operations, Ollama embeddings, database queries. Developers stop running full suite locally. CI becomes bottleneck.

**Why it happens:**
- Each test waits for Docker operations (container startup, DB queries, Ollama)
- Tests run one at a time by default (no parallelization)
- Startup costs (container initialization, model loading) repeated unnecessarily
- No session/module scoped fixtures for expensive setup
- Ollama embeddings are particularly slow (3+ seconds each)

**Warning signs:**
- Test suite takes >2 minutes for <20 tests
- Developers only run specific tests, not full suite: `pytest tests/integration/test_one.py`
- CI build time increases linearly with test count
- Tests spend most time waiting, not executing
- `pytest --durations=10` shows setup time dominating

**Prevention:**
- Use session/module scope for expensive setup:
  ```python
  @pytest.fixture(scope="session")
  def docker_services():
      # Start once for entire test session
  ```
- Parallelize with pytest-xdist: `pytest -n auto tests/integration`
- BUT: Ensure database isolation for parallel tests (separate test DBs per worker)
- Front-load slow tests with pytest-order
- Use pytest profiling to find bottlenecks: `pytest --durations=10`
- Implement warmup fixture for Ollama (session scope)
- Consider test categorization:
  - Fast integration tests: run always
  - Slow integration tests: run in CI only

**Phase:** Phase 3 (Optimization)

**CocoSearch specific:**
Ollama embeddings are slow (3+ seconds each, 30s first run). Parallelization requires careful handling of shared Ollama container. May need multiple Ollama instances for parallel workers.

**Sources:**
- [How to speed up pytest](https://buildpulse.io/blog/how-to-speed-up-pytest)
- [Optimizing test execution time with pytest](https://medium.com/@ayoubebounaga/optimizing-test-execution-time-with-pytest-from-bottlenecks-to-speed-gains-7cd9d2b4bca5)
- [13 proven ways to improve pytest runtime](https://pytest-with-eric.com/pytest-advanced/pytest-improve-runtime/)

---

## Low Priority Pitfalls

These cause annoyance but are easily fixable.

### Pitfall 14: Container Logs Hidden During Test Failures

**What goes wrong:**
Test fails with connection error or unexpected behavior. Developer can't see PostgreSQL or Ollama logs to diagnose. Must manually run `docker-compose logs` in separate terminal to debug.

**Why it happens:**
- pytest captures test output by default
- Docker container logs aren't automatically shown on test failure
- Debugging requires multiple terminal windows and manual commands
- No automatic correlation between test failure and service logs

**Warning signs:**
- Failures show only Python traceback, no service logs
- Developers ask "how do I see the database logs?"
- Debugging takes longer than writing tests
- Test failure reports in CI are incomplete
- Issue reproduction requires manual log inspection

**Prevention:**
- Capture container logs in test fixtures on failure:
  ```python
  @pytest.fixture
  def docker_logs(request):
      yield
      if hasattr(request.node, 'rep_call') and request.node.rep_call.failed:
          os.system("docker-compose logs --tail=50 db ollama")
  ```
- Use pytest-docker plugins that auto-capture logs
- Document logging commands in README:
  ```
  # View container logs
  docker-compose logs db
  docker-compose logs ollama
  docker-compose logs -f  # follow
  ```
- Add `--log-cli-level=DEBUG` to pytest.ini for verbose output
- In CI, always capture logs as artifacts on failure

**Phase:** Phase 1 (Test infrastructure setup)

**CocoSearch specific:**
Both PostgreSQL and Ollama logs are useful for debugging. Consider capturing both on failure. Ollama logs show model loading progress.

**Sources:**
- [pytest-docker log capture](https://github.com/avast/pytest-docker)
- [Testcontainers Python logging](https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/)

---

### Pitfall 15: No Convention for Skipping Integration Tests Locally

**What goes wrong:**
Developers don't realize integration tests can be skipped for rapid local development. Running full suite on every code change slows down TDD workflow. Unit tests (fast with mocks) and integration tests (slow with Docker) are mixed.

**Why it happens:**
- No convention for when to run integration vs unit tests
- All tests run by default with `pytest`
- Developers either run all tests (slow) or run nothing (risky)
- No clear documentation about test categories
- Integration tests marked same as unit tests

**Warning signs:**
- Developers complain about slow test feedback loop
- Integration tests run unnecessarily for changes to unrelated code
- Unit test coverage drops because full suite is too slow
- "I don't run tests locally anymore" comments in code reviews
- TDD workflow abandoned due to slow feedback

**Prevention:**
- Add pytest markers to integration tests:
  ```python
  @pytest.mark.integration
  def test_full_search_flow():
      ...
  ```
- Configure pytest.ini:
  ```ini
  markers =
      integration: Integration tests requiring Docker
      unit: Fast unit tests with mocks
  ```
- Skip integration by default locally: `pytest -m "not integration"`
- Run in CI: `pytest -m integration`
- OR use custom option:
  ```python
  # conftest.py
  def pytest_addoption(parser):
      parser.addoption("--integration", action="store_true")
  ```
- Document in README:
  ```
  # Fast unit tests only (local development)
  pytest -m "not integration"

  # All tests including integration (before commit)
  pytest

  # Integration tests only
  pytest -m integration
  ```
- Add to pre-commit hook: run unit tests only

**Phase:** Phase 1 (Test infrastructure setup)

**CocoSearch specific:**
327 existing unit tests should run fast (<10s) with mocks. Integration tests for end-to-end validation only. Clear separation needed.

**Sources:**
- [Pytest markers for skipping tests](https://docs.pytest.org/en/stable/how-to/skipping.html)
- [Pytest skip unless option given](https://jwodder.github.io/kbits/posts/pytest-mark-off/)
- [Working with custom markers](https://docs.pytest.org/en/stable/example/markers.html)

---

### Pitfall 16: Docker Compose Project Name Conflicts

**What goes wrong:**
Multiple developers or CI jobs on same machine conflict. Containers get name collisions like "container name already in use". Tests fail with strange state or connect to wrong database from another developer's session.

**Why it happens:**
- Docker Compose uses directory name as default project name
- Multiple checkouts of same repo share the same project name
- Multiple CI jobs running simultaneously on same runner conflict
- Stopped containers from previous runs still exist with same names
- No isolation between different test runs

**Warning signs:**
- Error: "container name already in use"
- Tests see data from other developer's tests or previous runs
- CI jobs interfere with each other on same runner
- Stopping containers in one terminal affects other terminal sessions
- `docker ps -a` shows duplicate container names

**Prevention:**
- Set unique project name in docker-compose.yml:
  ```yaml
  name: cocosearch-test-${USER:-default}
  ```
- OR use environment variable:
  ```bash
  export COMPOSE_PROJECT_NAME=cocosearch-test-$USER
  ```
- In CI, use job ID:
  ```yaml
  env:
    COMPOSE_PROJECT_NAME: cocosearch-test-${{ github.run_id }}
  ```
- Add to README documentation
- For parallel test runs, use random suffix:
  ```python
  COMPOSE_PROJECT_NAME=cocosearch-test-$(uuidgen | cut -d'-' -f1)
  ```

**Phase:** Phase 3 (CI integration)

**CocoSearch specific:**
Especially important if multiple branches tested in parallel on same CI runner. Also useful for developers running multiple feature branches locally.

**Sources:**
- [pytest-docker-compose project naming](https://github.com/pytest-docker-compose/pytest-docker-compose)
- [Docker Compose project name docs](https://docs.docker.com/compose/)

---

### Pitfall 17: Volume Cleanup Accumulates Disk Space

**What goes wrong:**
After months of development, Docker volumes consume gigabytes of disk space. Old test data persists forever in named volumes. `docker system df` shows huge volume usage. Manual cleanup required periodically.

**Why it happens:**
- Docker Compose creates named volumes for database persistence
- Named volumes aren't deleted when containers stop (`docker-compose down`)
- Volumes persist across container recreations for data safety
- No automatic cleanup strategy implemented
- Volumes accumulate over time: one per test run if not managed

**Warning signs:**
- `df -h` shows low disk space without obvious cause
- `docker system df` shows large volume usage (gigabytes)
- Old test databases still exist from weeks/months ago
- Manual `docker volume prune` required periodically
- `/var/lib/docker/volumes` consuming significant disk

**Prevention:**
- Use anonymous volumes (not named) for test data:
  ```yaml
  volumes:
    - /var/lib/postgresql/data  # anonymous, deleted with container
  ```
- OR add cleanup script: `docker-compose down -v` (deletes volumes)
- Document cleanup command in README:
  ```bash
  # Stop containers and remove volumes
  docker-compose down -v
  ```
- Consider tmpfs for test database (fastest, no disk):
  ```yaml
  services:
    db:
      tmpfs:
        - /var/lib/postgresql/data
  ```
- Add cleanup to CI workflow (always use `-v`)
- For developers, add to pre-commit: check volume usage

**Phase:** Phase 1 (Test infrastructure setup)

**CocoSearch specific:**
PostgreSQL with pgvector can accumulate significant data (embeddings are large). tmpfs is ideal for tests - speed benefit + automatic cleanup.

**Sources:**
- [Docker Compose volume cleanup](https://docs.docker.com/compose/compose-file/compose-file-v3/#volumes)
- [Docker postgres for testing with tmpfs](https://github.com/labianchin/docker-postgres-for-testing)

---

### Pitfall 18: Tree-sitter Parser Files Not Available in Docker (LOW CONFIDENCE)

**What goes wrong:**
Tests fail with tree-sitter parsing errors or "parser not found" in Docker container. Works fine on host machine where parsers were compiled locally. CocoIndex chunking falls back to plain text.

**Why it happens:**
- CocoIndex may compile tree-sitter parsers to platform-specific shared libraries (.so, .dylib, .dll)
- Docker container may have different architecture than host (Linux vs macOS)
- Parsers compiled on macOS don't work in Linux container
- Parser files might not be copied into Docker image
- CocoIndex may handle this automatically but unclear from documentation

**Warning signs:**
- Error: "language parser not found" in container only
- Works on macOS/Windows host, fails in Linux Docker container
- Tree-sitter parsers exist on host but not in container
- Manual parser installation in container fixes temporarily
- CocoIndex falls back to plain-text chunking in Docker

**Prevention:**
- Verify CocoIndex handles tree-sitter in Docker automatically (check docs)
- If manual compilation needed, compile inside Docker container during build:
  ```dockerfile
  RUN python -c "from tree_sitter import Language; # trigger compilation"
  ```
- OR mount parser directory into container (with correct architecture)
- Use multi-stage build: compile parsers in build stage, copy to runtime
- Document parser compilation requirement in Dockerfile comments
- Test tree-sitter chunking in Docker explicitly

**Phase:** Phase 2 (Full integration tests with CocoIndex)

**CocoSearch specific:**
CocoIndex uses tree-sitter for 15+ languages. Critical for parsing test codebases. **LOW CONFIDENCE**: May not be an issue if CocoIndex handles this. Needs verification with CocoIndex documentation.

**Sources:**
- [tree-sitter Docker compilation issues](https://github.com/tree-sitter/py-tree-sitter/issues/99)
- [tree-sitter Docker build image](https://github.com/autosoft-dev/tree-sitter-docker)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Severity | Mitigation |
|-------------|---------------|----------|------------|
| Test infrastructure setup | Fixture scope conflicts (Pitfall 1, 7) | CRITICAL | Separate conftest for unit vs integration, clear naming |
| Test infrastructure setup | UV hardlink mode failure (Pitfall 6) | CRITICAL | UV_LINK_MODE=copy in Docker environment |
| Test infrastructure setup | Database state pollution (Pitfall 4) | CRITICAL | Cleanup fixture, transaction rollback pattern |
| Test infrastructure setup | pgvector extension missing (Pitfall 9) | MEDIUM | Init script or session fixture to enable extension |
| Test infrastructure setup | Connection pool leaks (Pitfall 8) | MEDIUM | Autouse cleanup fixture, reset singleton |
| Ollama integration | Model loading timeout (Pitfall 2) | CRITICAL | OLLAMA_KEEP_ALIVE=-1, warmup fixture, long timeouts |
| Ollama integration | Floating-point assertions (Pitfall 11) | MEDIUM | pytest.approx() for all similarity scores |
| CI integration | Network access differences (Pitfall 3) | CRITICAL | Environment-based hostname detection |
| CI integration | TTY requirement (Pitfall 5) | CRITICAL | docker-compose exec -T in CI workflows |
| CI integration | Project name conflicts (Pitfall 16) | LOW | Unique names with job ID or user prefix |
| Optimization | Slow test execution (Pitfall 13) | MEDIUM | Session fixtures, pytest-xdist, warmup |
| Ongoing | Docker build cache (Pitfall 12) | MEDIUM | Document rebuild requirement, CI uses --no-cache |

---

## Confidence Assessment

| Category | Confidence | Notes |
|----------|------------|-------|
| Container lifecycle | HIGH | Well-documented pytest-docker patterns, clear sources from 2025-2026 |
| PostgreSQL isolation | HIGH | Standard testcontainers approach, verified with pgvector docs |
| Ollama performance | HIGH | Recent GitHub issues (Jan 2026) confirm 30s startup delays |
| CI/CD integration | HIGH | GitHub Actions TTY issue widely documented with solutions |
| UV package manager | MEDIUM | Official docs exist, Docker hardlink issue documented |
| Network access patterns | HIGH | Common Docker networking issue, multiple sources confirm |
| Floating-point testing | HIGH | pytest.approx well-documented, applies to all vector operations |
| Tree-sitter in Docker | LOW | Based on general tree-sitter Docker issues, not CocoIndex-specific |

---

## Research Sources

**Primary Sources (Official Documentation):**
- [pytest fixtures documentation](https://docs.pytest.org/en/stable/how-to/fixtures.html)
- [Using uv in Docker - Official Guide](https://docs.astral.sh/uv/guides/integration/docker/)
- [pgvector GitHub repository](https://github.com/pgvector/pgvector)
- [Testcontainers Python guide](https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/)
- [Docker Compose documentation](https://docs.docker.com/compose/)

**Recent Issues (2025-2026):**
- [Ollama Docker slow startup Issue #13627](https://github.com/ollama/ollama/issues/13627) (Jan 2026)
- [pytest conftest fixture conflicts Issue #7053](https://github.com/pytest-dev/pytest/issues/7053)
- [Docker container port binding in GitHub Actions](https://github.com/orgs/community/discussions/31737)
- [pytest in docker-compose with GitHub Actions](https://github.com/orgs/community/discussions/27185)

**Community Resources (2024-2026):**
- [Cleaning PostgreSQL DB between Integration Tests](https://carbonhealth.com/blog-post/cleaning-postgresql-db-between-integration-tests-efficiently)
- [pytest approx for accurate numeric testing](https://pytest-with-eric.com/pytest-advanced/pytest-approx/)
- [Integration testing with pytest & Docker compose](https://xnuinside.medium.com/integration-testing-for-bunch-of-services-with-pytest-docker-compose-4892668f9cba)
- [GitHub Actions Service Containers and Docker Compose](https://medium.com/@sreeprad99/from-ci-chaos-to-orchestration-deep-dive-into-github-actions-service-containers-and-docker-compose-7cb2ff335864)
- [UV package management in Docker](https://medium.com/@shaliamekh/python-package-management-with-uv-for-dockerized-environments-f3d727795044)
- [Database testing with fixtures and seeding](https://neon.com/blog/database-testing-with-fixtures-and-seeding)

**Tools Referenced:**
- [pytest-docker](https://github.com/avast/pytest-docker)
- [pytest-docker-compose](https://github.com/pytest-docker-compose/pytest-docker-compose)
- [pytest-docker-tools](https://github.com/Jc2k/pytest-docker-tools)
- [Testcontainers pgvector module](https://testcontainers.com/modules/pgvector/)
- [pytest-xdist for parallelization](https://github.com/pytest-dev/pytest-xdist)

**Optimization and Best Practices:**
- [How to speed up pytest](https://buildpulse.io/blog/how-to-speed-up-pytest)
- [13 proven ways to improve pytest runtime](https://pytest-with-eric.com/pytest-advanced/pytest-improve-runtime/)
- [Pytest skip and markers](https://docs.pytest.org/en/stable/how-to/skipping.html)
- [Docker postgres for testing with tmpfs](https://github.com/labianchin/docker-postgres-for-testing)

---

*Research complete: 18 pitfalls identified across critical/medium/low priority categories*
*All pitfalls mapped to implementation phases with actionable prevention strategies*
*Sources verified from official documentation and recent community content (2024-2026)*
