# CocoSearch

## What This Is

A local-first semantic code search tool exposed via MCP and CLI. Point it at a codebase, it indexes using CocoIndex with Ollama embeddings and PostgreSQL storage, then search semantically through natural language queries. Built for understanding unfamiliar codebases without sending code to external services. Supports 31 languages including DevOps files (Terraform, Dockerfile, Bash) with language-aware chunking, symbol extraction, and rich metadata. Features hybrid search (vector + keyword), context expansion, and symbol filtering. Configurable via YAML config file with developer setup automation. Available as all-in-one Docker container or native installation.

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
- Project config file (cocosearch.yaml) with index settings, patterns, and custom options — v1.4
- CLI flag precedence over config file with environment variable support — v1.4
- Developer setup script (dev-setup.sh) for Docker infrastructure and auto-indexing — v1.4
- Self-indexing CocoSearch's own codebase as dogfooding validation — v1.4
- Environment variable substitution in config values (`${VAR}` and `${VAR:-default}` syntax) — v1.5
- Standardized all env vars to COCOSEARCH_* prefix (DATABASE_URL, OLLAMA_URL) — v1.5
- CLI config check command for env var validation with source display — v1.5
- Registry-based language handlers with autodiscovery (HCL, Dockerfile, Bash) — v1.5
- README table of contents with emoji prefixes and back-to-top navigation — v1.5
- CHANGELOG.md with migration guide for breaking env var changes — v1.5
- All-in-one Docker image bundling Ollama+model, PostgreSQL+pgvector, CocoSearch MCP — v1.6
- Pre-pulled nomic-embed-text model baked into image — v1.6
- SSE transport for Claude Desktop (HTTP-based MCP) — v1.6
- Streamable HTTP transport for future MCP standard — v1.6
- stdio transport for Claude Code / OpenCode — v1.6
- Auto-detect project from cwd (infer index from working directory) — v1.6
- Detection priority: cocosearch.yaml indexName > directory name — v1.6
- Collision detection: track source path per index, require explicit name on conflict — v1.6
- cocosearch.yaml `indexName` field for explicit naming — v1.6
- Prompt user when auto-detected index doesn't exist — v1.6
- Docker Quick Start documentation with MCP client configuration — v1.6
- Troubleshooting guide for Docker deployments — v1.6
- Hybrid search combining vector similarity + keyword matching via RRF fusion — v1.7
- CLI --hybrid flag and MCP use_hybrid_search parameter — v1.7
- Query analyzer detects identifier patterns (camelCase, snake_case) for auto-hybrid — v1.7
- GIN index on content_tsv for keyword search performance — v1.7
- Context expansion with -A/-B/-C flags and smart tree-sitter boundaries — v1.7
- MCP context_before, context_after, smart_context parameters — v1.7
- LRU cache for file I/O during context expansion — v1.7
- Symbol-aware indexing with tree-sitter extraction (Python, JS, TS, Go, Rust) — v1.7
- Symbol filtering with --symbol-type and --symbol-name CLI flags — v1.7
- MCP symbol_type and symbol_name parameters for symbol filtering — v1.7
- Definition boost (2x) in hybrid search results — v1.7
- Full language coverage: 31 languages (28 standard + 3 DevOps) — v1.7
- `cocosearch languages` command for language discovery — v1.7
- Per-language statistics in `cocosearch stats` command — v1.7
- Comprehensive v1.7 feature documentation in README — v1.7
- Hybrid + symbol filter combination (filters before RRF fusion) — v1.8
- Nested symbol hierarchy (ClassName.method_name format) — v1.8
- Query caching with exact hash and semantic similarity (0.95 cosine) — v1.8
- Symbol extraction for 10 languages (Java, C, C++, Ruby, PHP added) — v1.8
- External .scm query files for user-extensible symbol extraction — v1.8
- Stats CLI with health metrics, language breakdown, staleness warnings — v1.8
- HTTP API endpoint for stats (/api/stats) — v1.8
- Terminal dashboard with Rich Layout and Unicode graphs — v1.8
- Web UI dashboard with Chart.js visualization — v1.8
- Claude Code skill with installation and routing guidance — v1.8
- OpenCode skill with installation and routing guidance — v1.8
- README rebrand with hybrid search positioning — v1.8

