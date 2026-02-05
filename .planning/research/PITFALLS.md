# Pitfalls Research: v1.9 Multi-Repo & Polish

**Project:** CocoSearch v1.9
**Domain:** Adding multi-repo MCP support AND aggressive code cleanup in existing semantic code search tool
**Researched:** 2026-02-05
**Milestone:** v1.9 -- Multi-Repo & Polish
**Confidence:** MEDIUM-HIGH (verified with MCP SDK issues, codebase analysis, and 2026 cleanup research)

## Executive Summary

v1.9 combines two high-risk activities: adding cwd-based multi-repo detection to an existing MCP server AND aggressive code cleanup removing deprecated functions and migration logic. The primary risks are (1) breaking existing workflows when MCP clients pass unexpected working directories, (2) removing code that tests depend on before updating those tests, and (3) eliminating graceful degradation for edge cases that still occur in practice.

---

## Critical Pitfalls

### 1. MCP Working Directory Sandbox Isolation

**Risk:** `os.getcwd()` returns wrong directory when MCP server runs inside uvx sandbox. The [MCP Python SDK issue #1520](https://github.com/modelcontextprotocol/python-sdk/issues/1520) documents that uvx returns a temporary cache path under `~/.cache/uv/...` rather than the actual project workspace. Current code in `mcp/server.py` uses `find_project_root()` which may call `Path.cwd()` under the hood.

**Warning signs:**
- Auto-detect returns "No project detected" despite being in valid repo
- Index name derived from cache directory instead of project name
- Test passes locally but fails when run via Claude Code

**Prevention:**
- Test MCP tools via actual Claude Code invocation, not just unit tests
- Use `--directory $(pwd)` pattern when adding MCP server: `claude mcp add cocosearch -s project -- uvx --directory $(pwd) cocosearch mcp`
- Consider explicit workspace parameter injection rather than relying on cwd detection
- Add integration test that simulates uvx environment

**Phase:** Multi-repo MCP implementation (early phase)

---

### 2. Test Imports Breaking Before Cleanup Complete

**Risk:** Tests import deprecated modules directly. Analysis of codebase shows:

```
tests/unit/indexer/test_metadata.py imports from cocosearch.indexer.metadata:
  - DevOpsMetadata, extract_hcl_metadata, extract_dockerfile_metadata, extract_bash_metadata
  - _strip_leading_comments, _HCL_COMMENT_LINE, _DOCKERFILE_COMMENT_LINE, _BASH_COMMENT_LINE
  - _LANGUAGE_DISPATCH, _LANGUAGE_ID_MAP, _EMPTY_METADATA

tests/unit/indexer/test_languages.py imports from cocosearch.indexer.languages:
  - DEVOPS_CUSTOM_LANGUAGES (line 7)

tests/unit/indexer/test_flow.py imports from cocosearch.indexer.languages:
  - DEVOPS_CUSTOM_LANGUAGES (line 225)
```

Removing deprecated modules before updating tests causes immediate test failures.

**Warning signs:**
- ImportError in test collection phase
- Tests suddenly fail with "module not found" errors
- CI breaks on first commit of cleanup phase

**Prevention:**
- Run `grep -r "from cocosearch.indexer.metadata import\|from cocosearch.indexer.languages import" tests/` before removing any deprecated code
- Update test imports FIRST, then remove deprecated modules in same commit
- Keep deprecated modules as empty re-export stubs if needed temporarily
- Create checklist: for each deprecated module, list all test files importing it

**Phase:** Cleanup phase (AFTER new implementation working)

---

### 3. Removing Graceful Degradation With Older Indexes Still in Use

**Risk:** The codebase has multiple graceful degradation paths identified in `search/query.py`:

```python
# Lines 113-119: Module-level flags
_has_metadata_columns = True      # pre-v1.2 graceful degradation
_metadata_warning_emitted = False
_has_content_text_column = True   # pre-v1.7 graceful degradation
_hybrid_warning_emitted = False
```

These flags enable:
- Search on pre-v1.2 indexes without metadata columns (language_id, block_type, hierarchy)
- Search on pre-v1.7 indexes without hybrid search columns (content_text)
- Symbol filtering check via `check_symbol_columns_exist()`

Single-user doesn't mean single-machine. User may have old indexes on one machine, new on another (synced via volume). Removing degradation causes hard failures instead of soft warnings.

**Warning signs:**
- UndefinedColumn PostgreSQL errors in production
- "Index lacks metadata columns" errors becoming hard failures
- Users reporting "search stopped working" after upgrade

**Prevention:**
- Add `cocosearch stats` check that warns about pre-v1.8 indexes BEFORE removing degradation
- Document: "v1.9 requires all indexes to be v1.8 format - re-index to upgrade"
- Add one-time migration script or clear guidance in CHANGELOG
- Consider keeping degradation as explicit version check with user-facing error: "Index too old, please re-index"

**Phase:** Cleanup phase (near end)

---

### 4. Removing Migration Logic Prematurely

**Risk:** `schema_migration.py` contains `ensure_hybrid_search_schema()` and `ensure_symbol_columns()` which are called during indexing (via `indexer/flow.py` line 23) to add columns to existing indexes. Removing this logic means users who re-index get partial schema.

The functions are:
- `ensure_hybrid_search_schema()`: Adds content_tsv column + GIN index
- `ensure_symbol_columns()`: Adds symbol_type, symbol_name, symbol_signature columns

**Warning signs:**
- Re-indexing existing codebase fails silently (missing columns)
- Hybrid search stops working after re-index
- Symbol filtering raises ValueError on freshly re-indexed data

**Prevention:**
- Migration functions are ADDITIVE (safe to keep)
- Only remove if CocoIndex now handles all column creation natively
- Test: drop and recreate index, verify all columns present
- Keep migration logic but move to explicit "upgrade" command if removing automatic path

**Phase:** Cleanup phase (after verifying CocoIndex schema completeness)

---

### 5. Breaking Existing MCP Client Configurations

**Risk:** Multi-repo detection changes how index names are resolved. Existing Claude Desktop configs with explicit index_name may break if auto-detect logic runs first and conflicts.

Current collision detection in `mcp/server.py` (lines 248-265):
```python
metadata = get_index_metadata(index_name)
if metadata is not None:
    canonical_cwd = str(root_path.resolve())
    stored_path = metadata.get("canonical_path", "")
    if stored_path and stored_path != canonical_cwd:
        # Collision detected - error returned
```

**Warning signs:**
- "Index name collision" errors in previously working setups
- Auto-detect overriding explicit parameters
- Different behavior between Claude Code and Claude Desktop

**Prevention:**
- Explicit parameters ALWAYS override auto-detect (verify current behavior preserved)
- Test matrix: explicit index_name + git repo, explicit index_name + non-git, no index_name + git repo
- Document precedence clearly: CLI/MCP parameter > cocosearch.yaml indexName > git root name

**Phase:** Multi-repo MCP implementation

---

### 6. Git Root Detection Boundary Errors

**Risk:** The [Serena pattern](https://gist.github.com/semikolon/7f6791779e0f8ac07a41fd29a19eb44b) uses `git rev-parse --show-toplevel` for project detection. This fails or returns unexpected results for:
- Nested git repos (submodules)
- Worktrees
- Detached HEAD state
- Non-git directories with cocosearch.yaml

**Warning signs:**
- Index names derived from parent repo instead of submodule
- Worktree treated as different project
- "Not in a git repository" in valid cocosearch.yaml project

**Prevention:**
- Priority chain: cocosearch.yaml directory > git root > cwd (already implemented in `management/context.py`, verify)
- Test with submodule, worktree, bare repo, detached HEAD
- Fallback gracefully: if git fails, try cocosearch.yaml, then cwd

**Phase:** Multi-repo MCP implementation

---

### 7. Removing Internal Helpers That Tests Depend On

**Risk:** Test file `test_metadata.py` imports internal helpers with underscore prefixes:
```python
from cocosearch.indexer.metadata import (
    _strip_leading_comments,
    _HCL_COMMENT_LINE,
    _DOCKERFILE_COMMENT_LINE,
    _BASH_COMMENT_LINE,
    _LANGUAGE_DISPATCH,
    _LANGUAGE_ID_MAP,
    _EMPTY_METADATA,
)
```
These underscore-prefixed names were re-exported FOR test compatibility (see `indexer/metadata.py` lines 53-56, 58-80). Removing them breaks tests even though they're "internal."

**Warning signs:**
- Tests fail with ImportError on underscore-prefixed names
- "Private" function removal breaks something

**Prevention:**
- Grep for `_` prefixed imports in tests: `grep -r "import.*_[A-Z]" tests/`
- Either: update tests to use public API, OR keep re-exports in deprecated module
- Document: deprecation shims exist specifically for test compatibility

**Phase:** Cleanup phase

---

### 8. Incomplete Atomic Cleanup

**Risk:** [Research shows](https://securityboulevard.com/2026/01/how-to-automate-safe-removal-of-unused-code/) each transformation should ship as atomic pull requests under 200 lines. Large cleanup PRs hide regressions and are hard to review/revert.

**Warning signs:**
- Single PR removing 5+ deprecated items
- "Also cleaned up X while I was in there"
- Rollback requires partial revert with conflicts

**Prevention:**
- One PR per deprecated item: migration logic, metadata.py, languages.py, graceful degradation
- Each PR: remove code + update tests + update docs
- Run full test suite between each cleanup PR

**Phase:** Cleanup phase (structure)

---

## Cleanup-Specific Risks

### Deprecated Module Dependency Graph

Before removing any deprecated module, trace its dependents:

| Deprecated Module | Depends On | Depended On By |
|-------------------|------------|----------------|
| `indexer/metadata.py` | `handlers/*` | `tests/unit/indexer/test_metadata.py`, potentially old scripts |
| `indexer/languages.py` | `handlers/*` | `tests/unit/indexer/test_languages.py`, `tests/unit/indexer/test_flow.py` |
| `schema_migration.py` | psycopg | `indexer/flow.py` (line 23: `from cocosearch.indexer.schema_migration import ensure_symbol_columns`) |
| graceful degradation globals | - | `search/query.py` (internal), `search/hybrid.py` |

### Removal Order (Safe Sequence)

1. **First:** Update all test imports to use new paths
2. **Second:** Run tests, fix any failures
3. **Third:** Add deprecation warnings if not present (for external users tracking)
4. **Fourth:** Remove deprecated modules one at a time
5. **Fifth:** Remove graceful degradation (after confirming no old indexes)
6. **Sixth:** Remove migration logic (after confirming CocoIndex handles schema)

### Test Signature Format Mismatches

From PROJECT.md: "Fix test signature format mismatches" is an active task. This suggests existing test issues that cleanup could exacerbate.

**Risk:** Cleanup changes function signatures, tests fail due to signature mismatch rather than behavioral change.

**Prevention:**
- Fix signature mismatches BEFORE cleanup
- Use pytest's `--tb=short` to quickly identify signature vs. behavior failures
- Consider snapshot testing for MCP response formats

---

## MCP-Specific Risks

### Transport-Aware Testing

Different MCP transports have different cwd behaviors:
- **stdio:** May inherit shell cwd correctly
- **SSE/HTTP:** Running as daemon, cwd is process start directory
- **Docker:** cwd is container working directory

**Prevention:**
- Test auto-detect with all three transports
- Document which transports support cwd detection
- Consider: for HTTP/SSE, always require explicit index_name

### Index Name Collision Edge Cases

Current collision detection uses `get_index_metadata()` to check stored path. Edge cases:
- Symlinks: `/home/user/project` vs `/var/projects/project` (same dir, different paths)
- Case sensitivity: `MyProject` vs `myproject` on case-insensitive filesystems
- Network drives: paths may change across sessions

**Prevention:**
- Use `Path.resolve()` for canonical paths (already done in `mcp/server.py` line 250)
- Normalize case on case-insensitive systems
- Document: collision detection uses canonical resolved paths

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation | Severity |
|-------------|---------------|------------|----------|
| Multi-repo MCP | cwd returns uvx cache dir | Use `--directory $(pwd)` pattern | CRITICAL |
| Multi-repo MCP | Git submodule detection | Test with nested repos | HIGH |
| Multi-repo MCP | Collision with explicit params | Verify precedence preserved | MEDIUM |
| Cleanup: metadata.py | Test imports break | Update tests first | CRITICAL |
| Cleanup: languages.py | Test imports break | Update tests first | CRITICAL |
| Cleanup: graceful degradation | Old indexes fail hard | Require re-index before upgrade | HIGH |
| Cleanup: schema_migration | Re-index missing columns | Verify CocoIndex handles schema | HIGH |
| Cleanup: general | Large PRs hide regressions | Atomic PRs, one item each | MEDIUM |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|----------|-------|
| MCP cwd detection | HIGH | Verified with SDK issue #1520, current codebase analysis |
| Test import dependencies | HIGH | Direct grep of codebase shows exact imports |
| Graceful degradation flags | HIGH | Identified exact flags in search/query.py |
| Migration function usage | HIGH | Traced import in indexer/flow.py |
| Git detection edge cases | MEDIUM | Known issues, not all tested in this codebase |
| Atomic cleanup benefits | MEDIUM | General best practice, not CocoSearch-specific |

---

## Sources

**MCP Working Directory Issues:**
- [MCP Python SDK Issue #1520: Working directory detection](https://github.com/modelcontextprotocol/python-sdk/issues/1520)
- [mcp-server-git Issue #3029: Auto-detect git root](https://github.com/modelcontextprotocol/servers/issues/3029)
- [Serena MCP Auto-Wrapper: Zero-config multi-project](https://gist.github.com/semikolon/7f6791779e0f8ac07a41fd29a19eb44b)

**Code Cleanup Best Practices:**
- [Security Boulevard: Automate Safe Removal of Unused Code (2026)](https://securityboulevard.com/2026/01/how-to-automate-safe-removal-of-unused-code/)
- [Tideways: Refactoring with Deprecations](https://tideways.com/profiler/blog/refactoring-with-deprecations)
- [AI Code Refactoring Best Practices](https://www.augmentcode.com/tools/ai-code-refactoring-tools-tactics-and-best-practices)

**Database Migration Safety:**
- [PlanetScale: Backward Compatible Database Changes](https://planetscale.com/blog/backward-compatible-databases-changes)
- [Quesma: Schema Migration Pitfalls and Risks](https://quesma.com/blog/schema-migrations/)

**Codebase Analysis:**
- Direct grep of `src/cocosearch/` for deprecated markers and graceful degradation patterns
- Direct grep of `tests/` for deprecated module imports
- Line-by-line analysis of `search/query.py`, `indexer/schema_migration.py`, `mcp/server.py`

---

*Researched: 2026-02-05*
