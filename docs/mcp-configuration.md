## Configuring MCP

CocoSearch provides an MCP (Model Context Protocol) server for semantic code search integration with LLM clients. When configured, your AI assistant can search your codebase using natural language.

### Prerequisites

CocoSearch requires PostgreSQL (with pgvector) and Ollama running locally. The simplest setup:

```bash
# Option A: Docker Compose (recommended)
docker compose up -d

# Option B: All-in-one Docker image
docker build -t cocosearch -f docker/Dockerfile .
docker run -v cocosearch-data:/data -p 5432:5432 -p 11434:11434 cocosearch
```

With infrastructure running, configure your MCP client below. The database connection defaults to `postgresql://cocosearch:cocosearch@localhost:5432/cocosearch` -- no environment variables needed when using Docker.

**Available MCP tools:**

- `index_codebase` - Index a directory for semantic search
- `search_code` - Search indexed code with natural language queries
- `list_indexes` - List all available indexes
- `index_stats` - Get statistics for an index
- `clear_index` - Remove an index from the database

### Single Registration (Recommended)

Register CocoSearch once and use it across all your projects. The `--project-from-cwd` flag tells CocoSearch to detect the project from whichever directory you're working in.

**For Claude Code:**

```bash
# Register once for all projects (user scope)
claude mcp add --scope user cocosearch -- \
  uvx --from /absolute/path/to/cocosearch cocosearch mcp --project-from-cwd

# Verify registration
claude mcp list
```

**For Claude Desktop:**

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `~/.config/Claude/claude_desktop_config.json` (Linux):

```json
{
  "mcpServers": {
    "cocosearch": {
      "command": "uvx",
      "args": [
        "--from",
        "/absolute/path/to/cocosearch",
        "cocosearch",
        "mcp",
        "--project-from-cwd"
      ]
    }
  }
}
```

**How it works:**

- `--scope user` makes the registration available in ALL projects (not just current)
- `--project-from-cwd` tells CocoSearch to detect the project from whichever directory you're working in
- Open any project, CocoSearch automatically searches that project's index
- If the project isn't indexed yet, you'll get a prompt to index it

**For uvx users (git+https pattern):**

```bash
# Register with uvx using git+https pattern
claude mcp add --scope user cocosearch -- \
  uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch mcp --project-from-cwd
```

### Per-Project Registration (Alternative)

Use per-project registration when you need project-specific configuration or are running in isolated environments (CI/CD, Docker).

### Configuring Claude Code

**Option A - CLI (recommended):**

```bash
claude mcp add --transport stdio --scope user \
  --env COCOSEARCH_DATABASE_URL=postgresql://cocosearch:cocosearch@localhost:5432/cocosearch \
  cocosearch -- uv run --directory /absolute/path/to/cocosearch cocosearch mcp
```

Replace `/absolute/path/to/cocosearch` with the actual path where you cloned the repository. Use `pwd` in the cocosearch directory to get the absolute path.

> **Note:** The `COCOSEARCH_DATABASE_URL` above is optional when using Docker. It matches the default -- you can omit it if using docker compose or the all-in-one image.

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
        "COCOSEARCH_DATABASE_URL": "postgresql://cocosearch:cocosearch@localhost:5432/cocosearch"
      }
    }
  }
}
```

> **Important:** JSON does not expand `~` paths. Always use absolute paths like `/Users/yourname/cocosearch` or `/home/yourname/cocosearch`.

> **Note:** The `COCOSEARCH_DATABASE_URL` above is optional when using Docker. It matches the default -- you can omit it if using docker compose or the all-in-one image.

**Verification:**

1. Restart Claude Code (or run `/mcp` command to refresh)
2. Run `/mcp` - you should see `cocosearch` listed with status "connected"
3. Ask Claude: "Search for authentication logic in my codebase"

### Configuring Claude Desktop

**Config file locations:**

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

**Config content:**

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
        "COCOSEARCH_DATABASE_URL": "postgresql://cocosearch:cocosearch@localhost:5432/cocosearch"
      }
    }
  }
}
```

> **Note:** The `COCOSEARCH_DATABASE_URL` above is optional when using Docker. It matches the default -- you can omit it if using docker compose or the all-in-one image.

**Verification:**

1. Restart Claude Desktop completely (quit and reopen the application)
2. Look for the hammer icon in the chat input area
3. Click the hammer to see "cocosearch" tools listed
4. Start a new conversation and ask Claude to search your codebase

### Configuring OpenCode

**Config file locations:**

- **Global:** `~/.config/opencode/opencode.json`
- **Project:** `opencode.json` in project root

**Config content:**

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "cocosearch": {
      "type": "local",
      "command": [
        "uv",
        "run",
        "--directory",
        "/absolute/path/to/cocosearch",
        "cocosearch",
        "mcp"
      ],
      "enabled": true,
      "environment": {
        "COCOSEARCH_DATABASE_URL": "postgresql://cocosearch:cocosearch@localhost:5432/cocosearch"
      }
    }
  }
}
```

> **Note:** OpenCode config differs from Claude configs:
>
> - Uses `"type": "local"` (not implicit)
> - `command` is an array (not separate command/args)
> - Uses `"environment"` (not `"env"`)
> - Has explicit `"enabled": true`

> **Note:** The `COCOSEARCH_DATABASE_URL` above is optional when using Docker. It matches the default -- you can omit it if using docker compose or the all-in-one image.

**Verification:**

1. Restart OpenCode
2. Check MCP status in OpenCode settings/status
3. Verify cocosearch tools are available

---

**Remember:** Replace `/absolute/path/to/cocosearch` in all configs with the actual path where you cloned the repository.
