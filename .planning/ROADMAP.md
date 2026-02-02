# Roadmap: CocoSearch

## Milestones

- v1.0 MVP -- Phases 1-4 (shipped 2026-01-25)
- v1.1 Docs & Tests -- Phases 5-7 (shipped 2026-01-26)
- v1.2 DevOps Language Support -- Phases 8-10, 4-soi (shipped 2026-01-27)
- v1.3 Docker Integration Tests -- Phases 11-14 (shipped 2026-01-30)
- v1.4 Dogfooding Infrastructure -- Phases 15-18 (shipped 2026-01-31)
- v1.5 Configuration & Architecture Polish -- Phases 19-22 (shipped 2026-02-01)
- v1.6 All-in-One Docker & Auto-Detect -- Phases 23-26 (shipped 2026-02-02)

## Phases

<details>
<summary>v1.0-v1.5 (Phases 1-22) -- SHIPPED</summary>

See `.planning/milestones/` for archived roadmaps:
- v1.5-ROADMAP.md -- Phases 19-22, 11 plans (shipped 2026-02-01)

See project history for earlier milestones:
- v1.0-v1.4: 18 phases, 47 plans across 5 milestones

**Total:** 22 phases, 58 plans completed.

</details>

### v1.6 All-in-One Docker & Auto-Detect (In Progress)

**Milestone Goal:** Single `docker run` experience with all services bundled, plus auto-detect project from working directory.

#### Phase 23: MCP Transport Integration ✓
**Goal**: MCP server supports multiple transport protocols selectable at runtime
**Depends on**: Phase 22 (v1.5 complete)
**Requirements**: TRNS-01, TRNS-02, TRNS-03, TRNS-04
**Status**: Complete (2026-02-01)
**Plans**: 2 plans

Plans:
- [x] 23-01-PLAN.md - Multi-transport support in server and CLI
- [x] 23-02-PLAN.md - Unit tests for transport selection

#### Phase 24: Container Foundation ✓
**Goal**: All-in-one Docker container with PostgreSQL, Ollama, and MCP server under process supervision
**Depends on**: Phase 23
**Requirements**: DOCK-01, DOCK-02, DOCK-03, DOCK-04, DOCK-05, DOCK-06, ORCH-01, ORCH-02, ORCH-03, ORCH-04
**Status**: Complete (2026-02-02)
**Plans**: 4 plans

Plans:
- [x] 24-01-PLAN.md - Multi-stage Dockerfile with s6-overlay, PostgreSQL, Ollama, Python app
- [x] 24-02-PLAN.md - s6-overlay service definitions with dependency ordering
- [x] 24-03-PLAN.md - Health check and ready signal infrastructure
- [x] 24-04-PLAN.md - End-to-end verification and .dockerignore

#### Phase 25: Auto-Detect Feature ✓
**Goal**: MCP automatically detects project context from working directory
**Depends on**: Phase 23 (transport layer, not container)
**Requirements**: AUTO-01, AUTO-02, AUTO-03, AUTO-04, AUTO-05, AUTO-06
**Status**: Complete (2026-02-02)
**Plans**: 4 plans

Plans:
- [x] 25-01-PLAN.md - Context detection and metadata storage foundation
- [x] 25-02-PLAN.md - MCP auto-detect integration
- [x] 25-03-PLAN.md - CLI path registration and cleanup
- [x] 25-04-PLAN.md - Unit tests for auto-detect feature

#### Phase 26: Documentation & Polish ✓
**Goal**: Complete documentation for Docker deployment and MCP client configuration
**Depends on**: Phase 24, Phase 25
**Requirements**: DOCS-01, DOCS-02, DOCS-03, DOCS-04, DOCS-05
**Status**: Complete (2026-02-02)
**Plans**: 1 plan

Plans:
- [x] 26-01-PLAN.md - Docker quick start, MCP client configuration, and troubleshooting documentation

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

---
*Roadmap created: 2026-01-25*
*Last updated: 2026-02-02 after Phase 26 complete*
