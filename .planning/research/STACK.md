# Technology Stack: v1.3 Docker Integration Testing

**Project:** CocoSearch -- Local-first semantic code search via MCP
**Milestone:** v1.3 -- Docker Integration Tests & Infrastructure
**Researched:** 2026-01-30
**Confidence:** HIGH (testcontainers versions verified via PyPI; pytest integration patterns verified via official guides)

## Executive Summary

v1.3 requires **one new dev dependency: testcontainers-python** for programmatic Docker container management in integration tests. Your existing pytest + pytest-asyncio setup already supports the integration patterns needed. Do NOT add pytest-docker plugins or docker-compose Python libraries -- they add complexity for workflows you can manage more simply with testcontainers (tests) and native docker-compose CLI (user setup).

## Recommended Stack Additions

### testcontainers[postgres] (New)

- **Version:** >=4.14.0
- **Released:** 2026-01-07 (actively maintained)
- **Python requirement:** >=3.10 (your project is >=3.11, compatible)
- **License:** Apache 2.0
- **Purpose:** Programmatic Docker container lifecycle management for integration tests
- **Install:** `uv add --dev "testcontainers[postgres]>=4.14.0"`

**Why testcontainers:**

1. **Industry standard** - Cross-language project (Java, Node, Python, .NET, Go) with consistent patterns and active community
2. **PostgreSQL module** - Pre-configured container with health checks and connection URL helpers
3. **GenericContainer** - For Ollama Docker container (custom image support)
4. **pytest-friendly** - Context managers (`with PostgresContainer() as postgres`) integrate naturally with pytest fixtures
5. **Automatic cleanup** - Finalizers ensure containers stop/remove even on test failures
6. **Dynamic port mapping** - No hardcoded ports, supports parallel test execution
7. **Minimal API** - `.start()`, `.stop()`, `.get_connection_url()` -- no complex configuration

**What you get:**

```python
from testcontainers.postgres import PostgresContainer
from testcontainers.core.generic import GenericContainer

# PostgreSQL with pgvector
postgres = PostgresContainer("pgvector/pgvector:pg17")
postgres.start()
conn_url = postgres.get_connection_url()  # postgresql://test:test@localhost:DYNAMIC_PORT/test

# Ollama (generic container)
ollama = GenericContainer("ollama/ollama:latest")
ollama.with_exposed_ports(11434)
ollama.start()
host = ollama.get_container_host_ip()
port = ollama.get_exposed_port(11434)
```

**Integration with existing pytest:**

Module-scoped fixtures for container reuse (fast tests):

```python
# tests/integration/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="module")
def postgres_url(request):
    """PostgreSQL container shared across module tests."""
    container = PostgresContainer("pgvector/pgvector:pg17")
    container.start()

    def cleanup():
        container.stop()

    request.addfinalizer(cleanup)
    return container.get_connection_url()

# Async tests work with existing pytest-asyncio (function-scoped)
@pytest.mark.asyncio
async def test_index_and_search(postgres_url):
    async with await psycopg.AsyncConnection.connect(postgres_url) as conn:
        # Your existing async test patterns unchanged
        pass
```

**Confidence:** HIGH (verified via PyPI page, official testcontainers-python docs, and testcontainers.com getting started guide)

