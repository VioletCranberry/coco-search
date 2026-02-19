# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CocoSearch is a local-first hybrid semantic code search tool powered by CocoIndex and Tree-sitter. It indexes codebases into PostgreSQL with pgvector embeddings (via Ollama) and provides search through CLI, MCP server, or interactive REPL. No external APIs — everything runs locally. Requires Python >=3.11.

## Development Setup

```bash
# Prerequisites: Docker, uv (Python package manager)
# One-command setup (starts infra, pulls model, installs deps, indexes codebase):
./dev-setup.sh

# Or manually:
docker compose up -d                    # PostgreSQL 17 + Ollama
uv sync                                 # Install dependencies
uv run cocosearch index .               # Index the codebase
```

**Infrastructure:** PostgreSQL 17 (pgvector) on port 5432, Ollama on port 11434. Defaults require no `.env` file.

**Optional AI chat:** `uv sync --extra web-chat` installs `claude-agent-sdk` for the dashboard AI chat feature. Requires `claude` CLI on PATH (Claude Code users).

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
uv run cocosearch analyze "query"    # Pipeline analysis with diagnostics
uv run cocosearch analyze "query" --json  # JSON pipeline analysis
uv run cocosearch stats
uv run cocosearch list
uv run cocosearch clear <index>
uv run cocosearch languages              # List supported languages
uv run cocosearch grammars               # List supported grammars
uv run cocosearch init                   # Initialize cocosearch.yaml
uv run cocosearch config show
uv run cocosearch config path
uv run cocosearch config check
uv run cocosearch dashboard              # Terminal dashboard

