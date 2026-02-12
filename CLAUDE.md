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
uv run cocosearch stats
uv run cocosearch list
uv run cocosearch config check

# MCP server
uv run cocosearch mcp --project-from-cwd
```

## Architecture

**Entry points:** `cocosearch.cli:main` (CLI) and `cocosearch.mcp.server` (MCP via FastMCP).

**Module structure:**

- **`cli.py`** — Argparse CLI orchestrating all subcommands
- **`mcp/server.py`** — MCP server exposing tools (search_code, index_codebase, etc.) + web dashboard with custom HTTP routes (`/api/stats`, `/api/reindex`)
- **`mcp/project_detection.py`** — Auto-detect project from MCP Roots or CWD
- **`indexer/`** — CocoIndex pipeline: file filtering, Tree-sitter symbol extraction (14 languages via `.scm` queries in `indexer/queries/`), Ollama embedding, tsvector generation, parse health tracking, schema migration
- **`indexer/flow.py`** — CocoIndex flow definition (the indexing pipeline)
- **`search/`** — Hybrid search engine: RRF fusion of vector + keyword results, LRU query cache (exact + semantic similarity), context expansion via Tree-sitter boundaries, symbol/language filtering
- **`search/db.py`** — PostgreSQL connection pool (singleton) and query execution
- **`config/`** — YAML config with 4-level precedence resolution (CLI > env > file > defaults), `${VAR}` substitution
- **`management/`** — Index lifecycle: discovery, stats, clearing, git-based naming, metadata
- **`handlers/`** — Language-specific chunking (HCL, Go Template, Dockerfile, Bash, Scala) and grammar handlers (`handlers/grammars/` — Helm Template, Helm Values, GitHub Actions, GitLab CI, Docker Compose, Kubernetes) with autodiscovery registry
- **`dashboard/`** — Terminal (Rich) and web (Chart.js) dashboards

**Data flow:** Files → Tree-sitter parse → symbol extraction → chunking → Ollama embeddings → PostgreSQL (pgvector). Search queries → embedding → hybrid RRF (vector similarity + tsvector keyword) → context expansion → results.

**Key patterns:**

- Singleton DB connection pool via `search.db` — reset between tests with `reset_db_pool()` autouse fixture in `tests/conftest.py`
- Handler autodiscovery: any `handlers/*.py` (not prefixed with `_`) implementing `LanguageHandler` protocol is auto-registered. Grammar handlers in `handlers/grammars/*.py` are also autodiscovered. Total custom language specs: 11 (5 language + 6 grammar) — update `test_languages.py` and `test_flow.py` count assertions when adding handlers
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

After adding any handler/grammar, update the count assertion in `test_languages.py` and `test_flow.py`.

## Configuration

Project config via `cocosearch.yaml` (no leading dot) in project root. The `indexName` field sets the index name used by all commands. Environment variables prefixed with `COCOSEARCH_` (e.g., `COCOSEARCH_DATABASE_URL`, `COCOSEARCH_OLLAMA_URL`). Config keys map to env vars via camelCase→UPPER_SNAKE conversion (e.g., `indexName` → `COCOSEARCH_INDEX_NAME`). See `.env.example` for available options.
