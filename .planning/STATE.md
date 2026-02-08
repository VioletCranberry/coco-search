# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-08)

**Core value:** Semantic code search that runs entirely locally -- no data leaves your machine.
**Current focus:** Phase 45 - MCP Protocol Enhancements

## Current Position

Phase: 45 of 47 (MCP Protocol Enhancements)
Plan: 01 of ~4 (project detection module)
Status: In progress
Last activity: 2026-02-08 -- Completed 45-01-PLAN.md

Progress: [#####...............] 25% (5/~20 plans across v1.10)

## Performance Metrics

**Velocity:**
- Total plans completed: 118 (across v1.0-v1.10)
- Milestones shipped: 10 (v1.0-v1.9)
- Last milestone: v1.9 Multi-Repo & Polish (phases 38-42, 11 plans)

**By Recent Milestone:**

| Milestone | Phases | Plans | Shipped |
|-----------|--------|-------|---------|
| v1.10 Infrastructure & Protocol | 43-47 | 5/~20 | In progress |
| v1.9 Multi-Repo & Polish | 38-42 | 11 | 2026-02-06 |
| v1.8 Polish & Observability | 33-37 | 13 | 2026-02-05 |
| v1.7 Search Enhancement | 27-32 | 21 | 2026-02-03 |

*Updated: 2026-02-08 after 45-01 execution*

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

### Pending Todos

None -- ready for 45-02.

### Blockers/Concerns

**Research flags for later phases:**
- Phase 45 (MCP Roots): Validate `ctx.session.list_roots()` across transports; Claude Desktop does NOT support roots
- Phase 45 (HTTP Query Params): Verify Starlette query params accessible through FastMCP SDK transport layer
- Pre-existing MCP test failures in tests/unit/mcp/test_server.py (2 tests) -- unrelated to phase 43 work

## Session Continuity

Last session: 2026-02-08
Stopped at: Completed 45-01-PLAN.md (project detection module). Ready for 45-02.
Resume file: None
