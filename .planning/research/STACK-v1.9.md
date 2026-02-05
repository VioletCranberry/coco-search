# Stack Research: v1.9 Multi-Repo & Polish

## Executive Summary

CocoSearch already has the foundational stack for Serena-style multi-repo MCP support. The existing `find_project_root()` in `context.py` implements the same cwd-based detection pattern (searching for `.git` or `cocosearch.yaml` up the directory tree). For UV-based installation, the current `pyproject.toml` with `uv_build` backend and `[project.scripts]` entry point is already properly configured. **No new dependencies are needed.** The work is primarily adding a CLI flag (`--project-from-cwd`) and ensuring the MCP server passes OS cwd correctly.

## Current Stack Analysis

### Already In Place (DO NOT CHANGE)

| Component | Version | Purpose |
|-----------|---------|---------|
| `mcp[cli]` | >=1.26.0 | MCP SDK with FastMCP included |
| `uv_build` | >=0.8.13 | Build backend for UV compatibility |
| `[project.scripts]` | - | Entry point: `cocosearch = "cocosearch.cli:main"` |
| `context.py` | - | `find_project_root()` already detects `.git`/`cocosearch.yaml` |

### UV Installation Already Works

The current `pyproject.toml` structure supports direct UV installation:

```bash
# Install from git (works today)
uvx --from git+https://github.com/VioletCranberry/cocosearch cocosearch mcp

# Or with uv tool install for persistence
uv tool install git+https://github.com/VioletCranberry/cocosearch
```

**Verification:** The `[build-system]` uses `uv_build` which is the correct backend for UV toolchain compatibility.

## Recommended Stack Additions

### None Required

The existing stack is sufficient. The feature gap is implementation, not dependencies.

## Implementation Patterns (Not Stack)

### Pattern 1: Serena-style `--project-from-cwd` Flag

Serena uses `--project-from-cwd` to auto-detect project from current working directory. CocoSearch already has this logic in `find_project_root()`:

```python
# Already exists in src/cocosearch/management/context.py
def find_project_root(start_path: Path | None = None) -> tuple[Path | None, str | None]:
    """Walk up directory tree to find project root.

    Searches for .git directory first (git repository root), then
    cocosearch.yaml (explicit project configuration).
    """
```

**What's needed:** Add `--project-from-cwd` flag to `cocosearch mcp` command that:
1. Uses `os.getcwd()` as the start path
2. Calls existing `find_project_root()`
3. Resolves index name via existing `resolve_index_name()`

### Pattern 2: MCP Configuration for Claude Code

User-scope registration (single MCP for all projects):

```bash
claude mcp add --transport stdio --scope user cocosearch \
  -- uvx --from git+https://github.com/VioletCranberry/cocosearch \
  cocosearch mcp --project-from-cwd
```

Project-scope registration (per-project `.mcp.json`):

```json
{
  "mcpServers": {
    "cocosearch": {
      "type": "stdio",
      "command": "cocosearch",
      "args": ["mcp"]
    }
  }
}
```

**Key insight:** When MCP clients spawn stdio servers, the cwd is typically set to the project directory. The `--project-from-cwd` flag makes this explicit and consistent with Serena's pattern.

### Pattern 3: Per-Project Configuration via `cocosearch.yaml`

Already supported. The `indexName` field in `cocosearch.yaml` takes priority:

```yaml
# cocosearch.yaml (already works)
indexName: my-custom-index
```

## Integration Points

### How New Features Work with Existing Stack

| Existing Component | v1.9 Integration |
|-------------------|------------------|
| `find_project_root()` | Called by `--project-from-cwd` handler |
| `resolve_index_name()` | Determines index from detected project |
| `cocosearch.yaml` config | `indexName` overrides directory-based derivation |
| FastMCP `mcp.run()` | No changes needed, cwd comes from OS |
| `get_index_metadata()` | Collision detection already works |

### MCP Server Lifecycle

```
1. Claude Code starts MCP server with cwd=project_directory
2. cocosearch mcp --project-from-cwd
3. find_project_root(os.getcwd()) -> /path/to/project
4. resolve_index_name() -> "myproject" (from dir name or cocosearch.yaml)
5. All search_code() calls auto-target this index
```

## What NOT to Add

