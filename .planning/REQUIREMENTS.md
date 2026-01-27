# Requirements: v1.2 DevOps Language Support

**Milestone:** v1.2
**Status:** Roadmapped
**Source:** User questioning + research synthesis (2026-01-27)

## Scope Summary

Add language-aware chunking and rich metadata extraction for HCL (Terraform), Dockerfile, and Bash/Shell files using CocoIndex's `custom_languages` API. Zero new runtime dependencies. Works for pure infrastructure repos and mixed codebases.

## Requirements

### Chunking (Language-Aware)

| ID | Requirement | Priority | Notes |
|----|------------|----------|-------|
| REQ-01 | HCL block-level chunking via `CustomLanguageSpec` regex separators | Must | Top-level blocks: resource, data, module, variable, output, locals, provider, terraform, import, moved, removed, check |
| REQ-02 | Dockerfile instruction-level chunking via `CustomLanguageSpec` regex separators | Must | FROM as stage boundary (Level 1), major instructions as Level 2 |
| REQ-03 | Bash function-level chunking via `CustomLanguageSpec` regex separators | Must | Function definitions, control flow blocks. Note: Bash may be a built-in Tree-sitter language -- validate and use custom only if needed |
| REQ-04 | File patterns added to `IndexingConfig.include_patterns` | Must | `*.tf`, `*.hcl`, `*.tfvars`, `Dockerfile`, `Dockerfile.*`, `Containerfile`, `*.sh`, `*.bash` |
| REQ-05 | Correct language routing (extension/filename to language spec) | Must | Handle extensionless Dockerfile via filename-based detection |
| REQ-06 | Non-DevOps files unaffected by custom language additions | Must | Built-in Tree-sitter languages continue working identically |

### Metadata Extraction

| ID | Requirement | Priority | Notes |
|----|------------|----------|-------|
| REQ-07 | HCL block type extraction (resource, data, module, etc.) | Must | Regex on chunk text, 12 known top-level block types |
| REQ-08 | HCL resource hierarchy (e.g., `resource.aws_s3_bucket.data`) | Should | `block_type.label1.label2` format from block declarations |
| REQ-09 | Dockerfile instruction type extraction (FROM, RUN, COPY, etc.) | Must | First keyword of instruction |
| REQ-10 | Dockerfile stage name for FROM instructions (e.g., `stage:builder`) | Should | FROM...AS name extraction. Non-FROM instructions get empty hierarchy in v1.2 |
| REQ-11 | Bash function name extraction (e.g., `function:deploy_app`) | Should | Both `function name() {}` and `function name {}` syntax |
| REQ-12 | Metadata extraction as CocoIndex op function returning `DevOpsMetadata` dataclass | Must | Fields: `block_type`, `hierarchy`, `language_id` -- 3 new TEXT columns |
| REQ-13 | Empty strings (not NULLs) for non-DevOps files and missing metadata | Must | Simplifies SQL, consistent pattern |

### Flow and Schema Integration

| ID | Requirement | Priority | Notes |
|----|------------|----------|-------|
| REQ-14 | Pass `custom_languages` to `SplitRecursively` constructor in flow | Must | Extends existing `create_code_index_flow()` |
| REQ-15 | Add metadata extraction step after chunking in flow | Must | `extract_devops_metadata` runs for ALL files |
| REQ-16 | Three new TEXT columns in PostgreSQL chunks table | Must | `block_type`, `hierarchy`, `language_id` -- auto-created by CocoIndex schema inference |
| REQ-17 | Stable primary keys to prevent schema migration data loss | Must | Keep `["filename", "location"]` as primary keys |

### Search and Output Integration

