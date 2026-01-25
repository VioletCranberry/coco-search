---
phase: 04-index-management
plan: 03
subsystem: mcp
tags: [mcp, fastmcp, llm-integration, stdio-transport, tools]
dependency-graph:
  requires:
    - phase: 04-01
      provides: management functions (list_indexes, get_stats, clear_index)
    - phase: 03-search
      provides: search function and utilities
  provides:
    - MCP server with 5 tools for LLM integration
    - CLI 'mcp' subcommand for server launch
  affects: [claude-integration, llm-tooling]
tech-stack:
  added: []
  patterns: [fastmcp-tool-decorator, stderr-logging-for-stdio]
key-files:
  created:
    - src/cocosearch/mcp/__init__.py
    - src/cocosearch/mcp/server.py
  modified:
    - src/cocosearch/cli.py
key-decisions:
  - "Logging to stderr via logging.basicConfig to avoid stdout corruption of JSON-RPC protocol"
  - "Lazy import of run_server in mcp_command to avoid loading MCP dependencies until needed"
patterns-established:
  - "MCP tools import from existing modules (management, search, indexer)"
  - "Tool functions return dicts for JSON serialization"
  - "Error handling returns success/error dict instead of raising exceptions"
metrics:
  duration: 4 min
  completed: 2026-01-25
---

# Phase 04 Plan 03: MCP Server Summary

**FastMCP server exposing 5 tools (search_code, list_indexes, index_stats, clear_index, index_codebase) via stdio transport for Claude and LLM integration**

## Performance

- **Duration:** 4 min
- **Started:** 2026-01-25T14:30:00Z
- **Completed:** 2026-01-25T14:34:00Z
- **Tasks:** 2
- **Files created:** 2
- **Files modified:** 1

## Accomplishments
- Created MCP server module with FastMCP framework
- Exposed all index management and search functionality as MCP tools
- Added `cocosearch mcp` CLI command for server launch
- Configured logging to stderr to prevent stdio protocol corruption

## Task Commits

Each task was committed atomically:

1. **Task 1: Create MCP server module with tools** - `9914cfc` (feat)
2. **Task 2: Add 'mcp' subcommand to CLI** - `694f068` (feat)

## Files Created/Modified

- `src/cocosearch/mcp/__init__.py` - Module exports (mcp, run_server)
- `src/cocosearch/mcp/server.py` - FastMCP server with 5 tools
- `src/cocosearch/cli.py` - Added mcp_command and mcp subparser

## MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `search_code` | Search indexed code using natural language | query, index_name, limit, language |
| `list_indexes` | List all available indexes | (none) |
| `index_stats` | Get statistics for one or all indexes | index_name (optional) |
| `clear_index` | Delete an index (with warning) | index_name |
| `index_codebase` | Index a codebase directory | path, index_name (optional) |

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Logging to stderr immediately at module load | Prevents stdout corruption of JSON-RPC protocol; must happen before any other imports |
| Lazy import of run_server in CLI | Avoids loading MCP dependencies until `cocosearch mcp` is actually invoked |
| Return dicts from tool functions | Easy JSON serialization for MCP protocol |
| Error returns as `{success: False, error: ...}` | Graceful error handling without exceptions in MCP context |

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Usage

**Start MCP server:**
```bash
cocosearch mcp
```

**Claude Desktop configuration (claude_desktop_config.json):**
```json
{
  "mcpServers": {
    "cocosearch": {
      "command": "uv",
      "args": ["run", "cocosearch", "mcp"],
      "cwd": "/path/to/coco-s"
    }
  }
}
```

## Next Phase Readiness

- MCP server complete with all planned tools
- Ready for LLM integration testing
- Phase 4 complete after 04-02 CLI commands are committed

---
*Phase: 04-index-management*
*Completed: 2026-01-25*
