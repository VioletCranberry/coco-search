# Features Research: v1.9 Multi-Repo & Polish

## Executive Summary

Multi-repo MCP tools like Serena use a `--project-from-cwd` pattern that auto-detects the project root by walking up the directory tree looking for markers (`.git`, config files). CocoSearch already has the core auto-detect machinery in place (v1.6), but requires per-repo MCP registration. The key missing feature is a CLI flag (`--project-from-cwd` or equivalent) that enables single user-scope registration that works everywhere. The implementation is low complexity because the detection logic already exists.

## Table Stakes

Features required for Serena-style multi-repo functionality. Without these, the feature feels incomplete.

### Project Detection

- **`--project-from-cwd` CLI flag**: Enables project auto-detection mode for MCP server. When set, the server walks up from cwd looking for `.git` or `cocosearch.yaml` and uses that as the project root. This is the core Serena pattern. Complexity: **LOW** (detection logic exists in `management/context.py`)

- **User-scope registration support**: Single MCP registration at user scope (`--scope user`) that works across all repositories. The MCP server must detect the correct index at runtime, not registration time. Complexity: **LOW** (registration is handled by Claude CLI; CocoSearch just needs the flag)

- **Graceful "no project" handling**: When not in a git repo or configured directory, return actionable error message (not crash). Must guide user to either cd to project or specify index explicitly. Complexity: **LOW** (already implemented in `mcp/server.py` search_code function)

- **Graceful "project not indexed" handling**: When project detected but not indexed, return error with index command suggestion. Complexity: **LOW** (already implemented)

### Index Resolution

- **Priority chain for index name**: Resolution order: (1) `cocosearch.yaml` indexName field, (2) derived from directory name. This is already implemented. Complexity: **DONE**

- **Path-to-index mapping persistence**: Track which canonical path maps to which index name for collision detection. Already implemented via metadata registry. Complexity: **DONE**

- **Collision detection**: When same derived index name would map to different paths, detect and warn. Already implemented. Complexity: **DONE**

### Configuration

- **Per-project `cocosearch.yaml`**: Project-specific config with indexName field. Already implemented. Complexity: **DONE**

- **Config file discovery**: Walk up tree to find config in current dir or git root. Already implemented in `config/loader.py`. Complexity: **DONE**

## Differentiators

Features that would set CocoSearch apart from Serena and similar tools.

### MCP Protocol Integration

- **MCP roots capability support**: Implement the MCP `roots` capability to receive workspace roots from clients. Instead of relying on cwd, use the protocol's standardized `roots/list` request. This is more robust than cwd-based detection and works with multi-root workspaces. Complexity: **MEDIUM** (requires protocol extension to FastMCP)

- **roots/list_changed notification handling**: Subscribe to root changes and dynamically update context when user switches projects. Would enable seamless project switching without server restart. Complexity: **MEDIUM**

### Multi-Index Operations

- **Cross-index search**: Search across multiple indexes simultaneously with results ranked and merged. Useful for monorepo-adjacent setups or related projects. Complexity: **HIGH**

- **Index groups**: Define named groups of indexes (e.g., "backend" = [auth, api, shared]) for batch operations. Complexity: **MEDIUM**

- **Automatic related-index discovery**: When searching in project A, suggest related indexes if query seems to reference external code. Complexity: **HIGH** (requires semantic analysis)

### Developer Experience

- **Startup latency optimization**: Serena has cold-start penalty for language server initialization. CocoSearch should target <100ms startup for MCP server in project-from-cwd mode. Complexity: **LOW** (already fast due to simple architecture)

- **Index freshness warnings**: When index is stale (files changed since last index), include warning in search results with re-index suggestion. Complexity: **MEDIUM**

- **Smart project switching detection**: If user's subsequent queries reference different paths, proactively detect and suggest switching indexes. Complexity: **MEDIUM**

### Observability

- **Per-session search analytics**: Track queries, hit rates, and index usage per session for tuning. Complexity: **LOW**

- **Index health monitoring in MCP**: Expose index health via MCP resource or tool (not just CLI stats). Complexity: **LOW**

## Anti-Features

Things to deliberately NOT build. These are common mistakes or scope creep.

### Over-Engineering

- **DO NOT build `activate_project` tool**: Serena requires explicit project activation in certain modes. This is a workaround for their architecture, not a feature. CocoSearch's cwd-based auto-detection is cleaner. Users should not have to manually activate projects.

- **DO NOT build project registry UI**: Serena maintains a `serena_config.yml` with all previously activated projects. This adds complexity without value for CocoSearch's simpler model where projects = git repos with optional config.

- **DO NOT persist "current project" state**: The MCP server should be stateless between requests. Project is derived from cwd every time. Persisting state causes the exact problems Serena users complain about (wrong project activated after directory switch).

### Complexity Traps

- **DO NOT add language server integration**: Serena bundles LSP for semantic code understanding. CocoSearch uses tree-sitter for symbol extraction, which is simpler, faster, and sufficient. LSP adds startup latency, memory overhead, and language-specific complexity.

- **DO NOT add Docker-based project isolation**: Keep the simple model: one index per project, all in shared PostgreSQL. Container-per-project adds operational complexity without proportional benefit.

