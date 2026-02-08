# Phase 45: MCP Protocol Enhancements - Context

**Gathered:** 2026-02-08
**Status:** Ready for planning

<domain>
## Phase Boundary

MCP server detects the active project using the protocol-standard Roots capability with graceful fallback for unsupported clients. HTTP transport accepts query parameter for project context. Adds Streamable HTTP transport support alongside existing stdio and SSE.

</domain>

<decisions>
## Implementation Decisions

### Detection priority chain
- Priority order: roots > query_param > env > cwd — identical across all transports
- First match wins, but log when lower-priority sources disagree (aids debugging)
- If NO source provides a project path, return a clear error on tool call: "No project detected. Set COCOSEARCH_PROJECT or use --project-from-cwd."
- Project detection updates dynamically when roots change mid-session (re-detect on roots notification)

### Roots behavior
- Multiple roots: first root in the list wins (simple, predictable)
- file:// URI parsing: Unix-only for now (macOS and Linux). Windows support deferred.
- Invalid root path (doesn't exist on disk): silently skip, fall through to next source in priority chain
- Roots capability declaration: Claude's discretion (based on MCP spec and SDK behavior)

### Fallback experience
- When roots aren't available (e.g., Claude Desktop): use env > cwd silently, but include a one-time hint in the first tool response: "Tip: Use Claude Code for automatic project detection"
- Claude Desktop users: document both env var (COCOSEARCH_PROJECT in MCP config) and --project-from-cwd flag as options
- Unindexed project detected: return error with guidance — "Project detected at /path but not indexed. Run `cocosearch index /path` first."
- --project-from-cwd flag: keep indefinitely (useful for non-roots clients)

### HTTP query param design
- Parameter name: `project_path` (e.g., `?project_path=/path/to/repo`)
- Absolute paths only — no relative paths, no resolution against server cwd
- Per-request scope — each HTTP request can specify a different project
- Invalid path: return 400 Bad Request with message "Project path does not exist: /bad/path"
- Works on both SSE and Streamable HTTP transports

### Transport support
- Add Streamable HTTP transport alongside existing stdio and SSE
- Shared /mcp endpoint handles both SSE and Streamable HTTP (content negotiation)
- Existing `cocosearch mcp serve` commands unchanged — server auto-negotiates transport
- `project_path` query param available on all HTTP-based transports (SSE and Streamable HTTP)

### Claude's Discretion
- Whether to always declare Roots capability or conditionally
- Exact implementation of roots change notification handling
- Content negotiation mechanism for SSE vs Streamable HTTP on shared endpoint
- Logging format and verbosity for priority chain disagreements

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches following MCP protocol conventions and FastMCP SDK patterns.

</specifics>

<deferred>
## Deferred Ideas

- Windows file:// URI support — add when Windows users request it
- Multi-root search (searching across all workspace roots simultaneously) — future enhancement

</deferred>

---

*Phase: 45-mcp-protocol-enhancements*
*Context gathered: 2026-02-08*