| ID | Requirement | Priority | Notes |
|----|------------|----------|-------|
| REQ-18 | Extended `SearchResult` with `block_type`, `hierarchy`, `language_id` fields | Must | New fields in result dataclass |
| REQ-19 | SQL queries select new metadata columns | Must | `SELECT block_type, hierarchy, language_id` alongside existing columns |
| REQ-20 | New language filter values: `terraform`/`hcl`, `dockerfile`, `bash`/`shell` | Must | Extend `LANGUAGE_EXTENSIONS` mapping |
| REQ-21 | Dockerfile language filter via basename matching (no extension) | Must | `filename LIKE '%Dockerfile%' OR filename LIKE '%Containerfile%'` |
| REQ-22 | Metadata displayed in JSON output | Must | Include `block_type`, `hierarchy`, `language_id` in JSON results |
| REQ-23 | Metadata displayed in pretty output | Must | Show block type and hierarchy annotation in formatted results |
| REQ-24 | MCP server includes metadata in `search_code` response | Must | Calling LLMs need structured metadata for synthesis |
| REQ-25 | Graceful degradation for pre-v1.2 indexes | Should | Try/except fallback when metadata columns don't exist |
| REQ-26 | Syntax highlighting for HCL, Dockerfile, Bash in pretty output | Should | Add to `EXTENSION_LANG_MAP` in formatter |

## Deferred to v1.3+

| ID | Feature | Reason |
|----|---------|--------|
| DEF-01 | Dockerfile stage tracking for non-FROM instructions | Requires two-pass file-level processing |
| DEF-02 | Block type search filter (`--block-type`) | Validate demand first |
| DEF-03 | Hierarchy search filter (`--hierarchy`) | Power user feature, validate demand first |
| DEF-04 | Terraform provider inference (aws_, azurerm_ prefix heuristic) | Nice but not essential |
| DEF-05 | Bash script purpose annotation (path-based heuristics) | Heuristic reliability uncertain |

## Anti-Features (Deliberately Not Building)

- Terraform plan/state integration, module resolution
- Dockerfile build graph analysis, linting integration
- Bash execution analysis, shell dialect detection
- Custom Tree-sitter grammar shipping
- Secrets detection in DevOps files
- HCL1 support (deprecated since Terraform 0.12)

## Constraints

- **Zero new dependencies** -- CocoIndex `custom_languages` + Python stdlib `re` only
- **Regex-based approach** -- no external parsers. Upgrade path to `python-hcl2` (MIT) and `dockerfile-parse` (BSD) exists if needed
- **Single flow architecture** -- DevOps files go through the same pipeline as programming language files
- **Additive schema only** -- no changes to existing columns or primary keys

## Success Criteria

1. `cocosearch index` on a Terraform repo produces chunks at block boundaries with correct metadata
2. `cocosearch index` on a repo with Dockerfiles produces instruction-level chunks with stage context
3. `cocosearch index` on a mixed repo (Python + Terraform + Docker) works seamlessly in a single index
4. `cocosearch search "S3 bucket" --lang terraform --pretty` returns results with `block_type=resource` and `hierarchy=resource.aws_s3_bucket.*`
5. MCP `search_code` returns metadata fields usable by calling LLMs
6. Pre-v1.2 indexes continue to work (search returns results without metadata)

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| REQ-01 | Phase 1 | Complete |
| REQ-02 | Phase 1 | Complete |
| REQ-03 | Phase 1 | Complete |
| REQ-04 | Phase 1 | Complete |
| REQ-05 | Phase 1 | Complete |
| REQ-06 | Phase 1 | Complete |
| REQ-07 | Phase 2 | Complete |
| REQ-08 | Phase 2 | Complete |
| REQ-09 | Phase 2 | Complete |
| REQ-10 | Phase 2 | Complete |
| REQ-11 | Phase 2 | Complete |
| REQ-12 | Phase 2 | Complete |
| REQ-13 | Phase 2 | Complete |
| REQ-14 | Phase 3 | Complete |
| REQ-15 | Phase 3 | Complete |
| REQ-16 | Phase 3 | Complete |
| REQ-17 | Phase 3 | Complete |
| REQ-18 | Phase 4 | Pending |
| REQ-19 | Phase 4 | Pending |
| REQ-20 | Phase 4 | Pending |
| REQ-21 | Phase 4 | Pending |
| REQ-22 | Phase 4 | Pending |
| REQ-23 | Phase 4 | Pending |
| REQ-24 | Phase 4 | Pending |
| REQ-25 | Phase 4 | Pending |
| REQ-26 | Phase 4 | Pending |

---
*Scoped: 2026-01-27*
*Roadmapped: 2026-01-27*
