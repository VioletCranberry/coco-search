# Project Research Summary

**Project:** CocoSearch v1.9 (Multi-Repo & Polish)
**Domain:** MCP-based semantic code search tool enhancement
**Researched:** 2026-02-05
**Confidence:** HIGH

## Executive Summary

CocoSearch v1.9 is primarily an "unlock and polish" milestone rather than new capability work. The existing architecture already supports Serena-style multi-repo MCP behavior -- the `find_project_root()` function in `management/context.py` already performs cwd-based detection at tool invocation time. The key deliverable is adding a `--project-from-cwd` CLI flag for semantic clarity and documentation, not new detection logic. UV-based installation already works with the current `pyproject.toml` configuration using `uv_build` backend.

The primary risk is the cleanup phase, not the multi-repo feature. Removing deprecated modules (`indexer/metadata.py`, `indexer/languages.py`) and graceful degradation code requires careful sequencing: tests import these modules directly and must be updated before removal. The graceful degradation flags in `search/query.py` protect against pre-v1.8 indexes; removing them without warning will cause hard failures for users with older indexes.

The recommended approach is: implement the `--project-from-cwd` flag first (low risk, mostly documentation), then fix test signature mismatches, then perform atomic cleanup PRs removing one deprecated item at a time. Multi-step workflow skills and documentation can be developed in parallel since they have no dependencies on the cleanup work.

## Key Findings

### Recommended Stack

No new dependencies required. The existing stack fully supports v1.9 features.

**Core technologies (unchanged):**
- `mcp[cli]>=1.26.0`: MCP SDK with FastMCP included -- already provides all needed MCP functionality
- `uv_build>=0.8.13`: Build backend -- already configured correctly for UV toolchain compatibility
- `[project.scripts]`: Entry point -- `cocosearch = "cocosearch.cli:main"` already works

