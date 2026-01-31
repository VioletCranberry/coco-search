# CocoSearch

## What This Is

A local-first semantic code search tool exposed via MCP and CLI. Point it at a codebase, it indexes using CocoIndex with Ollama embeddings and PostgreSQL storage, then search semantically through natural language queries. Built for understanding unfamiliar codebases without sending code to external services. Supports DevOps files (Terraform, Dockerfile, Bash) with language-aware chunking and rich metadata extraction. Configurable via YAML config file with developer setup automation.

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
- User documentation with installation guide and quick start — v1.1
- MCP setup guides for Claude Code, Claude Desktop, and OpenCode — v1.1
- CLI reference documentation — v1.1
- Full pytest test suite with mocked dependencies — v1.1
- README.md quick start (CLI demo → MCP setup) — v1.1
- Custom chunking rules for HCL (Terraform) via CocoIndex custom_languages — v1.2
- Custom chunking rules for Dockerfile via CocoIndex custom_languages — v1.2
- Custom chunking rules for Bash/Shell via CocoIndex custom_languages — v1.2
- File patterns for DevOps files (*.tf, *.hcl, Dockerfile, *.sh, *.bash) — v1.2
- Rich metadata: block type, hierarchy, language ID extraction for DevOps chunks — v1.2
- DevOps language search filtering with alias resolution — v1.2
- Graceful degradation for pre-v1.2 indexes — v1.2
- Docker-based integration tests (real PostgreSQL+pgvector) — v1.3
- Ollama integration tests with native detection and Docker fallback — v1.3
- E2E flow tests (index → search → verify results) — v1.3
- Test organization with unit/integration separation and pytest markers — v1.3
- Session-scoped container fixtures for test performance — v1.3
- DevOps E2E validation (Terraform, Dockerfile, Bash with alias resolution) — v1.3
- ✓ Project config file (cocosearch.yaml) with index settings, patterns, and custom options — v1.4
- ✓ CLI flag precedence over config file with environment variable support — v1.4
- ✓ Developer setup script (dev-setup.sh) for Docker infrastructure and auto-indexing — v1.4
- ✓ Self-indexing CocoSearch's own codebase as dogfooding validation — v1.4

### Active

**v1.5 Configuration & Architecture Polish**

- Environment variable substitution in config values (e.g., `${COCOSEARCH_DATABASE_URL}`)
- Standardize all env vars to COCOSEARCH_* prefix across code, .env, docs
- Pluggable language chunking with per-language modules and registry pattern
- README table of contents for navigation

### Out of Scope

- Answer synthesis inside MCP — Claude (the caller) handles synthesis from returned chunks
- Cloud storage or external embedding APIs — this is local-first
- Real-time file watching / auto-reindex — manual index trigger only
- Web UI — MCP and CLI interface only
- Dockerfile stage tracking for non-FROM instructions — requires two-pass processing
- Block type / hierarchy search filters — validate demand first
- Config inheritance (base + override) — complexity vs value tradeoff, skip for now
- Per-directory config overrides — skip for now, reassess if demand emerges

## Current State

Shipped v1.4 with 3,801 LOC Python (src/).
Tech stack: CocoIndex, PostgreSQL + pgvector, Ollama, FastMCP.
Primary use case: onboarding to unfamiliar codebases via semantic search.
DevOps support: HCL (Terraform), Dockerfile, Bash with language-aware chunking and metadata.
Test coverage: 327 unit tests + integration tests with real PostgreSQL and Ollama.
Documentation: Comprehensive README with Quick Start, Installation, MCP config, CLI reference, dogfooding example.
Configuration: YAML config file with init command, 4-level precedence (CLI > env > config > default).
Developer setup: One-command bootstrap via dev-setup.sh with Docker Compose.

## Constraints

- **Runtime**: PostgreSQL in Docker, Ollama in Docker (dev-setup.sh) or native
- **Package manager**: UV (not pip)
- **Interface**: MCP server + CLI
- **Privacy**: All processing local — no external API calls

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| CocoIndex as indexing engine | User-specified, designed for this use case | ✓ Good |
| Ollama for embeddings | Local-first requirement, no external APIs | ✓ Good |
| PostgreSQL in Docker | Vector storage with pgvector, easy local setup | ✓ Good |
| MCP returns chunks only | Simpler architecture, calling LLM synthesizes | ✓ Good |
| Named indexes | Support multiple codebases without conflicts | ✓ Good |
| Package name: cocosearch | Clarity over default coco_s from directory | ✓ Good |
| Ollama native (not Docker) | Simplicity for Phase 1 per research | ✓ Good |
| pgvector/pgvector:pg17 image | Pre-compiled extension, official | ✓ Good |
| Reference-only storage | Store filename + location, not chunk text | ✓ Good |
| Direct PostgreSQL queries | Simpler than CocoIndex query handlers, more control | ✓ Good |
| JSON output by default | MCP/tool integration, --pretty for humans | ✓ Good |
| cmd module over prompt_toolkit | Standard library sufficient for REPL | ✓ Good |
| Git root detection for auto-index | More reliable than cwd when in subdirectories | ✓ Good |
| Logging to stderr in MCP | Prevents stdout corruption of JSON-RPC protocol | ✓ Good |
| Zero new dependencies for DevOps | CocoIndex custom_languages + Python stdlib re only | ✓ Good |
| Single flow architecture for DevOps | All file types through same pipeline, not separate flows | ✓ Good |
| Regex-only metadata extraction | No external parsers; upgrade path to python-hcl2 exists | ✓ Good |
| Empty strings over NULLs for metadata | Simplifies SQL, consistent pattern across all files | ✓ Good |
| Standard Rust regex for separators | CocoIndex uses regex v1.12.2, not fancy-regex | ✓ Good |
| Additive schema only | No primary key changes, safe schema migration | ✓ Good |
| Module-level graceful degradation | One-time flag prevents repeated failing SQL for pre-v1.2 indexes | ✓ Good |
| Flat metadata in MCP response | Top-level fields, not nested, for simplicity | ✓ Good |
| Default unit-only test execution | Fast feedback via -m unit marker in pytest addopts | ✓ Good |
| Session-scoped container fixtures | One container per session for performance | ✓ Good |
| TRUNCATE CASCADE for test cleanup | Fast cleanup, preserves schema | ✓ Good |
| Native-first Ollama detection | Check localhost:11434 before Docker fallback | ✓ Good |
| E2E tests via subprocess CLI | Environment propagation, realistic testing | ✓ Good |
| Nested config sections (indexing, search, embedding) | Better organization, clear grouping | ✓ Good |
| camelCase config keys | Consistency across config, JavaScript-friendly | ✓ Good |
| CLI > env > config > default precedence | Intuitive override model | ✓ Good |
| Docker-based Ollama for dev-setup | Consistency across developer environments | ✓ Good |
| Plain text output in dev-setup.sh | CI-friendly, grep-able, works in all terminals | ✓ Good |
| Minimal dogfooding config | Shows defaults work well, lowers barrier | ✓ Good |

---
*Last updated: 2026-01-31 after v1.5 milestone started*
