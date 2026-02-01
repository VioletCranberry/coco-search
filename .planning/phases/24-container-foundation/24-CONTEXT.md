# Phase 24: Container Foundation - Context

**Gathered:** 2026-02-01
**Status:** Ready for planning

<domain>
## Phase Boundary

All-in-one Docker container bundling PostgreSQL, Ollama, and MCP server under process supervision. Single `docker run cocosearch` starts everything. Volume mounts for code (`/mnt/repos:ro`) and data persistence (`/data`). Clean shutdown without data corruption.

</domain>

<decisions>
## Implementation Decisions

### Startup feedback
- Progress logs showing service-by-service status: "Starting PostgreSQL... ready. Starting Ollama... ready."
- Both stdout marker (`COCOSEARCH_READY`) AND Docker healthcheck for flexibility
- Quiet logs by default after startup (only errors/warnings), user adds `-e COCOSEARCH_LOG_LEVEL=debug` for more
- Ollama model warmup during startup so first real request is fast

### Port exposure
- Expose all services: MCP (3000), PostgreSQL (5432), Ollama (11434)
- All ports configurable via environment variables with COCOSEARCH_ prefix
  - COCOSEARCH_MCP_PORT, COCOSEARCH_PG_PORT, COCOSEARCH_OLLAMA_PORT
- All services bind to 0.0.0.0, accessible from host

### Configuration
- Default embedding model: nomic-embed-text, override with COCOSEARCH_EMBED_MODEL
- Auto-pull embedding model if not present (may be slow on first start)
- MCP transport configurable: COCOSEARCH_MCP_TRANSPORT=stdio|sse|streamable-http (default: streamable-http)
- Single /data volume contains pg_data, ollama_models, and cocosearch state

### Error behavior
- PostgreSQL failure: Retry 3 times with backoff, then exit with clear message
- Ollama failure: Retry 3 times with backoff, then exit with clear message
- Post-startup crashes: Process supervisor auto-restarts crashed services
- Tiered healthcheck: healthy/unhealthy/starting states based on which services are up

### Claude's Discretion
- Exact retry backoff timing
- Process supervisor choice (s6-overlay vs alternatives)
- Internal directory structure within /data
- Healthcheck endpoint implementation details

</decisions>

<specifics>
## Specific Ideas

- Environment variable naming: all use COCOSEARCH_ prefix for consistency
- Ready signal pattern: stdout marker for scripting + Docker healthcheck for orchestration
- Services should be fully accessible for debugging during development

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 24-container-foundation*
*Context gathered: 2026-02-01*
