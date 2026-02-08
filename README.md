# CocoSearch

Hybrid search for codebases — semantic understanding meets keyword precision. Search your code with natural language, filter by symbols, expand context. Works as CLI or MCP server. Everything runs locally.
Powered with [Cocoindex](https://github.com/cocoindex-io/cocoindex) data transformation framework for AI.

## Disclaimer

This is a personal initiative built using [GSD](https://github.com/glittercowboy/get-shit-done), with careful manual refinements. It was designed as a local-first, private solution to accelerate self-onboarding and explore spec-driven development. The project features both a Command Line Interface (CLI) and MCP tools, alongside a dashboard for quick status checks.

I suggest checking [Architecture Docs](./docs/architecture.md), [Retrieval Logic](./docs/retrieval.md) and [MCP Tools](./docs/mcp-tools.md) currently supported.

Finally, there are the following skills to use:

- **coco-debugging** ([SKILL.md](./skills/coco-debugging/SKILL.md)): Use when debugging an error, unexpected behavior, or tracing how code flows through a system. Guides root cause analysis using CocoSearch semantic and symbol search.
- **coco-onboarding** ([SKILL.md](./skills/coco-onboarding/SKILL.md)): Use when onboarding to a new or unfamiliar codebase. Guides you through understanding architecture, key modules, and code patterns step-by-step using CocoSearch.
- **coco-refactoring** ([SKILL.md](./skills/coco-refactoring/SKILL.md)): Use when planning a refactoring, extracting code into a new module, renaming across the codebase, or splitting a large file. Guides impact analysis and safe step-by-step execution using CocoSearch.

See [Extend Claude with skills](https://code.claude.com/docs/en/skills) for details how to install and use them.

CLI reference is available [here](./docs/cli-reference.md).  
See also [DogFooding](./docs/dogfooding.md.)

## Features

- **Hybrid search** — semantic similarity + keyword matching via RRF fusion.
- **Symbol filtering** — filter by function, class, method, or symbol name patterns.
- **Context expansion** — smart expansion to enclosing function/class boundaries.
- **Query caching** — exact and semantic cache for fast repeated queries.
- **Index observability** — stats dashboard for monitoring index health.
- **Stay private** — everything runs locally, no external API calls.
- **Use with AI assistants** — integrate via CLI or MCP (Claude Code, Claude Desktop, OpenCode).

Description of all search features is available [here](./docs/search-features.md.)

## Supported Languages

```bash
# View all supported extensions
cocosearch languages
```

CocoSearch indexes 31 programming languages via Tree-sitter. Symbol extraction (for --symbol-type and --symbol-name filtering) is available for 10 languages.

- **Full Support (Symbol-Aware)**: Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, Ruby, PHP. All features: Hybrid search, symbol filtering, smart context expansion. Symbol types extracted: `function`, `class`, `method`, `interface`.
- **Basic Support**: C#, CSS, Fortran, HTML, JSON, Kotlin, Markdown, Pascal, R, Scala, Shell, Solidity, SQL, Swift, TOML, XML, YAML, Bash, Dockerfile, HCL, and more. Features: Hybrid search, semantic + keyword search.

## Components

- **Ollama** - Runs the embedding model (`nomic-embed-text`) locally.
- **PostgreSQL + pgvector** - Stores code chunks and their vector embeddings for similarity search.
- **CocoSearch** - CLI and MCP server that coordinates indexing and search.

## Getting Started

**Option #1**: The Docker image bundles PostgreSQL (with pgvector) and Ollama (with pre-baked nomic-embed-text model) as infrastructure services. CocoSearch runs natively.

```bash
docker build -t cocosearch -f docker/Dockerfile .
# Build from the repository root.
# The build takes 5-10 minutes (downloads and bakes the Ollama model).
```

```bash
docker run -v cocosearch-data:/data -p 5432:5432 -p 11434:11434 cocosearch
# Starts PostgreSQL on port 5432 and Ollama on port 11434.
```

```bash
# Install and run CocoSearch natively
uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch --help
```

**Option #2**: Run components using docker compose and install cocosearch.

```bash
docker compose up -d
# Uses docker-compose.yml from this repository
# This creates a container cocosearch-db on port 5432 with pgvector pre-installed and cocosearch-ollama on port 11434.
# Set Ollama API URL for embeddings.
export COCOSEARCH_OLLAMA_URL="http://localhost:11434"
```

```bash
# Install and run CocoSearch natively
uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch --help
```

**Option #3**: Setup full development environment.
Run `./dev-setup.sh` for automated setup including Docker services, database initialization, and Ollama configuration.

## Configuring MCP

CocoSearch provides an MCP (Model Context Protocol) server for semantic code search integration with LLM clients. When configured, your AI assistant can search your codebase using natural language.

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

**For uvx users (git+https pattern):**

```bash
# Register with uvx using git+https pattern
claude mcp add --scope user cocosearch -- \
  uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch mcp --project-from-cwd
```

**How it works:**

- `--scope user` makes the registration available in ALL projects (not just current)
- `--project-from-cwd` tells CocoSearch to detect the project from whichever directory you're working in
- Open any project, CocoSearch automatically searches that project's index
- If the project isn't indexed yet, you'll get a prompt to index it

See [mcp-configuration](./docs/mcp-configuration.md) for all configuration options, including:

- [Claude Code](https://claude.com/product/claude-code)
- [Claude Desktop](https://claude.com/download)
- [OpenCode](https://opencode.ai/)

## Configuration File

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
