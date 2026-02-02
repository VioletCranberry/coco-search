# Requirements: CocoSearch v1.6

**Defined:** 2026-02-01
**Core Value:** Semantic code search that runs entirely locally -- no data leaves your machine

## v1.6 Requirements

Requirements for All-in-One Docker & Auto-Detect milestone.

### Container Deployment

- [ ] **DOCK-01**: User can run entire stack with single `docker run` command
- [ ] **DOCK-02**: Docker image includes pre-pulled nomic-embed-text model (no runtime download)
- [ ] **DOCK-03**: User can mount codebases via volume (`-v /local/repos:/mnt/repos:ro`)
- [ ] **DOCK-04**: User can persist data across restarts via volume (`-v cocosearch-data:/data`)
- [ ] **DOCK-05**: User can configure via existing COCOSEARCH_* environment variables
- [ ] **DOCK-06**: User can view logs via `docker logs` (stdout/stderr)

### Service Orchestration

- [ ] **ORCH-01**: Container exposes health check endpoint (`/health`) returning 200 when ready
- [ ] **ORCH-02**: Services start in correct order (PostgreSQL -> Ollama -> MCP server)
- [ ] **ORCH-03**: Container shuts down gracefully on SIGTERM (no data corruption)
- [ ] **ORCH-04**: Process supervisor (s6-overlay) manages and restarts crashed services

### MCP Transports

- [ ] **TRNS-01**: stdio transport works in container for Claude Code (`docker run -i`)
- [ ] **TRNS-02**: SSE transport available for Claude Desktop (`--transport sse`)
- [ ] **TRNS-03**: Streamable HTTP transport available as future standard (`--transport http`)
- [ ] **TRNS-04**: Transport selectable via `--transport` flag or `MCP_TRANSPORT` env var

### Auto-Detect Project

- [ ] **AUTO-01**: MCP can auto-detect project from working directory
- [ ] **AUTO-02**: Detection priority: cocosearch.yaml `indexName` > git repo name > directory name
- [ ] **AUTO-03**: System detects collision when same index name maps to different paths
- [ ] **AUTO-04**: On collision, user prompted to set explicit `indexName` in cocosearch.yaml
- [ ] **AUTO-05**: When auto-detected index doesn't exist, user prompted to run index command
- [ ] **AUTO-06**: cocosearch.yaml supports `indexName` field for explicit naming

### Documentation

- [ ] **DOCS-01**: Docker quick start guide with pull/run examples
- [ ] **DOCS-02**: Claude Code Docker configuration example (stdio transport)
- [ ] **DOCS-03**: Claude Desktop Docker configuration example (SSE/HTTP transport)
- [ ] **DOCS-04**: Volume mount and persistence documentation
- [ ] **DOCS-05**: Troubleshooting guide for common Docker issues

## Future Requirements

Deferred to future releases. Tracked but not in v1.6 roadmap.

### Container Enhancements

- **DOCK-07**: Multi-arch images (linux/amd64, linux/arm64) for Mac ARM
- **DOCK-08**: Container size optimization via multi-stage build
- **DOCK-09**: GPU passthrough documentation (`--gpus=all`)

### Advanced Features

- **AUTO-07**: Init-time auto-indexing of mounted codebases
- **AUTO-08**: Progress/status API for long indexing operations
- **DOCK-10**: Docker MCP Toolkit catalog submission

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Web UI dashboard | MCP clients are the UI, not the server |
| Runtime model downloading | Breaks offline use, slow startup |
| Multiple embedding models | Image bloat (274MB+ per model) |
| Docker-in-Docker | Security complexity for edge case |
| Authentication/authorization | Overkill for local-first tool |
| Kubernetes manifests | Beyond target audience |
| Windows containers | Tiny user base, massive complexity |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TRNS-01 | Phase 23 | Complete |
| TRNS-02 | Phase 23 | Complete |
| TRNS-03 | Phase 23 | Complete |
| TRNS-04 | Phase 23 | Complete |
| DOCK-01 | Phase 24 | Complete |
| DOCK-02 | Phase 24 | Complete |
| DOCK-03 | Phase 24 | Complete |
| DOCK-04 | Phase 24 | Complete |
| DOCK-05 | Phase 24 | Complete |
| DOCK-06 | Phase 24 | Complete |
| ORCH-01 | Phase 24 | Complete |
| ORCH-02 | Phase 24 | Complete |
| ORCH-03 | Phase 24 | Complete |
| ORCH-04 | Phase 24 | Complete |
| AUTO-01 | Phase 25 | Complete |
| AUTO-02 | Phase 25 | Complete |
| AUTO-03 | Phase 25 | Complete |
| AUTO-04 | Phase 25 | Complete |
| AUTO-05 | Phase 25 | Complete |
| AUTO-06 | Phase 25 | Complete |
| DOCS-01 | Phase 26 | Complete |
| DOCS-02 | Phase 26 | Complete |
| DOCS-03 | Phase 26 | Complete |
| DOCS-04 | Phase 26 | Complete |
| DOCS-05 | Phase 26 | Complete |

**Coverage:**
- v1.6 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0

---
*Requirements defined: 2026-02-01*
*Last updated: 2026-02-02 after Phase 26 complete*
