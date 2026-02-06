# Project Milestones: CocoSearch

## v1.9 Multi-Repo & Polish (Shipped: 2026-02-06)

**Delivered:** Single MCP registration for all projects via --project-from-cwd, codebase cleanup removing 237+ LOC of deprecated code, three adaptive workflow skills (onboarding, debugging, refactoring), and comprehensive technical documentation covering architecture, retrieval logic, and MCP tools reference.

**Phases completed:** 38-42 (11 plans total)

**Key accomplishments:**

- Multi-repo MCP support with --project-from-cwd flag, staleness warnings, and unindexed-repo prompts
- Fixed 29 failing tests (1022 passing) with corrected symbol signature extraction and CLI mocks
- Removed 237+ LOC of deprecated modules (languages.py, metadata.py) and v1.2 graceful degradation
- Three adaptive workflow skills (773 lines): onboarding, debugging, refactoring with index freshness checks
- Technical documentation (811 lines): architecture overview, retrieval logic with RRF formulas, MCP tools reference

**Stats:**

- 27 files created/modified
- +2,043 / -485 lines (9,012 Python LOC in src/)
- 5 phases, 11 plans
- 1 day (2026-02-05 → 2026-02-06)

**Git range:** `feat(38-01)` → `docs(42)`

**What's next:** Planning next milestone

---

## v1.8 Polish & Observability (Shipped: 2026-02-05)

**Delivered:** Query caching with semantic similarity, symbol extraction expanded to 10 languages (Java, C, C++, Ruby, PHP), stats dashboard with CLI/terminal/web interfaces, developer skills for Claude Code and OpenCode, and documentation rebrand — comprehensive observability and polish for production use.

**Phases completed:** 33-37 (13 plans total)

**Key accomplishments:**

- Hybrid + symbol filter combination working together (filters applied before RRF fusion)
- Nested symbol display with fully qualified names (ClassName.method_name format)
- Query caching with exact hash and semantic similarity (0.95 cosine threshold)
- Symbol extraction for 10 languages with external .scm query files
- Stats dashboard: CLI with Unicode bars, HTTP API, terminal dashboard, web UI with Chart.js
- Developer skills: Claude Code and OpenCode SKILL.md with installation and routing guidance
- README rebrand: hybrid search positioning, observability section, language tiering

**Stats:**

- 81 files created/modified
- +15,962 / -987 lines (9,210 Python LOC in src/)
- 5 phases, 13 plans
- 3 days (2026-02-03 → 2026-02-05)

**Git range:** `docs(33)` → `docs(audit) v1.8`

**What's next:** Planning next milestone

---

## v1.7 Search Enhancement (Shipped: 2026-02-03)

**Delivered:** Hybrid search combining vector similarity and keyword matching via RRF fusion, context expansion with smart tree-sitter boundaries, symbol-aware indexing for 5 languages (Python, JS, TS, Go, Rust), and full language coverage (31 languages) — comprehensive search quality improvements for code understanding.

**Phases completed:** 27-32 (21 plans total)

**Key accomplishments:**

- Hybrid search with RRF fusion combining semantic vector similarity and keyword matching
- Query analyzer auto-detecting code identifiers (camelCase, snake_case) for automatic hybrid mode
- Context expansion with -A/-B/-C flags and smart tree-sitter boundary detection
- Symbol-aware indexing extracting functions, classes, and methods with tree-sitter
- Symbol filtering with --symbol-type and --symbol-name CLI flags and MCP parameters
- Definition boost (2x) ranking function/class definitions higher than references
- Full language coverage: 31 languages (28 standard + 3 DevOps)
- `cocosearch languages` command for language discovery with symbol support indicators
- Per-language statistics in `cocosearch stats` showing files, chunks, and lines per language

**Stats:**

- 100 files created/modified
- +21,906 lines (8,225 Python LOC in src/)
- 6 phases, 21 plans
- 1 day (2026-02-03)

**Git range:** `docs(27)` → `docs(32)`

