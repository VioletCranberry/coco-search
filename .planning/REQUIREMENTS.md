# Requirements: CocoSearch v1.9

**Defined:** 2026-02-05
**Core Value:** Semantic code search that runs entirely locally — no data leaves your machine.

## v1.9 Requirements

Requirements for v1.9 Multi-Repo & Polish milestone.

### Multi-Repo MCP Support

- [ ] **MCP-01**: MCP server accepts `--project-from-cwd` flag for single-registration multi-repo support
- [ ] **MCP-02**: User-scope MCP registration documented for Claude Code (`claude mcp add --scope user`)
- [ ] **MCP-03**: User-scope MCP registration documented for Claude Desktop
- [ ] **MCP-04**: When search runs on unindexed repo, prompt user to index (not silent failure)
- [ ] **MCP-05**: Detect stale indexes and warn user (index freshness check)

### Test Fixes

- [ ] **TEST-01**: Fix test signature format mismatches

### Code Cleanup

- [ ] **CLEAN-01**: Remove DB migrations logic from codebase
- [ ] **CLEAN-02**: Remove deprecated functions
- [ ] **CLEAN-03**: Remove v1.2 graceful degradation (old index compat)
- [ ] **CLEAN-04**: Update test imports before module removal (prerequisite for CLEAN-01/02/03)

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
| MCP-01 | Pending | Pending |
| MCP-02 | Pending | Pending |
| MCP-03 | Pending | Pending |
| MCP-04 | Pending | Pending |
| MCP-05 | Pending | Pending |
| TEST-01 | Pending | Pending |
| CLEAN-01 | Pending | Pending |
| CLEAN-02 | Pending | Pending |
| CLEAN-03 | Pending | Pending |
| CLEAN-04 | Pending | Pending |
| DOC-01 | Pending | Pending |
| DOC-02 | Pending | Pending |
| DOC-03 | Pending | Pending |
| DOC-04 | Pending | Pending |
| DOC-05 | Pending | Pending |

**Coverage:**
- v1.9 requirements: 15 total
- Mapped to phases: 0
- Unmapped: 15 (awaiting roadmap)

---
*Requirements defined: 2026-02-05*
*Last updated: 2026-02-05 after initial definition*