### Active

**Planning next milestone**

### Out of Scope

- Answer synthesis inside MCP — Claude (the caller) handles synthesis from returned chunks
- Cloud storage or external embedding APIs — this is local-first
- Real-time file watching / auto-reindex — manual index trigger only
- Dockerfile stage tracking for non-FROM instructions — requires two-pass processing
- Block type / hierarchy search filters — validate demand first
- Config inheritance (base + override) — complexity vs value tradeoff, skip for now
- Per-directory config overrides — skip for now, reassess if demand emerges
- Multi-step workflow skills (onboarding, debugging, refactoring) — deferred from v1.8
- Retrieval logic documentation — deferred from v1.8
- MCP tools reference documentation — deferred from v1.8

## Current State

Shipped v1.8 with 9,210 LOC Python (src/).
Tech stack: CocoIndex, PostgreSQL + pgvector, Ollama, FastMCP, tree-sitter, tree-sitter-language-pack.
Primary use case: onboarding to unfamiliar codebases via hybrid search.
Language support: 31 languages (28 standard + 3 DevOps) with symbol extraction for 10.
Search features: Hybrid search (RRF), context expansion, symbol filtering, query caching, definition boost.
Observability: CLI stats, HTTP API, terminal dashboard, web UI with Chart.js.
Test coverage: 550+ unit tests + integration tests with real PostgreSQL and Ollama.
Documentation: README with hybrid search positioning, developer skills for Claude Code and OpenCode.
Configuration: YAML config with env var substitution, 4-level precedence, config check command.
Developer setup: One-command bootstrap via dev-setup.sh with Docker Compose.
Docker deployment: All-in-one container with s6-overlay, multi-transport support (stdio/SSE/HTTP).
Auto-detect: Project detection from working directory with collision handling.
Environment: COCOSEARCH_DATABASE_URL (required), COCOSEARCH_OLLAMA_URL (optional).

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
| Env var substitution after YAML parse | Resolves before Pydantic validation | ✓ Good |
| COCOSEARCH_* env var prefix | Consistent naming, clear ownership | ✓ Good |
| Registry-based language handlers | Autodiscovery, easy extension | ✓ Good |
| Protocol-based handler interface | Duck typing, no inheritance required | ✓ Good |
| TOC with emoji prefixes | Visual distinction, professional appearance | ✓ Good |
| Keep a Changelog format | Industry standard for change documentation | ✓ Good |
| RRF k=60 for hybrid search | Standard value for rank fusion constant | ✓ Good |
| PostgreSQL 'simple' text config | No stemming for code identifiers | ✓ Good |
| Two-phase tsvector generation | Python preprocessing + PostgreSQL generated column | ✓ Good |
| Tree-sitter 0.21.x for symbols | API compatibility with tree-sitter-languages | ✓ Good |
| Qualified method names format | ClassName.method_name for clarity | ✓ Good |
| Instance-level LRU cache | Search session isolation for context expansion | ✓ Good |
| 50-line context cap | Prevent unbounded context growth | ✓ Good |
| Definition boost after RRF | 2x multiplier applied post-fusion | ✓ Good |
| Symbol filters before RRF | Apply WHERE clause to both vector/keyword before fusion | ✓ Good |
| In-memory session-scoped cache | Simpler than diskcache, sufficient for repeated queries | ✓ Good |
| 0.95 cosine threshold for semantic cache | Balances cache hits with query relevance | ✓ Good |
| tree-sitter-language-pack 0.13.0 | Modern API, external query file support | ✓ Good |
| External .scm query files | User-extensible symbol extraction | ✓ Good |
| IndexStats dataclass | Single source of truth for all health metrics | ✓ Good |
| Single-page HTML dashboard | No build step, embedded CSS/JS | ✓ Good |
| Chart.js via CDN | Zero-config, browser caching | ✓ Good |
| Hybrid search tagline | Better positioning than "semantic search" | ✓ Good |

---
*Last updated: 2026-02-05 after v1.8 milestone complete*
