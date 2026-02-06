# Requirements: CocoSearch v1.9

**Defined:** 2026-02-05
**Core Value:** Semantic code search that runs entirely locally — no data leaves your machine.

## v1.9 Requirements

Requirements for v1.9 Multi-Repo & Polish milestone.

### Multi-Repo MCP Support

- [x] **MCP-01**: MCP server accepts `--project-from-cwd` flag for single-registration multi-repo support
- [x] **MCP-02**: User-scope MCP registration documented for Claude Code (`claude mcp add --scope user`)
- [x] **MCP-03**: User-scope MCP registration documented for Claude Desktop
- [x] **MCP-04**: When search runs on unindexed repo, prompt user to index (not silent failure)
- [x] **MCP-05**: Detect stale indexes and warn user (index freshness check)

### Test Fixes

- [x] **TEST-01**: Fix test signature format mismatches

### Code Cleanup

- [x] **CLEAN-01**: ~~Remove DB migrations logic from codebase~~ **Resolved with clarification** — Research (40-RESEARCH.md lines 357-362) proved `schema_migration.py` is NOT deprecated migration logic but necessary PostgreSQL feature enhancement (TSVECTOR generated columns, GIN indexes, symbol columns). CocoIndex cannot create these PostgreSQL-specific features. File should remain in codebase.
- [x] **CLEAN-02**: Remove deprecated functions
- [x] **CLEAN-03**: Remove v1.2 graceful degradation (old index compat)
- [x] **CLEAN-04**: Update test imports before module removal (prerequisite for CLEAN-01/02/03)

### Documentation

- [ ] **DOC-01**: Create onboarding workflow skill (multi-step)
- [ ] **DOC-02**: Create debugging workflow skill (multi-step)
- [ ] **DOC-03**: Create refactoring workflow skill (multi-step)
- [ ] **DOC-04**: Document retrieval logic (hybrid search, RRF fusion, symbol filtering)
- [ ] **DOC-05**: Create MCP tools reference with complete examples

## Future Requirements

Deferred to later milestones.

### Protocol Enhancements

- **PROTO-01**: MCP Roots capability support (protocol-correct project detection)
- **PROTO-02**: HTTP transport project context via query params

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Answer synthesis in MCP | Claude (caller) handles synthesis from chunks — simpler architecture |
| `activate_project` MCP tool | Serena users complain about confusion — cwd detection is cleaner |
| Project registry persistence | Unnecessary complexity for single-user tool |
| LSP integration | Out of scope for MCP-focused tool |
| Redis-backed cache | In-memory sufficient for single-user |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MCP-01 | Phase 38 | Complete |
| MCP-02 | Phase 38 | Complete |
| MCP-03 | Phase 38 | Complete |
| MCP-04 | Phase 38 | Complete |
| MCP-05 | Phase 38 | Complete |
| TEST-01 | Phase 39 | Complete |
| CLEAN-01 | Phase 40 | Resolved (research proved assumption incorrect) |
| CLEAN-02 | Phase 40 | Complete |
| CLEAN-03 | Phase 40 | Complete |
| CLEAN-04 | Phase 40 | Complete |
| DOC-01 | Phase 41 | Pending |
| DOC-02 | Phase 41 | Pending |
| DOC-03 | Phase 41 | Pending |
| DOC-04 | Phase 42 | Pending |
| DOC-05 | Phase 42 | Pending |

**Coverage:**
- v1.9 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0

---
*Requirements defined: 2026-02-05*
*Last updated: 2026-02-06 after phase 40 completion (CLEAN-02, CLEAN-03, CLEAN-04 complete)*