### No FastMCP Upgrade Needed

Current `mcp[cli]>=1.26.0` includes FastMCP. The PyPI `fastmcp` package (v2.14.5) is a separate distribution that would add unnecessary complexity. **Do not add `fastmcp` as a direct dependency.**

Rationale:
- `mcp[cli]` already provides `mcp.server.fastmcp.FastMCP`
- Current server code works correctly
- Adding standalone `fastmcp` would create version conflicts

### No Dynamic Project Switching Middleware

Some MCP patterns involve server-side project switching based on tool parameters. **Do not implement this.**

Rationale:
- Serena pattern uses startup-time detection, not runtime switching
- CocoSearch already has `index_name` parameter on tools for explicit override
- Runtime switching adds complexity without user benefit

### No Additional Configuration Libraries

The current Pydantic-based config with `ConfigResolver` is sufficient:
- CLI > env > config > default precedence already works
- Environment variable expansion not needed for MCP (handled by client)

### No MCP-Specific Authentication

CocoSearch is local-first with no remote auth requirements:
- Database auth via `COCOSEARCH_DATABASE_URL`
- Ollama connection local only
- No OAuth/API keys needed for MCP tools

## pyproject.toml Changes

None required for v1.9. Current configuration is correct:

```toml
[project.scripts]
cocosearch = "cocosearch.cli:main"

[build-system]
requires = ["uv_build>=0.8.13,<0.9.0"]
build-backend = "uv_build"
```

**Optional polish:** Add trove classifiers for discoverability:

```toml
[project]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "Topic :: Software Development :: Code Analyzers",
]
```

## MCP Client Configuration Reference

### Claude Code Scopes

| Scope | Storage | Use Case |
|-------|---------|----------|
| `local` | `~/.claude.json` (project path) | Personal dev, sensitive creds |
| `project` | `.mcp.json` in project root | Team sharing via git |
| `user` | `~/.claude.json` | Cross-project personal tools |

### Recommended: User-Scope with `--project-from-cwd`

This enables a single CocoSearch registration that works across all repos:

```bash
claude mcp add --transport stdio --scope user cocosearch \
  -- uvx --from git+https://github.com/VioletCranberry/cocosearch \
  cocosearch mcp --project-from-cwd
```

When user opens any project:
1. Claude Code spawns `cocosearch mcp --project-from-cwd` with cwd=project
2. CocoSearch detects project from cwd
3. Searches target that project's index

### Alternative: Project-Scope for Team Sharing

For teams, commit `.mcp.json` to repo:

```json
{
  "mcpServers": {
    "cocosearch": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/VioletCranberry/cocosearch",
        "cocosearch", "mcp"
      ],
      "env": {
        "COCOSEARCH_DATABASE_URL": "${DATABASE_URL}"
      }
    }
  }
}
```

Note: Project-scope doesn't need `--project-from-cwd` since it's already project-specific.

## Confidence Assessment

| Claim | Confidence | Basis |
|-------|------------|-------|
| UV installation works today | HIGH | Verified `uv_build` in pyproject.toml |
| No new dependencies needed | HIGH | Code inspection of existing implementation |
| Serena pattern compatible | HIGH | Official Serena docs + CocoSearch context.py |
| FastMCP upgrade not needed | HIGH | PyPI mcp package includes FastMCP |
| Claude Code scopes | HIGH | Official docs at code.claude.com |

## Sources

- [Serena Documentation - Running](https://oraios.github.io/serena/02-usage/020_running.html) - `--project-from-cwd` flag behavior
- [Serena GitHub](https://github.com/oraios/serena) - Multi-repo MCP pattern reference
- [UV Tools Documentation](https://docs.astral.sh/uv/guides/tools/) - `uvx --from git+` syntax
- [UV Project Configuration](https://docs.astral.sh/uv/concepts/projects/config/) - Entry points and build system
- [Claude Code MCP Docs](https://code.claude.com/docs/en/mcp) - MCP scopes and configuration
- [FastMCP PyPI](https://pypi.org/project/fastmcp/) - v2.14.5 (standalone, not needed)
- [MCP SDK PyPI](https://pypi.org/project/mcp/) - v1.26.0 (includes FastMCP)

---
*Researched: 2026-02-05*
