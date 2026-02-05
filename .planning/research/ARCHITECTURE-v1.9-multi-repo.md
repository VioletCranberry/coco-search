# Architecture Research: v1.9 Multi-Repo & Polish

## Executive Summary

CocoSearch already has the core architecture for Serena-style `--project-from-cwd` behavior - the `find_project_root()` function in `management/context.py` already detects project roots from cwd at runtime. The key architectural change is **when** this detection happens: currently it occurs per-tool-invocation; for single-MCP-registration it should work the same way but the server startup mode changes from per-repo to global.

The integration is straightforward because CocoSearch's auto-detect logic is already invocation-time rather than registration-time. No protocol-level changes needed - `os.getcwd()` works correctly for stdio transport when launched from a project directory.

## Integration Points

### 1. MCP Server (`src/cocosearch/mcp/server.py`)

**Current behavior:**
- Server instantiated globally: `mcp = FastMCP("cocosearch")`
- `search_code()` tool already calls `find_project_root()` when `index_name=None`
- Detection happens at invocation time, not registration time
- Returns contextual error messages for "not in project" and "project not indexed"

**Change needed:**
- Add `--project-from-cwd` CLI flag to `run_server()` (documentation/clarity only)
- The actual cwd detection already works - flag is semantic indicator
- Consider adding startup validation that cwd is a valid project (optional)

**Code location:** Lines 209-265 in `server.py` (auto-detect block in `search_code()`)

### 2. Context Detection (`src/cocosearch/management/context.py`)

**Current behavior:**
- `find_project_root(start_path=None)` defaults to `Path.cwd()`
- Walks up directory tree looking for `.git` or `cocosearch.yaml`
- Returns `(root_path, detection_method)` tuple
- `resolve_index_name()` follows priority: config `indexName` > directory name

**Change needed:**
- None for basic functionality - already works correctly
- Optional: Add caching layer if cwd detection becomes hot path
- Optional: Add `--project-from-cwd` validation at startup

**Why no change:** The current implementation already does runtime cwd detection per-invocation, which is exactly what Serena-style behavior requires.

### 3. CLI Entry Point (`src/cocosearch/cli.py`)

**Current behavior:**
- `mcp` command group with transport options
- `run_server()` called with transport/host/port

**Change needed:**
- Add `--project-from-cwd` flag (boolean, default False)
- When True: validate cwd is a project at startup, log detection
- Pass flag through to server for semantic clarity
- Update help text to explain single-registration usage

### 4. Metadata Storage (`src/cocosearch/management/metadata.py`)

**Current behavior:**
- `cocosearch_index_metadata` table maps `index_name` -> `canonical_path`
- `register_index_path()` handles collision detection
- `get_index_metadata()` retrieves stored path for comparison

**Change needed:**
- None for basic multi-repo support
- Collision detection already works correctly
- Consider: batch registration for pre-indexing multiple repos

## New Components

### None Required for Core Functionality

The existing architecture supports Serena-style behavior out of the box. The key insight is that CocoSearch's auto-detect is already invocation-time based.

### Optional Enhancements

**1. Project Validator (optional)**
```python
# src/cocosearch/mcp/project_validator.py
def validate_project_from_cwd() -> tuple[Path, str] | None:
    """Validate cwd is a project root at server startup.

    Returns (root_path, detection_method) or None if not in project.
    Used with --project-from-cwd to fail fast on misconfiguration.
    """
```

**2. Startup Logger (optional)**
```python
def log_project_detection(root_path: Path, method: str) -> None:
    """Log project detection for visibility in MCP server output."""
    logger.info(f"Detected project: {root_path} (via {method})")
```

## Data Flow

### Current Flow (Already Correct)

```
User in ~/projects/my-app runs Claude Code
    |
    v
Claude Code spawns MCP server (stdio)
    |
    v
MCP server starts with cwd = ~/projects/my-app
    |
    v
User asks: "search for authentication code"
    |
    v
search_code(query="authentication", index_name=None)
    |
    v
find_project_root()  # Uses os.getcwd() -> ~/projects/my-app
    |
    v
Detects .git at ~/projects/my-app, method="git"
    |
    v
resolve_index_name(root_path, "git")
    |
    v
Check cocosearch.yaml for indexName, else use "my-app"
    |
    v
Verify index exists, check collision
    |
    v
Execute search on "my-app" index
```

### With --project-from-cwd Flag (Enhancement)

```
User configures global MCP:
  claude mcp add --scope user cocosearch -- cocosearch mcp --project-from-cwd
    |
    v
User in ~/projects/my-app runs Claude Code
    |
    v
Claude Code spawns MCP server
    |
    v
Server starts, --project-from-cwd triggers validation:
  - find_project_root() at startup
  - Log: "Detected project: ~/projects/my-app (git)"
  - If not in project: warning (non-fatal)
    |
    v
(Same flow as current for tool invocations)
```

## Transport Considerations

### stdio Transport (Primary Use Case)

- **cwd inheritance:** Works correctly - subprocess inherits parent's cwd
- **Claude Code behavior:** Starts MCP server from project directory
- **Serena pattern:** Uses `uvx --directory $(pwd)` for explicit control
- **CocoSearch approach:** Relies on natural cwd inheritance (simpler)

### SSE/HTTP Transport (Secondary)

