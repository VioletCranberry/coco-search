# Project Instructions

This file provides guidance to AI coding agents (Claude Code, OpenCode, and others) when working with code in this repository. It is the single source of truth — `AGENTS.md` is a symlink to this file.

## Project Overview

CocoSearch is a local-first hybrid semantic code search tool powered by CocoIndex and Tree-sitter. It indexes codebases into PostgreSQL with pgvector embeddings and provides search through CLI, MCP server, or interactive REPL. Local by default with Ollama; optional remote embedding providers (OpenAI, OpenRouter) available for teams that prefer managed infrastructure. Requires Python >=3.11.

## Tool Routing (IMPORTANT)

When CocoSearch MCP tools are available, ALWAYS use them instead of Grep, Glob, or Task/Explore agents for code search and exploration:

| Task | Use this | NOT this |
|------|----------|----------|
| Code search / "how does X work?" | `search_code` | Grep, Glob, Task (Explore) |
| Symbol lookup / "find function Y" | `search_code` with `symbol_name`/`symbol_type` | Grep for def/class patterns |
| Dependency tracing / "what imports X?" | `get_file_dependencies` / `get_file_impact` | Grep for import statements |
| Batch dependency analysis (multiple files) | `get_batch_dependencies` / `get_batch_impact` | Per-file `get_file_dependencies` calls |
| Search debugging / "why no results?" | `analyze_query` | Manual pipeline investigation |

Fall back to Grep/Glob ONLY for:
- Exact literal string matches (e.g., a specific error message or config value)
- File path pattern matching (e.g., "find all `*.test.ts` files")
- Editing operations that need line numbers from a known file

## Development Setup

```bash
# Prerequisites: Docker, uv (Python package manager)
# One-command setup (starts infra, pulls model, installs deps, indexes codebase):
./dev-setup.sh

# Or manually:
docker compose --profile ollama up -d    # PostgreSQL 17 + Ollama
uv sync                                 # Install dependencies
uv run cocosearch index .               # Index the codebase
```

**Infrastructure:** PostgreSQL 17 (pgvector) on port 5432, Ollama on port 11434. Defaults require no `.env` file.

## Commands

```bash
# Run all unit tests (default, mocked, no infra needed). Takes a long time.
uv run pytest

# Run a single test file
uv run pytest tests/unit/search/test_cache.py -v

# Run a single test by name
uv run pytest -k "test_rrf_double_match_ranks_higher" -v

# Run handler tests
uv run pytest tests/unit/handlers/ -v

# Lint and format
uv run ruff check src/ tests/
uv run ruff check --fix src/ tests/     # Auto-fix lint issues
uv run ruff format src/ tests/          # Format code

# CLI usage
uv run cocosearch index .
uv run cocosearch search "query"
uv run cocosearch search -i          # Interactive REPL
uv run cocosearch search -i --indexes "repo_a,repo_b"  # Cross-index interactive REPL
uv run cocosearch search --indexes "repo_a,repo_b" "query"  # Cross-index search
uv run cocosearch analyze "query"    # Pipeline analysis with diagnostics
uv run cocosearch analyze "query" --json  # JSON pipeline analysis
uv run cocosearch analyze --indexes "repo_a,repo_b" "query"  # Cross-index analysis
uv run cocosearch stats
uv run cocosearch list
uv run cocosearch clear <index>
uv run cocosearch clear idx1 idx2    # Delete multiple indexes
uv run cocosearch clear --all        # Delete all indexes
uv run cocosearch languages              # List supported languages
uv run cocosearch grammars               # List supported grammars
uv run cocosearch init                   # Initialize cocosearch.yaml + optional CLAUDE.md/AGENTS.md
uv run cocosearch init --no-claude-md    # Initialize without CLAUDE.md prompt
uv run cocosearch init --no-agents-md    # Initialize without AGENTS.md prompt
uv run cocosearch init --no-opencode-mcp # Initialize without OpenCode MCP registration prompt
uv run cocosearch init --no-opencode-skills # Initialize without OpenCode skills installation prompt
uv run cocosearch init --no-claude-mcp   # Initialize without Claude Code plugin prompt
uv run cocosearch config show
uv run cocosearch config path
uv run cocosearch config check
uv run cocosearch dashboard              # Terminal dashboard

# Dependency graph (incremental by default, use --fresh for full re-extraction)
uv run cocosearch index . --deps          # Index + extract dependencies
uv run cocosearch deps extract .          # Extract dependencies (incremental)
uv run cocosearch deps extract . --fresh  # Force full re-extraction
uv run cocosearch deps show <file>        # Show dependencies for a file
uv run cocosearch deps tree <file>        # Forward dependency tree (transitive)
uv run cocosearch deps impact <file>      # Reverse impact tree (what depends on this)
uv run cocosearch deps stats              # Show dependency graph statistics

# MCP server
uv run cocosearch mcp --project-from-cwd

# Auto-reindex on git events (three composable layers — see "Auto-reindex" below)
uv run cocosearch hooks install            # Install post-checkout/merge/commit/rewrite hooks
uv run cocosearch hooks status             # Show which hooks are active
uv run cocosearch hooks uninstall          # Remove the hooks
uv run cocosearch watch .                  # Foreground incremental-reindex loop
uv run cocosearch watch . --interval 60 --no-deps
uv run cocosearch index . --if-exists      # Skip if index not yet created (used by hooks)
uv run cocosearch index . --quiet          # Suppress Rich output (used by hooks)
```

