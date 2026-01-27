# Project Milestones: CocoSearch

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
