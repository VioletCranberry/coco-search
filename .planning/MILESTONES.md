# Project Milestones: CocoSearch

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
