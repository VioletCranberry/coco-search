# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-27)

**Core value:** Semantic code search that runs entirely locally -- no data leaves your machine.
**Current focus:** v1.2 DevOps Language Support -- COMPLETE (all 4 phases, 8 plans shipped)

## Current Position

Phase: 4 of 4 (Search and Output Integration)
Plan: 2 of 2 complete (04-02-PLAN.md)
Status: Phase complete -- v1.2 milestone complete
Last activity: 2026-01-27 -- Completed 04-02-PLAN.md (output integration)

Progress: [####################] 100% (v1.2: 4/4 phases complete, 8/8 plans)

## Milestones Shipped

| Milestone | Phases | Plans | Shipped |
|-----------|--------|-------|---------|
| v1.0 MVP | 1-4 | 12 | 2026-01-25 |
| v1.1 Docs & Tests | 5-7 | 11 | 2026-01-26 |
| v1.2 DevOps Language Support | 1-4 | 8 | 2026-01-27 |

**Total shipped:** 11 phases, 31 plans

## Completed Milestone: v1.2 DevOps Language Support

| Phase | Name | Requirements | Status |
|-------|------|--------------|--------|
| 1 | Custom Language Definitions and File Routing | 6 | Complete |
| 2 | Metadata Extraction | 7 | Complete |
| 3 | Flow Integration and Schema | 4 | Complete |
| 4 | Search and Output Integration | 9 | Complete |

**All 26 requirements implemented and verified.**

## Performance Metrics

| Metric | Value |
|--------|-------|
| v1.2 requirements | 26 |
| v1.2 phases | 4 |
| v1.2 plans | 8 |
| New dependencies | 0 |
| New files | 3 (languages.py, metadata.py, test_metadata.py) |
| Modified files | 6 (config.py, flow.py, query.py, cli.py, formatter.py, server.py) |
| Total tests | 327 (all passing) |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Key decisions for v1.2:

- Zero new dependencies (CocoIndex custom_languages + Python stdlib re)
- Single flow architecture (not separate DevOps flow)
- Regex-only approach (no external parsers)
- Empty strings over NULLs for metadata
- Metadata extraction inside the flow (not post-processing)
- Additive schema only (no primary key changes)
- Standard Rust regex only for separators (CocoIndex uses regex v1.12.2, NOT fancy-regex)
- HCL: 12 block keywords in Level 1 separator; aliases tf, tfvars
- Dockerfile: FROM at higher priority than other instructions; no aliases (routing via extract_language)
- Bash: function keyword at Level 1; aliases sh, zsh, shell; bash NOT in CocoIndex built-in list
- Bare filename patterns for Dockerfile/Containerfile (LOW confidence, needs integration validation)
- extract_language uses basename.startswith("Dockerfile") for variants, exact match for Containerfile
- Flow field kept as "extension" (not renamed to "language") to minimize changes
- chunk_size default kept at 1000 (user can configure for DevOps via .cocosearch.yaml)
- Match block keywords at chunk start only (after comment stripping)
- Language identifier passed as parameter to extract_devops_metadata (not auto-detected)
- Non-FROM Dockerfile instructions get empty hierarchy in v1.2 (no inter-chunk state)
- Top-level Bash code gets empty block_type/hierarchy (consistent with non-DevOps convention)
- Metadata transform runs unconditionally on all chunks (non-DevOps get empty strings)
- Bracket notation for struct sub-field access in collect() kwargs
- LANGUAGE_ALIASES resolves terraform->hcl, shell->bash, sh->bash before validation
- ALL_LANGUAGES = LANGUAGE_EXTENSIONS keys + DEVOPS_LANGUAGES keys; alias keys excluded
- Module-level _has_metadata_columns flag for one-time graceful degradation
- DevOps languages filter via language_id column; extension-based via filename LIKE
- Rich bracket escaping with backslash for literal [lang] annotation display
- _PYGMENTS_LEXER_MAP maps dockerfile->docker for Pygments lexer lookup
- Flat metadata fields in MCP response (not nested)

### Pending Todos

None -- v1.2 milestone complete.

### Blockers/Concerns

- Bare Dockerfile filename pattern support in CocoIndex include_patterns needs validation (LOW confidence)

## Session Continuity

Last session: 2026-01-27T18:47:18Z
Stopped at: Completed 04-02-PLAN.md -- v1.2 milestone complete
Resume file: None

---
*Updated: 2026-01-27 after completing 04-02-PLAN.md (v1.2 complete)*
