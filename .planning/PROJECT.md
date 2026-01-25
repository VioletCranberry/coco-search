# CocoSearch

## What This Is

A local-first semantic code search tool exposed via MCP and CLI. Point it at a codebase, it indexes using CocoIndex with Ollama embeddings and PostgreSQL storage, then search semantically through natural language queries. Built for understanding unfamiliar codebases without sending code to external services.

## Core Value

Semantic code search that runs entirely locally — no data leaves your machine.

## Requirements

### Validated

- Index a codebase directory under a named index — v1.0
- Search a named index with natural language, return relevant code chunks — v1.0
- Clear a specific named index — v1.0
- Support multiple named indexes simultaneously — v1.0
- Run PostgreSQL via Docker for vector storage (pgvector) — v1.0
- Use Ollama for local embeddings (nomic-embed-text) — v1.0
- Expose functionality via MCP server — v1.0
- Language-aware chunking via Tree-sitter (15+ languages) — v1.0
- Respect .gitignore patterns — v1.0
- File filtering with include/exclude patterns — v1.0
- Incremental indexing (only changed files) — v1.0
- Return file paths, line numbers, and relevance scores — v1.0
- Limit results to avoid context overflow — v1.0
- Filter results by programming language — v1.0
- List all indexes and show statistics — v1.0

### Active

(None yet — planning v2)

### Out of Scope

- Answer synthesis inside MCP — Claude (the caller) handles synthesis from returned chunks
- Cloud storage or external embedding APIs — this is local-first
- Real-time file watching / auto-reindex — manual index trigger only
- Web UI — MCP and CLI interface only

## Context

Shipped v1.0 with 2,432 LOC Python.
Tech stack: CocoIndex, PostgreSQL + pgvector, Ollama, FastMCP.
Primary use case: onboarding to unfamiliar codebases via semantic search.

## Constraints

- **Runtime**: PostgreSQL in Docker, Ollama running locally
- **Package manager**: UV (not pip)
- **Interface**: MCP server + CLI
- **Privacy**: All processing local — no external API calls

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| CocoIndex as indexing engine | User-specified, designed for this use case | Good |
| Ollama for embeddings | Local-first requirement, no external APIs | Good |
| PostgreSQL in Docker | Vector storage with pgvector, easy local setup | Good |
| MCP returns chunks only | Simpler architecture, calling LLM synthesizes | Good |
| Named indexes | Support multiple codebases without conflicts | Good |
| Package name: cocosearch | Clarity over default coco_s from directory | Good |
| Ollama native (not Docker) | Simplicity for Phase 1 per research | Good |
| pgvector/pgvector:pg17 image | Pre-compiled extension, official | Good |
| Reference-only storage | Store filename + location, not chunk text | Good |
| Direct PostgreSQL queries | Simpler than CocoIndex query handlers, more control | Good |
| JSON output by default | MCP/tool integration, --pretty for humans | Good |
| cmd module over prompt_toolkit | Standard library sufficient for REPL | Good |
| Git root detection for auto-index | More reliable than cwd when in subdirectories | Good |
| Logging to stderr in MCP | Prevents stdout corruption of JSON-RPC protocol | Good |

---
*Last updated: 2026-01-25 after v1.0 milestone*
