## Dogfooding

CocoSearch uses CocoSearch to index its own codebase. This demonstrates real-world usage and lets you explore the implementation.

### Indexing the Codebase

Index the CocoSearch source code:

```bash
uv run cocosearch index .
```

### Verifying Indexing

Check the index stats to confirm everything was indexed:

```bash
uv run cocosearch stats --pretty
```

### Example Searches

**Find embedding implementation:**

```bash
uv run cocosearch search "how does embedding work" --pretty
```

**Search for database operations:**

```bash
uv run cocosearch search "database connection handling" --pretty
```

**Find Docker setup (filtered by language):**

```bash
uv run cocosearch search "docker setup" --lang bash --pretty
```

**Explore configuration system:**

```bash
uv run cocosearch search "config file discovery" --pretty
```

### MCP Server (Local Development)

The repo includes a `.mcp.json` at the project root. Claude Code automatically picks it up — no manual configuration needed. Just make sure Docker containers are running (`docker compose up -d`) and restart Claude Code.

To run the MCP server manually (e.g., for debugging):

```bash
uv run cocosearch mcp --project-from-cwd
```

### Example MCP Queries

Once connected, try these queries in Claude to verify MCP is working:

**Semantic search:**

> "Use cocosearch to find how embeddings are generated"

**Symbol-filtered search:**

> "Use cocosearch to find all classes with symbol_type='class'"

**Language-filtered search:**

> "Use cocosearch to search for 'container setup' filtered to dockerfile"

**List indexes:**

> "Use cocosearch to list all available indexes"

**Index stats:**

> "Use cocosearch to show stats for the 'self' index"
