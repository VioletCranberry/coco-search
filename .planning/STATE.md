# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-24)

**Core value:** Semantic code search that runs entirely locally — no data leaves your machine.
**Current focus:** Phase 4 - Index Management

## Current Position

Phase: 4 of 4 (Index Management)
Plan: 3 of 3 in current phase
Status: In progress
Last activity: 2026-01-25 — Completed 04-03-PLAN.md

Progress: [█████████░] 91% (10/11 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 10
- Average duration: 3.4 min
- Total execution time: 34 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation | 2/2 | 6 min | 3 min |
| 2. Indexing Pipeline | 3/3 | 11 min | 3.7 min |
| 3. Search | 3/3 | 10 min | 3.3 min |
| 4. Index Management | 2/3 | 7 min | 3.5 min |

**Recent Trend:**
- Last 5 plans: 03-01 (2 min), 03-02 (4 min), 03-03 (4 min), 04-01 (3 min), 04-03 (4 min)
- Trend: stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

| Decision | Phase | Rationale |
|----------|-------|-----------|
| Package name: cocosearch | 01-01 | Clarity over default coco_s from directory |
| Ollama native (not Docker) | 01-01 | Simplicity for Phase 1 per research |
| pgvector/pgvector:pg17 image | 01-01 | Pre-compiled extension, official |
| pgvector 0.8.1 via CREATE EXTENSION | 01-02 | Database operation vs init script (container already running) |
| Flow name includes index_name | 02-02 | Multi-codebase isolation via CodeIndex_{name} pattern |
| Reference-only storage | 02-02 | Store filename + location, not chunk text |
| argparse over click | 02-03 | Simplicity for single subcommand |
| Direct PostgreSQL queries | 03-01 | Simpler than CocoIndex query handlers, more control |
| JSON output by default | 03-02 | MCP/tool integration, --pretty for humans |
| Default action via sys.argv | 03-02 | Clean support for `cocosearch "query"` without subcommand |
| cmd module over prompt_toolkit | 03-03 | Standard library sufficient for REPL |
| Reuse connection pool from search.db | 04-01 | Singleton pattern already handles pgvector registration |
| Import derive_index_name from cli | 04-01 | Single source of truth, no duplicate logic |
| Logging to stderr in MCP server | 04-03 | Prevents stdout corruption of JSON-RPC protocol |
| Lazy import of MCP run_server | 04-03 | Avoids loading MCP dependencies until needed |

### Pending Todos

None yet.

### Blockers/Concerns

None - Phase 4 plan 03 complete, 04-02 (CLI commands) still pending.

## Session Continuity

Last session: 2026-01-25
Stopped at: Completed 04-03-PLAN.md
Resume file: None

## Phase 1 Summary

Foundation infrastructure is fully operational:
- PostgreSQL with pgvector 0.8.1 running in Docker
- Ollama serving nomic-embed-text (768-dim embeddings)
- Python project with cocoindex 0.3.28, psycopg, pgvector
- Verification script: `uv run python scripts/verify_setup.py`

## Phase 2 Summary

Indexing pipeline complete and operational:

Plan 02-01:
- Indexer module created at `src/cocosearch/indexer/`
- IndexingConfig Pydantic model with chunk_size/overlap
- File filter with .gitignore support and DEFAULT_EXCLUDES
- Dependencies: pathspec, pyyaml, rich

Plan 02-02:
- Shared embedding transform: `code_to_embedding` with @cocoindex.transform_flow
- Extension helper: `extract_extension` for Tree-sitter language detection
- CocoIndex flow: LocalFile -> SplitRecursively -> EmbedText -> Postgres
- run_index() orchestration function
- Integration tested with real codebase indexing

Plan 02-03:
- CLI entry point: `cocosearch index <path>`
- Progress reporting with Rich (spinner, bar, elapsed time)
- Index name derivation from directory paths
- Flags: --name, --include, --exclude, --no-gitignore
- End-to-end verified with real infrastructure

**Usage:**
```bash
export COCOINDEX_DATABASE_URL="postgresql://cocoindex:cocoindex@localhost:5432/cocoindex"
uv run cocosearch index /path/to/codebase --name myindex
```

## Phase 3 Summary (Complete)

Search interface development complete:

Plan 03-01:
- Search module created at `src/cocosearch/search/`
- Connection pool singleton with pgvector type registration
- Table name resolver: `codeindex_{name}__{name}_chunks`
- Core search function using code_to_embedding.eval() for query embedding
- SearchResult dataclass with filename, byte offsets, and similarity score
- Language filtering supporting 15 programming languages

Plan 03-02:
- Utility functions: byte_to_line, read_chunk_content, get_context_lines
- JSON formatter with file_path, lines, score, content, context
- Pretty formatter with Rich syntax highlighting (25+ languages)
- CLI search command with all flags from CONTEXT.md
- Default action: `cocosearch "query"` works without subcommand
- Inline filter parsing: `lang:python` extracted from query

Plan 03-03:
- Interactive REPL with SearchREPL class using cmd.Cmd
- Settings commands: `:limit N`, `:lang X`, `:context N`, `:index X`, `:help`
- readline history/editing support (Up/Down arrows)
- CLI `--interactive` flag launches REPL
- Exit via quit/exit/Ctrl-D

**Search CLI Usage:**
```bash
# JSON output (default)
cocosearch search "authentication handler" --index myproject --limit 5

# Pretty output with syntax highlighting
cocosearch "config" --index myproject --pretty

# Language filter
cocosearch "database" --lang python --pretty

# Inline syntax
cocosearch "error handling lang:typescript" --pretty

# Interactive mode
cocosearch --interactive --index myproject
```

Next: Phase 4 (Index Management)

## Phase 4 Summary (In Progress)

Index management module development:

Plan 04-01:
- Management module created at `src/cocosearch/management/`
- `list_indexes()`: Queries information_schema for CocoIndex tables
- `get_stats()`: Returns file/chunk count and storage size
- `clear_index()`: Validates existence before DROP TABLE
- `get_git_root()` / `derive_index_from_git()`: Git-based auto-detection

**Management Functions:**
```python
from cocosearch.management import (
    list_indexes,      # -> list[dict] with name, table_name
    get_stats,         # -> dict with file_count, chunk_count, storage_size
    clear_index,       # -> dict with success, message
    get_git_root,      # -> Path | None
    derive_index_from_git,  # -> str | None
)
```

Plan 04-03:
- MCP server module at `src/cocosearch/mcp/`
- FastMCP server with 5 tools for LLM integration
- `cocosearch mcp` CLI command for server launch
- Tools: search_code, list_indexes, index_stats, clear_index, index_codebase
- Logging configured to stderr for stdio transport

**MCP Server Usage:**
```bash
# Start MCP server
cocosearch mcp

# Claude Desktop configuration (claude_desktop_config.json)
{
  "mcpServers": {
    "cocosearch": {
      "command": "uv",
      "args": ["run", "cocosearch", "mcp"]
    }
  }
}
```
