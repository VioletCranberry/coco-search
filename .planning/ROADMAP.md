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
- v1.8 Polish & Observability -- Phases 33-37 (shipped 2026-02-05)
- v1.9 Multi-Repo & Polish -- Phases 38-42 (in progress)

## Phases

<details>
<summary>v1.0-v1.8 (Phases 1-37) -- SHIPPED</summary>

See `.planning/milestones/` for archived roadmaps:
- v1.8-ROADMAP.md -- Phases 33-37, 13 plans (shipped 2026-02-05)
- v1.7-ROADMAP.md -- Phases 27-32, 21 plans (shipped 2026-02-03)
- v1.6-ROADMAP.md -- Phases 23-26, 11 plans (shipped 2026-02-02)
- v1.5-ROADMAP.md -- Phases 19-22, 11 plans (shipped 2026-02-01)

See project history for earlier milestones:
- v1.0-v1.4: 18 phases, 47 plans across 5 milestones

**Total:** 37 phases, 103 plans completed.

</details>

### v1.9 Multi-Repo & Polish (In Progress)

**Milestone Goal:** Enable single MCP registration for all projects, clean up technical debt, and document workflow patterns for users.

#### Phase 38: Multi-Repo MCP Support
**Goal**: Users can register CocoSearch once and use it across all their projects
**Depends on**: Phase 37 (v1.8 complete)
**Requirements**: MCP-01, MCP-02, MCP-03, MCP-04, MCP-05
**Success Criteria** (what must be TRUE):
  1. User can add CocoSearch to Claude Code with user scope and search any project's codebase by opening that project
  2. User can add CocoSearch to Claude Desktop with user scope and search any project
  3. When user searches an unindexed project, they receive a prompt to index it (not silent failure or cryptic error)
  4. When user searches a stale index, they receive a warning about index freshness
  5. Documentation clearly shows the single-registration pattern with `--project-from-cwd` flag
**Plans**: 2 plans

Plans:
- [ ] 38-01-PLAN.md — Add --project-from-cwd flag and staleness warnings
- [ ] 38-02-PLAN.md — Document user-scope MCP registration patterns

#### Phase 39: Test Fixes
**Goal**: Test suite passes reliably with correct signature format expectations
**Depends on**: Phase 38
**Requirements**: TEST-01
**Success Criteria** (what must be TRUE):
  1. All existing tests pass without signature format assertion failures
  2. Signature format tests match actual implementation behavior
**Plans**: TBD

Plans:
- [ ] 39-01: TBD

#### Phase 40: Code Cleanup
**Goal**: Remove deprecated code and migration logic safely without breaking functionality
**Depends on**: Phase 39 (tests must pass first)
**Requirements**: CLEAN-01, CLEAN-02, CLEAN-03, CLEAN-04
**Success Criteria** (what must be TRUE):
  1. DB migrations module removed from codebase (single-user tool, no backwards compat needed)
  2. All deprecated functions removed with no remaining references
  3. v1.2 graceful degradation code removed (old index compat no longer supported)
  4. All tests updated and passing after each cleanup step
  5. Codebase is cleaner with reduced LOC count
**Plans**: TBD

Plans:
- [ ] 40-01: TBD

#### Phase 41: Workflow Skills
**Goal**: Users have multi-step workflow guidance for common tasks
**Depends on**: Phase 38 (multi-repo enables workflows)
**Requirements**: DOC-01, DOC-02, DOC-03
**Success Criteria** (what must be TRUE):
  1. Onboarding workflow skill guides users through understanding a new codebase step-by-step
  2. Debugging workflow skill guides users through finding root cause of issues
  3. Refactoring workflow skill guides users through safe code changes with impact analysis
  4. Skills follow consistent multi-step format with clear when-to-use guidance
**Plans**: TBD

Plans:
- [ ] 41-01: TBD

#### Phase 42: Technical Documentation
**Goal**: Users and contributors understand retrieval logic and MCP tool usage
**Depends on**: Phase 40 (document final implementation, not interim states)
**Requirements**: DOC-04, DOC-05
**Success Criteria** (what must be TRUE):
  1. Retrieval logic documentation explains hybrid search, RRF fusion, symbol filtering, and query caching
  2. MCP tools reference provides complete examples for all tools with parameter descriptions
  3. Documentation is accurate to current implementation (post-cleanup)
**Plans**: TBD

Plans:
- [ ] 42-01: TBD

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
| v1.8 Polish & Observability | 33-37 | 13 | Complete | 2026-02-05 |
| v1.9 Multi-Repo & Polish | 38-42 | TBD | In progress | - |

---
*Roadmap created: 2026-01-25*
*Last updated: 2026-02-05 — v1.9 roadmap created*