**What's next:** v1.8 features (hybrid+symbol combination, nested symbol hierarchy, query caching)

---

## v1.6 All-in-One Docker & Auto-Detect (Shipped: 2026-02-02)

**Delivered:** All-in-one Docker container bundling PostgreSQL+pgvector, Ollama with pre-baked model, and MCP server under s6-overlay supervision — single `docker run` deployment with multi-transport support (stdio/SSE/HTTP) and auto-detect project from working directory.

**Phases completed:** 23-26 (11 plans total)

**Key accomplishments:**

- Multi-transport MCP server with stdio, SSE, and Streamable HTTP protocols selectable at runtime
- All-in-one Docker container with s6-overlay process supervision and service dependency chain
- Pre-baked nomic-embed-text model in image (274MB, no runtime download)
- Auto-detect project from working directory with path-to-index metadata storage
- Collision detection preventing different codebases from overwriting same index name
- Docker Quick Start documentation with Claude Code and Claude Desktop configuration examples

**Stats:**

- 77 files created/modified
- +8,616 lines (5,042 Python LOC in src/)
- 4 phases, 11 plans
- 2 days (2026-02-01 → 2026-02-02)

**Git range:** `feat(23-01)` → `docs(26)`

**What's next:** Multi-arch image publishing, init-time auto-indexing, or next feature milestone

---

## v1.5 Configuration & Architecture Polish (Shipped: 2026-02-01)

**Delivered:** Environment variable substitution in config files, standardized COCOSEARCH_* env var naming, registry-based language handler architecture, and professional README with comprehensive navigation — clean configuration patterns and extensible architecture.

**Phases completed:** 19-22 (11 plans total)

**Key accomplishments:**

- Config env var substitution with `${VAR}` and `${VAR:-default}` syntax in cocosearch.yaml
- Standardized all env vars to COCOSEARCH_* prefix (COCOSEARCH_DATABASE_URL, COCOSEARCH_OLLAMA_URL)
- CLI config check command (`cocosearch config check`) validating env vars with source display
- Registry-based language handlers with autodiscovery for HCL, Dockerfile, Bash
- Comprehensive README with emoji TOC, user journey structure, and back-to-top navigation
- CHANGELOG.md documenting breaking changes with migration guide

**Stats:**

- 69 files created/modified
- +8,138 / -478 lines (4,574 Python LOC in src/)
- 4 phases, 11 plans
- 1 day (2026-02-01)

**Git range:** `feat(19-01)` → `docs(22-01)`

**What's next:** Project stable, ready for new feature milestone or maintenance

---

## v1.4 Dogfooding Infrastructure (Shipped: 2026-01-31)

**Delivered:** Configuration system with YAML config file, developer setup script for one-command bootstrap, and dogfooding validation with CocoSearch indexing itself — four-level precedence chain (CLI > env > config > default) with helpful error messages.

**Phases completed:** 15-18 (7 plans total)

**Key accomplishments:**

- Configuration system with cocosearch.yaml supporting index settings, patterns, and embedding options
- Four-level precedence chain (CLI flag > environment variable > config file > default) with source tracking
- Developer setup script (dev-setup.sh) for one-command Docker environment bootstrap
- Dogfooding validation with CocoSearch indexing its own codebase
- Config commands (`coco config show/path`) for configuration inspection
- Typo detection and user-friendly error messages for config validation

**Stats:**

- 53 files created/modified
- +9,092 lines (3,801 Python LOC in src/)
- 4 phases, 7 plans, ~18 tasks
- 2 days (2026-01-30 → 2026-01-31)

**Git range:** `feat(15-01)` → `docs(18)`

**What's next:** v1.5 features (environment variable substitution, config inheritance, per-directory overrides)

---

## v1.3 Docker Integration Tests (Shipped: 2026-01-30)

**Delivered:** Docker-based integration test infrastructure validating real PostgreSQL+pgvector and Ollama behavior — E2E flows for indexing and search with DevOps file validation.

