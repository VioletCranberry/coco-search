# CocoSearch

Local-first semantic code search via MCP. Search your codebase using natural language, entirely offline.

## What CocoSearch Does

CocoSearch indexes your code and enables semantic search powered by local embeddings. All processing happens on your machine - no data leaves your system.

- **Index codebases** using Ollama embeddings stored in PostgreSQL with pgvector
- **Search semantically** via CLI or any MCP-compatible client (Claude Code, Claude Desktop, OpenCode)
- **Stay private** - everything runs locally, no external API calls
- **Use with AI assistants** - integrate via Model Context Protocol (MCP)

## Architecture

```mermaid
flowchart LR
    subgraph Local
        Code[Codebase] --> Indexer
        Indexer --> |embeddings| PG[(PostgreSQL + pgvector)]
        Ollama[Ollama] --> |nomic-embed-text| Indexer
    end

    subgraph Clients
        CLI[CLI] --> Search
        Claude[Claude Code/Desktop] --> |MCP| Search
        OpenCode --> |MCP| Search
    end

    Search --> PG
    Ollama --> Search
```

**Components:**

- **Ollama** - Runs the embedding model (`nomic-embed-text`) locally
- **PostgreSQL + pgvector** - Stores code chunks and their vector embeddings for similarity search
- **CocoSearch** - CLI and MCP server that coordinates indexing and search

## Table of Contents

