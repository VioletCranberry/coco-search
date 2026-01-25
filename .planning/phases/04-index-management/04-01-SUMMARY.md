---
phase: 04-index-management
plan: 01
subsystem: management
tags: [postgresql, git, statistics, discovery]
dependency-graph:
  requires: [03-search]
  provides: [management-module]
  affects: [04-02-cli, 04-03-mcp]
tech-stack:
  added: []
  patterns: [singleton-pool-reuse, subprocess-git-detection]
key-files:
  created:
    - src/cocosearch/management/__init__.py
    - src/cocosearch/management/discovery.py
    - src/cocosearch/management/stats.py
    - src/cocosearch/management/clear.py
    - src/cocosearch/management/git.py
  modified: []
decisions:
  - desc: "Reuse existing connection pool from search.db"
    rationale: "Consistent connection management, no duplicate pool logic"
  - desc: "Import derive_index_name from cli module"
    rationale: "Avoid code duplication, single source of truth for name derivation"
metrics:
  duration: 3 min
  completed: 2026-01-25
---

# Phase 04 Plan 01: Management Module Core Summary

**One-liner:** Core management functions for index discovery, statistics, clearing, and git-based auto-detection using PostgreSQL information_schema and subprocess git integration.

## What Was Built

### Index Discovery (`discovery.py`)
- `list_indexes()` function queries `information_schema.tables` for tables matching `codeindex_%__%_chunks` pattern
- Parses table names to extract human-readable index names
- Returns list of dicts with `name` and `table_name` keys

### Index Statistics (`stats.py`)
- `get_stats(index_name)` returns comprehensive metrics:
  - `file_count`: Number of unique files indexed (via `COUNT(DISTINCT filename)`)
  - `chunk_count`: Total chunks (via `COUNT(*)`)
  - `storage_size`: Bytes (via `pg_table_size()`)
  - `storage_size_pretty`: Human-readable (e.g., "1.5 MB")
- `format_bytes(size)` helper for B/KB/MB/GB formatting
- Validates index exists before querying

### Index Clearing (`clear.py`)
- `clear_index(index_name)` safely deletes an index
- Validates existence in `information_schema` before `DROP TABLE`
- Returns success status and confirmation message
- Raises `ValueError` for non-existent indexes

### Git Integration (`git.py`)
- `get_git_root()` uses `git rev-parse --show-toplevel` via subprocess
- Returns `Path` on success, `None` if not in a git repo
- `derive_index_from_git()` combines git detection with `derive_index_name` from cli module
- Enables automatic index name inference from repository name

## Key Decisions Made

| Decision | Rationale |
|----------|-----------|
| Reuse `get_connection_pool` from search.db | Singleton pattern already handles pgvector registration |
| Import `derive_index_name` from cli module | Single source of truth, no duplicate sanitization logic |
| Validate existence before operations | Fail fast with clear error messages |

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 1b826f5 | feat | Create management module with discovery and stats |
| 3a626c3 | feat | Add clear_index and git detection functions |

## Deviations from Plan

None - plan executed exactly as written.

## Files Created

```
src/cocosearch/management/
  __init__.py      # Module exports (5 functions)
  discovery.py     # list_indexes()
  stats.py         # get_stats(), format_bytes()
  clear.py         # clear_index()
  git.py           # get_git_root(), derive_index_from_git()
```

## Next Phase Readiness

Management module provides the foundation for:
- **04-02**: CLI commands (`list`, `stats`, `clear`) can call these functions directly
- **04-03**: MCP server tools can expose these as Claude-callable operations

All functions follow consistent patterns:
- Return dicts for easy JSON serialization
- Raise `ValueError` with clear messages for invalid inputs
- Reuse connection pool for efficient database access
