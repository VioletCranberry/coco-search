# Roadmap: CocoSearch v1.10

## Overview

v1.10 is a refinement milestone that standardizes credentials, simplifies the Docker image to infra-only, adds protocol-correct MCP Roots support, introduces parse failure tracking for observability, and updates documentation to reflect the new architecture. Five phases deliver these changes in dependency order: foundation fixes first, then infrastructure, protocol, observability, and documentation.

## Milestones

- v1.0-v1.9: See .planning/MILESTONES.md (shipped)
- v1.10 Infrastructure & Protocol: Phases 43-47 (in progress)

## Phases

- [ ] **Phase 43: Bug Fix & Credential Defaults** - Fix DevOps metadata bug and standardize database credentials for zero-config setup
- [ ] **Phase 44: Docker Image Simplification** - Strip CocoSearch from Docker image, making it infra-only (PostgreSQL+pgvector, Ollama+model)
- [ ] **Phase 45: MCP Protocol Enhancements** - Add Roots capability for protocol-correct project detection with HTTP query param fallback
- [ ] **Phase 46: Parse Failure Tracking** - Track and surface tree-sitter parse failures per language in stats output
- [ ] **Phase 47: Documentation Update** - Update all documentation for infra-only Docker model and new defaults

## Phase Details

### Phase 43: Bug Fix & Credential Defaults
**Goal**: Users can run `docker compose up && cocosearch index .` with zero environment variable configuration
**Depends on**: Nothing (first phase of milestone)
**Requirements**: FIX-01, INFRA-01, INFRA-02, INFRA-03
**Success Criteria** (what must be TRUE):
  1. DevOps files (Terraform, Dockerfile, Bash) index without errors when `language_id` metadata is present
  2. Running `cocosearch index .` without setting COCOSEARCH_DATABASE_URL connects to `postgresql://cocosearch:cocosearch@localhost:5432/cocosearch`
  3. `docker compose up` starts PostgreSQL with `cocosearch:cocosearch` credentials matching the application default
  4. `cocosearch config check` shows "default" as the source for DATABASE_URL when no env var is set (not an error)
**Plans**: TBD

Plans:
- [ ] 43-01: TBD

### Phase 44: Docker Image Simplification
**Goal**: Docker image provides only infrastructure services (PostgreSQL+pgvector, Ollama+model) with no application code
**Depends on**: Phase 43 (credential alignment)
**Requirements**: DOCK-01, DOCK-02, DOCK-03, DOCK-04, DOCK-05, DOCK-06
**Success Criteria** (what must be TRUE):
  1. Docker image builds without Python builder stage and contains no CocoSearch application code
  2. Container starts successfully with only PostgreSQL and Ollama services (no svc-mcp references anywhere)
  3. Health check reports healthy when PostgreSQL accepts connections and Ollama responds on port 11434
  4. Container exposes only ports 5432 (PostgreSQL) and 11434 (Ollama), not port 3000
  5. Users can follow documentation to set up docker-compose for infrastructure and uvx for MCP registration
**Plans**: TBD

Plans:
- [ ] 44-01: TBD

### Phase 45: MCP Protocol Enhancements
**Goal**: MCP server detects the active project using the protocol-standard Roots capability with graceful fallback for unsupported clients
**Depends on**: Phase 43 (working database connection)
**Requirements**: PROTO-01, PROTO-02, PROTO-03, PROTO-04, PROTO-05, PROTO-06
**Success Criteria** (what must be TRUE):
  1. MCP tools in Claude Code (which supports Roots) automatically detect the project without --project-from-cwd
  2. MCP tools in Claude Desktop (which does NOT support Roots) fall back to env var or cwd detection without errors
  3. HTTP transport accepts `?project=/path/to/repo` query parameter for project context
  4. Project detection follows consistent priority: roots > query_param > env > cwd across all transports
  5. `file://` URIs from Roots are correctly parsed to filesystem paths on the current platform
**Plans**: TBD

Plans:
- [ ] 45-01: TBD

### Phase 46: Parse Failure Tracking
**Goal**: Users can see how many files failed tree-sitter parsing per language when reviewing index health
**Depends on**: Phase 43 (working indexing pipeline)
**Requirements**: OBS-01, OBS-02, OBS-03, OBS-04
**Success Criteria** (what must be TRUE):
  1. After indexing, each chunk has a `parse_status` value (ok, error, or unsupported) stored in the database
  2. `cocosearch stats` CLI shows parse failure counts per language alongside existing metrics
  3. MCP `index_stats` tool response includes parse failure breakdown per language
  4. HTTP `/api/stats` endpoint includes parse failure data in its JSON response
**Plans**: TBD

Plans:
- [ ] 46-01: TBD

### Phase 47: Documentation Update
**Goal**: All documentation accurately reflects the infra-only Docker model, new defaults, and protocol enhancements
**Depends on**: Phases 43-46 (all feature work complete)
**Requirements**: DOC-01, DOC-02, DOC-03, DOC-04
**Success Criteria** (what must be TRUE):
  1. Each reference doc in docs/ has a table of contents with navigable links
  2. Docker documentation describes the infra-only model (docker-compose for PostgreSQL+Ollama, native CocoSearch)
  3. README reflects the new usage model: `docker compose up` for infrastructure, `uvx cocosearch` for the tool
  4. MCP configuration docs show default DATABASE_URL and explain when env vars are optional
**Plans**: TBD

Plans:
- [ ] 47-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 43 -> 44 -> 45 -> 46 -> 47

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 43. Bug Fix & Credential Defaults | 0/TBD | Not started | - |
| 44. Docker Image Simplification | 0/TBD | Not started | - |
| 45. MCP Protocol Enhancements | 0/TBD | Not started | - |
| 46. Parse Failure Tracking | 0/TBD | Not started | - |
| 47. Documentation Update | 0/TBD | Not started | - |

---
*Roadmap created: 2026-02-08*
*Milestone: v1.10 Infrastructure & Protocol*