**Key insight:** The feature gap is implementation and documentation, not dependencies. Do not add the standalone `fastmcp` package (it would conflict with the MCP SDK's bundled version).

### Expected Features

**Must have (table stakes):**
- `--project-from-cwd` CLI flag for MCP server -- enables single user-scope registration across all repos
- User-scope registration documentation -- `claude mcp add --scope user cocosearch -- uvx ... cocosearch mcp --project-from-cwd`
- Graceful error handling for "no project detected" and "project not indexed" -- already implemented

**Should have (competitive):**
- Startup validation when `--project-from-cwd` is set -- fail fast if not in a valid project
- Index freshness warnings in search results -- help users know when to re-index
- MCP Roots protocol support -- protocol-standard alternative to cwd detection

**Defer (v2+):**
- Cross-index search (multiple indexes in one query)
- Index groups for batch operations
- Dynamic project switching based on tool parameters (anti-pattern)

### Architecture Approach

The existing architecture is correct for multi-repo support. CocoSearch uses invocation-time detection (detects project at each tool call) rather than registration-time detection (captures project once at startup). This is more flexible than Serena's approach and already works without code changes.

**Integration points:**
1. `mcp/server.py` `search_code()` -- already calls `find_project_root()` when `index_name=None`
2. `management/context.py` -- `find_project_root()` walks up from cwd looking for `.git` or `cocosearch.yaml`
3. `cli.py` -- needs `--project-from-cwd` flag added to `mcp` command
4. `management/metadata.py` -- collision detection already works via `get_index_metadata()`

**Data flow (unchanged):**
```
Claude Code starts MCP server with cwd=project_directory
  -> cocosearch mcp --project-from-cwd
  -> find_project_root(os.getcwd())
  -> resolve_index_name()
  -> search executes on detected index
```

### Critical Pitfalls

1. **MCP Working Directory Sandbox Isolation** -- `os.getcwd()` returns uvx cache path, not workspace. Prevention: use `uvx --directory $(pwd)` pattern in MCP registration; test via actual Claude Code invocation.

2. **Test Imports Breaking Before Cleanup** -- Tests import deprecated modules directly (`test_metadata.py`, `test_languages.py`, `test_flow.py`). Prevention: update test imports FIRST, then remove deprecated modules in same commit.

3. **Removing Graceful Degradation With Old Indexes in Use** -- `_has_metadata_columns` and `_has_content_text_column` flags protect pre-v1.8 indexes. Prevention: add `cocosearch stats` warning about old indexes; document upgrade requirement before removal.

4. **Removing Migration Logic Prematurely** -- `ensure_hybrid_search_schema()` and `ensure_symbol_columns()` are called during indexing. Prevention: verify CocoIndex handles all column creation before removing migration functions.

5. **Large Cleanup PRs Hiding Regressions** -- Single PR removing multiple deprecated items is hard to review/revert. Prevention: one PR per deprecated item, run full test suite between each.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Multi-Repo MCP Support
**Rationale:** Low risk, mostly documentation; enables core v1.9 value proposition
**Delivers:** `--project-from-cwd` flag, user-scope registration pattern, updated docs
**Addresses:** Single MCP registration for all projects (table stakes feature)
**Avoids:** MCP cwd sandbox issue by documenting `--directory $(pwd)` pattern

### Phase 2: Test Fixes
**Rationale:** Must fix tests before cleanup phase can begin safely
**Delivers:** Fixed signature format mismatches, stable test suite
**Uses:** Existing test infrastructure
**Avoids:** Cleanup regressions masked by pre-existing test failures

### Phase 3: Atomic Cleanup
**Rationale:** Cleanup must happen after tests are stable; each item is atomic PR
**Delivers:** Removal of deprecated code in safe sequence
**Implements:** Safe removal order: test imports -> deprecated modules -> graceful degradation -> migration logic
**Avoids:** Test import breakage, old index hard failures

### Phase 4: Multi-Step Workflow Skills
**Rationale:** Can be developed in parallel with cleanup; no dependencies
**Delivers:** Onboarding, debugging, refactoring workflow guidance
**Uses:** MCP tools reference (Phase 5)
**Avoids:** N/A -- independent work stream

### Phase 5: Documentation
**Rationale:** Retrieval logic and MCP tools reference needed for skills and external users
**Delivers:** Complete documentation for retrieval logic, MCP tools reference
**Uses:** Completed multi-repo implementation as reference
**Avoids:** Documentation drift by documenting after implementation stable

### Phase Ordering Rationale

- **Multi-repo before cleanup:** Multi-repo is low-risk and delivers value immediately; cleanup is high-risk and can break things
- **Test fixes before cleanup:** Cannot safely remove deprecated code when tests are already failing; fixes establish stable baseline
- **Atomic cleanup sequence:** Each deprecated item removed in separate PR enables clean rollback if issues found
- **Skills parallel to cleanup:** No code dependencies; can progress independently
- **Documentation last:** Ensures docs reflect final implementation, not interim states

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (Workflow Skills):** Need to research effective multi-step patterns for each workflow type

Phases with standard patterns (skip research-phase):
- **Phase 1 (Multi-Repo):** Well-documented Serena pattern; existing code already supports it
- **Phase 2 (Test Fixes):** Straightforward fix work, no research needed
- **Phase 3 (Cleanup):** Dependency graph already mapped; safe sequence documented
- **Phase 5 (Documentation):** Documenting existing functionality

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Verified pyproject.toml, UV installation tested |
| Features | HIGH | Serena pattern documented, existing code analyzed |
| Architecture | HIGH | Codebase inspection confirms invocation-time detection works |
| Pitfalls | HIGH | Direct grep of tests shows exact imports; SDK issue #1520 verified |

**Overall confidence:** HIGH

### Gaps to Address

- **uvx cwd behavior validation:** Need integration test confirming `os.getcwd()` returns correct path when launched from Claude Code (not just unit tests)
- **Old index prevalence:** Unknown how many users have pre-v1.8 indexes; may need migration guidance before removing graceful degradation
- **CocoIndex schema completeness:** Need to verify CocoIndex natively creates all columns before removing migration functions

## Sources

### Primary (HIGH confidence)
- [MCP Python SDK Issue #1520](https://github.com/modelcontextprotocol/python-sdk/issues/1520) -- Working directory detection in uvx sandbox
- [Serena Running Documentation](https://oraios.github.io/serena/02-usage/020_running.html) -- `--project-from-cwd` pattern
- [Claude Code MCP Documentation](https://code.claude.com/docs/en/mcp) -- MCP scopes and configuration
- CocoSearch codebase analysis -- `management/context.py`, `mcp/server.py`, `search/query.py`

### Secondary (MEDIUM confidence)
- [MCP Roots Specification](https://modelcontextprotocol.io/specification/2025-06-18/client/roots) -- Protocol-level workspace roots (future enhancement)
- [Security Boulevard: Safe Code Removal](https://securityboulevard.com/2026/01/how-to-automate-safe-removal-of-unused-code/) -- Atomic cleanup best practices

### Tertiary (LOW confidence)
- [Serena Issue #895](https://github.com/oraios/serena/issues/895) -- Auto-activate limitations (Serena-specific, may not apply)

---
*Research completed: 2026-02-05*
*Ready for roadmap: yes*
