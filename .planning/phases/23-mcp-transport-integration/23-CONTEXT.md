# Phase 23: MCP Transport Integration - Context

**Gathered:** 2026-02-01
**Status:** Ready for planning

<domain>
## Phase Boundary

MCP server supports multiple transport protocols (stdio, SSE, Streamable HTTP) selectable at runtime via CLI flag or environment variable. Single transport active per server instance. Existing stdio behavior preserved as default.

</domain>

<decisions>
## Implementation Decisions

### Port Configuration
- Single `--port` flag used by whichever network transport is active
- Default port: 3000 when not specified
- Environment variable: `COCOSEARCH_MCP_PORT` (follows existing naming convention)
- Priority: CLI flag wins over environment variable

### Default & Fallback Behavior
- Default transport: stdio (backwards compatible — no change for existing users)
- Invalid transport value: error and exit with clear message listing valid options
- Always log transport and port on startup (all transports, including stdio)
- For SSE/HTTP: log full connection URL (e.g., "Connect at http://localhost:3000/sse")

### Multi-Transport Mode
- Single transport only per server instance
- Multiple instances expected pattern: user runs separate processes for different transports
- If `--port` specified with stdio transport: warn and ignore (not an error)
- Available transports listed in `--help` output only, no separate `--list-transports` flag

### Connection Lifecycle
- Port already in use: error and exit with clear message
- SIGTERM/SIGINT handling: immediate shutdown (no graceful wait period)
- SSE client disconnection: log at debug level only
- Health endpoint: GET `/health` returns 200 OK (for Docker healthcheck, load balancers)

### Claude's Discretion
- SSE endpoint path conventions (e.g., `/sse` vs `/events`)
- HTTP Streamable endpoint path conventions
- Exact error message wording
- Debug log format for disconnections

</decisions>

<specifics>
## Specific Ideas

- Environment variables should follow existing `COCOSEARCH_*` prefix pattern
- Full connection URL in logs for easy copy-paste into client config
- Health endpoint enables Docker HEALTHCHECK in Phase 24

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 23-mcp-transport-integration*
*Context gathered: 2026-02-01*
