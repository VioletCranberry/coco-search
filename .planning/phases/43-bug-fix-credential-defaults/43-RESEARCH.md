# Phase 43: Bug Fix & Credential Defaults - Research

**Researched:** 2026-02-08
**Domain:** Python configuration defaults, Docker credential alignment, CocoIndex parameter fix
**Confidence:** HIGH

## Summary

This phase addresses four tightly coupled issues: a keyword argument bug in the indexing pipeline, establishing a default `COCOSEARCH_DATABASE_URL`, aligning Docker Compose credentials, and updating `config check` to show defaults gracefully. The changes are small in scope but touch critical code paths across configuration, indexing, and infrastructure.

The bug (FIX-01) is a confirmed keyword argument mismatch: `flow.py:93` passes `language=file["extension"]` to `extract_devops_metadata()`, but the function signature expects `language_id`. This causes DevOps files (Terraform, Dockerfile, Bash) to fail during indexing when CocoIndex validates the transform call. The fix is a single keyword change.

The infrastructure changes (INFRA-01 through INFRA-03) center on establishing `postgresql://cocosearch:cocosearch@localhost:5432/cocosearch` as the default database URL across all components. Currently, `COCOSEARCH_DATABASE_URL` is treated as required with no default -- users must export it before running any command. Additionally, `docker-compose.yml` still uses legacy `cocoindex:cocoindex` credentials from before the Phase 20 env var standardization.

**Critical discovery:** There is a dual-environment-variable situation. CocoSearch application code reads `COCOSEARCH_DATABASE_URL` (in `search/db.py`, `indexer/flow.py`, `config/env_validation.py`), but `cocoindex.init()` reads `COCOINDEX_DATABASE_URL` via its own `Settings.from_env()`. Currently there is NO bridging between these two variables. When implementing defaults, the default mechanism must set BOTH variables (or pass explicit `Settings` to `cocoindex.init()`). The recommended approach: when `COCOSEARCH_DATABASE_URL` is resolved (whether from env or default), also set `os.environ["COCOINDEX_DATABASE_URL"]` to the same value before any `cocoindex.init()` call.

**Primary recommendation:** Introduce a single `get_database_url()` function in `config/env_validation.py` that returns the default when no env var is set, and use this consistently across all callsites. Ensure the CocoIndex bridge is handled at application startup.

## Standard Stack

No new libraries needed. This phase modifies existing code only.

### Core (Already in Use)
| Library | Purpose | Relevant Files |
|---------|---------|----------------|
| `cocoindex` | Indexing framework; `cocoindex.init()` reads `COCOINDEX_DATABASE_URL` | `indexer/flow.py`, `cli.py`, `mcp/server.py` |
| `psycopg` | Direct PostgreSQL connections | `indexer/flow.py:209` |
| `psycopg_pool` | Connection pooling | `search/db.py` |
| `rich` | CLI output formatting | `cli.py` (config check table) |

### No New Dependencies Required

All changes use existing standard library (`os`, `os.environ`) and project modules.

## Architecture Patterns

### Pattern 1: Centralized Default with `get_database_url()`

**What:** A single function that resolves the database URL from environment or returns the hardcoded default.

**When to use:** Every place that currently calls `os.getenv("COCOSEARCH_DATABASE_URL")`.

**Why:** Eliminates the scattered `os.getenv()` calls that each need to handle the missing-value case differently. Currently there are 3 callsites in application code plus the `cocoindex.init()` bridge.

**Example:**
```python
# Source: Existing pattern from COCOSEARCH_OLLAMA_URL handling in embedder.py:75
DEFAULT_DATABASE_URL = "postgresql://cocosearch:cocosearch@localhost:5432/cocosearch"

def get_database_url() -> str:
    """Get database URL from environment or return default.

    Returns COCOSEARCH_DATABASE_URL if set, otherwise the default.
    Also ensures COCOINDEX_DATABASE_URL is set for CocoIndex SDK compatibility.
    """
    url = os.getenv("COCOSEARCH_DATABASE_URL", DEFAULT_DATABASE_URL)
    # Bridge to CocoIndex SDK (reads COCOINDEX_DATABASE_URL)
    if not os.getenv("COCOINDEX_DATABASE_URL"):
        os.environ["COCOINDEX_DATABASE_URL"] = url
    return url
```

### Pattern 2: Source Attribution in Config Check

