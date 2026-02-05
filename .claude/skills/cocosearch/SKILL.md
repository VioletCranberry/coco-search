---
name: cocosearch
description: Semantic code search via MCP. Use for understanding unfamiliar code, finding related functionality, exploring symbols.
---

# CocoSearch Skill

## Quick Setup

**Install UV:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Install CocoSearch:**
```bash
uv pip install cocosearch
```

**Next:** Configure MCP (see below), then index your codebase:
```bash
cocosearch index /path/to/your/project
```

## MCP Configuration

**Option A - CLI (recommended):**

```bash
claude mcp add --transport stdio --scope user \
  --env COCOSEARCH_DATABASE_URL=postgresql://cocoindex:cocoindex@localhost:5432/cocoindex \
  cocosearch -- uv run --directory /absolute/path/to/cocosearch cocosearch mcp
```

Replace `/absolute/path/to/cocosearch` with actual clone path. Use `pwd` to get it.

**Verify CLI setup:**
```bash
claude mcp list
```

**Option B - JSON config:**

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "cocosearch": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/cocosearch",
        "cocosearch",
        "mcp"
      ],
      "env": {
        "COCOSEARCH_DATABASE_URL": "postgresql://cocoindex:cocoindex@localhost:5432/cocoindex"
      }
    }
  }
}
```

**Verification:**
- Restart Claude Code or run `/mcp` command
- Check `cocosearch` appears with status "connected"
- Confirm database connection: `cocosearch stats`

## When to Use CocoSearch

**Use CocoSearch for:**
- **Intent-based discovery:** "find authentication logic", "locate error handling patterns"
- **Symbol exploration:** Functions, classes with specific types: `--symbol-type function`
- **Cross-file patterns:** Discover similar implementations across codebase
- **Context expansion:** Get full function body with `--smart` or `-C <lines>`
- **Semantic queries:** Natural language understanding of code purpose

**Use grep/ripgrep for:**
- **Exact identifiers:** `rg "getUserById"`
- **Regex patterns:** `rg "TODO:.*urgent"`
- **Known locations:** When you know filename/directory
- **String literals:** Finding specific error messages, URLs
- **Fast exhaustive search:** All occurrences of exact token

**Use IDE tools for:**
- **Go-to-definition:** Cmd+Click / F12
- **Find-references:** Shift+F12
- **Rename refactoring:** Guaranteed correctness across files
- **Type hierarchy:** Class inheritance trees
- **Call hierarchy:** Function caller/callee graphs

## Workflow Examples

**1. Semantic discovery:**
```bash
cocosearch search "database connection handling"
```
Output:
```
src/db/pool.py:45 [function: create_connection_pool]
def create_connection_pool(config: DatabaseConfig) -> asyncpg.Pool:
    """Initialize connection pool with retry logic and health checks."""
    [...]

src/db/session.py:12 [function: get_session]
[...]
```

**2. Hybrid + symbol filter (most powerful):**
```bash
cocosearch search "authenticate" --hybrid --symbol-type function
```
Output:
```
src/auth/jwt.py:89 [function: authenticate_request]
async def authenticate_request(token: str) -> User | None:
    [...]

src/auth/middleware.py:34 [function: authenticate_user]
[...]
```

**3. Context expansion:**
```bash
cocosearch search "error handler" -C 10
```
Output shows 10 lines before/after each match (full function context).

**4. Language filter:**
```bash
cocosearch search "API routes" --lang typescript
```
Output restricted to TypeScript files only.

**5. Symbol name wildcard:**
```bash
cocosearch search "User" --symbol-name "User*"
```
Output:
```
src/models/user.py:10 [class: User]
src/models/user.py:45 [class: UserProfile]
src/auth/user.py:8 [function: UserAuthenticator]
[...]
```

**6. Combined filters:**
```bash
cocosearch search "validate input" --hybrid --symbol-type function --lang python
```
Hybrid search + Python functions only.

## Anti-Patterns

**Don't use CocoSearch for:**
- Exact string matches (use grep/rg)
- Regex patterns (use grep/rg)
- Single-file edits with known location (use IDE)
- Renaming/refactoring (use IDE refactor tools)

**Don't forget:**
- Reindex after major changes: `cocosearch index /path/to/project`
- Check index health: `cocosearch stats`

## Troubleshooting

See [README.md](../../../README.md) for:
- Docker setup (all-in-one container)
- Database connection issues
- Advanced configuration options