# MCP server
uv run cocosearch mcp --project-from-cwd
```

## Architecture

**Entry points:** `cocosearch.cli:main` (CLI) and `cocosearch.mcp.server` (MCP via FastMCP).

**Module structure:**

- **`cli.py`** — Argparse CLI orchestrating all subcommands. When `COCOSEARCH_SERVER_URL` is set, dispatches to `client.py` instead of local execution.
- **`client.py`** — HTTP client for remote server mode. `CocoSearchClient` forwards CLI commands to a running CocoSearch server via HTTP API (`/api/search`, `/api/index`, `/api/stats`, `/api/list`, `/api/analyze`, `/api/languages`, `/api/grammars`, `/api/delete-index`). Path translation via `COCOSEARCH_PATH_PREFIX` rewrites host↔container paths.
- **`exceptions.py`** — Structured exception hierarchy: `CocoSearchError` (base), `IndexNotFoundError`, `IndexValidationError`, `SearchError`, `InfrastructureError`. Inherits from `ValueError` where needed for backward compatibility.
- **`validation.py`** — Input validation guards: `validate_index_name()` (SQL injection protection for dynamic table names), `validate_query()` (resource exhaustion protection, max 10,000 chars)
- **`mcp/server.py`** — MCP server exposing tools (search_code, analyze_query, index_codebase, etc.) + web dashboard with HTTP API (`/api/stats`, `/api/reindex`, `/api/search`, `/api/project`, `/api/projects`, `/api/index`, `/api/stop-indexing`, `/api/delete-index`, `/api/list`, `/api/analyze`, `/api/languages`, `/api/grammars`, `/api/open-in-editor`, `/api/file-content`, `/health`, `/api/heartbeat` SSE, `/api/ai-chat/*` AI chat)
- **`mcp/project_detection.py`** — Auto-detect project from MCP Roots or CWD
- **`indexer/`** — CocoIndex pipeline: file filtering (`file_filter.py`), Tree-sitter symbol extraction (15 languages via `.scm` queries in `indexer/queries/`), Ollama embedding, tsvector generation, parse health tracking, schema migration, preflight validation (`preflight.py`), progress reporting (`progress.py`)
- **`indexer/flow.py`** — CocoIndex flow definition (the indexing pipeline)
- **`search/`** — Hybrid search engine: RRF fusion of vector + keyword results, two-level LRU query cache (`cache.py` — exact + semantic similarity at cosine > 0.92), context expansion via Tree-sitter boundaries for 8 languages (`context_expander.py`, exports `CONTEXT_EXPANSION_LANGUAGES`), symbol/language filtering (`filters.py`), auto-detection of code identifiers for hybrid mode (`query_analyzer.py`), interactive REPL (`repl.py`), result formatting (`formatter.py`), pipeline analysis with stage-by-stage diagnostics (`analyze.py`)
- **`search/db.py`** — PostgreSQL connection pool (singleton) and query execution
- **`config/`** — YAML config with 4-level precedence resolution (CLI > env > file > defaults), `${VAR}` substitution (`env_substitution.py`), Pydantic schema validation (`schema.py` with `extra="forbid"`, `strict=True`), user-friendly error formatting with fuzzy field suggestions (`errors.py`), env var validation (`env_validation.py`)
- **`management/`** — Index lifecycle: discovery (`discovery.py`), stats (`stats.py`), clearing (`clear.py`), git-based naming (`git.py`), metadata with collision detection and status tracking (`metadata.py`), project root detection (`context.py`)
- **`handlers/`** — Language-specific chunking (HCL, Go Template, Dockerfile, Bash, Scala, Groovy) and grammar handlers (`handlers/grammars/` — Helm Template, Helm Values, GitHub Actions, GitLab CI, Docker Compose, Kubernetes, Terraform) with autodiscovery registry
- **`chat/`** — Optional AI chat module powered by the Claude Agent SDK (`claude-agent-sdk`). `ChatSession` wraps `ClaudeSDKClient` in a private asyncio event loop thread; `ChatSessionManager` is a singleton managing up to 10 concurrent sessions with 30-minute idle timeout. The agent has access to Read, Grep, Glob and a custom `search_codebase` MCP tool wrapping `cocosearch.search.search()`. Requires `cocosearch[web-chat]` optional dependency and `claude` CLI on PATH.
- **`dashboard/`** — Terminal (Rich) and web (Chart.js) dashboards with optional AI chat (inline `[Search] [Ask AI]` toggle with markdown rendering, tool use display, and session stats)
- **`.claude-plugin/`** — Claude Code plugin metadata: `plugin.json` (MCP server definition, version, keywords) and `marketplace.json` (marketplace listing). Versions must match `pyproject.toml` — the release workflow syncs them automatically.

**Data flow:** Files → Tree-sitter parse → symbol extraction → chunking → Ollama embeddings → PostgreSQL (pgvector). Search queries → embedding → hybrid RRF (vector similarity + tsvector keyword) → context expansion → results.

**Key patterns:**

- Singleton DB connection pool via `search.db` — reset between tests with `reset_db_pool()` autouse fixture in `tests/conftest.py`
- Handler autodiscovery: any `handlers/*.py` (not prefixed with `_`) implementing `LanguageHandler` protocol is auto-registered. Grammar handlers in `handlers/grammars/*.py` are also autodiscovered. Total custom language specs: 13 (6 language + 7 grammar) — update count assertions in `tests/unit/handlers/test_registry.py` and `tests/unit/handlers/test_grammar_registry.py` when adding handlers
- CocoIndex framework orchestrates the indexing pipeline in `indexer/flow.py`
- **CocoIndex table naming:** `codeindex_{index_name}__{index_name}_chunks` (flow name `CodeIndex_{name}` is lowercased by CocoIndex). Parse results go to `cocosearch_parse_results_{index_name}`.
- Parse status categories: `ok`, `partial`, `error`, `no_grammar`. Text-only formats (md, yaml, json, etc.) are skipped from parse tracking entirely via `_SKIP_PARSE_EXTENSIONS` in `indexer/parse_tracking.py`.

## Testing

All tests are unit tests (`tests/unit/`), fully mocked and requiring no infrastructure. `uv run pytest` runs them by default.

**Markers are auto-applied** by conftest.py — tests under `tests/unit/` get `@pytest.mark.unit` automatically. No need to add them manually.

Async tests use `pytest-asyncio` with `strict` mode — async test functions must be decorated with `@pytest.mark.asyncio`.

Shared fixtures live in `tests/fixtures/`.

Symbol extraction tests live in `tests/unit/indexer/symbols/` (one file per language). Handler tests are in `tests/unit/handlers/`.

## Adding Language Support

Three independent systems — a language can use any combination. See `docs/adding-languages.md` for the full guide.

**Language Handler** (custom chunking for languages not in CocoIndex's built-in list):

1. Copy `src/cocosearch/handlers/_template.py` to `<language>.py`
2. Define `EXTENSIONS`, `SEPARATOR_SPEC` (using `CustomLanguageSpec`), and `extract_metadata()`
3. Add file extensions to `include_patterns` in `src/cocosearch/indexer/config.py`
4. Separators must use standard regex only — no lookaheads/lookbehinds (CocoIndex uses Rust regex)
5. Create `tests/unit/handlers/test_<language>.py`

**Symbol Extraction** (enables `--symbol-type`/`--symbol-name` filtering):

1. Create `src/cocosearch/indexer/queries/<language>.scm` with tree-sitter queries
2. Add the language to `LANGUAGE_MAP` in `src/cocosearch/indexer/symbols.py`
3. Create `tests/unit/indexer/symbols/test_<language>.py`

**Grammar Handler** (domain-specific chunking within a base language, e.g. GitHub Actions within YAML):

1. Copy `src/cocosearch/handlers/grammars/_template.py` to `<grammar>.py`
2. Define path patterns, content matchers, separators, and metadata extraction
3. Create `tests/unit/handlers/test_<grammar>.py`

After adding any handler/grammar, update the count assertions in `tests/unit/handlers/test_registry.py` and `tests/unit/handlers/test_grammar_registry.py`.

## Code Exploration

When exploring or searching this codebase, prefer CocoSearch MCP tools (`search_code`, `list_indexes`, `index_stats`) over raw Grep/Glob for semantic and symbol-aware search. Use CocoSearch first for questions like "how does X work?", "find code related to Y", or symbol lookups. Fall back to Grep/Glob only for exact string matches or file pattern lookups.

## Configuration

Project config via `cocosearch.yaml` (no leading dot) in project root. The `indexName` field sets the index name used by all commands. Environment variables prefixed with `COCOSEARCH_` (e.g., `COCOSEARCH_DATABASE_URL`, `COCOSEARCH_OLLAMA_URL`). Config keys map to env vars via camelCase→UPPER_SNAKE conversion (e.g., `indexName` → `COCOSEARCH_INDEX_NAME`). `COCOSEARCH_EDITOR` is a runtime env var (not a config field) for the dashboard's "Open in Editor" feature — falls back to `$EDITOR` then `$VISUAL`. See `.env.example` for available options.

**Docker / client mode env vars:**
- `COCOSEARCH_SERVER_URL` — When set, CLI forwards commands to the remote server instead of running locally (e.g., `http://localhost:3000`)
- `COCOSEARCH_PATH_PREFIX` — Host↔container path rewriting for client mode (e.g., `~/GIT:/projects`)
- `COCOSEARCH_PROJECTS_DIR` — Directory to scan for available projects. Dashboard shows unindexed projects with an "Index Now" option. Defaults to `.` in `cocosearch dashboard`; set to `/projects` in docker-compose.yml. Override with `--projects-dir` flag.
- `PROJECTS_DIR` — Docker Compose variable: directory to mount into the app container as `/projects` (default: `.`)
- `COCOSEARCH_MCP_PORT` — Server port, used by both CLI and Docker Compose (default: `3000`)

**Docker deployment:**
```bash
docker compose --profile app up --build          # Full stack (db + ollama + app)
PROJECTS_DIR=~/GIT docker compose --profile app up  # Mount projects directory
docker compose up -d                              # Infrastructure only (unchanged)
```

**Docker MCP (SSE transport):** The container runs an SSE-based MCP server. Connect AI assistants directly via URL instead of spawning a local process:
```bash
claude mcp add --scope user cocosearch --url http://localhost:3000/sse
```

## Documentation Policy

**Always update documentation when making code changes.** This includes:

- **CLAUDE.md** — Update module descriptions, counts, patterns, and commands when adding/removing/modifying modules, handlers, CLI commands, MCP tools, or architectural patterns
- **docs/** — Update relevant docs (`architecture.md`, `how-it-works.md`, `retrieval.md`, `adding-languages.md`) when changing the systems they describe
- **Test count assertions** — Update handler/grammar count assertions in `tests/unit/handlers/test_registry.py` and `tests/unit/handlers/test_grammar_registry.py` when adding handlers
- **README.md** — Update feature lists, usage examples, or screenshots when user-facing behavior changes
- **`.claude-plugin/`** — Plugin version files (`plugin.json`, `marketplace.json`) and `src/cocosearch/__init__.py` must stay in sync with `pyproject.toml`. The release workflow handles this automatically. If editing `marketplace.json` descriptions or `plugin.json` metadata manually, ensure accuracy (skill count, server command).

Documentation updates should be part of the same change, not deferred to a follow-up.

## Plugin Usage (for projects using the CocoSearch plugin)

When this plugin is active, you have access to MCP tools and workflow skills for code search.

### MCP Tools

- `search_code` — Semantic + keyword hybrid search. Always use `use_hybrid_search=True` and `smart_context=True`.
- `analyze_query` — Pipeline diagnostics: see why a query returns specific results (stage timings, mode selection, RRF fusion breakdown)
- `index_codebase` — Index a directory for search
- `list_indexes` — List all available indexes
- `index_stats` — Statistics and health for an index
- `clear_index` — Remove an index

### Search Best Practices

- Always check `cocosearch.yaml` for `indexName` first — use it for all operations
- `use_hybrid_search=True` — combines semantic + keyword via RRF fusion
- `smart_context=True` — expands to full function/class boundaries via Tree-sitter
- `symbol_name` with glob patterns for precision (e.g., `User*`)
- `symbol_type` for structural filtering: "function", "class", "method", "interface"
- Prefer CocoSearch tools over Grep/Glob for semantic and intent-based queries

### Workflow Skills

- `/cocosearch:cocosearch-quickstart` — First-time setup and verification
- `/cocosearch:cocosearch-onboarding` — Guided codebase tour
- `/cocosearch:cocosearch-explore` — "How does X work?" (autonomous or interactive)
- `/cocosearch:cocosearch-debugging` — Root cause analysis
- `/cocosearch:cocosearch-refactoring` — Impact analysis and safe refactoring
- `/cocosearch:cocosearch-new-feature` — Pattern-matching feature development
- `/cocosearch:cocosearch-subway` — Codebase visualization as subway map
- `/cocosearch:cocosearch-add-language` — Add language support (handlers, symbols, context expansion)
- `/cocosearch:cocosearch-add-grammar` — Add grammar handler (domain-specific formats within a base language)

### Prerequisites

Docker running PostgreSQL 17 (pgvector) on port 5432 and Ollama on port 11434. Use `/cocosearch:cocosearch-quickstart` to verify.