**What:** The `config check` command shows where each value comes from: "environment" vs "default".

**When to use:** Already exists for `COCOSEARCH_OLLAMA_URL` (cli.py:988-996). Apply same pattern to `DATABASE_URL`.

**Example:**
```python
# Source: Existing pattern in cli.py:988-996
db_url = os.getenv("COCOSEARCH_DATABASE_URL")
if db_url:
    table.add_row("COCOSEARCH_DATABASE_URL", mask_password(db_url), "environment")
else:
    table.add_row(
        "COCOSEARCH_DATABASE_URL",
        mask_password(DEFAULT_DATABASE_URL),
        "default"
    )
```

### Callsite Inventory (Complete)

Files that read `COCOSEARCH_DATABASE_URL` and need updating:

| File | Line | Current Code | Change Needed |
|------|------|-------------|---------------|
| `search/db.py` | 36-38 | `os.getenv("COCOSEARCH_DATABASE_URL")` then raise if None | Use `get_database_url()`, remove raise |
| `indexer/flow.py` | 199-201 | `os.getenv("COCOSEARCH_DATABASE_URL")` then raise if None | Use `get_database_url()`, remove raise |
| `config/env_validation.py` | 34 | `os.getenv("COCOSEARCH_DATABASE_URL")` returns error if None | Remove from required validation |
| `cli.py` | 960-968 | `validate_required_env_vars()` returns error | Update to not error on DATABASE_URL |
| `cli.py` | 979-985 | Shows DATABASE_URL value, source="environment" | Show "default" when using default |

Files that call `cocoindex.init()` (need bridge):

| File | Lines | Notes |
|------|-------|-------|
| `indexer/flow.py` | 175 | Called during `cocosearch index` |
| `cli.py` | 266, 409, 525, 554, 692 | Called in search, list, stats, clear commands |
| `mcp/server.py` | 71, 105, 280, 475 | Called in MCP tool handlers |

**Bridge strategy:** Call `get_database_url()` early (before first `cocoindex.init()`) to set both env vars. The function only needs to be called once since it sets `os.environ["COCOINDEX_DATABASE_URL"]` as a side effect. Best place: in `main()` before command dispatch, or in each command handler before `cocoindex.init()`.

### Anti-Patterns to Avoid

- **Scattered defaults:** Do NOT put `or DEFAULT_URL` in each callsite. Use the centralized function.
- **Forgetting the CocoIndex bridge:** CocoIndex SDK reads `COCOINDEX_DATABASE_URL`, not `COCOSEARCH_DATABASE_URL`. If you only set defaults for the app var, `cocoindex.init()` will get `database=None` and fail.
- **Changing cocoindex.init() to pass Settings:** While possible, this would require modifying all 10+ callsites. The env var bridge is simpler and follows the existing pattern.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Default env var with source tracking | Custom config system | `os.getenv(key, default)` + source check | Standard Python pattern, already used for OLLAMA_URL |
| Password masking for display | Regex replacement | Existing `mask_password()` in `env_validation.py` | Already handles edge cases (no password, invalid URL) |

## Common Pitfalls

### Pitfall 1: CocoIndex Environment Variable Bridge

**What goes wrong:** Setting default for `COCOSEARCH_DATABASE_URL` but forgetting `COCOINDEX_DATABASE_URL`. CocoIndex SDK silently gets `database=None`, causing failures on first `cocoindex.init()` call.

**Why it happens:** The app uses `COCOSEARCH_*` prefix (standardized in Phase 20), but the CocoIndex SDK reads `COCOINDEX_*` prefix. There is currently NO bridging mechanism in the codebase.

**How to avoid:** The `get_database_url()` function must set both variables. Test by unsetting both env vars and running `cocosearch index .`.

**Warning signs:** `cocoindex.init()` throwing errors about missing database configuration.

**Confidence:** HIGH -- verified by reading `cocoindex.setting.Settings.from_env()` source code which explicitly reads `COCOINDEX_DATABASE_URL`.

### Pitfall 2: Docker Compose Data Volume on Credential Change

**What goes wrong:** Users with existing `postgres_data/` volume from old `cocoindex:cocoindex` credentials will fail to connect after switching `docker-compose.yml` to `cocosearch:cocosearch`. PostgreSQL stores credentials in the data directory; changing POSTGRES_USER/PASSWORD in docker-compose only affects first initialization.

