---
phase: 47-documentation-update
plan: 02
subsystem: documentation
tags: [docs, cli-reference, architecture, mcp-tools, retrieval, search-features, dogfooding, parse-health, roots, uvx]

dependency_graph:
  requires:
    - phase-43 (credential defaults)
    - phase-44 (docker simplification)
    - phase-45 (mcp protocol enhancements)
    - phase-46 (parse failure tracking)
    - plan-47-01 (README and MCP configuration)
  provides:
    - Updated reference docs reflecting current system state
    - Parse health documented in cli-reference and mcp-tools
    - Roots capability documented in architecture
    - 8-stage indexing pipeline in retrieval
  affects: []

tech_stack:
  added: []
  patterns: []

key_files:
  created: []
  modified:
    - docs/cli-reference.md
    - docs/architecture.md
    - docs/dogfooding.md
    - docs/mcp-tools.md
    - docs/retrieval.md
    - docs/search-features.md

decisions:
  - id: doc-output-blocks-removed
    description: "All output blocks removed from reference docs per CONTEXT.md decision"
  - id: doc-uvx-standardized
    description: "All command examples use uvx cocosearch throughout all 6 reference docs"
  - id: doc-json-flag-kept
    description: "--json flag kept in cli-reference.md since it exists on stats and languages commands"

metrics:
  duration: ~4 minutes
  completed: 2026-02-08
---

# Phase 47 Plan 02: Reference Docs Update Summary

Updated all 6 reference docs (cli-reference, architecture, mcp-tools, retrieval, search-features, dogfooding) to reflect features from phases 43-46, remove output blocks, standardize on uvx cocosearch, and add parse health and Roots documentation.

## What Was Done

### Task 1: Update cli-reference.md, architecture.md, and dogfooding.md

**cli-reference.md:**
- Removed all output blocks (6 fenced output blocks eliminated)
- Changed all command examples from bare `cocosearch` to `uvx cocosearch`
- Added `--show-failures` flag to the stats command flag table with description
- Added parse health section describing default parse health display and detailed failure listing
- Removed stale "Language Breakdown" section that duplicated stats content with output blocks
- Kept `--json` flag reference (verified it exists in actual CLI source for both stats and languages commands)
- Added complete flag table for stats command with all current flags

**architecture.md:**
- Updated FastMCP description to mention Roots capability for automatic project detection
- Added step 8 "Parse Tracking" to the indexing data flow section
- Updated MCP Integration section: search_code noted as async with Context, index_stats mentions parse health and include_failures, clear_index mentions parse results cleanup
- Updated Project Detection paragraph with full priority chain (Roots > --project-from-cwd > env > cwd)
- Added "Infra-only Docker" key decision explaining Docker provides infrastructure only
- Added "Parse tracking" key decision explaining non-fatal per-file parse status tracking

**dogfooding.md:**
- Replaced all `uv run cocosearch` with `uvx cocosearch` (6 command examples)
- Removed all output blocks (4 fenced output blocks and descriptive text)
- Kept section structure (Indexing, Verifying, Example Searches) with brief descriptions

### Task 2: Update mcp-tools.md, retrieval.md, and search-features.md

**mcp-tools.md:**
- Added `include_failures` parameter to index_stats Parameters table
- Added `parse_stats` object with `parse_health_pct` and `by_language` to Single Index response example
- Added `parse_failures` array example showing file paths and error details when include_failures is true
- Added `parse_stats` to All Indexes response example (both index entries)
- Updated search_code description to mention Roots-based automatic project detection
- Updated clear_index description to note parse_results table is also removed
- Added `parse_tracking.py` to Implementation section references

**retrieval.md:**
- Added "### 8. Parse Tracking" section after Storage, describing post-flow parse tracking pass
- Documented parse status values (ok, partial, error, unsupported)
- Documented per-index parse_results table schema
- Updated Summary from "7-stage pipeline" to "8-stage pipeline"

**search-features.md:**
- Changed all bare `cocosearch search` to `uvx cocosearch search` (13 command examples)
- No structural changes needed -- content was accurate for search features
- Inline comments in code blocks (like `# May return:`) kept as they serve as brief annotations

## Deviations from Plan

None -- plan executed exactly as written.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Kept `--json` flag in cli-reference.md | Verified in CLI source that `--json` exists on both `stats` and `languages` commands |
| Kept inline comments in search-features.md code blocks | Comments like `# May return:` are inside code blocks as annotations, not standalone output blocks |
| Added complete stats flag table | cli-reference.md now has all 9 stats flags documented in one place |

## Verification Results

All verification checks passed:
- No `uv run` in any docs/ file
- No `:3000` or `port 3000` in any docs/ file
- No standalone `Output:` labels in any docs/ file
- `include_failures` documented in mcp-tools.md
- `--show-failures` documented in cli-reference.md
- `Roots` mentioned in architecture.md
- `Parse Tracking` section exists in retrieval.md
- `uvx cocosearch` used throughout dogfooding.md and search-features.md
- `8-stage` pipeline count in retrieval.md summary

## Commits

| Hash | Message |
|------|---------|
| 990cf41 | docs(47-02): update cli-reference, architecture, and dogfooding docs |
| 5209abb | docs(47-02): update mcp-tools, retrieval, and search-features docs |

## Next Phase Readiness

Phase 47 is complete. All 8 documentation files (README.md, docs/mcp-configuration.md from plan 01, plus the 6 reference docs from this plan) are now up to date with the current system state through phase 46.

No blockers or concerns for future work.
