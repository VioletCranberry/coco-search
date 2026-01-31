# Requirements: CocoSearch

**Defined:** 2026-01-31
**Core Value:** Semantic code search that runs entirely locally — no data leaves your machine.

## v1.5 Requirements

Requirements for v1.5 Configuration & Architecture Polish. Each maps to roadmap phases.

### Configuration

- [ ] **CONFIG-01**: Config values support `${VAR}` syntax for env var substitution
- [ ] **CONFIG-02**: Missing env vars in substitution produce clear error messages
- [ ] **CONFIG-03**: Env var substitution works in all config sections (indexing, search, embedding)

### Environment Variables

- [ ] **ENV-01**: All app env vars use COCOSEARCH_* prefix
- [ ] **ENV-02**: Code reads COCOSEARCH_DATABASE_URL (replaces COCOINDEX_DATABASE_URL)
- [ ] **ENV-03**: Code reads COCOSEARCH_OLLAMA_URL (replaces OLLAMA_HOST)
- [ ] **ENV-04**: .env.example and docker-compose.yml use COCOSEARCH_* vars
- [ ] **ENV-05**: Documentation reflects COCOSEARCH_* naming throughout

### Language Chunking

- [ ] **LANG-01**: Each language (HCL, Dockerfile, Bash) has its own module file
- [ ] **LANG-02**: Language modules follow consistent interface (separator, metadata extractor)
- [ ] **LANG-03**: Registry pattern allows discovering available language handlers
- [ ] **LANG-04**: Adding new language requires only creating new module file
- [ ] **LANG-05**: Existing chunking behavior preserved (no regression)

### Documentation

- [ ] **DOCS-01**: README.md has clickable table of contents
- [ ] **DOCS-02**: TOC covers all major sections

## Future Requirements

Deferred to later milestones.

### Configuration Extensions

- **CONFIG-EXT-01**: Config inheritance (base + override files)
- **CONFIG-EXT-02**: Per-directory config overrides

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Backward compatibility env var aliases | Hard cutover preferred for clean break |
| Config inheritance | Complexity vs value tradeoff |
| Per-directory config overrides | Reassess if demand emerges |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONFIG-01 | Phase 19 | Pending |
| CONFIG-02 | Phase 19 | Pending |
| CONFIG-03 | Phase 19 | Pending |
| ENV-01 | Phase 20 | Pending |
| ENV-02 | Phase 20 | Pending |
| ENV-03 | Phase 20 | Pending |
| ENV-04 | Phase 20 | Pending |
| ENV-05 | Phase 20 | Pending |
| LANG-01 | Phase 21 | Pending |
| LANG-02 | Phase 21 | Pending |
| LANG-03 | Phase 21 | Pending |
| LANG-04 | Phase 21 | Pending |
| LANG-05 | Phase 21 | Pending |
| DOCS-01 | Phase 22 | Pending |
| DOCS-02 | Phase 22 | Pending |

**Coverage:**
- v1.5 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0

---
*Requirements defined: 2026-01-31*
*Last updated: 2026-01-31 after roadmap creation*
