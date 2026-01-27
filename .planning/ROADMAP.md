# Roadmap: v1.2 DevOps Language Support

**Milestone:** v1.2
**Phases:** 4
**Depth:** Standard
**Coverage:** 26/26 requirements mapped

## Overview

CocoSearch v1.2 adds language-aware chunking and rich metadata extraction for HCL (Terraform), Dockerfile, and Bash/Shell files. The milestone extends the existing single-flow pipeline with zero new runtime dependencies, using CocoIndex's `custom_languages` API and Python stdlib `re`. Four phases follow a strict dependency chain: correct chunk boundaries enable metadata extraction, which feeds into the flow/schema, which populates data for search to surface.

## Phases

### Phase 1: Custom Language Definitions and File Routing

**Goal:** DevOps files are chunked at structurally meaningful boundaries, not plain-text splits.

**Dependencies:** None (foundation phase).

**Plans:** 2 plans

Plans:
- [x] 08-01-PLAN.md -- Language definitions (HCL, Dockerfile, Bash CustomLanguageSpecs) and DevOps file patterns
- [x] 08-02-PLAN.md -- Language routing (extract_language) and flow integration (custom_languages wiring)

**Requirements:**
- REQ-01: HCL block-level chunking via `CustomLanguageSpec` regex separators
- REQ-02: Dockerfile instruction-level chunking via `CustomLanguageSpec` regex separators
- REQ-03: Bash function-level chunking via `CustomLanguageSpec` regex separators
- REQ-04: File patterns added to `IndexingConfig.include_patterns`
- REQ-05: Correct language routing (extension/filename to language spec)
- REQ-06: Non-DevOps files unaffected by custom language additions

**Success Criteria:**
1. A Terraform file with nested resources, heredocs, and dynamic blocks produces chunks that start at top-level block boundaries (`resource`, `data`, `module`, etc.) -- not mid-block
2. A multi-stage Dockerfile produces chunks split at FROM and major instruction boundaries, with stage transitions preserved as chunk starts
3. A Bash script with function definitions produces chunks split at function boundaries, not inside heredocs or nested quoting
4. Files matching `*.tf`, `*.hcl`, `*.tfvars`, `Dockerfile`, `Dockerfile.*`, `Containerfile`, `*.sh`, `*.bash` are detected and routed to their custom language specs
5. Existing Python, JavaScript, and other Tree-sitter-supported files continue to chunk identically to v1.1

**Research flag:** YES -- Bash custom vs. built-in Tree-sitter name collision behavior, optimal chunk_size for DevOps files, `fancy-regex` separator pattern validation with real files. The Bash built-in status contradiction (FEATURES.md vs. STACK.md) must be resolved by runtime testing.

**Key pitfalls:** Regex splits mid-block in HCL (Pitfall 1), HCL heredoc false splits (Pitfall 2), Bash heredoc/quoting edge cases (Pitfall 5), chunk size too small for DevOps files (Pitfall 7), language detection conflicts (Pitfall 10), extensionless Dockerfile detection (Pitfall 13), inconsistent file patterns (Pitfall 11).

**New files:** `src/cocosearch/indexer/languages.py`
**Modified files:** `src/cocosearch/indexer/config.py`

---

### Phase 2: Metadata Extraction

**Goal:** Every DevOps chunk carries structured metadata identifying what it is (block type, hierarchy, language).

**Dependencies:** Phase 1 (chunk boundaries must be correct for metadata regex to match block starts).

**Plans:** 1 plan

Plans:
- [x] 09-01-PLAN.md -- DevOpsMetadata dataclass, per-language extractors (HCL, Dockerfile, Bash), dispatch function, and comprehensive tests