## Architecture

**Entry points:** `cocosearch.cli:main` (CLI) and `cocosearch.mcp.server` (MCP via FastMCP).

**Module structure:**

- **`cli.py`** — Argparse CLI orchestrating all subcommands. When `COCOSEARCH_SERVER_URL` is set, dispatches to `client.py` instead of local execution. Includes `cocosearch watch`, `cocosearch hooks {install,uninstall,status}`, and `--if-exists` / `--quiet` flags on `cocosearch index` for hook-friendly invocation.
- **`client.py`** — HTTP client for remote server mode. `CocoSearchClient` forwards CLI commands to a running CocoSearch server via HTTP API (`/api/search`, `/api/index`, `/api/stats`, `/api/list`, `/api/analyze`, `/api/languages`, `/api/grammars`, `/api/delete-index`). Path translation via `COCOSEARCH_PATH_PREFIX` rewrites host↔container paths.
- **`exceptions.py`** — Structured exception hierarchy: `CocoSearchError` (base), `IndexNotFoundError`, `IndexValidationError`, `SearchError`, `InfrastructureError`. Inherits from `ValueError` where needed for backward compatibility.
- **`validation.py`** — Input validation guards: `validate_index_name()` (SQL injection protection for dynamic table names), `validate_query()` (resource exhaustion protection, max 10,000 chars)
- **`mcp/server.py`** — MCP server exposing tools (search_code, analyze_query, index_codebase, get_file_dependencies, get_file_impact, get_batch_dependencies, get_batch_impact, etc.) + web dashboard with HTTP API (`/api/stats`, `/api/reindex`, `/api/search`, `/api/project`, `/api/projects`, `/api/index`, `/api/stop-indexing`, `/api/delete-index`, `/api/list`, `/api/analyze`, `/api/languages`, `/api/grammars`, `/api/open-in-editor`, `/api/file-content`, `/api/deps`, `/api/deps/impact`, `/api/deps/graph`, `/health`, `/api/heartbeat` SSE, `/api/logs` SSE, `/api/shutdown` POST). Includes idle watchdog for stdio transport (auto-exits after `COCOSEARCH_IDLE_TIMEOUT` seconds of inactivity, default 30 min) and auto-reindex watchdog (`_start_auto_reindex_watchdog` + `_watchdog_tick_once`) that polls git state and triggers incremental reindex on branch/commit drift via the shared `cocosearch.auto_reindex` core.
- **`auto_reindex.py`** — Shared drift-detection + trigger core used by the MCP watchdog, git hooks, and `cocosearch watch`. Exports `DriftReport`, `detect_drift()` (wraps `check_branch_staleness`), `has_deps_table()`, `run_reindex_sync()` (synchronous in-process reindex + optional deps refresh), and `trigger_reindex()` (spawns a daemon thread; accepts pluggable lock + active-indexing registry so the MCP server can reuse its existing `_indexing_lock` / `_active_indexing`).
- **`hooks.py`** — Git hook manager for `cocosearch hooks install/uninstall/status`. Writes marker-wrapped blocks (`# >>> cocosearch auto-reindex >>>`) into `$(git rev-parse --git-common-dir)/hooks/{post-checkout,post-merge,post-commit,post-rewrite}` so hooks are shared across worktrees. Append-safe: coexists with husky/pre-commit/lefthook by preserving existing content. Idempotent install + clean uninstall that deletes the file when nothing else remains.
- **`watch.py`** — Foreground `cocosearch watch` command. Polling loop that calls `auto_reindex.run_reindex_sync()` every `--interval` seconds (default 30). Cheap in steady state because `flow.update()` is content-hash incremental. Accepts an injectable `stop_event` for testability; the CLI binds SIGINT to set it.
- **`logging.py`** — Structured domain logger (`cs_log`) with category-specific methods (`search`, `index`, `mcp`, `cache`, `infra`, `system`, `deps`). Each method creates a `LogEntry` with category and structured fields, pushing to `LogBuffer` for unified output. Falls back to Python logging when no buffer is initialized. `LogCategory` enum defines the 7 categories.
- **`mcp/log_stream.py`** — Real-time log capture for dashboard: `LogEntry` (with `category` and `fields`), `LogBuffer` ring buffer with SSE pub/sub and handler fan-out, `BufferHandler` (logging.Handler), `StderrCapture` (tee wrapper for CocoIndex framework output), `RichLogHandler` (color-coded terminal output via Rich), `FileLogHandler` (rotating log file at `~/.cocosearch/logs/`), `setup_log_capture()` singleton lifecycle
- **`mcp/project_detection.py`** — Auto-detect project from MCP Roots or CWD
- **`indexer/`** — CocoIndex pipeline: file filtering (`file_filter.py`), Tree-sitter symbol extraction (16 languages via `.scm` queries in `indexer/queries/`), multi-provider embedding (`embedder.py` — Ollama/OpenAI/OpenRouter via `PROVIDER_MAP`), tsvector generation, parse health tracking, schema migration, preflight validation (`preflight.py` — conditional Ollama vs API key checks), progress reporting (`progress.py`)
- **`indexer/flow.py`** — CocoIndex flow definition (the indexing pipeline)
- **`search/`** — Hybrid search engine: RRF fusion of vector + keyword results, two-level LRU query cache (`cache.py` — exact + semantic similarity at cosine > 0.92), context expansion via Tree-sitter boundaries for 10 languages (`context_expander.py`, exports `CONTEXT_EXPANSION_LANGUAGES`), symbol/language filtering (`filters.py`), auto-detection of code identifiers for hybrid mode (`query_analyzer.py`), optional dependency enrichment (`include_deps` attaches direct dependencies/dependents to search results), interactive REPL with cross-index support (`repl.py` — `:indexes`, `:searchall` commands), result formatting (`formatter.py`), pipeline analysis with stage-by-stage diagnostics and cross-index `multi_analyze()` (`analyze.py`), cross-index orchestrator (`multi.py`)
- **`search/multi.py`** — Cross-index search orchestrator: `multi_search()` queries multiple indexes in parallel via `ThreadPoolExecutor`, pre-computes query embedding once, tags results with source `index_name`, merges by score. Handles partial failures gracefully. Accepts optional `warnings` list to surface embedding model mismatch warnings to callers.
- **`search/db.py`** — PostgreSQL connection pool (singleton) and query execution
- **`config/`** — YAML config with 4-level precedence resolution (CLI > env > file > defaults), `${VAR}` substitution (`env_substitution.py`), Pydantic schema validation (`schema.py` with `extra="forbid"`, `strict=True`, `EmbeddingSection` with `provider` field, provider-aware model defaults, and optional `baseUrl` for custom endpoints, `LoggingSection` with `file` toggle, `linkedIndexes` list for cross-index search auto-expansion, `AutoReindexSection` with `enabled`/`intervalSeconds` for the MCP watchdog), user-friendly error formatting with fuzzy field suggestions (`errors.py`), env var validation (`env_validation.py`)
- **`management/`** — Index lifecycle: discovery (`discovery.py`), stats (`stats.py` — `collect_warnings()` runs staleness, branch drift, and deps freshness checks for both the main index and all `linkedIndexes`; includes `check_deps_staleness()` for dependency freshness checks), clearing (`clear.py`), git-based naming (`git.py`), metadata with collision detection, status tracking, embedding provider/model tracking, and `deps_extracted_at` timestamp (`metadata.py`), project root detection (`context.py`)
- **`deps/`** — Dependency graph framework: pluggable extractors (`extractors/`), pluggable module resolvers (`resolver.py`), edge storage (`db.py`), extraction orchestrator (`extractor.py`), query API with transitive BFS traversal (`query.py`), data models (`models.py`), autodiscovery registry (`registry.py`). 11 extractors: Python imports, JavaScript/TypeScript (ES6 + CommonJS + re-exports), Go imports, ArgoCD (Application/ApplicationSet/AppProject — project refs, source repos/charts/paths, destinations, generator repos; multi-document YAML via `safe_load_all`), Docker Compose (image/depends_on/extends), GitHub Actions (uses refs with parsed owner/repo/version, needs inter-job deps), GitLab CI (include local/project/remote/template, extends template inheritance, needs DAG deps, trigger child/multi-project pipelines, image/service refs), Terraform (module sources with version, required_providers, remote_state, tfvars associations), Helm (template includes, Chart.yaml subcharts, chart membership ownership with `is_subchart` indicator, subchart-to-parent links), Markdown (documentation references: frontmatter depends, links, inline code, code blocks). 5 module resolvers: Python (dotted modules, `__init__.py`, relative imports, `src/`/`lib/` prefix stripping), JavaScript (extension probing, index files), Go (import path suffix matching), Terraform (local module sources), Markdown (relative path normalization, directory reference matching). Query layer supports direct lookups (`get_dependencies`/`get_dependents`), transitive BFS trees (`get_dependency_tree`/`get_impact` with cycle detection and depth limits), batch-aware multi-root BFS (`get_dependency_tree_batch`/`get_impact_batch` with shared visited set), and detailed stats (`get_dep_stats_detailed`). Three edge types: "import" (code imports), "call" (symbol calls), "reference" (grammar-level refs with `metadata.kind` for specifics — Helm uses `chart_member` for template/values→Chart.yaml ownership and `subchart_of` for subchart→parent chart links).
- **`handlers/`** — Language-specific chunking (HCL, Go Template, Dockerfile, Bash, Scala, Groovy) and grammar handlers (`handlers/grammars/` — ArgoCD, Helm Chart, Helm Template, Helm Values, GitHub Actions, GitLab CI, Docker Compose, Kubernetes, Terraform) with autodiscovery registry
- **`dashboard/`** — Terminal (Rich) and web (Chart.js) dashboards. In stdio MCP mode, `server.py` launches uvicorn in a daemon thread running the MCP server's `sse_app()` — all routes are served from a single source of truth (no duplicated handlers). Web static assets are split into ES modules: `dashboard/web/static/index.html` (HTML only), `css/styles.css`, and `js/` with modules (`app.js` entry point, `state.js` shared state, `api.js`, `utils.js`, `charts.js`, `dashboard.js`, `index-mgmt.js`, `search.js`, `logs.js`, `theme.js`). Supports light (sepia parchment) and dark (Coco Orange Phosphor) themes via `theme.js` — OS preference (`prefers-color-scheme`) on first visit, user choice persisted in `localStorage['cocosearch-theme']`, with a FOUC-prevention inline script in `<head>` and Prism stylesheet swapping; charts and tab favicon re-read CSS variables on theme change. Static files served via `/static/{path}` route with path traversal protection.
- **`.claude-plugin/`** — Claude Code plugin metadata: `plugin.json` (MCP server definition, version, keywords) and `marketplace.json` (marketplace listing). Versions must match `pyproject.toml` — the release workflow syncs them automatically.