**Why it happens:** PostgreSQL environment variables only apply when `initdb` runs (first startup with empty data directory). Existing data directories keep the old credentials.

**How to avoid:** Document in any migration notes: `docker compose down -v && docker compose up -d` to reset. Or accept that existing users keep their old credentials and set `COCOSEARCH_DATABASE_URL` explicitly.

**Warning signs:** "authentication failed for user cocosearch" errors after updating docker-compose.yml.

**Confidence:** HIGH -- this is standard PostgreSQL behavior.

### Pitfall 3: Validation Function Still Treating DATABASE_URL as Required

**What goes wrong:** `validate_required_env_vars()` currently returns an error when `COCOSEARCH_DATABASE_URL` is not set. If the validation function is not updated but defaults are added elsewhere, `config check` will show an error while the app actually works fine.

**Why it happens:** The validation was written when DATABASE_URL had no default. Now that it has a default, it should not be "required".

**How to avoid:** Update `validate_required_env_vars()` to remove the DATABASE_URL check entirely (it now always has a value). Update `config_check_command()` to show "default" source.

**Warning signs:** `cocosearch config check` showing errors when `cocosearch index .` works fine.

### Pitfall 4: Tests That Assert on Missing DATABASE_URL Error

**What goes wrong:** Existing tests verify that missing `COCOSEARCH_DATABASE_URL` raises `ValueError`. After adding defaults, these tests will fail because the URL is never missing.

**Why it happens:** Tests like `tests/unit/search/test_db.py:19-29` explicitly test the "missing env var" case.

**How to avoid:** Update tests to reflect the new behavior (default is used when env var is not set).

**Confidence:** HIGH -- verified test at `tests/unit/search/test_db.py:19-29`.

## Code Examples

### FIX-01: Parameter Name Fix (flow.py:93)

```python
# BEFORE (buggy) - flow.py:93
chunk["metadata"] = chunk["text"].transform(
    extract_devops_metadata,
    language=file["extension"],  # BUG: wrong keyword
)

# AFTER (fixed)
chunk["metadata"] = chunk["text"].transform(
    extract_devops_metadata,
    language_id=file["extension"],  # Matches function signature
)
```

**Source:** Verified by reading `extract_devops_metadata` signature at `handlers/__init__.py:181`:
```python
@cocoindex.op.function()
def extract_devops_metadata(text: str, language_id: str) -> dict:
```

Note: `extract_symbol_metadata` at `indexer/symbols.py:393` uses `language` (not `language_id`), so flow.py:99 `language=file["extension"]` is correct for that call. Only line 93 needs fixing.

### INFRA-01: Default Database URL

```python
# In config/env_validation.py - add constant and helper
DEFAULT_DATABASE_URL = "postgresql://cocosearch:cocosearch@localhost:5432/cocosearch"

def get_database_url() -> str:
    """Get database URL from environment or return default.

    Also bridges to COCOINDEX_DATABASE_URL for CocoIndex SDK.
    """
    url = os.getenv("COCOSEARCH_DATABASE_URL", DEFAULT_DATABASE_URL)
    # Bridge: CocoIndex SDK reads COCOINDEX_DATABASE_URL
    if not os.getenv("COCOINDEX_DATABASE_URL"):
        os.environ["COCOINDEX_DATABASE_URL"] = url
    return url
```

### INFRA-02: Docker Compose Credential Alignment

```yaml
# BEFORE - docker-compose.yml
environment:
  POSTGRES_USER: cocoindex
  POSTGRES_PASSWORD: cocoindex
  POSTGRES_DB: cocoindex
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U cocoindex -d cocoindex"]

# AFTER
environment:
  POSTGRES_USER: cocosearch
  POSTGRES_PASSWORD: cocosearch
  POSTGRES_DB: cocosearch
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U cocosearch -d cocosearch"]
```

### INFRA-03: Config Check Default Source

```python
# In cli.py config_check_command - replace current DATABASE_URL handling
# BEFORE:
db_url = os.getenv("COCOSEARCH_DATABASE_URL")
table.add_row(
    "COCOSEARCH_DATABASE_URL",
    mask_password(db_url),
    "environment"
)

# AFTER:
db_url_env = os.getenv("COCOSEARCH_DATABASE_URL")
if db_url_env:
    table.add_row("COCOSEARCH_DATABASE_URL", mask_password(db_url_env), "environment")
else:
    table.add_row(
        "COCOSEARCH_DATABASE_URL",
        mask_password(DEFAULT_DATABASE_URL),
        "default"
    )
```