- **DO NOT add workspace-relative path resolution**: Always use canonical (resolved) paths. Relative paths and symlink handling should happen at detection time, not throughout the codebase.

### Premature Optimization

- **DO NOT add incremental cwd caching**: Re-detect project root on every request. The walk-up operation is fast (<1ms for typical depth). Caching introduces staleness bugs when user changes directories.

- **DO NOT add index auto-creation on search**: When index not found, return error with instructions. Auto-creating indexes on search would be surprising behavior and could create indexes with wrong settings.

## Reference Implementations

### Serena's `--project-from-cwd` Pattern

Serena's implementation (documented at [oraios/serena](https://github.com/oraios/serena)):

**Detection mechanism:**
1. Walk up from cwd looking for `.serena/project.yml` or `.git`
2. Activate the containing directory as project root
3. Initialize language servers for detected languages

**Registration command:**
```bash
claude mcp add --scope user serena -- uvx --from git+https://github.com/oraios/serena \
  serena start-mcp-server --context=claude-code --project-from-cwd
```

**Key flags:**
- `--project-from-cwd`: Enable auto-detection from working directory
- `--project <path>`: Explicit project path (disables auto-detection)
- `--context <name>`: Client context for tool filtering

**Fallback behavior:**
- If no project markers found: requires explicit `activate_project` tool call
- If markers found but project not registered: auto-registers to `serena_config.yml`

**Known limitations (from [GitHub issue #895](https://github.com/oraios/serena/issues/895)):**
- Project state persists across sessions unexpectedly
- Users must manually request activation when switching directories
- Confusion between `--project-from-cwd` and persisted selection

### MCP Roots Capability (Protocol Standard)

From [MCP Specification 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/client/roots):

**Purpose:** Clients expose filesystem "roots" to servers, defining operational boundaries.

**Capability declaration:**
```json
{
  "capabilities": {
    "roots": {
      "listChanged": true
    }
  }
}
```

**Request/Response:**
```json
// Request
{"jsonrpc": "2.0", "id": 1, "method": "roots/list"}

// Response
{
  "roots": [
    {"uri": "file:///home/user/project-a", "name": "Project A"},
    {"uri": "file:///home/user/project-b", "name": "Project B"}
  ]
}
```

**Change notification:**
```json
{"jsonrpc": "2.0", "method": "notifications/roots/list_changed"}
```

**Advantages over cwd:**
- Protocol-level standardization
- Multi-root workspace support
- Client-managed, not process-dependent

### Claude Code Scope Behavior

From [Claude Code MCP docs](https://code.claude.com/docs/en/mcp):

**Scope precedence:** local > project > user

**User scope storage:** `~/.claude.json`

**Known cwd limitation (from [python-sdk issue #1520](https://github.com/modelcontextprotocol/python-sdk/issues/1520)):**
- MCP servers run in uvx sandbox
- `os.getcwd()` returns cache path, not workspace
- Workaround: `uvx --directory $(pwd) ...` at registration time
- Problem: `$(pwd)` evaluated once at registration, not per-invocation

**Proper solution for CocoSearch:**
The server should use the directory passed at startup, not rely on `os.getcwd()` at runtime. For user-scope registration, the client (Claude Code) invokes the server with the correct cwd set by the MCP client implementation.

## Implementation Recommendations

### Minimum Viable Multi-Repo

To achieve Serena-style multi-repo with minimal changes:

1. **Add `--project-from-cwd` flag to MCP server** (or enable by default)
2. **Document user-scope registration pattern**
3. **Verify cwd inheritance works** with Claude Code's MCP client

That's it. The detection logic exists. The collision detection exists. The graceful error handling exists.

### Optional Enhancements (Post-MVP)

In priority order:

1. **MCP roots capability** - Protocol-correct alternative to cwd detection
2. **Index freshness warnings** - Better UX for stale indexes
3. **Cross-index search** - For monorepo-adjacent workflows

### What NOT to Change

- Do not add project registry/persistence
- Do not add explicit activation tools
- Do not add LSP integration
- Keep the stateless model

## Sources

**Official Documentation:**
- [Serena Documentation - Connecting Your MCP Client](https://oraios.github.io/serena/02-usage/030_clients.html)
- [Serena Documentation - Running Serena](https://oraios.github.io/serena/02-usage/020_running.html)
- [MCP Specification - Roots](https://modelcontextprotocol.io/specification/2025-06-18/client/roots)
- [Claude Code MCP Documentation](https://code.claude.com/docs/en/mcp)

**GitHub Issues and Discussions:**
- [Serena Issue #895 - Auto-activate project based on MCP client working directory](https://github.com/oraios/serena/issues/895)
- [MCP Python SDK Issue #1520 - How to access working directory](https://github.com/modelcontextprotocol/python-sdk/issues/1520)
- [Glama - activate_project tool details](https://glama.ai/mcp/servers/@oraios/serena/tools/activate_project)

**Guides and Articles:**
- [Augment Code - MCP Integration for Multi-Repo Development](https://www.augmentcode.com/guides/mcp-integration-streamlining-multi-repo-development)

---
*Researched: 2026-02-05*
