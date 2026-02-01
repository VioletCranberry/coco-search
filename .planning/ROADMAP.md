# Roadmap: CocoSearch

## Milestones

- v1.0 MVP -- Phases 1-4 (shipped 2026-01-25)
- v1.1 Docs & Tests -- Phases 5-7 (shipped 2026-01-26)
- v1.2 DevOps Language Support -- Phases 8-10, 4-soi (shipped 2026-01-27)
- v1.3 Docker Integration Tests -- Phases 11-14 (shipped 2026-01-30)
- v1.4 Dogfooding Infrastructure -- Phases 15-18 (shipped 2026-01-31)
- v1.5 Configuration & Architecture Polish -- Phases 19-22 (shipped 2026-02-01)
- v1.6 All-in-One Docker & Auto-Detect -- Phases 23-26 (in progress)

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

#### Phase 24: Container Foundation
**Goal**: All-in-one Docker container with PostgreSQL, Ollama, and MCP server under process supervision
**Depends on**: Phase 23
**Requirements**: DOCK-01, DOCK-02, DOCK-03, DOCK-04, DOCK-05, DOCK-06, ORCH-01, ORCH-02, ORCH-03, ORCH-04
**Success Criteria** (what must be TRUE):
  1. User can start entire stack with single `docker run cocosearch` command
  2. Container starts services in correct order (PostgreSQL ready before MCP attempts connection)
  3. User can mount local codebase via `-v /path/to/code:/mnt/repos:ro` and index it
  4. User can persist data across container restarts via `-v cocosearch-data:/data`
  5. Container shuts down cleanly on `docker stop` without data corruption
**Plans**: TBD

Plans:
- [ ] 24-01: TBD

#### Phase 25: Auto-Detect Feature
**Goal**: MCP automatically detects project context from working directory
**Depends on**: Phase 23 (transport layer, not container)
**Requirements**: AUTO-01, AUTO-02, AUTO-03, AUTO-04, AUTO-05, AUTO-06
**Success Criteria** (what must be TRUE):
  1. User can use MCP tools without specifying index_name when cwd is in indexed project
  2. System uses priority chain: cocosearch.yaml indexName > git repo name > directory name
  3. User is warned when same index name maps to different paths (collision)
  4. User is prompted to set explicit indexName in cocosearch.yaml on collision
  5. User is prompted to run index command when auto-detected project has no index
**Plans**: TBD

Plans:
- [ ] 25-01: TBD

#### Phase 26: Documentation & Polish
**Goal**: Complete documentation for Docker deployment and MCP client configuration
**Depends on**: Phase 24, Phase 25
**Requirements**: DOCS-01, DOCS-02, DOCS-03, DOCS-04, DOCS-05
**Success Criteria** (what must be TRUE):
  1. Docker quick start guide exists with copy-paste `docker run` examples
  2. Claude Code configuration example exists showing stdio transport setup
  3. Claude Desktop configuration example exists showing SSE/HTTP transport setup
  4. Volume mount and data persistence documentation covers common scenarios
  5. Troubleshooting guide covers container startup failures and connectivity issues
**Plans**: TBD

Plans:
- [ ] 26-01: TBD

## Progress

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1.0 MVP | 1-4 | 11 | Complete | 2026-01-25 |
| v1.1 Docs & Tests | 5-7 | 11 | Complete | 2026-01-26 |
| v1.2 DevOps | 8-10, 4-soi | 6 | Complete | 2026-01-27 |
| v1.3 Integration Tests | 11-14 | 11 | Complete | 2026-01-30 |
| v1.4 Dogfooding | 15-18 | 7 | Complete | 2026-01-31 |
| v1.5 Config & Architecture | 19-22 | 11 | Complete | 2026-02-01 |
| v1.6 Docker & Auto-Detect | 23-26 | 2+ | In progress | - |

---
*Roadmap created: 2026-01-25*
*Last updated: 2026-02-01 after Phase 23 complete*