- [Quick Start](#quick-start)
- [Searching CocoSearch](#searching-cocosearch)
- [Installation](#installation)
- [MCP Configuration](#mcp-configuration)
- [CLI Reference](#cli-reference)
- [Configuration](#configuration)

## Quick Start

**Prerequisites:** Ollama, PostgreSQL with pgvector, and CocoSearch installed. See [Installation](#installation) for setup.

### Index Your Code

```bash
# Index a project
cocosearch index ./my-project

# Output:
# Using derived index name: my_project
# Indexing ./my-project...
# [progress bar]
# Indexed 42 files (127 chunks)
```

### Search Semantically

```bash
# Search with natural language
cocosearch search "authentication logic" --pretty

# Or enter interactive mode
cocosearch search --interactive
```

### Use with MCP

For AI assistant integration with Claude Code, Claude Desktop, or OpenCode, see [MCP Configuration](#mcp-configuration) below.

## Searching CocoSearch

CocoSearch uses CocoSearch to index its own codebase. This demonstrates real-world usage and lets you explore the implementation.

### Prerequisites

Docker (for PostgreSQL) and Python 3.12+ with [uv](https://docs.astral.sh/uv/) installed.

### Index the Codebase

```bash
uv run cocosearch index . --name self
```

Expected output:
```
Using index name: self
Indexing .
Indexed 45 files (287 chunks)
```

### Verify Indexing

```bash
uv run cocosearch stats self --pretty
```

Output shows file count, chunk count, and index size:
```
    Index: self
┏━━━━━━━━━┳━━━━━━━━━━━┓
┃ Metric  ┃ Value     ┃
┡━━━━━━━━━╇━━━━━━━━━━━┩
│ Files   │ 45        │
│ Chunks  │ 287       │
│ Size    │ 1.2 MB    │
└─────────┴───────────┘
```

### Example Searches

**Find embedding implementation:**

```bash
uv run cocosearch search "how does embedding work" --index self --pretty
```

Finds the embedder module and Ollama integration:
```
[1] src/cocosearch/indexer/embedder.py:15-45 (score: 0.91)
    class OllamaEmbedder:
        """Generate embeddings using Ollama's nomic-embed-text model."""

        def __init__(self, host: str = "http://localhost:11434"):
            self.host = host
            self.model = "nomic-embed-text"
```

**Search for database operations:**

```bash
uv run cocosearch search "database connection handling" --index self --pretty
```

Finds database initialization and connection management:
```
[1] src/cocosearch/database.py:20-55 (score: 0.88)
    def init_db(database_url: str) -> None:
        """Initialize database with pgvector extension and indexes."""
        engine = create_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
```

**Find Docker setup (filtered by language):**

```bash
uv run cocosearch search "docker setup" --index self --lang bash --pretty
```

Finds the development setup script:
```
[1] dev-setup.sh:45-78 (score: 0.86)
    setup_docker() {
        step "Setting up Docker services"
        if ! docker compose ps | grep -q cocosearch-db; then
            docker compose up -d
        fi
    }
```

**Explore configuration system:**

```bash
uv run cocosearch search "config file discovery" --index self --pretty
```

Finds the configuration loader logic:
```
[1] src/cocosearch/config/loader.py:28-65 (score: 0.89)
    def find_config_file(start_path: Path) -> Path | None:
        """Find cocosearch.yaml in current directory or git root."""
        # Try current directory first
        config_path = start_path / "cocosearch.yaml"
        if config_path.exists():
            return config_path
```

### Need Full Development Environment?

Run `./dev-setup.sh` for automated setup including Docker services, database initialization, and Ollama configuration.

## Installation

### 1. Install Ollama

Ollama runs the embedding model locally.

**macOS:**

```bash
brew install ollama
```

**Linux:**

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Start Ollama and pull the embedding model:**

```bash
# Start Ollama (runs as service on macOS, or in separate terminal)
ollama serve

# Pull the embedding model
ollama pull nomic-embed-text
```

**Verify:** `ollama list` should show `nomic-embed-text`.

### 2. Start PostgreSQL with pgvector

pgvector is a PostgreSQL extension for vector similarity search.

**Option A - Docker (recommended):**

```bash
# Uses docker-compose.yml from this repository
docker compose up -d
```

This creates a container `cocosearch-db` on port 5432 with pgvector pre-installed.

**Option B - Native PostgreSQL:**

```bash
# macOS with Homebrew
brew install postgresql@17 pgvector
brew services start postgresql@17
createdb cocoindex
psql cocoindex -c "CREATE EXTENSION vector;"
```

**Verify:**

- Docker: `docker ps` shows `cocosearch-db` running
- Native: `psql -c "SELECT 1"` succeeds

### 3. Install CocoSearch

```bash
# Clone and install
git clone https://github.com/VioletCranberry/coco-s.git
cd coco-s
uv sync

# Verify installation
uv run cocosearch --help
```

**Set database URL** (if not using default Docker setup):

```bash
export COCOINDEX_DATABASE_URL="postgresql://cocoindex:cocoindex@localhost:5432/cocoindex"
```

**Windows users:** Use WSL2 for best compatibility.

## MCP Configuration

CocoSearch provides an MCP (Model Context Protocol) server for semantic code search integration with LLM clients. When configured, your AI assistant can search your codebase using natural language.

**Available MCP tools:**

- `index_codebase` - Index a directory for semantic search
- `search_code` - Search indexed code with natural language queries
- `list_indexes` - List all available indexes
- `index_stats` - Get statistics for an index
- `clear_index` - Remove an index from the database

### Claude Code

**Option A - CLI (recommended):**

```bash
claude mcp add --transport stdio --scope user \
  --env COCOINDEX_DATABASE_URL=postgresql://cocoindex:cocoindex@localhost:5432/cocoindex \
  cocosearch -- uv run --directory /absolute/path/to/cocosearch cocosearch mcp
```

Replace `/absolute/path/to/cocosearch` with the actual path where you cloned the repository. Use `pwd` in the cocosearch directory to get the absolute path.

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
        "COCOINDEX_DATABASE_URL": "postgresql://cocoindex:cocoindex@localhost:5432/cocoindex"
      }
    }
  }
}
```

> **Important:** JSON does not expand `~` paths. Always use absolute paths like `/Users/yourname/cocosearch` or `/home/yourname/cocosearch`.

**Verification:**

1. Restart Claude Code (or run `/mcp` command to refresh)
2. Run `/mcp` - you should see `cocosearch` listed with status "connected"
3. Ask Claude: "Search for authentication logic in my codebase"

### Claude Desktop

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
        "COCOINDEX_DATABASE_URL": "postgresql://cocoindex:cocoindex@localhost:5432/cocoindex"
      }
    }
  }
}
```

**Verification:**

1. Restart Claude Desktop completely (quit and reopen the application)
2. Look for the hammer icon in the chat input area
3. Click the hammer to see "cocosearch" tools listed
4. Start a new conversation and ask Claude to search your codebase

### OpenCode

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
        "COCOINDEX_DATABASE_URL": "postgresql://cocoindex:cocoindex@localhost:5432/cocoindex"
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

**Verification:**

1. Restart OpenCode
2. Check MCP status in OpenCode settings/status
3. Verify cocosearch tools are available

---

**Remember:** Replace `/absolute/path/to/cocosearch` in all configs with the actual path where you cloned the repository.

## CLI Reference

CocoSearch provides a command-line interface for indexing and searching code. Output is JSON by default (for scripting/MCP); use `--pretty` for human-readable output.

### Indexing

`cocosearch index <path> [options]`

Index a codebase for semantic search.

| Flag             | Description                        | Default                |
| ---------------- | ---------------------------------- | ---------------------- |
| `-n, --name`     | Index name                         | Derived from directory |
| `-i, --include`  | Include file patterns (repeatable) | See defaults below     |
| `-e, --exclude`  | Exclude file patterns (repeatable) | None                   |
| `--no-gitignore` | Ignore .gitignore patterns         | Respects .gitignore    |

**Example:**

```bash
cocosearch index ./my-project --name myproject
```

Output:

```
Using derived index name: myproject
Indexing ./my-project...
Indexed 42 files
```

### Searching

`cocosearch search <query> [options]`
`cocosearch search --interactive`

Search indexed code using natural language.

| Flag                | Description              | Default              |
| ------------------- | ------------------------ | -------------------- |
| `-n, --index`       | Index to search          | Auto-detect from cwd |
| `-l, --limit`       | Max results              | 10                   |
| `--lang`            | Filter by language       | None                 |
| `--min-score`       | Minimum similarity (0-1) | 0.3                  |
| `-c, --context`     | Context lines            | 5                    |
| `-i, --interactive` | Enter REPL mode          | Off                  |
| `--pretty`          | Human-readable output    | JSON                 |

**Examples:**

```bash
# Basic search
cocosearch search "authentication logic" --pretty

# Filter by language
cocosearch search "error handling" --lang python

# Inline language filter
cocosearch search "database connection lang:go"

# Interactive mode
cocosearch search --interactive
```

Output (--pretty):

```
[1] src/auth/login.py:45-67 (score: 0.89)
    def authenticate_user(username: str, password: str) -> User:
        """Authenticate user credentials against database."""
        ...
```

### Managing Indexes

**List indexes:** `cocosearch list [--pretty]`

Show all available indexes.

```bash
cocosearch list --pretty
```

Output:

```
       Indexes
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name       ┃ Table                  ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━┩
│ myproject  │ cocosearch_myproject   │
│ another    │ cocosearch_another     │
└────────────┴────────────────────────┘
```

**Index statistics:** `cocosearch stats [index] [--pretty]`

Show statistics for one or all indexes.

```bash
cocosearch stats myproject --pretty
```

Output:

```
    Index: myproject
┏━━━━━━━━━┳━━━━━━━━━━━┓
┃ Metric  ┃ Value     ┃
┡━━━━━━━━━╇━━━━━━━━━━━┩
│ Files   │ 42        │
│ Chunks  │ 127       │
│ Size    │ 2.3 MB    │
└─────────┴───────────┘
```

**Clear index:** `cocosearch clear <index> [--force] [--pretty]`

Delete an index and all its data. Prompts for confirmation unless `--force`.

```bash
cocosearch clear myproject --force
```

Output:

```
Index 'myproject' deleted successfully
```

**Start MCP server:** `cocosearch mcp`

Start the MCP server for LLM integration. Typically invoked by MCP clients, not directly.

```bash
cocosearch mcp  # Runs until killed, used by Claude/OpenCode
```

## Configuration

### .cocosearch.yaml

Create `.cocosearch.yaml` in your project root to customize indexing:

```yaml
indexing:
  # See also https://cocoindex.io/docs/ops/functions#supported-languages
  include_patterns:
    - "*.py"
    - "*.js"
    - "*.ts"
    - "*.go"
    - "*.rs"
  exclude_patterns:
    - "*_test.go"
    - "*.min.js"
  chunk_size: 1000 # bytes
  chunk_overlap: 300 # bytes
```

### Environment Variables

| Variable                 | Description               | Default                                                     |
| ------------------------ | ------------------------- | ----------------------------------------------------------- |
| `COCOINDEX_DATABASE_URL` | PostgreSQL connection URL | `postgresql://cocoindex:cocoindex@localhost:5432/cocoindex` |
| `OLLAMA_HOST`            | Ollama API host           | `http://localhost:11434`                                    |
