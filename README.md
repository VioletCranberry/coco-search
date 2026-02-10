# Coco-s

Coco[-S]earch is a local-first hybrid semantic code search tool powered by [CocoIndex](https://github.com/cocoindex-io/cocoindex) and [Tree-sitter](https://tree-sitter.github.io/tree-sitter/). It indexes codebases into PostgreSQL with pgvector embeddings (via Ollama) and provides search through CLI, MCP server, or interactive REPL. No external APIs — everything runs locally. Incremental updates by default. `.gitignore` is respected. Supports 30 [languages](#supported-languages) with symbol extraction for 12, plus domain-specific [grammars](#supported-grammars) for structured config files.

## Disclaimer

A personal initiative, originally scaffolded with [GSD](https://github.com/glittercowboy/get-shit-done) and refined by hand. Built as a local-first, private tool for accelerating self-onboarding and exploring spec-driven development. Ships with a CLI, MCP tools, dashboards (TUI/WEB), a status API, and reusable [Claude SKILLS](https://code.claude.com/docs/en/skills).

## Where MCP wins (fewer tokens, fewer round-trips)

For codebases of meaningful size, CocoSearch reduces the number of MCP tool calls needed to find relevant code — often from 5-15 iterative grep/read cycles down to 1-2 semantic searches. This means fewer round-trips, less irrelevant content in the context window, and lower token consumption for exploratory and intent-based queries.

- **Exploratory/semantic queries**: "how does authentication work", "where is error handling done", "find the caching logic".
  - Native approach: Claude does 5-15 iterative grep/glob/read cycles, each adding results to context. Lots of trial-and-error, irrelevant matches, and full-file reads.
  - CocoSearch: 1 search_code call returns ranked, pre-chunked results with smart context expansion to function/class boundaries. Dramatically fewer tokens in context.
- **Identifier search with fuzzy intent**: "find the function that handles user signup".
  - Native grep requires Claude to guess the exact name (grep "signup", grep "register", grep "create_user"...). Each miss costs a round-trip + tokens.
  - CocoSearch's hybrid RRF (vector + keyword) handles this in 1 call.
- **Filtered searches**: language/symbol type/symbol name filtering is built-in. Native tools require Claude to manually assemble glob patterns and filter results.

## Useful Documentation

- [Architecture Overview](./docs/architecture.md)
- [Search Features](./docs/search-features.md)
- [Dogfooding](./docs/dogfooding.md)
- [MCP Configuration](./docs/mcp-configuration.md)
- [MCP Tools Reference](./docs/mcp-tools.md)
- [CLI Reference](./docs/cli-reference.md)
- [Retrieval Logic](./docs/retrieval.md)
- [Adding Languages](./docs/adding-languages.md)

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

CocoSearch indexes 30 programming languages. Chunking strategy depends on the language:

- **Tree-sitter chunking (~20 languages)**: CocoIndex's `SplitRecursively` uses Tree-sitter internally to split at syntax-aware boundaries (function/class edges). Covers Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, C#, Ruby, PHP, and others in CocoIndex's [built-in list](https://cocoindex.io/docs/ops/functions#supported-languages).
- **Custom handler chunking (3 languages)**: HCL, Dockerfile, and Bash use regex-based `CustomLanguageSpec` separators tuned for their syntax — no Tree-sitter grammar available for these in CocoIndex.
- **Text fallback**: Languages not recognized by either tier (Markdown, JSON, YAML, TOML, etc.) are split on blank lines and whitespace boundaries.

Independently of chunking, CocoSearch runs its own Tree-sitter queries (`.scm` files in `src/cocosearch/indexer/queries/`) to extract symbol metadata — function, class, method, and interface names and signatures. This powers `--symbol-type` and `--symbol-name` filtering. Symbol extraction is available for 12 languages:

- **Full Support (Symbol-Aware)**: Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, Ruby, PHP, HCL, Bash. All features: hybrid search, symbol filtering, smart context expansion. Symbol types extracted: `function`, `class`, `method`, `interface`.
- **Basic Support**: C#, CSS, Fortran, HTML, JSON, Kotlin, Markdown, Pascal, R, Scala, Solidity, SQL, Swift, TOML, XML, YAML, Dockerfile, and more. Features: hybrid search, semantic + keyword search.

See [Adding Languages](./docs/adding-languages.md) for details on how these tiers work and how to add new languages or grammars.

```bash
uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch languages

                 Supported Languages
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Language   ┃ Extensions                  ┃ Symbols ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ C          │ .c, .h                      │    ✓    │
│ C++        │ .cpp, .cc, .cxx, .hpp, .hxx │    ✓    │
│ C#         │ .cs                         │    ✗    │
│ CSS        │ .css, .scss                 │    ✗    │
│ DTD        │ .dtd                        │    ✗    │
│ Fortran    │ .f, .f90, .f95, .f03        │    ✗    │
│ Go         │ .go                         │    ✓    │
│ HTML       │ .html, .htm                 │    ✗    │
│ Java       │ .java                       │    ✓    │
│ Javascript │ .js, .mjs, .cjs, .jsx       │    ✓    │
│ JSON       │ .json                       │    ✗    │
│ Kotlin     │ .kt, .kts                   │    ✗    │
│ Markdown   │ .md, .mdx                   │    ✗    │
│ Pascal     │ .pas, .dpr                  │    ✗    │
│ Php        │ .php                        │    ✓    │
│ Python     │ .py, .pyw, .pyi             │    ✓    │
│ R          │ .r, .R                      │    ✗    │
│ Ruby       │ .rb                         │    ✓    │
│ Rust       │ .rs                         │    ✓    │
│ Scala      │ .scala                      │    ✗    │
│ Solidity   │ .sol                        │    ✗    │
│ SQL        │ .sql                        │    ✗    │
│ Swift      │ .swift                      │    ✗    │
│ TOML       │ .toml                       │    ✗    │
│ Typescript │ .ts, .tsx, .mts, .cts       │    ✓    │
│ XML        │ .xml                        │    ✗    │
│ YAML       │ .yaml, .yml                 │    ✗    │
│ Bash       │ .sh, .bash, .zsh            │    ✓    │
│ Dockerfile │ Dockerfile                  │    ✗    │
│ HCL        │ .tf, .hcl, .tfvars          │    ✓    │
└────────────┴─────────────────────────────┴─────────┘

Symbol-aware languages support --symbol-type and --symbol-name filtering.
```

## Supported Grammars

Beyond language-level support, CocoSearch recognizes **grammars** -- domain-specific schemas within a base language. A **language** is matched by file extension (e.g., `.yaml` -> YAML), while a **grammar** is matched by file path and content patterns (e.g., `.github/workflows/ci.yml` containing `on:` + `jobs:` -> GitHub Actions). Grammars provide structured chunking and richer metadata (job names, service names, stages) compared to generic text chunking.

Priority: Grammar match > Language match > TextHandler fallback.

```bash
uvx --from git+https://github.com/VioletCranberry/coco-s cocosearch grammars

                             Supported Grammars
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Grammar        ┃ Base Language ┃ Path Patterns                                          ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ docker-compose │ yaml          │ docker-compose*.yml, docker-compose*.yaml,             │
│                │               │ compose*.yml, compose*.yaml                            │
│ github-actions │ yaml          │ .github/workflows/*.yml, .github/workflows/*.yaml      │
│ gitlab-ci      │ yaml          │ .gitlab-ci.yml                                         │
└────────────────┴───────────────┴────────────────────────────────────────────────────────┘

Grammars provide domain-specific chunking for files within a base language.
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