**Source:** [testcontainers PyPI](https://pypi.org/project/testcontainers/)

## Stack Unchanged

### Existing Dependencies (No Changes Needed)

| Dependency | Version | Status in v1.3 |
|------------|---------|---------------|
| pytest | >=9.0.2 | **Unchanged** -- integration tests use same pytest runner |
| pytest-asyncio | >=1.3.0 | **Unchanged** -- async fixtures work with sync container setup |
| pytest-mock | >=3.15.1 | **Unchanged** -- still used for unit tests (no containers) |
| pytest-httpx | >=0.36.0 | **Unchanged** -- mock Ollama HTTP in unit tests |
| pytest-subprocess | >=1.5.3 | **Unchanged** -- mock CLI subprocess in unit tests |
| psycopg[binary,pool] | >=3.3.2 | **Unchanged** -- connection library for integration tests |
| Docker daemon | user-installed | **Required** -- testcontainers needs Docker running |

**Why no changes:**

- pytest handles both unit tests (mocked) and integration tests (real containers)
- pytest-asyncio supports async tests with sync container fixtures (different scopes)
- Existing test helpers (pytest-httpx, pytest-mock) still needed for fast unit tests

**Confidence:** HIGH (existing pyproject.toml reviewed)

## Alternatives Considered

### pytest-docker (NOT recommended)

- **Version:** 3.2.5 (maintained, released 2025-11-12)
- **What it does:** Spins up docker-compose.yml services as pytest fixtures
- **Why NOT:**
  - Requires external docker-compose.yml management
  - Less programmatic control (can't modify containers from test code)
  - Your use case needs dynamic containers (start/stop Ollama conditionally)
  - docker-compose.yml is for **user setup**, not test infrastructure
  - Adds indirection: docker-compose.yml → pytest fixture → test code

**When pytest-docker is better:** Static docker-compose setups that never change from tests. Not your case.

**Source:** [pytest-docker PyPI](https://pypi.org/project/pytest-docker/)

### pytest-docker-compose (NOT recommended)

- **Similar limitations to pytest-docker**
- Depends on docker-compose CLI being in PATH
- Your v1.3 goal is "unified docker-compose for one-command setup" **for users**, not for test infrastructure

**When it's better:** When docker-compose.yml already defines your test environment. You're building that compose file for users, not tests.

### pytest-docker-tools (NOT recommended)

- **Version:** 0.x (less active)
- **What it does:** Advanced fixture model with port collision avoidance
- **Why NOT:**
  - More complex fixture DSL
  - Smaller community than testcontainers
  - Less documentation
  - Overkill for your needs

**When it's better:** Highly parallel test scenarios with complex port management. Not needed here.

### docker-py SDK (NOT recommended as direct dependency)

- **Version:** 7.1.0 (official Docker SDK for Python)
- **What it does:** Low-level Docker API (containers, images, networks, volumes)
- **Why NOT:**
  - Requires reimplementing testcontainers patterns (health checks, wait strategies, cleanup)
  - No pytest integration helpers
  - No PostgreSQL-specific conveniences
  - More code to maintain

**When it's better:** Building custom container orchestration tools. Not for tests.

**Note:** testcontainers-python uses docker-py internally, so you get the mature Docker API without boilerplate.

**Source:** [docker-py PyPI](https://pypi.org/project/docker/)

### docker-compose Python libraries (NOT recommended)

**Options:**
- `docker-composer` (v2 wrapper)
- `python-on-whales` (calls Docker Compose v2 Go binary)
- `pytest-docker-compose-v2` (pytest plugin for compose v2)

**Why NOT:**
- These are for **programmatic manipulation** of docker-compose.yml
- Your user setup is **static config + shell commands**
- Integration tests need **dynamic containers** (testcontainers)
- No value add over native docker-compose CLI for user setup

**User setup pattern (no Python library needed):**

```bash
# In your Makefile or docs
docker compose up -d postgres ollama  # Native CLI, zero Python deps
```

**Confidence:** MEDIUM (libraries exist per WebSearch, but rationale is clear from use case analysis)

**Source:** [WebSearch: docker-compose v2 python API](https://www.cloudbees.com/blog/using-docker-compose-for-python-development)

## No New Dependencies Needed For

### Async Testing (Already Covered)

**pytest-asyncio 1.3.0 is current** (released 2025-11-10). No changes needed.

**Pattern that works:**

```python
# Container fixture: sync, module-scoped
@pytest.fixture(scope="module")
def db_url(request):
    container = PostgresContainer("pgvector/pgvector:pg17").start()
    request.addfinalizer(container.stop)
    return container.get_connection_url()

# Test: async, function-scoped
@pytest.mark.asyncio
async def test_search(db_url):
    async with await psycopg.AsyncConnection.connect(db_url) as conn:
        # Async test body
        pass
```

**Why this works:**

- Async event loop is function-scoped in pytest-asyncio
- Container fixtures are sync (no event loop needed)
- Test bodies are async (use the event loop)
- Different scopes don't conflict

**Confidence:** HIGH (verified via pytest-asyncio PyPI docs and testcontainers guides)

**Source:** [pytest-asyncio PyPI](https://pypi.org/project/pytest-asyncio/)

### Container Wait Strategies (Built Into testcontainers)

**Available patterns:**

- `PostgresContainer` - Waits for `pg_isready` automatically
- `GenericContainer` - `.with_exposed_ports()` waits for port to open
- Custom wait - `.waiting_for()` with log messages or HTTP endpoints

**Example (Ollama):**

```python
ollama = (
    GenericContainer("ollama/ollama:latest")
    .with_exposed_ports(11434)  # Port exposure = readiness check
    .with_env("OLLAMA_MODELS", "/models")
)
```

**Why no separate library:** Wait strategies are part of testcontainers core. No pytest-wait or similar needed.

**Confidence:** MEDIUM (wait strategies confirmed via GitHub source code and community examples; specific API details not in official docs but pattern is standard across testcontainers implementations in Java/Node/Python)

**Source:** [testcontainers-python GitHub](https://github.com/testcontainers/testcontainers-python/blob/main/core/testcontainers/core/waiting_utils.py)

### Test Discovery (Already Configured)

**Your existing pytest config is complete:**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "strict"
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
```

**For integration tests:** Add `tests/integration/` directory, same discovery rules apply. No pytest plugins needed.

**Recommended structure:**

```
tests/
  unit/          # Use pytest-mock, no containers (fast)
  integration/   # Use testcontainers, no mocks (slower)
    conftest.py  # Container fixtures
    test_postgres.py
    test_ollama.py
    test_full_flow.py
```

### Mocking (Still Used for Unit Tests)

**pytest-mock 3.15.1 stays for unit tests.** Integration tests use real containers (no mocks).

**Pattern separation:**

| Test Type | Dependencies | Speed | When to Run |
|-----------|-------------|-------|-------------|
| Unit tests (`tests/unit/`) | pytest-mock, pytest-httpx | Fast (ms) | Every save, pre-commit |
| Integration tests (`tests/integration/`) | testcontainers, real containers | Slow (seconds) | Pre-push, CI |

**Confidence:** HIGH (standard testing pyramid pattern)

## Installation

**Update `pyproject.toml`:**

```toml
[dependency-groups]
dev = [
    # Existing deps
    "pytest>=9.0.2",
    "pytest-asyncio>=1.3.0",
    "pytest-httpx>=0.36.0",
    "pytest-mock>=3.15.1",
    "pytest-subprocess>=1.5.3",
    "ruff>=0.14.14",

    # NEW for v1.3
    "testcontainers[postgres]>=4.14.0",
]
```

**Install with UV:**

```bash
uv sync --dev
```

**What gets installed:**

- `testcontainers` core (4.14.0)
- `testcontainers-postgres` module (included via `[postgres]` extra)
- `docker-py` (transitive dependency, automatic)

**Docker runtime requirement:** Docker daemon must be running. Tests will fail fast if Docker unavailable.

**Verify installation:**

```bash
# Check testcontainers installed
uv run python -c "import testcontainers; print(testcontainers.__version__)"

# Run sample integration test (will pull containers on first run)
uv run pytest tests/integration/test_postgres.py -v

# Verify cleanup (no leftover containers)
docker ps -a | grep testcontainers  # Should be empty
```

## Integration Patterns

### Module-Scoped Containers (Recommended)

**Pattern:** Start containers once per test module, reuse across tests.

```python
# tests/integration/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="module")
def postgres_url(request):
    """PostgreSQL container shared across all module tests."""
    container = PostgresContainer("pgvector/pgvector:pg17")
    container.start()

    def cleanup():
        container.stop()

    request.addfinalizer(cleanup)
    return container.get_connection_url()
```

**Why module scope:**

- Faster test suite (container startup is expensive: 2-5 seconds)
- Amortize startup cost across all tests in module
- Matches your "component integration tests" goal (PostgreSQL separately, Ollama separately)

**Data cleanup between tests:**

Data persists across tests in the module. Reset state with function-scoped fixtures:

```python
@pytest.fixture(scope="function")
async def clean_db(postgres_url):
    """Truncate tables before each test."""
    async with await psycopg.AsyncConnection.connect(postgres_url) as conn:
        await conn.execute("TRUNCATE TABLE embeddings CASCADE")
        await conn.execute("DELETE FROM indexes WHERE 1=1")
```

**Confidence:** HIGH (recommended pattern in testcontainers guides)

**Source:** [Getting started with Testcontainers for Python](https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/)

### Optional Ollama Container (Native vs Docker)

**Your v1.3 requirement:** "Optional dockerized Ollama (users can choose native or Docker)"

**Pattern:** Try native first, fallback to Docker.

```python
@pytest.fixture(scope="module")
def ollama_base_url(request):
    """Ollama URL (native or Docker fallback)."""
    import httpx
    from testcontainers.core.generic import GenericContainer

    # Try native Ollama
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            return "http://localhost:11434"  # Use native
    except httpx.RequestError:
        pass

    # Fallback: Docker Ollama
    container = GenericContainer("ollama/ollama:latest")
    container.with_exposed_ports(11434)
    container.start()

    def cleanup():
        container.stop()

    request.addfinalizer(cleanup)

    host = container.get_container_host_ip()
    port = container.get_exposed_port(11434)
    return f"http://{host}:{port}"
```

**Why this pattern:**

- Matches user flexibility (native or Docker)
- Tests work in both scenarios
- Faster when native Ollama available (CI can use Docker)

**Confidence:** HIGH (pattern matches v1.3 requirement)

### Component vs Full-Flow Tests

**Component tests:** One container at a time.

```python
# tests/integration/test_postgres.py
def test_postgres_vector_storage(postgres_url):
    """Test PostgreSQL + pgvector only."""
    # No Ollama dependency
    pass

# tests/integration/test_ollama.py
def test_ollama_embedding_generation(ollama_base_url):
    """Test Ollama only."""
    # No PostgreSQL dependency
    pass
```

**Full-flow tests:** Both containers together.

```python
# tests/integration/test_full_flow.py
@pytest.mark.asyncio
async def test_index_and_search_integration(postgres_url, ollama_base_url):
    """Test complete pipeline: index → embed → store → search."""
    # Both dependencies
    pass
```

**Why separate:**

- Component tests isolate failures (easier debugging)
- Full-flow tests validate integration (catch cross-component issues)
- Matches your v1.3 requirements: "Component integration tests (PostgreSQL, Ollama separately)" + "Full-flow integration tests"

**Confidence:** HIGH (matches milestone requirements)

## Common Pitfalls (and How to Avoid Them)

### Pitfall 1: Mixing docker-compose.yml and testcontainers

**Bad pattern:**

```python
# Don't do this
pytest_plugins = ["docker_compose"]  # Plugin for docker-compose.yml
# AND
from testcontainers.postgres import PostgresContainer  # Programmatic
```

**Why bad:** Two competing container lifecycles. Race conditions, port conflicts, cleanup issues.

**Good pattern:** Pick one approach:

- **Integration tests:** testcontainers (programmatic, dynamic)
- **User setup:** docker-compose.yml (declarative, CLI-driven)

### Pitfall 2: Assuming containers auto-commit

**Bad pattern:**

```python
container = PostgresContainer("pgvector/pgvector:pg17")
container.start()
# Test runs
# Container never stops (leaked)
```

**Good pattern:** Always use finalizers or context managers.

```python
# Option 1: Finalizer (pytest fixture)
@pytest.fixture(scope="module")
def postgres_url(request):
    container = PostgresContainer("pgvector/pgvector:pg17").start()
    request.addfinalizer(container.stop)  # Always runs, even on failure
    return container.get_connection_url()

# Option 2: Context manager (one-off test)
def test_something():
    with PostgresContainer("pgvector/pgvector:pg17") as postgres:
        # Test code
        pass  # Container stops automatically
```

**Why this matters:** testcontainers cleans up automatically IF you use finalizers/context managers. Manual `.start()` without `.stop()` leaks containers.

**Confidence:** HIGH (testcontainers best practice)

### Pitfall 3: Hardcoding ports

**Bad pattern:**

```python
conn = await psycopg.connect("postgresql://localhost:5432/test")  # Hardcoded 5432
```

**Why bad:** testcontainers dynamically assigns ports to avoid conflicts. Hardcoded ports fail when 5432 is in use.

**Good pattern:**

```python
conn = await psycopg.connect(postgres_url)  # From fixture, dynamic port
```

**Benefit:** Parallel test execution, CI environments, port conflict resilience.

**Confidence:** HIGH (testcontainers design principle)

### Pitfall 4: Async fixture scope mismatch

**Bad pattern:**

```python
@pytest.fixture(scope="module")  # Module scope
async def postgres_url(request):  # Async fixture
    # Error: async module fixtures don't work (event loop is function-scoped)
```

**Why bad:** pytest-asyncio event loop is function-scoped. Module-scoped async fixtures fail.

**Good pattern:**

```python
@pytest.fixture(scope="module")  # Module scope, SYNC
def postgres_url(request):
    container = PostgresContainer("pgvector/pgvector:pg17").start()
    # Container setup is sync
    request.addfinalizer(container.stop)
    return container.get_connection_url()

@pytest.mark.asyncio  # Function scope, ASYNC
async def test_search(postgres_url):
    # Test body is async
    async with await psycopg.AsyncConnection.connect(postgres_url):
        pass
```

**Why this works:** Container lifecycle is sync. Test logic is async. Different scopes, no conflict.

**Confidence:** HIGH (pytest-asyncio limitation documented)

**Source:** [pytest-asyncio async fixture scoping limitations](https://pytest-asyncio.readthedocs.io/)

## Testing the Tests

**Verification steps after adding testcontainers:**

```bash
# 1. Install dependency
uv sync --dev

# 2. Verify import
uv run python -c "from testcontainers.postgres import PostgresContainer; print('OK')"

# 3. Run single integration test (first run pulls images)
uv run pytest tests/integration/test_postgres.py -v

# 4. Check cleanup (should be empty)
docker ps -a | grep testcontainers

# 5. Run full integration suite
uv run pytest tests/integration/ -v
```

**Expected behavior:**

1. First run pulls `pgvector/pgvector:pg17` image (slow, ~200MB)
2. Subsequent runs reuse cached image (fast)
3. Each test starts container, runs, stops container
4. No leftover containers after tests complete
5. Failures still clean up containers (finalizers run)

**Confidence:** HIGH (standard testcontainers workflow)

## Version Strategy

**Pinning approach:**

```toml
"testcontainers[postgres]>=4.14.0,<5.0.0"
```

**Why:**

- Major version 4 is current (released 2026-01-07, actively maintained)
- Minor/patch updates are backward compatible per semantic versioning
- Avoid surprise breakage from major version bumps

**When to upgrade:** Major version 5.x releases. Review changelog for breaking changes first.

**Confidence:** HIGH (semantic versioning standard practice)

## CI Considerations (Future, Not v1.3 Scope)

**For reference when adding CI later:**

- CI needs Docker daemon running (GitHub Actions has it pre-installed)
- Container images pulled on first run (cache in CI for speed)
- Integration tests are slower than unit tests (separate CI job recommended)
- Use `pytest --maxfail=1` to fail fast on container issues
- Consider `pytest -m "not integration"` for fast unit-only runs

**Confidence:** MEDIUM (standard CI patterns, not validated for this project yet)

## What NOT to Use (and Why)

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **pytest-docker** | Requires external docker-compose.yml, less dynamic | testcontainers (programmatic) |
| **pytest-docker-compose** | Same limitations as pytest-docker | testcontainers (programmatic) |
| **docker-py** directly | Low-level API, no test helpers, reimplements testcontainers | testcontainers (built on docker-py) |
| **docker-composer** / **python-on-whales** | For programmatic compose manipulation, not needed | Native `docker compose` CLI for user setup |
| **pytest-docker-tools** | More complex, smaller community | testcontainers (industry standard) |

## Confidence Assessment

| Component | Confidence | Rationale |
|-----------|------------|-----------|
| testcontainers-python version | **HIGH** | Verified via PyPI (4.14.0, 2026-01-07) |
| PostgreSQL module availability | **HIGH** | Confirmed via PyPI extras and official docs |
| GenericContainer for Ollama | **HIGH** | Documented in testcontainers-python docs |
| pytest integration patterns | **HIGH** | Verified via official getting started guide |
| Module-scoped fixtures | **HIGH** | Recommended pattern in testcontainers guides |
| Async test compatibility | **HIGH** | Verified via pytest-asyncio docs |
| Wait strategies API | **MEDIUM** | Confirmed via GitHub source, not in full official docs |
| Alternatives evaluation | **HIGH** | PyPI pages verified for pytest-docker, docker-py |

## Sources

**HIGH confidence (official sources):**

- [testcontainers PyPI](https://pypi.org/project/testcontainers/) - Version 4.14.0, Python >=3.10, Apache 2.0 license
- [testcontainers-python documentation](https://testcontainers-python.readthedocs.io/) - PostgreSQL module, context managers
- [Getting started with Testcontainers for Python](https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/) - Fixture patterns, best practices
- [pytest-asyncio PyPI](https://pypi.org/project/pytest-asyncio/) - Version 1.3.0 (2025-11-10), async fixture scoping
- [docker-py PyPI](https://pypi.org/project/docker/) - Version 7.1.0, official Docker SDK
- [pytest-docker PyPI](https://pypi.org/project/pytest-docker/) - Version 3.2.5, alternative evaluation

**MEDIUM confidence (verified via multiple sources):**

- [Python Integration Tests: docker-compose vs testcontainers](https://medium.com/codex/python-integration-tests-docker-compose-vs-testcontainers-94986d7547ce) - Comparison rationale
- [testcontainers-python GitHub](https://github.com/testcontainers/testcontainers-python) - Wait strategies source code
- WebSearch findings on docker-compose Python libraries - Multiple options exist, rationale for not using them is clear from use case

**LOW confidence (WebSearch only, not critical):**

- Specific wait strategy API methods - Pattern confirmed via source code, but full API not documented. Safe to use `.with_exposed_ports()` and `.waiting_for()` based on cross-language testcontainers consistency.

---

*Stack research for: CocoSearch v1.3 Docker Integration Tests & Infrastructure*
*Researched: 2026-01-30*
*Previous milestones: v1.0 MVP (4 phases, shipped 2026-01-25), v1.1 Docs & Tests (3 phases, shipped 2026-01-26), v1.2 DevOps Language Support (3 phases, shipped 2026-01-27)*
