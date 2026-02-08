# Requirements: CocoSearch v1.10

**Defined:** 2026-02-08
**Core Value:** Semantic code search that runs entirely locally — no data leaves your machine.

## v1 Requirements

Requirements for v1.10 milestone. Each maps to roadmap phases.

### Bug Fixes

- [x] **FIX-01**: Fix `language` → `language_id` parameter in `extract_devops_metadata` transform call (flow.py:93)

### Infrastructure Defaults

- [x] **INFRA-01**: Default `COCOSEARCH_DATABASE_URL` to `postgresql://cocosearch:cocosearch@localhost:5432/cocosearch`
- [x] **INFRA-02**: Align docker-compose.yml credentials from `cocoindex:cocoindex` to `cocosearch:cocosearch`
- [x] **INFRA-03**: Update `config check` to show "default" source instead of error when DATABASE_URL uses default

### Docker Simplification

- [ ] **DOCK-01**: Remove Python builder stage from Dockerfile (no CocoSearch in image)
- [ ] **DOCK-02**: Remove svc-mcp service from s6-overlay (delete service dir and all references)
- [ ] **DOCK-03**: Update health-check script to check PostgreSQL and Ollama only
- [ ] **DOCK-04**: Update Dockerfile exposed ports (remove 3000, keep 5432 and 11434)
- [ ] **DOCK-05**: Document docker-compose for dev workflow (infra + native CocoSearch)
- [ ] **DOCK-06**: Document uvx MCP registration pointing at Docker services

### MCP Protocol

- [ ] **PROTO-01**: Implement MCP Roots capability for project detection via `ctx.list_roots()`
- [ ] **PROTO-02**: Convert relevant MCP tools to async for Context access
- [ ] **PROTO-03**: Graceful fallback when client doesn't support Roots (catch error, fall to env/cwd)
- [ ] **PROTO-04**: Shared `_detect_project()` helper with priority: roots > query_param > env > cwd
- [ ] **PROTO-05**: HTTP transport `?project=` query param via ContextVar middleware
- [ ] **PROTO-06**: Parse `file://` URIs to filesystem paths with platform handling

### Observability

- [ ] **OBS-01**: Add `parse_status` field to symbol extraction return (ok/error/unsupported)
- [ ] **OBS-02**: Add `parse_status` column via schema migration (additive, same pattern as symbol columns)
- [ ] **OBS-03**: Aggregate parse failure counts per language in stats queries
- [ ] **OBS-04**: Surface parse failure stats in CLI stats, MCP index_stats, and HTTP /api/stats

### Documentation

- [ ] **DOC-01**: Add simple link list TOC to each reference doc file in docs/
- [ ] **DOC-02**: Rewrite Docker documentation for infra-only model
- [ ] **DOC-03**: Update README for new usage model (docker-compose + native CocoSearch)
- [ ] **DOC-04**: Update MCP configuration docs with new default DATABASE_URL

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Protocol Extensions

- **PROTO-EXT-01**: Multi-root project support (search across multiple roots)
- **PROTO-EXT-02**: MCP Roots change notification handling (invalidate cached detection)
- **PROTO-EXT-03**: Custom header alternative to query params (`X-CocoSearch-Project`)

### Observability Extensions

- **OBS-EXT-01**: Verbose parse failure output with file paths and error details
- **OBS-EXT-02**: Parse failure breakdown in web dashboard Chart.js visualization

## Out of Scope

| Feature | Reason |
|---------|--------|
| C/C++ macro extraction testing | Dropped from this milestone per user decision |
| Roots-based filesystem access control | CocoSearch only reads indexed data, not arbitrary files |
| OAuth/auth on HTTP transport | Local-first tool; reverse proxy handles auth if exposed |
| Parse failure auto-remediation | Track and report only; users investigate |
| All-in-one Docker image restoration | Infra-only is the new model |
| MCP SDK v2 migration | v2 is pre-alpha; stay on v1.26.x |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FIX-01 | Phase 43 | Complete |
| INFRA-01 | Phase 43 | Complete |
| INFRA-02 | Phase 43 | Complete |
| INFRA-03 | Phase 43 | Complete |
| DOCK-01 | Phase 44 | Pending |
| DOCK-02 | Phase 44 | Pending |
| DOCK-03 | Phase 44 | Pending |
| DOCK-04 | Phase 44 | Pending |
| DOCK-05 | Phase 44 | Pending |
| DOCK-06 | Phase 44 | Pending |
| PROTO-01 | Phase 45 | Pending |
| PROTO-02 | Phase 45 | Pending |
| PROTO-03 | Phase 45 | Pending |
| PROTO-04 | Phase 45 | Pending |
| PROTO-05 | Phase 45 | Pending |
| PROTO-06 | Phase 45 | Pending |
| OBS-01 | Phase 46 | Pending |
| OBS-02 | Phase 46 | Pending |
| OBS-03 | Phase 46 | Pending |
| OBS-04 | Phase 46 | Pending |
| DOC-01 | Phase 47 | Pending |
| DOC-02 | Phase 47 | Pending |
| DOC-03 | Phase 47 | Pending |
| DOC-04 | Phase 47 | Pending |

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-08*
*Last updated: 2026-02-08 after Phase 43 completion*
