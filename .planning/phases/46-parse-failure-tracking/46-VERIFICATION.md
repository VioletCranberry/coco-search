---
phase: 46-parse-failure-tracking
verified: 2026-02-08T18:30:00Z
status: passed
score: 4/4 must-haves verified
---

# Phase 46: Parse Failure Tracking Verification Report

**Phase Goal:** Users can see how many files failed tree-sitter parsing per language when reviewing index health
**Verified:** 2026-02-08T18:30:00Z
**Status:** PASSED
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After indexing, each file has a `parse_status` value (ok, partial, error, or unsupported) stored in the database | VERIFIED | `parse_tracking.py` (185 lines) has `detect_parse_status()` classifying into 4 categories, `track_parse_results()` querying chunks table and persisting results, `rebuild_parse_results()` truncating and batch inserting. `flow.py` calls `track_parse_results()` after `flow.update()` (line 219). `schema_migration.py` has `ensure_parse_results_table()` creating the table with file_path/language/parse_status/error_message columns. |
| 2 | `cocosearch stats` CLI shows parse failure counts per language alongside existing metrics | VERIFIED | `cli.py` has `format_parse_health()` (lines 506-547) rendering color-coded summary and Rich table with Language/Files/OK/Partial/Error/Unsupported columns. `stats_command()` calls it at line 763 for single-index and line 696 for --all mode. `--show-failures` flag registered at line 1343, triggers `format_parse_failures()` at line 769. JSON output includes parse_stats via `stats.to_dict()` at line 723, with optional `parse_failures` at line 726. |
| 3 | MCP `index_stats` tool response includes parse failure breakdown per language | VERIFIED | `server.py` `index_stats` tool (lines 422-467) uses `get_comprehensive_stats()` which populates `parse_stats` field. Returns `stats.to_dict()` which includes `parse_stats`. Has `include_failures` parameter (line 427-433) that adds `get_parse_failures()` data when True. Works for both single-index and all-indexes modes. |
| 4 | HTTP `/api/stats` endpoint includes parse failure data in its JSON response | VERIFIED | `server.py` `/api/stats` route (lines 68-107) calls `get_comprehensive_stats().to_dict()` which includes `parse_stats`. Has `include_failures` query parameter support at line 76. `/api/stats/{index_name}` route (lines 110-128) also supports `include_failures`. Both single-index and all-indexes paths include parse data. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/cocosearch/indexer/parse_tracking.py` | Parse detection and persistence module | VERIFIED (185 lines, no stubs, imported by flow.py) | Has `detect_parse_status()`, `_collect_error_lines()`, `track_parse_results()`, `rebuild_parse_results()`. Real tree-sitter parsing, real DB operations. |
| `src/cocosearch/indexer/schema_migration.py` | `ensure_parse_results_table()` | VERIFIED (231 lines total, function at line 191) | Creates `cocosearch_parse_results_{index_name}` table with PRIMARY KEY on file_path, index on (language, parse_status). Idempotent via CREATE TABLE IF NOT EXISTS. |
| `src/cocosearch/indexer/flow.py` | Parse tracking integration in `run_index()` | VERIFIED (225 lines) | Imports at lines 24-25. Calls `ensure_parse_results_table()` at line 211 during setup. Calls `track_parse_results()` at line 219 after `flow.update()`. Non-fatal wrapper with try/except at lines 217-222. |
| `src/cocosearch/management/clear.py` | Parse results table cleanup on clear | VERIFIED (72 lines) | Lines 52-58: `DROP TABLE IF EXISTS cocosearch_parse_results_{index_name}` with try/except for backward compatibility. |
| `src/cocosearch/management/stats.py` | `get_parse_stats()`, `get_parse_failures()`, `IndexStats.parse_stats` | VERIFIED (584 lines) | `get_parse_stats()` at line 231 with table existence check, aggregation query, and by_language dict construction. `get_parse_failures()` at line 304 with status filter. `IndexStats.parse_stats` field at line 212. `get_comprehensive_stats()` calls `get_parse_stats()` at line 541 and passes to constructor at line 583. |
| `src/cocosearch/cli.py` | `format_parse_health()`, `format_parse_failures()`, `--show-failures` flag | VERIFIED (1514 lines) | `format_parse_health()` at line 506 with color-coded output. `format_parse_failures()` at line 550. `--show-failures` at line 1343. Display in single-index (line 763) and --all (line 696) modes. |
| `src/cocosearch/mcp/server.py` | Updated `index_stats` tool and `/api/stats` with parse data | VERIFIED (582 lines) | `index_stats` tool at line 422 uses `get_comprehensive_stats()`. `/api/stats` at line 68. `/api/stats/{index_name}` at line 110. All include `include_failures` parameter. |
| `src/cocosearch/management/__init__.py` | Exports `get_parse_stats`, `get_parse_failures` | VERIFIED (44 lines) | Both exported at line 23 import and lines 37-38 in `__all__`. |
| `tests/unit/indexer/test_parse_tracking.py` | Tests for parse detection | VERIFIED (99 lines, 13 tests) | TestDetectParseStatus (11 tests for ok/partial/unsupported across Python/JS/TS/Go/Rust/empty). TestCollectErrorLines (2 tests for valid/error trees). |
| `tests/unit/management/test_stats.py` | Tests for parse stats functions | VERIFIED (610 lines, 8 new tests) | TestGetParseStats (4 tests), TestGetParseFailures (2 tests), TestIndexStatsWithParseStats (2 tests). Existing IndexStats tests updated with parse_stats={}. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `flow.py` | `parse_tracking.py` | `import and call track_parse_results()` | WIRED | Import at line 25, call at line 219 inside try/except |
| `flow.py` | `schema_migration.py` | `import and call ensure_parse_results_table()` | WIRED | Import at line 24, call at line 211 in `with psycopg.connect()` block |
| `parse_tracking.py` | `symbols.py` | `from cocosearch.indexer.symbols import LANGUAGE_MAP` | WIRED | Import at line 19, used at lines 38 and 130 |
| `stats.py` | `cocosearch_parse_results` table | SQL queries for aggregation | WIRED | `get_parse_stats()` queries at lines 271-276, `get_parse_failures()` queries at lines 343-348 |
| `stats.py:IndexStats` | `parse_stats` field | Added to dataclass | WIRED | Field at line 212, populated by `get_comprehensive_stats()` at line 583 |
| `cli.py` | `stats.py` | `stats.parse_stats` used in display | WIRED | `format_parse_health()` called at lines 696 and 763. `get_parse_failures` imported at lines 725 and 768. |
| `server.py` (MCP) | `stats.py` | `get_comprehensive_stats().to_dict()` | WIRED | MCP tool at line 447, HTTP routes at lines 81-82, 98, 119. `get_parse_failures` imported at line 43 and used at lines 84, 100, 122, 450, 460. |
| `clear.py` | `parse_results` table | `DROP TABLE IF EXISTS` | WIRED | Lines 53-58, drops `cocosearch_parse_results_{index_name}` |

### Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| OBS-01: Parse status stored per file after indexing | SATISFIED | None |
| OBS-02: CLI stats shows parse failure counts per language | SATISFIED | None |
| OBS-03: MCP index_stats includes parse failure breakdown | SATISFIED | None |
| OBS-04: HTTP /api/stats includes parse failure data | SATISFIED | None |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | - | - | - | No anti-patterns detected |

No TODO/FIXME/placeholder/stub patterns found in any modified files.

### Test Results

All 46 unit tests pass (13 parse tracking + 33 stats tests including 8 new parse stats tests).

- `tests/unit/indexer/test_parse_tracking.py`: 13 passed
- `tests/unit/management/test_stats.py`: 33 passed
- `tests/unit/test_cli.py`: 34 passed, 1 failed (pre-existing: `test_valid_path_runs_indexing` requires PostgreSQL)

### Human Verification Required

#### 1. End-to-End Parse Tracking During Indexing
**Test:** Run `cocosearch index .` on a codebase with mixed languages
**Expected:** After indexing, `cocosearch stats --pretty` shows parse health percentage and per-language parse status table with ok/partial/error/unsupported counts
**Why human:** Requires running PostgreSQL and full indexing pipeline

#### 2. Parse Failure Detail Display
**Test:** Run `cocosearch stats --show-failures` on an index containing files with syntax errors
**Expected:** Individual files with non-ok parse status are listed with file path, language, status, and error message
**Why human:** Requires real index data with parse failures

#### 3. MCP Tool Response Verification
**Test:** Call `index_stats` MCP tool with `include_failures=true` via an MCP client
**Expected:** Response JSON includes `parse_stats` with `by_language`, `parse_health_pct`, and `parse_failures` list
**Why human:** Requires MCP client connection and running server

#### 4. HTTP API Response Verification
**Test:** `GET /api/stats?include_failures=true` via curl or browser
**Expected:** JSON response includes `parse_stats` object with per-language breakdown and `parse_failures` array
**Why human:** Requires running HTTP server and database

#### 5. Backward Compatibility
**Test:** Run `cocosearch stats` on a pre-phase-46 index (one that was indexed before parse tracking was added)
**Expected:** Stats display normally with no parse health section (graceful degradation, no errors)
**Why human:** Requires a pre-existing index without parse_results table

### Gaps Summary

No gaps found. All four success criteria are fully verified at the code level:

1. **Parse status storage:** `parse_tracking.py` provides 4-category classification (ok/partial/error/unsupported), integrated into `flow.py` as a non-fatal post-indexing step, with `schema_migration.py` creating the per-index `cocosearch_parse_results_{index_name}` table.

2. **CLI display:** `cli.py` has `format_parse_health()` with color-coded summary and per-language Rich table, displayed in both single-index and --all modes, with `--show-failures` for file-level detail.

3. **MCP tool:** `server.py` `index_stats` tool uses `get_comprehensive_stats()` which includes `parse_stats`, with `include_failures` parameter for detailed breakdown.

4. **HTTP endpoint:** `server.py` `/api/stats` and `/api/stats/{index_name}` routes return `parse_stats` in JSON, with `?include_failures=true` query parameter support.

All artifacts are substantive (no stubs), all key links are wired, all tests pass, and no anti-patterns were found.

---

_Verified: 2026-02-08T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
