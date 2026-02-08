## Configuring MCP

CocoSearch provides an MCP (Model Context Protocol) server for semantic code search integration with LLM clients. Once configured, your AI assistant can search your codebase using natural language, index new projects, and check index health -- all without leaving the conversation.

### Prerequisites

Start the infrastructure services:

```bash
docker compose up -d
```

This gives you PostgreSQL (with pgvector) on port `5432` and Ollama (with `nomic-embed-text`) on port `11434`. The database connection defaults to `postgresql://cocosearch:cocosearch@localhost:5432/cocosearch`, which matches the Docker credentials -- no environment variables needed.

### Available MCP Tools

- `index_codebase` -- index a directory for semantic search
- `search_code` -- search indexed code with natural language queries
- `list_indexes` -- list all available indexes
- `index_stats` -- get statistics and parse health for an index
- `clear_index` -- remove an index from the database

### Single Registration (Recommended)

Register CocoSearch once for all your projects using Claude Code:

```bash
claude mcp add --scope user cocosearch -- \
  uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch mcp --project-from-cwd
```

**What these flags do:**

- `--scope user` makes the registration available in all your projects, not just the current one
- `--project-from-cwd` tells CocoSearch to detect the project from whichever directory you are working in

Claude Code supports MCP Roots capability, so project detection is fully automatic -- CocoSearch receives the workspace root directly from the client.

To verify:

```bash
claude mcp list
```

### Claude Desktop

Claude Desktop does not support MCP Roots, so it relies on `--project-from-cwd` for project detection.

**Config file locations:**

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add CocoSearch to your config:

```json
{
  "mcpServers": {
    "cocosearch": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/VioletCranberry/coco-s",
        "cocosearch",
        "mcp",
        "--project-from-cwd"
      ]
    }
  }
}
```

After saving, restart Claude Desktop. You should see the hammer icon in the chat input area with CocoSearch tools listed.

### OpenCode

**Config file locations:**

- **Global:** `~/.config/opencode/opencode.json`
- **Project:** `opencode.json` in project root

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "cocosearch": {
      "type": "local",
      "command": [
        "uvx",
        "--from",
        "git+https://github.com/VioletCranberry/coco-s",
        "cocosearch",
        "mcp",
        "--project-from-cwd"
      ],
      "enabled": true
    }
  }
}
```

OpenCode config differs from Claude configs: it uses `"type": "local"`, `command` is an array (not separate command/args), and it requires an explicit `"enabled": true`.

### Custom Database Connection

By default, CocoSearch connects to `postgresql://cocosearch:cocosearch@localhost:5432/cocosearch`. This matches the Docker Compose credentials, so no configuration is needed for the standard setup.

If you are connecting to a different PostgreSQL instance, set `COCOSEARCH_DATABASE_URL`:

**Claude Code:**

```bash
claude mcp add --scope user \
  --env COCOSEARCH_DATABASE_URL=postgresql://user:pass@host:5432/dbname \
  cocosearch -- \
  uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch mcp --project-from-cwd
```

**Claude Desktop / OpenCode (JSON config):**

Add an `"env"` block (or `"environment"` for OpenCode) to your server config:

```json
{
  "env": {
    "COCOSEARCH_DATABASE_URL": "postgresql://user:pass@host:5432/dbname"
  }
}
```

### Project Detection

CocoSearch determines which project to search using the following priority chain:

1. **MCP Roots** -- if the client supports Roots capability (Claude Code does), the workspace root is received directly from the client. This is the most reliable method.
2. **`--project-from-cwd`** -- detects the project from the current working directory. Used by clients that do not support Roots (Claude Desktop, OpenCode).
3. **Environment variable** -- falls back to the configured project path if set.
4. **Current working directory** -- unconditional fallback.

For programmatic use via HTTP transport, you can pass the project as a query parameter: `?project=/path/to/project`.