## Affected Documentation and Scripts

Files outside `src/` that reference old `cocoindex:cocoindex` credentials and need updating:

| File | What to Change | Lines |
|------|---------------|-------|
| `docker-compose.yml` | `cocoindex` -> `cocosearch` (4 occurrences) | 8-10, 14 |
| `dev-setup.sh` | `cocoindex:cocoindex` -> `cocosearch:cocosearch` in URLs | 9, 117 |
| `.env.example` | `cocoindex:cocoindex` -> `cocosearch:cocosearch` in URL | 10 |
| `README.md` | `cocoindex:cocoindex` -> `cocosearch:cocosearch` in URL | 70 |
| `docs/mcp-configuration.md` | `cocoindex:cocoindex` -> `cocosearch:cocosearch` in URLs | 74, 103, 141, 180 |

**Note:** The Dockerfile (`docker/Dockerfile:134`) and its PostgreSQL init script (`docker/rootfs/.../svc-postgresql/run`) already use `cocosearch:cocosearch` credentials -- these are correct and need no changes.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `COCOINDEX_DATABASE_URL` env var | `COCOSEARCH_DATABASE_URL` env var | Phase 20 (v1.5) | App code migrated, but CocoIndex SDK still reads old name |
| `cocoindex:cocoindex` credentials | `cocosearch:cocosearch` credentials | Phase 24 (Docker image) | Dockerfile uses new creds, docker-compose.yml still has old |
| DATABASE_URL required, no default | DATABASE_URL with default | This phase | Zero-config startup possible |

## Open Questions

1. **Where to call `get_database_url()` for the CocoIndex bridge?**
   - What we know: `cocoindex.init()` is called in 10+ places, each needs `COCOINDEX_DATABASE_URL` set before the call.
   - Options: (a) Call in `main()` before command dispatch, (b) Call in each command handler before `cocoindex.init()`, (c) Call once at module import time in `__init__.py`.
   - Recommendation: Option (a) is cleanest -- call `get_database_url()` once in `main()` before any command executes. This sets the env var globally for the process. For MCP server handlers, also call it in the server startup path.

2. **Should `check_env_or_exit()` still exit when DATABASE_URL is missing?**
   - What we know: This function is defined but NOT called anywhere in the codebase (checked all grep results). It exists in `config/env_validation.py` but no CLI entry point uses it.
   - Recommendation: Update it alongside `validate_required_env_vars()` for consistency, but this has zero runtime impact since it is not called.

3. **What about existing users with `cocoindex:cocoindex` data volumes?**
   - What we know: PostgreSQL ignores POSTGRES_USER/PASSWORD env vars when data directory already exists.
   - Recommendation: Document in commit message that `docker compose down -v && docker compose up -d` is needed for existing users. The default DATABASE_URL is for new setups.

## Sources

### Primary (HIGH confidence)
- **CocoIndex SDK source:** `cocoindex.setting.Settings.from_env()` -- inspected via `inspect.getsource()`, confirmed reads `COCOINDEX_DATABASE_URL`
- **CocoIndex `init()` source:** Confirmed `init(settings=None)` calls `Settings.from_env()` when no settings passed
- **Application source:** Directly read all affected files in `src/cocosearch/`
- **Test source:** Verified test at `tests/unit/search/test_db.py:19-29` that will need updating

### Secondary (MEDIUM confidence)
- **Docker/PostgreSQL behavior:** Well-known that POSTGRES_USER/PASSWORD only apply on first `initdb` -- standard PostgreSQL documentation

## Metadata

**Confidence breakdown:**
- FIX-01 (parameter bug): HIGH -- confirmed by reading both function signature and call site
- INFRA-01 (default URL): HIGH -- straightforward `os.getenv(key, default)` pattern
- INFRA-02 (docker-compose): HIGH -- simple string replacement, confirmed current values
- INFRA-03 (config check): HIGH -- existing pattern for OLLAMA_URL already in codebase
- CocoIndex bridge: HIGH -- verified by reading SDK source code and testing with Python

**Research date:** 2026-02-08
**Valid until:** 2026-03-08 (stable domain, no external dependencies changing)
