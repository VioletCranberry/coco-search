# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-08)

**Core value:** Semantic code search that runs entirely locally -- no data leaves your machine.
**Current focus:** Phase 45 - MCP Protocol Enhancements

## Current Position

Phase: 45 of 47 (MCP Protocol Enhancements)
Plan: 03 of ~4 (test suite)
Status: In progress
Last activity: 2026-02-08 -- Completed 45-03-PLAN.md

Progress: [#######.............] 35% (7/~20 plans across v1.10)

## Performance Metrics

**Velocity:**
- Total plans completed: 120 (across v1.0-v1.10)
- Milestones shipped: 10 (v1.0-v1.9)
- Last milestone: v1.9 Multi-Repo & Polish (phases 38-42, 11 plans)

**By Recent Milestone:**

| Milestone | Phases | Plans | Shipped |
|-----------|--------|-------|---------|
| v1.10 Infrastructure & Protocol | 43-47 | 7/~20 | In progress |
| v1.9 Multi-Repo & Polish | 38-42 | 11 | 2026-02-06 |
| v1.8 Polish & Observability | 33-37 | 13 | 2026-02-05 |
| v1.7 Search Enhancement | 27-32 | 21 | 2026-02-03 |

*Updated: 2026-02-08 after 45-03 execution*

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

### Pending Todos

None -- ready for 45-04.

### Blockers/Concerns

**Research flags for later phases:**
- Phase 45 (MCP Roots): Validate `ctx.session.list_roots()` across transports; Claude Desktop does NOT support roots
- Phase 45 (HTTP Query Params): Verify Starlette query params accessible through FastMCP SDK transport layer
- Pre-existing CLI test failure: tests/unit/test_cli.py::TestIndexCommand::test_valid_path_runs_indexing (missing register_index_path mock -- not MCP-related)

## Session Continuity

Last session: 2026-02-08
Stopped at: Completed 45-03-PLAN.md (test suite). Ready for 45-04.
Resume file: None
