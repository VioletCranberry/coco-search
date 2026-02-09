# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CocoSearch is a local-first hybrid semantic code search tool powered by CocoIndex and Tree-sitter. It indexes codebases into PostgreSQL with pgvector embeddings (via Ollama) and provides search through CLI, MCP server, or interactive REPL. No external APIs — everything runs locally.

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

# Run integration tests (requires Docker containers running)
uv run pytest tests/integration -m integration

# Run handler tests
uv run pytest tests/unit/handlers/ -v

# Lint
uv run ruff check src/ tests/

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
- **`mcp/server.py`** — MCP server exposing tools (search_code, index_codebase, etc.) + web dashboard
- **`mcp/project_detection.py`** — Auto-detect project from MCP Roots or CWD
- **`indexer/`** — CocoIndex pipeline: file filtering, Tree-sitter symbol extraction (10 languages), Ollama embedding, tsvector generation, parse health tracking, schema migration
- **`indexer/flow.py`** — CocoIndex flow definition (the indexing pipeline)
- **`search/`** — Hybrid search engine: RRF fusion of vector + keyword results, LRU query cache (exact + semantic similarity), context expansion via Tree-sitter boundaries, symbol/language filtering
- **`search/db.py`** — PostgreSQL connection pool (singleton) and query execution
- **`config/`** — YAML config with 4-level precedence resolution (CLI > env > file > defaults), `${VAR}` substitution
- **`management/`** — Index lifecycle: discovery, stats, clearing, git-based naming, metadata
- **`handlers/`** — Language-specific chunking for DevOps files (HCL, Dockerfile, Bash) with autodiscovery registry
- **`dashboard/`** — Terminal (Rich) and web (Chart.js) dashboards

**Data flow:** Files → Tree-sitter parse → symbol extraction → chunking → Ollama embeddings → PostgreSQL (pgvector). Search queries → embedding → hybrid RRF (vector similarity + tsvector keyword) → context expansion → results.

**Key patterns:**

- Singleton DB connection pool via `search.db` — reset between tests with `reset_db_pool()` auto-use fixture
- Handler autodiscovery: any `handlers/*.py` (not prefixed with `_`) implementing `LanguageHandler` protocol is auto-registered
- CocoIndex framework orchestrates the indexing pipeline in `indexer/flow.py`

## Testing

Tests are split into `tests/unit/` (mocked, default) and `tests/integration/` (real Docker containers via testcontainers). The default pytest marker is `unit` (set in `addopts`), so `uv run pytest` runs only unit tests.

Async tests use `pytest-asyncio` with `strict` mode — async test functions must be decorated with `@pytest.mark.asyncio`.

Integration tests use `testcontainers` to spin up PostgreSQL (port 5433) and Ollama automatically. Shared fixtures live in `tests/fixtures/`.

## Adding a Language Handler

1. Copy `src/cocosearch/handlers/_template.py` to `<language>.py`
2. Define `EXTENSIONS`, `SEPARATOR_SPEC` (using `CustomLanguageSpec`), and `extract_metadata()`
3. Separators must use standard regex only — no lookaheads/lookbehinds (CocoIndex uses Rust regex)
4. Create `tests/unit/handlers/test_<language>.py`
5. Run: `uv run pytest tests/unit/handlers/test_<language>.py -v`

## Configuration

Project config via `cocosearch.yaml` in project root. Environment variables prefixed with `COCOSEARCH_` (e.g., `COCOSEARCH_DATABASE_URL`, `COCOSEARCH_OLLAMA_URL`). See `.env.example` for available options.