**Requirements:**
- REQ-07: HCL block type extraction (resource, data, module, etc.)
- REQ-08: HCL resource hierarchy (e.g., `resource.aws_s3_bucket.data`)
- REQ-09: Dockerfile instruction type extraction (FROM, RUN, COPY, etc.)
- REQ-10: Dockerfile stage name for FROM instructions (e.g., `stage:builder`)
- REQ-11: Bash function name extraction (e.g., `function:deploy_app`)
- REQ-12: Metadata extraction as CocoIndex op function returning `DevOpsMetadata` dataclass
- REQ-13: Empty strings (not NULLs) for non-DevOps files and missing metadata

**Success Criteria:**
1. An HCL chunk starting with `resource "aws_s3_bucket" "data"` produces metadata `block_type=resource`, `hierarchy=resource.aws_s3_bucket.data`, `language_id=hcl`
2. A Dockerfile chunk starting with `FROM golang:1.21 AS builder` produces metadata `block_type=FROM`, `hierarchy=stage:builder`, `language_id=dockerfile`
3. A Bash chunk starting with `deploy_app() {` produces metadata `block_type=function`, `hierarchy=function:deploy_app`, `language_id=bash`
4. A Python file chunk produces metadata `block_type=""`, `hierarchy=""`, `language_id=""` (empty strings, not NULLs)
5. Comments containing keywords like `# This resource was replaced` do not produce false-positive metadata extraction when they appear mid-chunk

**Research flag:** No -- well-documented regex patterns, pure Python logic, fully unit-testable without CocoIndex API uncertainties.

**Key pitfalls:** Metadata false positives from comments/strings (Pitfall 3), Dockerfile stage context limitations (Pitfall 6), extraction performance overhead (Pitfall 8).

**New files:** `src/cocosearch/indexer/metadata.py`
**Modified files:** None (standalone module until Phase 3 wires it in).

---

### Phase 3: Flow Integration and Schema

**Goal:** The indexing pipeline produces DevOps-aware chunks with metadata stored in PostgreSQL, without breaking existing indexes.

**Dependencies:** Phase 1 (language definitions) + Phase 2 (metadata extraction).

**Plans:** 1 plan

Plans:
- [x] 10-01-PLAN.md -- Wire metadata extraction into flow pipeline and add metadata fields to collector

**Requirements:**
- REQ-14: Pass `custom_languages` to `SplitRecursively` constructor in flow
- REQ-15: Add metadata extraction step after chunking in flow
- REQ-16: Three new TEXT columns in PostgreSQL chunks table
- REQ-17: Stable primary keys to prevent schema migration data loss

**Success Criteria:**
1. Running `cocosearch index` on a directory containing Terraform, Dockerfile, and Bash files produces chunks with populated `block_type`, `hierarchy`, and `language_id` columns in PostgreSQL
2. Running `cocosearch index` on a pure Python codebase still works identically to v1.1 -- same chunks, same embeddings, plus three empty-string metadata columns
3. The PostgreSQL table retains `["filename", "location"]` as primary keys -- schema migration does not drop and recreate existing tables
4. Re-indexing a mixed codebase (Python + Terraform + Docker) completes successfully with all file types in a single index

**Research flag:** YES -- CocoIndex schema migration behavior when adding non-primary-key columns, `@cocoindex.op.function()` dataclass-to-column mapping verification, `collector.collect()` with struct field access syntax.

**Key pitfalls:** Schema migration destroys existing indexes (Pitfall 4), metadata running for all files must return empty strings (Pitfall pattern from Architecture).

**New files:** None.
**Modified files:** `src/cocosearch/indexer/flow.py`

---

### Phase 4: Search and Output Integration

**Goal:** Users and calling LLMs see DevOps metadata in search results and can filter by DevOps language.

**Dependencies:** Phase 3 (metadata must be populated in PostgreSQL before search can surface it).

**Plans:** 2 plans

Plans:
- [x] 04-01-PLAN.md -- Search query layer: extended SearchResult, metadata SQL, DevOps language filter, graceful degradation
- [x] 04-02-PLAN.md -- Output integration: JSON/pretty formatters with metadata annotations, MCP response with metadata fields

