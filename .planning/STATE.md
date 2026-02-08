# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-08)

**Core value:** Semantic code search that runs entirely locally -- no data leaves your machine.
**Current focus:** Phase 47 - Documentation Update

## Current Position

Phase: 46 of 47 (Parse Failure Tracking) — VERIFIED COMPLETE
Plan: Ready for phase 47
Status: Phase 46 verified and complete (4/4 must-haves passed)
Last activity: 2026-02-08 -- Phase 46 verified and complete

Progress: [##########..........] 50% (10/~20 plans across v1.10)

## Performance Metrics

**Velocity:**
- Total plans completed: 122 (across v1.0-v1.10)
- Milestones shipped: 10 (v1.0-v1.9)
- Last milestone: v1.9 Multi-Repo & Polish (phases 38-42, 11 plans)

**By Recent Milestone:**

| Milestone | Phases | Plans | Shipped |
|-----------|--------|-------|---------|
| v1.10 Infrastructure & Protocol | 43-47 | 10/~20 | In progress   |
| v1.9 Multi-Repo & Polish | 38-42 | 11 | 2026-02-06 |
| v1.8 Polish & Observability | 33-37 | 13 | 2026-02-05 |
| v1.7 Search Enhancement | 27-32 | 21 | 2026-02-03 |

*Updated: 2026-02-08 after 46-03 completion*

## Accumulated Context

### Decisions

Full decision log in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Docker = infra only (CocoSearch runs natively; Docker provides PostgreSQL+Ollama only)
- Docker base image switched from python:3.11-slim to debian:bookworm-slim
- PostgreSQL upgraded from 16 to 17 in Docker image (aligns with docker-compose.yml)
- Default DATABASE_URL to match Docker image creds, reduce setup friction
- Standardize cocosearch:cocosearch credentials everywhere
- .env.example DATABASE_URL marked as optional (commented out) since app has default
- dev-setup.sh messaging updated: env var is optional when using docker compose
- get_database_url() bridges COCOSEARCH_DATABASE_URL to COCOINDEX_DATABASE_URL as side-effect
- validate_required_env_vars() returns empty list (no required env vars remain)
- All DATABASE_URL callsites centralized through get_database_url()
- README Option #1 describes infra-only Docker (ports 5432+11434 only, no 3000)
- MCP docs note DATABASE_URL is optional when using Docker
- Documentation model: Docker = infrastructure, uvx = application
- _detect_project() returns tuple[Path, str] (never None) -- cwd is unconditional fallback
- file:// URI parsing uses urlparse+unquote (FileUrl.path does NOT percent-decode)
- No caching in _detect_project -- re-detect fresh each tool call
- Low-level server notification_handlers dict used for roots change (no FastMCP public API)
- Local import `from cocosearch.management.context import find_project_root` inside search_code body (exact mock target for tests)
- No None guard on _detect_project return -- cwd is unconditional fallback
- Hint for non-roots clients appended on every env/cwd detection call (no one-time suppression)
- Only search_code is async; other tools remain sync (no Context needed)
- McpError constructor requires ErrorData(code, message), not a plain string
- Mock _detect_project at definition site (cocosearch.mcp.project_detection._detect_project), not import site
- Mock find_project_root at cocosearch.management.context.find_project_root (matches local import)
- "No project detected" error removed in Plan 02; auto-detect tests expect "Index not found" when find_project_root returns (None, None)
- Store tree-sitter language name (e.g., "python") in parse_results.language, not file extension
- Parse tracking is non-fatal: wrapped in try/except in run_index()
- Post-flow tracking pattern: query chunks table for DISTINCT filenames, read from disk, process independently
- Parse health shown by default (not gated by --verbose); failure details require --show-failures flag
- Top-level import for get_parse_failures in server.py (consistent with get_comprehensive_stats import style)
- MCP index_stats upgraded from get_stats() to get_comprehensive_stats() for richer response data
- include_failures defaults to false on both MCP tool and HTTP endpoints

### Pending Todos

None -- ready for phase 47 planning.

### Blockers/Concerns

**Research flags for later phases:**
- Pre-existing CLI test failure: tests/unit/test_cli.py::TestIndexCommand::test_valid_path_runs_indexing (missing register_index_path mock -- not MCP-related)

## Session Continuity

Last session: 2026-02-08
Stopped at: Phase 46 verified complete. Ready for `/gsd:discuss-phase 47`.
Resume file: None
