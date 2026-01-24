---
phase: 02-indexing-pipeline
plan: 01
subsystem: indexer
tags: [config, pydantic, gitignore, file-filter]

dependency_graph:
  requires:
    - "01-foundation: Python project with cocoindex"
  provides:
    - "IndexingConfig Pydantic model"
    - "File filtering infrastructure (.gitignore + patterns)"
  affects:
    - "02-02: File discovery uses exclude patterns"
    - "02-03: Chunking uses config values"

tech_stack:
  added:
    - "pathspec 1.0.3"
    - "pyyaml 6.0.2"
    - "rich 13.0.0"
  patterns:
    - "Pydantic models for config"
    - "YAML config file loading"

key_files:
  created:
    - src/cocosearch/indexer/__init__.py
    - src/cocosearch/indexer/config.py
    - src/cocosearch/indexer/file_filter.py
  modified:
    - pyproject.toml
    - uv.lock

decisions: []

metrics:
  duration: "2 min"
  completed: "2026-01-24"
---

# Phase 02 Plan 01: Indexer Config & File Filter Summary

**One-liner:** Indexer module with Pydantic config (chunk_size/overlap, include/exclude patterns) and file filter that combines defaults + .gitignore + user excludes.

## What Was Done

### Task 1: Add Phase 2 dependencies
Added pathspec, pyyaml, and rich to pyproject.toml. These provide:
- pathspec: GitIgnoreSpec for .gitignore parsing
- pyyaml: YAML loading for .cocosearch.yaml config
- rich: Progress bars for indexing (future use)

### Task 2: Create indexer config module
Created `src/cocosearch/indexer/config.py` with:
- `IndexingConfig` Pydantic model with defaults:
  - 19 include patterns for common code file extensions
  - chunk_size=1000, chunk_overlap=300 bytes
- `load_config()` function that reads .cocosearch.yaml when present

### Task 3: Create file filter module
Created `src/cocosearch/indexer/file_filter.py` with:
- `DEFAULT_EXCLUDES`: 10 patterns for node_modules, __pycache__, .git, etc.
- `load_gitignore_patterns()`: Reads .gitignore, filters comments/empty lines
- `build_exclude_patterns()`: Combines defaults + .gitignore + user patterns

## Key Artifacts

| File | Purpose | Exports |
|------|---------|---------|
| config.py | Configuration loading | `IndexingConfig`, `load_config` |
| file_filter.py | Pattern-based filtering | `DEFAULT_EXCLUDES`, `load_gitignore_patterns`, `build_exclude_patterns` |

## Decisions Made

None - followed plan exactly.

## Deviations from Plan

None - plan executed exactly as written.

## Next Phase Readiness

**Ready for:** Plan 02-02 (File Discovery) which will:
- Use `build_exclude_patterns()` to filter discovered files
- Use `IndexingConfig.include_patterns` to match file types

**Blocking issues:** None
