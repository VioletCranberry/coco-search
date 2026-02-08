# Roadmap: CocoSearch v1.10

## Overview

v1.10 is a refinement milestone that standardizes credentials, simplifies the Docker image to infra-only, adds protocol-correct MCP Roots support, introduces parse failure tracking for observability, and updates documentation to reflect the new architecture. Five phases deliver these changes in dependency order: foundation fixes first, then infrastructure, protocol, observability, and documentation.

## Milestones

- v1.0-v1.9: See .planning/MILESTONES.md (shipped)
- v1.10 Infrastructure & Protocol: Phases 43-47 (in progress)

## Phases

- [x] **Phase 43: Bug Fix & Credential Defaults** - Fix DevOps metadata bug and standardize database credentials for zero-config setup
- [x] **Phase 44: Docker Image Simplification** - Strip CocoSearch from Docker image, making it infra-only (PostgreSQL+pgvector, Ollama+model)
- [x] **Phase 45: MCP Protocol Enhancements** - Add Roots capability for protocol-correct project detection with HTTP query param fallback
- [x] **Phase 46: Parse Failure Tracking** - Track and surface tree-sitter parse failures per language in stats output
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
**Plans**: 2 plans

Plans:
- [x] 43-01-PLAN.md -- Fix DevOps metadata bug, create get_database_url() helper, update all Python callsites and tests
- [x] 43-02-PLAN.md -- Align docker-compose.yml and all docs/scripts to cocosearch:cocosearch credentials

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
**Plans**: 2 plans

Plans:
- [x] 44-01-PLAN.md -- Strip Docker image: remove Python builder, delete svc-mcp, rewire init-ready, upgrade PG 16 to 17
- [x] 44-02-PLAN.md -- Update README and MCP docs for infra-only Docker model

### Phase 45: MCP Protocol Enhancements
**Goal**: MCP server detects the active project using the protocol-standard Roots capability with graceful fallback for unsupported clients
**Depends on**: Phase 43 (working database connection)
**Requirements**: PROTO-01, PROTO-02, PROTO-03, PROTO-04, PROTO-05, PROTO-06
**Success Criteria** (what must be TRUE):
  1. MCP tools in Claude Code (which supports Roots) automatically detect the project without --project-from-cwd
  2. MCP tools in Claude Desktop (which does NOT support Roots) fall back to env var or cwd detection without errors
  3. HTTP transport accepts `?project_path=/path/to/repo` query parameter for project context
  4. Project detection follows consistent priority: roots > query_param > env > cwd across all transports
  5. `file://` URIs from Roots are correctly parsed to filesystem paths on the current platform
**Plans**: 3 plans

Plans:
- [x] 45-01-PLAN.md -- Create project_detection.py module with file_uri_to_path, _detect_project priority chain, and roots notification handler
- [x] 45-02-PLAN.md -- Convert search_code to async with Context injection, integrate _detect_project for project detection
- [x] 45-03-PLAN.md -- Create project detection tests, update existing MCP tests for async, fix pre-existing test failures

### Phase 46: Parse Failure Tracking
**Goal**: Users can see how many files failed tree-sitter parsing per language when reviewing index health
**Depends on**: Phase 43 (working indexing pipeline)
**Requirements**: OBS-01, OBS-02, OBS-03, OBS-04
**Success Criteria** (what must be TRUE):
  1. After indexing, each file has a `parse_status` value (ok, partial, error, or unsupported) stored in the database
  2. `cocosearch stats` CLI shows parse failure counts per language alongside existing metrics
  3. MCP `index_stats` tool response includes parse failure breakdown per language
  4. HTTP `/api/stats` endpoint includes parse failure data in its JSON response
**Plans**: 3 plans

Plans:
- [x] 46-01-PLAN.md -- Create parse_tracking module, schema migration, integrate into flow.py and clear.py
- [x] 46-02-PLAN.md -- Add parse stats queries, extend IndexStats, update CLI with parse health display and --show-failures
- [x] 46-03-PLAN.md -- Surface parse stats in MCP/HTTP endpoints, add comprehensive tests

### Phase 47: Documentation Update
**Goal**: All documentation accurately reflects the infra-only Docker model, new defaults, and protocol enhancements
**Depends on**: Phases 43-46 (all feature work complete)
**Requirements**: DOC-01, DOC-02, DOC-03, DOC-04
**Success Criteria** (what must be TRUE):
  1. Each reference doc has clear section headers for GitHub sidebar navigation (relying on GitHub auto-ToC)
  2. Docker documentation describes the infra-only model (docker-compose for PostgreSQL+Ollama, native CocoSearch)
  3. README reflects the new usage model: `docker compose up` for infrastructure, `uvx cocosearch` for the tool
  4. MCP configuration docs show default DATABASE_URL and explain when env vars are optional
**Plans**: 2 plans

Plans:
- [ ] 47-01-PLAN.md -- Rewrite README.md and docs/mcp-configuration.md for infra-only Docker model and simplified MCP setup
- [ ] 47-02-PLAN.md -- Update 6 reference docs with parse health features, Roots capability, uvx commands, remove output blocks

## Progress

**Execution Order:**
Phases execute in numeric order: 43 -> 44 -> 45 -> 46 -> 47

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 43. Bug Fix & Credential Defaults | 2/2 | Complete | 2026-02-08 |
| 44. Docker Image Simplification | 2/2 | Complete | 2026-02-08 |
| 45. MCP Protocol Enhancements | 3/3 | Complete | 2026-02-08 |
| 46. Parse Failure Tracking | 3/3 | Complete | 2026-02-08 |
| 47. Documentation Update | 0/2 | Not started | - |

---
*Roadmap created: 2026-02-08*
*Milestone: v1.10 Infrastructure & Protocol*
