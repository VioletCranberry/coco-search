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
- `get_stats` - Get statistics for an index
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
      "args": ["run", "--directory", "/absolute/path/to/cocosearch", "cocosearch", "mcp"],
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
