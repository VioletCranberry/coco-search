# Roadmap: CocoSearch

## Milestones

- v1.0 MVP -- Phases 1-4 (shipped 2026-01-25)
- v1.1 Docs & Tests -- Phases 5-7 (shipped 2026-01-26)
- v1.2 DevOps Language Support -- Phases 8-10, 4-soi (shipped 2026-01-27)
- v1.3 Docker Integration Tests -- Phases 11-14 (shipped 2026-01-30)
- v1.4 Dogfooding Infrastructure -- Phases 15-18 (shipped 2026-01-31)
- v1.5 Configuration & Architecture Polish -- Phases 19-22 (shipped 2026-02-01)
- v1.6 All-in-One Docker & Auto-Detect -- Phases 23-26 (shipped 2026-02-02)
- v1.7 Search Enhancement -- Phases 27-32 (in progress)

## Phases

<details>
<summary>v1.0-v1.6 (Phases 1-26) -- SHIPPED</summary>

See `.planning/milestones/` for archived roadmaps:
- v1.6-ROADMAP.md -- Phases 23-26, 11 plans (shipped 2026-02-02)
- v1.5-ROADMAP.md -- Phases 19-22, 11 plans (shipped 2026-02-01)

See project history for earlier milestones:
- v1.0-v1.4: 18 phases, 47 plans across 5 milestones

**Total:** 26 phases, 69 plans completed.

</details>

### v1.7 Search Enhancement (In Progress)

**Milestone Goal:** Improve search quality with hybrid search (vector + keyword), context expansion, symbol-aware indexing, and full language coverage (30+ languages).

#### Phase 27: Hybrid Search Foundation

**Goal:** Enable hybrid search infrastructure with schema changes and keyword indexing

**Depends on:** Nothing (starts v1.7 milestone)

**Requirements:** HYBR-05, HYBR-06, HYBR-07

**Success Criteria** (what must be TRUE):
  1. Database schema includes content_text and content_tsv columns for keyword search
  2. GIN index created on content_tsv for keyword search performance
  3. Existing indexes (pre-v1.7) continue to work without errors (vector-only mode)
  4. New indexes automatically populate content_text and content_tsv during indexing

**Plans:** 3 plans

Plans:
- [x] 27-01-PLAN.md — Add content_text field to indexing flow
- [x] 27-02-PLAN.md — Add graceful degradation for hybrid search columns
- [x] 27-03-PLAN.md — Add tsvector generation and GIN index support

#### Phase 28: Hybrid Search Query

**Goal:** Users can search using both vector similarity and keyword matching with RRF fusion

**Depends on:** Phase 27

**Requirements:** HYBR-01, HYBR-02, HYBR-03, HYBR-04

**Success Criteria** (what must be TRUE):
  1. User can search with --hybrid flag to enable combined vector+keyword search
  2. MCP clients can pass use_hybrid_search parameter to enable hybrid mode
  3. Identifier patterns (camelCase, snake_case) automatically trigger hybrid search
  4. Search results show relevance from both semantic meaning and literal keyword matches

**Plans:** TBD

Plans:
- [ ] TBD

#### Phase 29: Symbol-Aware Indexing

**Goal:** Index function and class definitions as first-class entities with metadata

**Depends on:** Nothing (parallel to Phases 27-28)

**Requirements:** SYMB-01, SYMB-02, SYMB-03, SYMB-10

**Success Criteria** (what must be TRUE):
  1. Database schema includes symbol_type, symbol_name, symbol_signature columns
  2. Python functions and classes are extracted and stored with symbol metadata during indexing
  3. Existing indexes (pre-v1.7) continue to work without symbol filtering capability
  4. Symbol extraction handles parse errors gracefully without corrupting index

**Plans:** TBD

Plans:
- [ ] TBD

#### Phase 30: Symbol Search Filters + Language Expansion

**Goal:** Users can filter searches by symbol type and name across top 5 languages

**Depends on:** Phase 29

**Requirements:** SYMB-04, SYMB-05, SYMB-06, SYMB-07, SYMB-08, SYMB-09

**Success Criteria** (what must be TRUE):
  1. User can filter search with --symbol-type function/class/method flags
  2. User can filter search with --symbol-name pattern to match specific symbols
  3. MCP clients can pass symbol_type and symbol_name parameters for filtering
  4. Symbol extraction works for JavaScript, TypeScript, Go, Rust in addition to Python
  5. Function and class definitions rank higher than references in search results

**Plans:** TBD

Plans:
- [ ] TBD

#### Phase 31: Context Expansion Enhancement

**Goal:** Search results show surrounding code context with smart boundaries and performance optimization

**Depends on:** Nothing (parallel to Phases 29-30)

**Requirements:** CTXT-01, CTXT-02, CTXT-03, CTXT-04, CTXT-05, CTXT-06

**Success Criteria** (what must be TRUE):
  1. User can specify -A/-B/-C flags to show N lines before/after/around matches
  2. MCP clients can request context via context_before and context_after parameters
  3. Multiple results from the same file read the file once (batched I/O)
  4. Context boundaries expand to include enclosing function or class when appropriate
  5. Context appears in both JSON output and pretty-printed format

**Plans:** TBD

Plans:
- [ ] TBD

#### Phase 32: Full Language Coverage + Documentation

**Goal:** All 30+ CocoIndex languages enabled with comprehensive documentation

**Depends on:** Phases 28, 30, 31

**Requirements:** LANG-01, LANG-02, LANG-03, LANG-04

**Success Criteria** (what must be TRUE):
  1. All CocoIndex built-in languages (YAML, JSON, Markdown, etc.) are indexed
  2. cocosearch stats command shows lines-per-language breakdown
  3. Documentation lists all supported languages with file extensions
  4. Hybrid search, symbol filtering, and context expansion are documented with examples

**Plans:** TBD

Plans:
- [ ] TBD

## Progress

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1.0 MVP | 1-4 | 11 | Complete | 2026-01-25 |
| v1.1 Docs & Tests | 5-7 | 11 | Complete | 2026-01-26 |
| v1.2 DevOps | 8-10, 4-soi | 6 | Complete | 2026-01-27 |
| v1.3 Integration Tests | 11-14 | 11 | Complete | 2026-01-30 |
| v1.4 Dogfooding | 15-18 | 7 | Complete | 2026-01-31 |
| v1.5 Config & Architecture | 19-22 | 11 | Complete | 2026-02-01 |
| v1.6 Docker & Auto-Detect | 23-26 | 11 | Complete | 2026-02-02 |
| v1.7 Search Enhancement | 27-32 | 6 | In progress | - |

---
*Roadmap created: 2026-01-25*
*Last updated: 2026-02-03 after Phase 27 completion*
