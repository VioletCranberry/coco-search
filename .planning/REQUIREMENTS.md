# Requirements: CocoSearch

**Defined:** 2026-01-31
**Core Value:** Semantic code search that runs entirely locally — no data leaves your machine.

## v1.4 Requirements

Requirements for Dogfooding Infrastructure milestone.

### Project Configuration

- [x] **CONF-01**: CLI loads configuration from `cocosearch.yaml` in project root or git root
- [x] **CONF-02**: Config supports `index_name` field to set the index name
- [x] **CONF-03**: Config supports `include_patterns` list for file inclusion globs
- [x] **CONF-04**: Config supports `exclude_patterns` list for file exclusion globs
- [x] **CONF-05**: Config supports `languages` list to filter indexed languages
- [x] **CONF-06**: Config supports `embedding_model` field to specify Ollama model
- [x] **CONF-07**: Config supports `chunk_size` and `result_limit` settings
- [x] **CONF-08**: Config validation with helpful error messages on invalid YAML or missing fields
- [x] **CONF-09**: CLI flags override config file settings when both specified

### Developer Setup Script

- [ ] **DEVS-01**: Shell script `dev-setup.sh` starts PostgreSQL via docker-compose
- [ ] **DEVS-02**: Script waits for PostgreSQL to be healthy before proceeding
- [ ] **DEVS-03**: Script checks for native Ollama availability on localhost:11434
- [ ] **DEVS-04**: Script launches Ollama in Docker if native Ollama not detected
- [ ] **DEVS-05**: Script pulls required embedding model (nomic-embed-text) if not available
- [ ] **DEVS-06**: Script runs `cocosearch index` on current project after services ready
- [ ] **DEVS-07**: Script is idempotent (safe to run multiple times)
- [ ] **DEVS-08**: Script uses colored output with progress indicators

### Dogfooding

- [ ] **DOGF-01**: Repository includes working `cocosearch.yaml` configured for CocoSearch codebase
- [ ] **DOGF-02**: README documents dogfooding setup as example usage

## Future Requirements

Deferred to later milestones.

### Configuration Extensions

- **CONF-10**: Environment variable substitution in config values
- **CONF-11**: Config inheritance (base config + override)
- **CONF-12**: Per-directory config overrides

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Web-based config editor | CLI-first tool, no web UI |
| Remote config loading | Local-first, no network dependencies |
| Config migration tooling | v1.4 is first version, nothing to migrate |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONF-01 | Phase 15 | Complete |
| CONF-02 | Phase 15 | Complete |
| CONF-03 | Phase 15 | Complete |
| CONF-04 | Phase 15 | Complete |
| CONF-05 | Phase 15 | Complete |
| CONF-06 | Phase 15 | Complete |
| CONF-07 | Phase 15 | Complete |
| CONF-08 | Phase 15 | Complete |
| CONF-09 | Phase 16 | Complete |
| DEVS-01 | Phase 17 | Pending |
| DEVS-02 | Phase 17 | Pending |
| DEVS-03 | Phase 17 | Pending |
| DEVS-04 | Phase 17 | Pending |
| DEVS-05 | Phase 17 | Pending |
| DEVS-06 | Phase 17 | Pending |
| DEVS-07 | Phase 17 | Pending |
| DEVS-08 | Phase 17 | Pending |
| DOGF-01 | Phase 18 | Pending |
| DOGF-02 | Phase 18 | Pending |

**Coverage:**
- v1.4 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0

---
*Requirements defined: 2026-01-31*
*Last updated: 2026-01-31 after roadmap creation*
