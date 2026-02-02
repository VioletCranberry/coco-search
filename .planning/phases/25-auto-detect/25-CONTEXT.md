# Phase 25: Auto-Detect Feature - Context

**Gathered:** 2026-02-02
**Status:** Ready for planning

<domain>
## Phase Boundary

MCP automatically detects project context from working directory, eliminating the need for explicit `index_name` in tool calls. Uses priority chain: cocosearch.yaml indexName > git repo name > directory name. Handles collisions and missing indexes gracefully.

</domain>

<decisions>
## Implementation Decisions

### Detection Strategy
- Walk up directory tree to find .git directory (git root = project root)
- If no .git found, fall back to cocosearch.yaml search, then directory name
- Resolve symlinks to real paths (use realpath()) to avoid duplicate indexes
- Priority chain: cocosearch.yaml indexName > git repo name > directory name

### Collision Handling
- Detect collisions when same index name maps to different paths
- Warn at both index time AND auto-detect time
- On collision: fail with guidance (don't auto-detect, don't proceed with warning)
- Store path-to-index mappings in database (add path column to index metadata)
- Collision message shows both options: set indexName in cocosearch.yaml OR use --index-name flag

### Missing Index Behavior
- When auto-detected project has no index: return prompt in tool response
- Tool response includes both: CLI command (`cocosearch index /path --name name`) and MCP tool suggestion (`index_codebase`)
- If cocosearch.yaml exists but no index: use config settings (indexName if present) in the prompt

### Config File Discovery
- For git repos: look for cocosearch.yaml at git root only
- For non-git directories: look for cocosearch.yaml in cwd only
- If config exists but no indexName: use git repo directory name
- Read all config settings (ignore patterns, file extensions, etc.), not just indexName

### Claude's Discretion
- Caching strategy for path-to-index mappings (memory vs disk vs none)
- Exact error message wording
- Database schema details for path storage

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 25-auto-detect*
*Context gathered: 2026-02-02*