**Requirements:**
- REQ-18: Extended `SearchResult` with `block_type`, `hierarchy`, `language_id` fields
- REQ-19: SQL queries select new metadata columns
- REQ-20: New language filter values: `terraform`/`hcl`, `dockerfile`, `bash`/`shell`
- REQ-21: Dockerfile language filter via basename matching (no extension)
- REQ-22: Metadata displayed in JSON output
- REQ-23: Metadata displayed in pretty output
- REQ-24: MCP server includes metadata in `search_code` response
- REQ-25: Graceful degradation for pre-v1.2 indexes
- REQ-26: Syntax highlighting for HCL, Dockerfile, Bash in pretty output

**Success Criteria:**
1. `cocosearch search "S3 bucket" --lang terraform --pretty` returns results with block type and hierarchy annotations (e.g., `[hcl] resource.aws_s3_bucket.data`)
2. `cocosearch search "build stage" --lang dockerfile` returns Dockerfile results filtered by basename matching, not extension
3. JSON output includes `block_type`, `hierarchy`, and `language_id` fields for DevOps files, and empty strings for non-DevOps files
4. MCP `search_code` response includes metadata fields usable by calling LLMs for synthesis context
5. Searching a pre-v1.2 index (without metadata columns) returns results without metadata instead of crashing

**Research flag:** No -- standard SQL SELECT extension, dataclass field additions, formatter updates. All patterns exist in the current codebase.

**Key pitfalls:** pgvector post-filter returning too few results with metadata filters (Pitfall 9), Dockerfile basename-based language filter requiring SQL LIKE pattern (Pitfall from Architecture).

**New files:** None.
**Modified files:** `src/cocosearch/search/query.py`, `src/cocosearch/search/formatter.py`, `src/cocosearch/mcp/server.py`

---

## Coverage

| Requirement | Phase | Category |
|-------------|-------|----------|
| REQ-01 | Phase 1 | Chunking |
| REQ-02 | Phase 1 | Chunking |
| REQ-03 | Phase 1 | Chunking |
| REQ-04 | Phase 1 | Chunking |
| REQ-05 | Phase 1 | Chunking |
| REQ-06 | Phase 1 | Chunking |
| REQ-07 | Phase 2 | Metadata |
| REQ-08 | Phase 2 | Metadata |
| REQ-09 | Phase 2 | Metadata |
| REQ-10 | Phase 2 | Metadata |
| REQ-11 | Phase 2 | Metadata |
| REQ-12 | Phase 2 | Metadata |
| REQ-13 | Phase 2 | Metadata |
| REQ-14 | Phase 3 | Flow/Schema |
| REQ-15 | Phase 3 | Flow/Schema |
| REQ-16 | Phase 3 | Flow/Schema |
| REQ-17 | Phase 3 | Flow/Schema |
| REQ-18 | Phase 4 | Search/Output |
| REQ-19 | Phase 4 | Search/Output |
| REQ-20 | Phase 4 | Search/Output |
| REQ-21 | Phase 4 | Search/Output |
| REQ-22 | Phase 4 | Search/Output |
| REQ-23 | Phase 4 | Search/Output |
| REQ-24 | Phase 4 | Search/Output |
| REQ-25 | Phase 4 | Search/Output |
| REQ-26 | Phase 4 | Search/Output |

**Mapped:** 26/26 -- no orphaned requirements.

## Progress

| Phase | Name | Requirements | Status |
|-------|------|--------------|--------|
| 1 | Custom Language Definitions and File Routing | 6 | ✓ Complete (2/2 plans) |
| 2 | Metadata Extraction | 7 | ✓ Complete (1/1 plans) |
| 3 | Flow Integration and Schema | 4 | ✓ Verified (1/1 plans) |
| 4 | Search and Output Integration | 9 | ✓ Verified (2/2 plans) |

---
*Created: 2026-01-27*
*Milestone: v1.2 DevOps Language Support*