**Data flow:** Files → Tree-sitter parse → symbol extraction → chunking → embeddings (Ollama/OpenAI/OpenRouter) → PostgreSQL (pgvector). Search queries → embedding → hybrid RRF (vector similarity + tsvector keyword) → context expansion → results. Cross-index search: query → single embedding → parallel per-index search → score-based merge → unified results. `linkedIndexes` config auto-expands single-index searches to cross-index when linked indexes exist.

**Key patterns:**

- Singleton DB connection pool via `search.db` — reset between tests with `reset_db_pool()` autouse fixture in `tests/conftest.py`
- Handler autodiscovery: any `handlers/*.py` (not prefixed with `_`) implementing `LanguageHandler` protocol is auto-registered. Grammar handlers in `handlers/grammars/*.py` are also autodiscovered. YAML-based grammar handlers inherit from `YamlGrammarBase` (`handlers/grammars/_base.py`) for shared comment stripping, matching, and fallback metadata chain. `include_patterns` in `IndexingConfig` are auto-derived from handler `EXTENSIONS` and grammar `PATH_PATTERNS`.
- CocoIndex framework orchestrates the indexing pipeline in `indexer/flow.py`
- **CocoIndex table naming:** `codeindex_{index_name}__{index_name}_chunks` (flow name `CodeIndex_{name}` is lowercased by CocoIndex). Parse results go to `cocosearch_parse_results_{index_name}`.
- Parse status categories: `ok`, `partial`, `error`, `no_grammar`. Text-only formats (md, yaml, json, etc.) are skipped from parse tracking entirely via `_SKIP_PARSE_EXTENSIONS` in `indexer/parse_tracking.py`.
- Dependency extractor autodiscovery: any `deps/extractors/*.py` (not prefixed with `_`) implementing `DependencyExtractor` protocol is auto-registered. Lookup by `language_id` (file extension or grammar name, e.g., "py", "js", "go", "md", "mdx", "docker-compose", "github-actions", "terraform", "helm-template", "helm-values", "helm-chart"). Dependency edges stored in `cocosearch_deps_{index_name}`. Module resolvers in `deps/resolver.py` are registered per language_id and resolve module names to file paths after extraction. Extraction is incremental by default: SHA-256 content hashes tracked in `cocosearch_deps_tracking_{index_name}` detect changed/added/deleted files; only dirty files are re-extracted, then ALL edges are re-resolved for correctness. Successful extraction stamps `deps_extracted_at` in `cocosearch_index_metadata` for staleness detection by MCP dependency tools. Use `--fresh` to force full re-extraction.

