# Coco-s

Coco[S]earch is a local-first hybrid semantic code search tool powered by [CocoIndex](https://github.com/cocoindex-io/cocoindex) and [Tree-sitter](https://tree-sitter.github.io/tree-sitter/). It indexes codebases into PostgreSQL with pgvector embeddings (via Ollama) and provides search through CLI, MCP server, or interactive REPL. No external APIs — everything runs locally. Incremental updates by default. `.gitignore` is respected.

## Disclaimer

This is a personal initiative built using [GSD](https://github.com/glittercowboy/get-shit-done), with manual refinements. It was designed as a local-first, private solution to accelerate self-onboarding and explore spec-driven development. The project features both a Command Line Interface (CLI) and MCP tools, alongside dashboards (TUI/WEB), API for quick status checks and useful [Claude SKILLS](https://code.claude.com/docs/en/skills).

## Useful Documentation

- [Architecture Overview](./docs/architecture.md)
- [Search Features](./docs/search-features.md)
- [Dogfooding](./docs/dogfooding.md)
- [MCP Configuration](./docs/mcp-configuration.md)
- [MCP Tools Reference](./docs/mcp-tools.md)
- [CLI Reference](./docs/cli-reference.md)
- [Retrieval Logic](./docs/retrieval.md)

## Components

- **Ollama** -- runs the embedding model (`nomic-embed-text`) locally.
- **PostgreSQL + pgvector** -- stores code chunks and their vector embeddings for similarity search.
- **CocoSearch** -- CLI and MCP server that coordinates indexing and search.

### Available MCP Tools

- `index_codebase` -- index a directory for semantic search
- `search_code` -- search indexed code with natural language queries
- `list_indexes` -- list all available indexes
- `index_stats` -- get statistics and parse health for an index
- `clear_index` -- remove an index from the database

### Available Skills

- **coco-quickstart** ([SKILL.md](./skills/coco-quickstart/SKILL.md)): Use when setting up CocoSearch for the first time or indexing a new project. Guides through infrastructure check, indexing, and verification in under 2 minutes.
- **coco-debugging** ([SKILL.md](./skills/coco-debugging/SKILL.md)): Use when debugging an error, unexpected behavior, or tracing how code flows through a system. Guides root cause analysis using CocoSearch semantic and symbol search.
- **coco-onboarding** ([SKILL.md](./skills/coco-onboarding/SKILL.md)): Use when onboarding to a new or unfamiliar codebase. Guides you through understanding architecture, key modules, and code patterns step-by-step using CocoSearch.
- **coco-refactoring** ([SKILL.md](./skills/coco-refactoring/SKILL.md)): Use when planning a refactoring, extracting code into a new module, renaming across the codebase, or splitting a large file. Guides impact analysis and safe step-by-step execution using CocoSearch.
- **coco-explain** ([SKILL.md](./skills/coco-explain/SKILL.md)): Use when a user asks how something works — a flow, logic path, subsystem, or concept. Guides targeted deep-dive explanations using CocoSearch semantic and hybrid search.
- **coco-new-feature** ([SKILL.md](./skills/coco-new-feature/SKILL.md)): Use when adding new functionality — a new command, endpoint, module, handler, or capability. Guides placement, pattern matching, and integration using CocoSearch.
- **coco-subway** ([SKILL.md](./skills/coco-subway/SKILL.md)): Use when the user wants to visualize codebase structure as an interactive London Underground-style subway map. AI-generated visualization using CocoSearch tools for exploration.

## Quick Start

```bash
# 1. Start infrastructure.
docker compose up -d
# 2. Index your project.
uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch index .
# 3. Register with your AI assistant.
claude mcp add --scope user cocosearch -- \
  uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch mcp --project-from-cwd
```

Use skills:

```bash
# Clone this repository and install coco skills. For global installation install them to ~/.claude/skills/
for skill in coco-onboarding coco-refactoring coco-debugging coco-quickstart coco-explain coco-new-feature coco-subway; do
    mkdir -p .claude/skills/$skill
    cp skills/$skill/SKILL.md .claude/skills/$skill/SKILL.md
done
# Then restart your Claude session and instruct it to
# 'onboard current repository with CocoSearch' or use
# '/coco-quickstart' skill.
```

## Supported Languages

CocoSearch indexes 31 programming languages via Tree-sitter. Symbol extraction (for `--symbol-type` and `--symbol-name` filtering) is available for 10 languages.

- **Full Support (Symbol-Aware)**: Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, Ruby, PHP. All features: hybrid search, symbol filtering, smart context expansion. Symbol types extracted: `function`, `class`, `method`, `interface`.
- **Basic Support**: C#, CSS, Fortran, HTML, JSON, Kotlin, Markdown, Pascal, R, Scala, Shell, Solidity, SQL, Swift, TOML, XML, YAML, Bash, Dockerfile, HCL, and more. Features: hybrid search, semantic + keyword search.

```bash
uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch languages

                 Supported Languages
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Language   ┃ Extensions                  ┃ Symbols ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ C          │ .c, .h                      │    ✗    │
│ C++        │ .cpp, .cc, .cxx, .hpp, .hxx │    ✗    │
│ C#         │ .cs                         │    ✗    │
│ CSS        │ .css, .scss                 │    ✗    │
│ DTD        │ .dtd                        │    ✗    │
│ Fortran    │ .f, .f90, .f95, .f03        │    ✗    │
│ Go         │ .go                         │    ✓    │
│ HTML       │ .html, .htm                 │    ✗    │
│ Java       │ .java                       │    ✗    │
│ Javascript │ .js, .mjs, .cjs, .jsx       │    ✓    │
│ JSON       │ .json                       │    ✗    │
│ Kotlin     │ .kt, .kts                   │    ✗    │
│ Markdown   │ .md, .mdx                   │    ✗    │
│ Pascal     │ .pas, .dpr                  │    ✗    │
│ Php        │ .php                        │    ✗    │
│ Python     │ .py, .pyw, .pyi             │    ✓    │
│ R          │ .r, .R                      │    ✗    │
│ Ruby       │ .rb                         │    ✗    │
│ Rust       │ .rs                         │    ✓    │
│ Scala      │ .scala                      │    ✗    │
│ Shell      │ .sh, .bash, .zsh            │    ✗    │
│ Solidity   │ .sol                        │    ✗    │
│ SQL        │ .sql                        │    ✗    │
│ Swift      │ .swift                      │    ✗    │
│ TOML       │ .toml                       │    ✗    │
│ Typescript │ .ts, .tsx, .mts, .cts       │    ✓    │
│ XML        │ .xml                        │    ✗    │
│ YAML       │ .yaml, .yml                 │    ✗    │
│ Dockerfile │ Dockerfile                  │    ✗    │
│ HCL        │ .hcl                        │    ✗    │
└────────────┴─────────────────────────────┴─────────┘
```

## Features

- **Hybrid search** -- semantic similarity + keyword matching via RRF fusion.
- **Symbol filtering** -- filter by function, class, method, or symbol name patterns.
- **Context expansion** -- smart expansion to enclosing function/class boundaries.
- **Query caching** -- exact and semantic cache for fast repeated queries.
- **Index observability** -- stats dashboard for monitoring index health.
- **Parse health tracking** -- detect and report parsing issues across indexed files.
- **Stay private** -- everything runs locally, no external API calls.
- **Use with AI assistants** -- integrate via CLI or MCP ([Claude Code](https://claude.com/product/claude-code), [Claude Desktop](https://claude.com/download), [OpenCode](https://opencode.ai/)).

### CLI

```bash
# Index a project
uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch index /path/to/project

# Search with natural language
uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch search "authentication flow" --pretty

# Serve CocoSearch WEB dashboard
uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch serve-dashboard

# Start interactive REPL
uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch search --interactive

# View index stats with parse health
uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch stats --pretty

Files: 147 | Chunks: 1,537 | Size: 8.6 MB
Created: 2026-02-09
Last Updated: 2026-02-09 (0 days ago)

                        Language Distribution
┏━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Language     ┃  Files ┃   Chunks ┃ Distribution                   ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ py           │    124 │     1281 │ ██████████████████████████████ │
│ md           │     18 │      200 │ ████▋                          │
│ html         │      1 │       46 │ █                              │
│ bash         │      1 │        6 │ ▏                              │
│ toml         │      1 │        2 │                                │
│ yaml         │      1 │        1 │                                │
│ yml          │      1 │        1 │                                │
└──────────────┴────────┴──────────┴────────────────────────────────┘

Parse health: 100.0% clean (125/125 files)
                Parse Status by Language
┏━━━━━━━━━━┳━━━━━━━┳━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━┓
┃ Language ┃ Files ┃  OK ┃ Partial ┃ Error ┃ No Grammar ┃
┡━━━━━━━━━━╇━━━━━━━╇━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━┩
│ bash     │     1 │   1 │       0 │     0 │          0 │
│ html     │     1 │   0 │       0 │     0 │          0 │
│ md       │    18 │   0 │       0 │     0 │          0 │
│ python   │   124 │ 124 │       0 │     0 │          0 │
│ toml     │     1 │   0 │       0 │     0 │          0 │
│ yaml     │     1 │   0 │       0 │     0 │          0 │
│ yml      │     1 │   0 │       0 │     0 │          0 │
└──────────┴───────┴─────┴─────────┴───────┴────────────┘


# View index stats with parse health live
uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch stats --live

```

For the full list of commands and flags, see [CLI Reference](./docs/cli-reference.md).

## Configuration

Create `cocosearch.yaml` in your project root to customize indexing:

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

## Testing

Tests use [pytest](https://docs.pytest.org/). All tests are unit tests, fully mocked, and require no infrastructure. Markers are auto-applied based on directory -- no need to add them manually.

```bash
uv run pytest                                          # Run all unit tests
uv run pytest tests/unit/search/test_cache.py -v       # Single file
uv run pytest -k "test_rrf_double_match" -v            # Single test by name
uv run pytest tests/unit/handlers/ -v                  # Handler tests
```
