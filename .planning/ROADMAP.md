# Roadmap: CocoSearch

## Milestones

- v1.0 MVP -- Phases 1-4 (shipped 2026-01-25)
- v1.1 Docs & Tests -- Phases 5-7 (shipped 2026-01-26)
- v1.2 DevOps Language Support -- Phases 8-10, 4-soi (shipped 2026-01-27)
- v1.3 Docker Integration Tests -- Phases 11-14 (shipped 2026-01-30)
- v1.4 Dogfooding Infrastructure -- Phases 15-18 (shipped 2026-01-31)
- v1.5 Configuration & Architecture Polish -- Phases 19-22 (shipped 2026-02-01)
- v1.6 All-in-One Docker & Auto-Detect -- Phases 23-26 (shipped 2026-02-02)
- v1.7 Search Enhancement -- Phases 27-32 (shipped 2026-02-03)
- v1.8 Polish & Observability -- Phases 33-37 (in progress)

## Phases

<details>
<summary>v1.0-v1.7 (Phases 1-32) -- SHIPPED</summary>

See `.planning/milestones/` for archived roadmaps:
- v1.7-ROADMAP.md -- Phases 27-32, 21 plans (shipped 2026-02-03)
- v1.6-ROADMAP.md -- Phases 23-26, 11 plans (shipped 2026-02-02)
- v1.5-ROADMAP.md -- Phases 19-22, 11 plans (shipped 2026-02-01)

See project history for earlier milestones:
- v1.0-v1.4: 18 phases, 47 plans across 5 milestones

**Total:** 32 phases, 90 plans completed.

</details>

### v1.8 Polish & Observability (In Progress)

**Milestone Goal:** Complete deferred v1.7 features, expand symbol coverage to 10 languages, add observability dashboard with CLI/terminal/web interfaces, create developer skills for Claude Code and OpenCode, and rebrand documentation.

#### Phase 33: Deferred v1.7 Foundation
**Goal**: Complete search features deferred from v1.7 -- hybrid+symbol combination, nested symbols, query caching
**Depends on**: Phase 32 (v1.7 complete)
**Requirements**: REQ-001, REQ-002, REQ-003, REQ-004
**Success Criteria** (what must be TRUE):
  1. User can combine hybrid search with symbol filters (--hybrid --symbol-type function works)
  2. Symbol names display with parent context (ClassName.method_name format)
  3. Repeated identical queries return cached results (sub-10ms response)
  4. Semantic cache hits similar queries (cosine >0.95 reuses embeddings)
  5. Cache invalidates automatically on reindex (--no-cache bypasses)
**Plans**: 3 plans

Plans:
- [ ] 33-01-PLAN.md -- Hybrid + symbol filter combination (pass WHERE to both vector/keyword before RRF)
- [ ] 33-02-PLAN.md -- Nested symbol display (add symbol_name/type/signature to JSON and pretty output)
- [ ] 33-03-PLAN.md -- Query caching (exact hash + semantic similarity, invalidate on reindex, --no-cache flag)

#### Phase 34: Symbol Extraction Expansion
**Goal**: Extend symbol extraction from 5 to 10 languages with external query files
**Depends on**: Phase 33
**Requirements**: REQ-013, REQ-014, REQ-015, REQ-016, REQ-017, REQ-018
**Success Criteria** (what must be TRUE):
  1. Java files indexed with functions, classes, interfaces, enums as symbols
  2. C files indexed with functions, structs, enums, typedefs as symbols
  3. C++ files indexed with functions, classes, structs, namespaces as symbols
  4. Ruby files indexed with functions, classes, modules as symbols
  5. PHP files indexed with functions, classes, interfaces, traits as symbols
  6. Symbol extraction uses external .scm query files (not hardcoded Python)
**Plans**: TBD

Plans:
- [ ] 34-01: Query file architecture + tree-sitter-language-pack migration
- [ ] 34-02: Java + Ruby symbol extraction
- [ ] 34-03: C + C++ symbol extraction
- [ ] 34-04: PHP + additional types

#### Phase 35: Stats Dashboard
**Goal**: Provide index observability via CLI, terminal dashboard, and web UI
**Depends on**: Phase 34
**Requirements**: REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-010, REQ-011, REQ-012
**Success Criteria** (what must be TRUE):
  1. `cocosearch stats` shows health metrics (files, chunks, size, last update)
  2. Stats include per-language breakdown and symbol type counts
  3. `--json` flag outputs machine-readable stats for automation
  4. Stats warn if index is stale (>7 days since last update)
  5. HTTP API serves stats at /api/stats endpoint
  6. Terminal dashboard shows live stats with Unicode graphs
  7. Web UI accessible via browser at /dashboard
**Plans**: TBD

Plans:
- [ ] 35-01: Stats CLI enhancement (metrics, language, symbols)
- [ ] 35-02: HTTP API + terminal dashboard
- [ ] 35-03: Web UI dashboard

#### Phase 36: Developer Skills
**Goal**: Create skills for Claude Code and OpenCode with installation and routing guidance
**Depends on**: Phase 35
**Requirements**: REQ-019, REQ-020, REQ-021, REQ-022
**Success Criteria** (what must be TRUE):
  1. Claude Code SKILL.md exists with setup instructions and MCP configuration
  2. Claude Code skill includes routing guidance (when CocoSearch vs grep/find)
  3. OpenCode SKILL.md exists with setup instructions
  4. OpenCode skill includes routing guidance for code exploration workflows
**Plans**: TBD

Plans:
- [ ] 36-01: Claude Code skill (installation + routing)
- [ ] 36-02: OpenCode skill (installation + routing)

#### Phase 37: Documentation Rebrand
**Goal**: Update README to reflect CocoSearch's full capabilities beyond "semantic search"
**Depends on**: Phase 36
**Requirements**: REQ-023
**Success Criteria** (what must be TRUE):
  1. README positions CocoSearch as hybrid search + symbol filtering + context expansion tool
  2. README accurately describes all v1.8 features (caching, 10-language symbols, stats dashboard)
  3. Feature overview matches current capabilities (not just "semantic code search")
**Plans**: TBD

Plans:
- [ ] 37-01: README rebrand

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
| v1.7 Search Enhancement | 27-32 | 21 | Complete | 2026-02-03 |
| v1.8 Polish & Observability | 33-37 | 0/13 | In progress | - |

---
*Roadmap created: 2026-01-25*
*Last updated: 2026-02-03 after v1.8 roadmap created*