## Testing

All tests are unit tests (`tests/unit/`), fully mocked and requiring no infrastructure. `uv run pytest` runs them by default.

**Markers are auto-applied** by conftest.py — tests under `tests/unit/` get `@pytest.mark.unit` automatically. No need to add them manually.

Async tests use `pytest-asyncio` with `strict` mode — async test functions must be decorated with `@pytest.mark.asyncio`.

Shared fixtures live in `tests/fixtures/`.

Symbol extraction tests live in `tests/unit/indexer/symbols/` (one file per language). Handler tests are in `tests/unit/handlers/`.

Dashboard tests in `tests/unit/dashboard/` include HTML structure tests (`test_html_structure.py`) and ASGI integration tests (`test_dashboard_serving.py`) that exercise the full Starlette stack via `httpx.AsyncClient` + `ASGITransport`. API smoke tests in `tests/unit/mcp/test_api_smoke.py` similarly test key endpoints through the ASGI app. When adding dashboard routes or static assets, add corresponding ASGI integration tests.

## Adding Language Support

Three independent systems — a language can use any combination. See `docs/adding-languages.md` for the full guide.

**Language Handler** (custom chunking for languages not in CocoIndex's built-in list):

1. Copy `src/cocosearch/handlers/_template.py` to `<language>.py`
2. Define `EXTENSIONS`, `SEPARATOR_SPEC` (using `CustomLanguageSpec`), and `extract_metadata()`
3. Include patterns are auto-derived from `EXTENSIONS` — no manual `config.py` edit needed
4. Separators must use standard regex only — no lookaheads/lookbehinds (CocoIndex uses Rust regex)
5. Create `tests/unit/handlers/test_<language>.py`

**Symbol Extraction** (enables `--symbol-type`/`--symbol-name` filtering):

1. Create `src/cocosearch/indexer/queries/<language>.scm` with tree-sitter queries
2. Add the language to `LANGUAGE_MAP` in `src/cocosearch/indexer/symbols.py`
3. Create `tests/unit/indexer/symbols/test_<language>.py`

**Grammar Handler** (domain-specific chunking within a base language, e.g. GitHub Actions within YAML):

1. Copy `src/cocosearch/handlers/grammars/_template.py` to `<grammar>.py`
2. For YAML-based grammars, inherit `YamlGrammarBase` and implement `_has_content_markers()` and `_extract_grammar_metadata()`
3. Create `tests/unit/handlers/grammars/test_<grammar>.py`

## Adding Skills

Workflow skills are SKILL.md files that guide AI coding assistants through structured workflows using CocoSearch MCP tools.

1. Create `skills/cocosearch-<name>/SKILL.md` with YAML frontmatter (`name`, `description`) and the workflow steps
2. Run `./scripts/sync_skills.sh` to sync skills into the Python package
3. Add to the skills table in `skills/README.md`
4. Add to all installation `for` loops in `skills/README.md` (Claude Code project-local, global, OpenCode project-local, global)
5. Update skill count in `skills/README.md` ("all N skills")
6. Add to the Workflow Skills list in the Plugin Usage section of this file
7. Update `tests/unit/config/test_generator.py` expected skill count

Skills are autodiscovered by `_get_bundled_skills()` in `src/cocosearch/config/generator.py` — any `cocosearch-*` subdirectory under `src/cocosearch/skills/` with a `SKILL.md` is included automatically. No manual registration in code is needed.

## Configuration

Project config via `cocosearch.yaml` (no leading dot) in project root. The `indexName` field sets the index name used by all commands. The `linkedIndexes` field (list of strings) declares related indexes for automatic cross-index search expansion — when set, search tools auto-include linked indexes without requiring explicit `index_names` parameter (missing linked indexes are skipped gracefully; explicit `index_names` overrides config). Environment variables prefixed with `COCOSEARCH_` (e.g., `COCOSEARCH_DATABASE_URL`, `COCOSEARCH_OLLAMA_URL`). Config keys map to env vars via camelCase→UPPER_SNAKE conversion (e.g., `indexName` → `COCOSEARCH_INDEX_NAME`). `COCOSEARCH_EDITOR` is a runtime env var (not a config field) for the dashboard's "Open in Editor" feature — falls back to `$EDITOR` then `$VISUAL`. See `.env.example` for available options.

**Logging:** Log file output is disabled by default. Enable via `logging.file: true` in `cocosearch.yaml` or `COCOSEARCH_LOG_FILE=true` env var. Logs are written to `~/.cocosearch/logs/cocosearch.log` with 10MB rotation and 3 backups. The web dashboard log panel supports category filtering (search, index, mcp, cache, infra, system, deps) and level filtering (DEBUG+, INFO+, WARN+, ERROR+).

**Auto-reindex (keep the index fresh automatically):** Three composable layers, all sharing one core (`src/cocosearch/auto_reindex.py`).
- **MCP server watchdog** (Layer 1, on by default, stdio transport) — `_start_auto_reindex_watchdog` runs a daemon thread that polls `check_branch_staleness()` for the detected project + its `linkedIndexes` every `intervalSeconds` (default 60). On branch/commit drift it calls `trigger_reindex()`, reusing the existing `_indexing_lock` / `_active_indexing` dict so it coordinates with `/api/reindex` (one reindex at a time per index). Configure via `autoReindex.enabled`/`autoReindex.intervalSeconds` in `cocosearch.yaml` or env vars `COCOSEARCH_AUTO_REINDEX_ENABLED` / `COCOSEARCH_AUTO_REINDEX_INTERVAL_SECONDS`. Env vars override config.
- **Git hooks** (Layer 2, opt-in per repo) — `cocosearch hooks install` writes marker-wrapped blocks into `post-checkout`, `post-merge`, `post-commit`, and `post-rewrite` hooks under `$(git rev-parse --git-common-dir)/hooks/` (worktree-safe). Each hook fires `cocosearch index . --deps --if-exists --quiet` in the background. Append-safe with husky/pre-commit/lefthook; idempotent install; clean uninstall. `cocosearch hooks status` reports coexistence.
- **`cocosearch watch`** (Layer 3, foreground) — Polling loop that calls `auto_reindex.run_reindex_sync()` every `--interval` seconds (default 30). Cheap because `flow.update()` is already content-hash incremental. Handles SIGINT cleanly. `--no-deps` skips the dependency graph refresh.

Dependency extraction auto-runs on every trigger if the `cocosearch_deps_{index}` table exists (indexes never built with `--deps` stay fast).

**Embedding providers:** CocoSearch supports multiple embedding providers: `ollama` (default, local), `openai`, and `openrouter`. Provider selection is via `COCOSEARCH_EMBEDDING_PROVIDER` env var or the `embedding.provider` field in `cocosearch.yaml`. Remote providers require `COCOSEARCH_EMBEDDING_API_KEY` (unless `baseUrl` is set for local OpenAI-compatible servers). `COCOSEARCH_EMBEDDING_BASE_URL` (or `embedding.baseUrl` in config) overrides the provider's default endpoint — use it with local OpenAI-API-compatible servers (Infinity, text-embeddings-inference, vLLM). For the `ollama` provider, `baseUrl` overrides `COCOSEARCH_OLLAMA_URL`. Default models: ollama→`nomic-embed-text`, openai→`text-embedding-3-small`, openrouter→`openai/text-embedding-3-small`. Index metadata tracks which provider/model was used; switching requires `--fresh` reindex.

**Docker / client mode env vars:**
- `COCOSEARCH_SERVER_URL` — When set, CLI forwards commands to the remote server instead of running locally (e.g., `http://localhost:3000`)
- `COCOSEARCH_PATH_PREFIX` — Host↔container path rewriting for client mode (e.g., `~/GIT:/projects`)
- `COCOSEARCH_PROJECTS_DIR` — Directory to scan for available projects. Dashboard shows unindexed projects with an "Index Now" option. Defaults to `.` in `cocosearch dashboard`; set to `/projects` in docker-compose.yml. Override with `--projects-dir` flag.
- `PROJECTS_DIR` — Docker Compose variable: directory to mount into the app container as `/projects` (default: `.`)
- `COCOSEARCH_MCP_PORT` — Server port, used by both CLI and Docker Compose (default: `3000`)
- `COCOSEARCH_IDLE_TIMEOUT` — Idle timeout in seconds for stdio MCP servers; auto-exits after inactivity (default: `1800` / 30 min, `0` to disable)

**Docker deployment:**
```bash
docker compose --profile app --profile ollama up --build  # Full stack (local embeddings)
docker compose --profile app up --build                   # DB + app only (remote embeddings)
docker compose --profile ollama up -d                     # PostgreSQL + Ollama (local dev)
```

**Docker MCP (SSE transport):** The container runs an SSE-based MCP server. Connect AI assistants directly via URL instead of spawning a local process:
```bash
claude mcp add --scope user cocosearch --url http://localhost:3000/sse
```

## Documentation Policy

**Always update documentation when making code changes.** This includes:

- **CLAUDE.md / AGENTS.md** — Update module descriptions, counts, patterns, and commands when adding/removing/modifying modules, handlers, CLI commands, MCP tools, or architectural patterns. `AGENTS.md` is a symlink to `CLAUDE.md`, so only one file needs editing.
- **docs/** — Update relevant docs (`architecture.md`, `how-it-works.md`, `retrieval.md`, `adding-languages.md`) when changing the systems they describe
- **README.md** — Update feature lists, usage examples, or screenshots when user-facing behavior changes
- **`.claude-plugin/`** — Plugin version files (`plugin.json`, `marketplace.json`) and `src/cocosearch/__init__.py` must stay in sync with `pyproject.toml`. The release workflow handles this automatically. If editing `marketplace.json` descriptions or `plugin.json` metadata manually, ensure accuracy (skill count, server command).

Documentation updates should be part of the same change, not deferred to a follow-up.

## Plugin Usage (for projects using the CocoSearch plugin)

When this plugin is active, you have access to MCP tools and workflow skills for code search.

### MCP Tools

- `search_code` — Semantic + keyword hybrid search. Always use `use_hybrid_search=True` and `smart_context=True`. Optional `include_deps=True` attaches dependency info to results. Optional `index_names` parameter for cross-index search across multiple projects. Auto-expands to include `linkedIndexes` from `cocosearch.yaml` when `index_names` is not explicitly provided.
- `analyze_query` — Pipeline diagnostics: see why a query returns specific results (stage timings, mode selection, RRF fusion breakdown). Optional `index_names` parameter for cross-index analysis with per-index breakdowns.
- `index_codebase` — Index a directory for search
- `list_indexes` — List all available indexes
- `index_stats` — Statistics and health for an index
- `clear_index` — Remove one or more indexes (supports `index_name` for single, `index_names` for bulk deletion)
- `get_file_dependencies` — Forward dependency query: what does a file depend on? `depth=1` returns flat edge list, `depth>1` returns transitive tree. Includes staleness warnings when deps are outdated.
- `get_file_impact` — Reverse impact query: what would be affected if a file changes? Returns transitive impact tree. Includes staleness warnings when deps are outdated.
- `get_batch_dependencies` — Batch forward dependency query for multiple files. Shared visited set eliminates redundant traversal of overlapping subgraphs. More efficient than per-file calls for git diff analysis. Includes staleness warnings.
- `get_batch_impact` — Batch reverse impact query for multiple files. Shared visited set across all roots. More efficient than per-file calls for change blast radius analysis. Includes staleness warnings.

### Search Best Practices

- Always check `cocosearch.yaml` for `indexName` first — use it for all operations
- `use_hybrid_search=True` — combines semantic + keyword via RRF fusion
- `smart_context=True` — expands to full function/class boundaries via Tree-sitter
- `symbol_name` with glob patterns for precision (e.g., `User*`)
- `symbol_type` for structural filtering: "function", "class", "method", "interface"
- ALWAYS use CocoSearch tools instead of Grep/Glob for code search — see "Tool Routing" section above

### Workflow Skills

- `/cocosearch:cocosearch-quickstart` — First-time setup and verification
- `/cocosearch:cocosearch-onboarding` — Guided codebase tour
- `/cocosearch:cocosearch-explore` — "How does X work?" (autonomous or interactive)
- `/cocosearch:cocosearch-debugging` — Root cause analysis
- `/cocosearch:cocosearch-deps` — Dependency graph exploration (impact, connections, hubs)
- `/cocosearch:cocosearch-refactoring` — Impact analysis and safe refactoring
- `/cocosearch:cocosearch-new-feature` — Pattern-matching feature development
- `/cocosearch:cocosearch-add-language` — Add language support (handlers, symbols, context expansion)
- `/cocosearch:cocosearch-add-grammar` — Add grammar handler (domain-specific formats within a base language)
- `/cocosearch:cocosearch-add-extractor` — Add dependency extractor (enables `deps tree`, `deps impact`, dependency-enriched search)
- `/cocosearch:cocosearch-review-pr` — Review GitHub PRs / GitLab MRs with blast radius and dependency analysis
- `/cocosearch:cocosearch-commit` — Smart commit messages: analyzes diffs with semantic search and dependency impact

### Prerequisites

Docker running PostgreSQL 17 (pgvector) on port 5432 and Ollama on port 11434. Use `/cocosearch:cocosearch-quickstart` to verify.

## CocoSearch Tool Routing

When CocoSearch MCP tools are available, ALWAYS use them instead of Grep, Glob, or Task/Explore agents for code search and exploration:

| Task | Use this | NOT this |
|------|----------|----------|
| Code search / "how does X work?" | `search_code` | Grep, Glob, Task (Explore) |
| Symbol lookup / "find function Y" | `search_code` with `symbol_name`/`symbol_type` | Grep for def/class patterns |
| Dependency tracing / "what imports X?" | `get_file_dependencies` / `get_file_impact` | Grep for import statements |
| Batch dependency analysis (multiple files) | `get_batch_dependencies` / `get_batch_impact` | Per-file `get_file_dependencies` calls |
| Search debugging / "why no results?" | `analyze_query` | Manual pipeline investigation |

Fall back to Grep/Glob ONLY for:
- Exact literal string matches (e.g., a specific error message or config value)
- File path pattern matching (e.g., "find all `*.test.ts` files")
- Editing operations that need line numbers from a known file