- **cwd is server machine's directory:** May not be meaningful
- **Recommendation:** For network transports, require explicit `index_name`
- **Alternative:** Add `?project_root=/path` query parameter support

### MCP Roots Protocol (Future Enhancement)

The MCP protocol has a "Roots" feature for clients to tell servers about filesystem boundaries:

```json
{
  "roots": [{
    "uri": "file:///home/user/projects/myproject",
    "name": "My Project"
  }]
}
```

**Current status:** Not needed for Serena-style behavior
**Future value:** Would enable Claude Code to pass project root explicitly
**CocoSearch consideration:** Could listen for `roots/list` and use first root as project

## Build Order

### Phase 1: Documentation & Flag (Low Risk)

1. **Add `--project-from-cwd` flag to CLI**
   - Boolean flag, default False
   - Update `mcp` command in `cli.py`
   - Pass through to `run_server()`

2. **Add startup logging**
   - When flag is True, call `find_project_root()` at startup
   - Log detected project or "no project detected" warning
   - Non-fatal - still allows explicit `index_name` usage

3. **Update documentation**
   - README: Single MCP registration pattern
   - Example: `claude mcp add --scope user cocosearch -- cocosearch mcp --project-from-cwd`

### Phase 2: Validation & UX (Medium Risk)

4. **Improve error messages for multi-repo scenarios**
   - When no project detected and no index_name: suggest `list_indexes()` first
   - When collision detected: clearer resolution steps

5. **Add `index_codebase` auto-detection**
   - If `path` is cwd and no `index_name`, auto-detect like `search_code`
   - Ensures consistency across tools

### Phase 3: Protocol Enhancements (Optional, Future)

6. **MCP Roots support** (if needed)
   - Listen for `roots/list` request
   - Use first root URI as implicit project root
   - Fallback to cwd if no roots provided

## Architectural Patterns

### Pattern: Invocation-Time Detection (Current, Recommended)

```python
@mcp.tool()
def search_code(query: str, index_name: str | None = None):
    if index_name is None:
        root_path, method = find_project_root()  # Detects at call time
        index_name = resolve_index_name(root_path, method)
    # ... search logic
```

**Pros:**
- No state management needed
- Works with any MCP registration pattern
- Naturally handles directory changes (though rare)

**Cons:**
- Small overhead per invocation (file system checks)
- Detection logic repeated in multiple tools

### Anti-Pattern: Registration-Time Detection

```python
# DON'T DO THIS
detected_project = find_project_root()  # At module load time

@mcp.tool()
def search_code(query: str, index_name: str | None = None):
    if index_name is None:
        index_name = detected_project  # Stale if user switches projects
```

**Why bad:**
- Captures cwd at server start, not tool invocation
- Doesn't handle multi-window/multi-project scenarios
- Serena explicitly supports this pattern, but CocoSearch's per-invocation approach is more flexible

### Pattern: Graceful Degradation

```python
if index_name is None:
    root_path, method = find_project_root()
    if root_path is None:
        return [{
            "error": "No project detected",
            "message": "Navigate to project directory or specify index_name",
            "hint": "Use list_indexes() to see available indexes"
        }]
```

**CocoSearch already implements this pattern** - see lines 213-222 in `server.py`.

## Confidence Assessment

| Component | Confidence | Rationale |
|-----------|------------|-----------|
| cwd detection works | HIGH | Verified in current code, stdio inheritance is standard |
| No protocol changes needed | HIGH | Serena uses same approach, MCP Roots is optional |
| Build order is correct | HIGH | Dependencies are clear, low-risk items first |
| Future Roots support | MEDIUM | Protocol exists but client support varies |

## Key Architectural Insight

**CocoSearch already implements Serena-style behavior.** The critical observation is:

1. **Serena** detects project at startup with `--project-from-cwd`, then uses that for all tool calls
2. **CocoSearch** detects project at each tool invocation when `index_name=None`

Both approaches work. CocoSearch's approach is **more flexible** because:
- Each tool call can detect a fresh cwd (rare but handles edge cases)
- No stale state if user somehow changes directories
- Already works without any code changes

The `--project-from-cwd` flag for CocoSearch would be:
1. **Semantic documentation** - tells users "this is the single-registration pattern"
2. **Startup validation** - optionally fail fast if not in a project
3. **Logging enhancement** - show detected project at startup

## Sources

### Official Documentation
- [MCP Roots Specification](https://modelcontextprotocol.io/specification/2025-06-18/client/roots) - Protocol-level project boundaries
- [Claude Code MCP Configuration](https://code.claude.com/docs/en/mcp) - How Claude Code configures MCP servers

### Serena Implementation
- [Serena Running Documentation](https://oraios.github.io/serena/02-usage/020_running.html) - `--project-from-cwd` flag details
- [Serena Client Integration](https://oraios.github.io/serena/02-usage/030_clients.html) - Claude Code integration patterns

### Community Discussions
- [MCP Python SDK Issue #1520](https://github.com/modelcontextprotocol/python-sdk/issues/1520) - Working directory access challenges
- [Cline Discussion #2635](https://github.com/cline/cline/discussions/2635) - Workspace directory handling patterns

### Research Notes
- [What are Roots in MCP](https://www.mcpevals.io/blog/roots-mcp) - Practical explanation of MCP Roots feature

---
*Researched: 2026-02-05*