**Phases completed:** 11-14 (11 plans total)

**Key accomplishments:**

- Test infrastructure reorganized with pytest markers (unit vs integration)
- Docker container fixtures for PostgreSQL+pgvector with session-scoped containers
- Real pgvector integration tests validating vector similarity search
- Ollama embedding integration with native detection and warmup fixture
- End-to-end flow tests for CLI index/search with real services
- DevOps E2E validation for Terraform, Dockerfile, Bash with alias resolution

**Stats:**

- 45 files created/modified
- +6,676 lines (8,983 total Python LOC)
- 4 phases, 11 plans
- 1 day (2026-01-30)

**Git range:** `21d8d10` → `67f029a`

**What's next:** CI/CD integration deferred; ready for next feature milestone

---

## v1.2 DevOps Language Support (Shipped: 2026-01-27)

**Delivered:** Language-aware chunking and rich metadata extraction for HCL (Terraform), Dockerfile, and Bash/Shell files — zero new dependencies, single-flow pipeline with DevOps search filtering and metadata annotations.

**Phases completed:** 8-10, 4-soi (6 plans total)

**Key accomplishments:**

- Language-aware chunking for HCL, Dockerfile, and Bash via CocoIndex `CustomLanguageSpec` regex separators
- Rich metadata extraction (block type, hierarchy, language ID) for every DevOps chunk
- Zero-dependency pipeline integration with three new PostgreSQL columns via additive schema
- DevOps search filtering (`--lang terraform/dockerfile/bash`) with alias resolution
- Graceful degradation for pre-v1.2 indexes
- Full output surface coverage: JSON, pretty, and MCP metadata annotations with syntax highlighting

**Stats:**

- 51 files created/modified
- +8,253 / -1,148 lines (7,303 total Python LOC)
- 4 phases, 6 plans, 26 requirements
- 327 tests (all passing)
- 1 day (2026-01-27)

**Git range:** `8c86580` → `a753938`

**What's next:** v1.3+ features (block type search filter, hierarchy filter, Terraform provider inference)

---

## v1.1 Docs & Tests (Shipped: 2026-01-26)

**Delivered:** Test infrastructure and user documentation — 190 unit tests with mocked dependencies, comprehensive README with installation, MCP configuration, and CLI reference.

**Phases completed:** 5-7 (11 plans total)

**Key accomplishments:**

- Test infrastructure with pytest, async support, and mocking system
- 190 unit tests covering all modules (indexer, search, management, CLI, MCP)
- Mock system for PostgreSQL and Ollama enabling isolated testing
- 430-line README with architecture diagram and Quick Start
- MCP configuration guides for Claude Code, Claude Desktop, OpenCode
- CLI reference with all commands, flags, examples, and output

**Stats:**

- 34 files created/modified
- 3,458 lines added (5,401 total Python LOC)
- 3 phases, 11 plans
- 2 days (2026-01-25 → 2026-01-26)

**Git range:** `docs(05)` → `docs(v1.1)`

**What's next:** v2 features or next maintenance milestone

---

## v1.0 MVP (Shipped: 2026-01-25)

**Delivered:** Local-first semantic code search with MCP integration — index codebases, search with natural language, manage multiple indexes, all without sending data to external services.

**Phases completed:** 1-4 (11 plans total)

**Key accomplishments:**

- Local-first infrastructure with PostgreSQL + pgvector + Ollama
- Language-aware code indexing via Tree-sitter (15+ languages)
- Semantic vector search with natural language queries
- Multiple named indexes for isolated codebase search
- Rich CLI with JSON/pretty output and interactive REPL
- MCP server with 5 tools for LLM client integration

**Stats:**

- 58 files created/modified
- 2,432 lines of Python
- 4 phases, 11 plans, ~40 tasks
- 2 days from project start to ship

**Git range:** `feat(01-01)` → `feat(04-03)`

**What's next:** v2 features (chunk context expansion, hybrid search, symbol-aware indexing)

---
