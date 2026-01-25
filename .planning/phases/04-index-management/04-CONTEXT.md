# Phase 4: Index Management - Context

**Gathered:** 2026-01-25
**Status:** Ready for planning

<domain>
## Phase Boundary

CLI commands and MCP server for managing multiple named indexes. Users can list, inspect, and clear indexes through CLI. Claude can access all index operations through MCP tools. Indexing and search functionality already exist from prior phases.

</domain>

<decisions>
## Implementation Decisions

### CLI management commands
- JSON output by default, `--pretty` for Rich-formatted human output (consistent with search command)
- `cocosearch list` shows all indexes
- `cocosearch stats` without index shows stats for all indexes
- `cocosearch stats <index>` shows stats for specific index
- `cocosearch clear <index>` prompts for confirmation by default
- `--force` flag skips confirmation on clear

### MCP server integration
- Full tool suite exposed: search, list_indexes, stats, clear, index
- Launch via `cocosearch mcp` subcommand (stdio transport)
- Search results return full content (actual code chunks with file paths and lines)
- No auto-start of infrastructure — return helpful error if Postgres/Ollama not running

### Index naming & discovery
- Auto-detect index from git root directory name when inside a repo
- Always print "Using index: {name}" before results (both JSON and pretty modes)
- If not in a git repo and no `--index` specified: error with clear message
- Explicit `--index` flag overrides auto-detection

### Statistics display
- Metrics: file count, chunk count, last indexed time, storage size
- Storage size from `pg_table_size()` query for accuracy
- Show staleness: "X files modified since last index"

### Claude's Discretion
- Staleness check implementation (scan files vs stored metadata) — balance accuracy and performance
- Exact error message wording for infrastructure not running
- MCP tool parameter naming and descriptions

</decisions>

<specifics>
## Specific Ideas

- "Using index: myapp" hint printed before any output so user knows which index is active
- Confirmation prompt for clear: "Delete index X? [y/N]"

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-index-management*
*Context gathered: 2026-01-25*
