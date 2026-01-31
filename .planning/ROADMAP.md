# Roadmap: CocoSearch

## Milestones

- ✅ **v1.0 MVP** - Phases 1-4 (shipped 2026-01-25)
- ✅ **v1.1 Docs & Tests** - Phases 5-7 (shipped 2026-01-26)
- ✅ **v1.2 DevOps Language Support** - Phases 8-10, 4-soi (shipped 2026-01-27)
- ✅ **v1.3 Docker Integration Tests** - Phases 11-14 (shipped 2026-01-30)
- ✅ **v1.4 Dogfooding Infrastructure** - Phases 15-18 (shipped 2026-01-31)
- 🚧 **v1.5 Configuration & Architecture Polish** - Phases 19-22 (in progress)

## Phases

<details>
<summary>✅ v1.0-v1.4 (Phases 1-18) - SHIPPED</summary>

See project history. 19 phases, 47 plans completed across 5 milestones.

</details>

### 🚧 v1.5 Configuration & Architecture Polish (In Progress)

**Milestone Goal:** Clean up configuration patterns, standardize environment variables, and refactor language chunking for extensibility.

- [ ] **Phase 19: Config Env Var Substitution** - Support ${VAR} syntax in config files
- [ ] **Phase 20: Env Var Standardization** - Migrate to COCOSEARCH_* prefix everywhere
- [ ] **Phase 21: Language Chunking Refactor** - Registry-based language handler architecture
- [ ] **Phase 22: Documentation Polish** - README with clickable table of contents

## Phase Details

### Phase 19: Config Env Var Substitution
**Goal**: Config files support environment variable substitution for flexible deployment
**Depends on**: Nothing (first phase of v1.5)
**Requirements**: CONFIG-01, CONFIG-02, CONFIG-03
**Success Criteria** (what must be TRUE):
  1. User can write `${DATABASE_URL}` in config and it resolves to env var value
  2. User sees clear error message when referenced env var is missing
  3. User can use env var substitution in indexing, search, and embedding config sections
**Plans**: TBD

Plans:
- [ ] 19-01: TBD

### Phase 20: Env Var Standardization
**Goal**: All CocoSearch environment variables use consistent COCOSEARCH_* naming
**Depends on**: Phase 19 (config substitution enables cleaner env var usage)
**Requirements**: ENV-01, ENV-02, ENV-03, ENV-04, ENV-05
**Success Criteria** (what must be TRUE):
  1. User sees only COCOSEARCH_* prefixed env vars in .env.example
  2. User can set COCOSEARCH_DATABASE_URL and app connects to database
  3. User can set COCOSEARCH_OLLAMA_URL and app uses that Ollama instance
  4. User finds COCOSEARCH_* naming in all documentation
  5. docker-compose.yml uses COCOSEARCH_* vars consistently
**Plans**: TBD

Plans:
- [ ] 20-01: TBD

### Phase 21: Language Chunking Refactor
**Goal**: Language handlers use registry pattern for clean extensibility
**Depends on**: Phase 20 (standalone refactor, ordered after env cleanup)
**Requirements**: LANG-01, LANG-02, LANG-03, LANG-04, LANG-05
**Success Criteria** (what must be TRUE):
  1. User sees separate module files for HCL, Dockerfile, and Bash chunking
  2. Developer adding new language creates single module file following documented interface
  3. Registry autodiscovers available language handlers without manual registration
  4. Existing chunking behavior unchanged (HCL, Dockerfile, Bash work as before)
  5. Each language module exports consistent separator and metadata extractor
**Plans**: TBD

Plans:
- [ ] 21-01: TBD

### Phase 22: Documentation Polish
**Goal**: README has professional navigation via table of contents
**Depends on**: Phase 21 (documentation reflects final state)
**Requirements**: DOCS-01, DOCS-02
**Success Criteria** (what must be TRUE):
  1. User can click TOC entry in README and jump to that section
  2. TOC covers all major README sections (installation, usage, configuration, etc.)
**Plans**: TBD

Plans:
- [ ] 22-01: TBD

## Progress

**Execution Order:** 19 → 20 → 21 → 22

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 19. Config Env Var Substitution | v1.5 | 0/TBD | Not started | - |
| 20. Env Var Standardization | v1.5 | 0/TBD | Not started | - |
| 21. Language Chunking Refactor | v1.5 | 0/TBD | Not started | - |
| 22. Documentation Polish | v1.5 | 0/TBD | Not started | - |

---
*Roadmap created: 2026-01-31*
*Last updated: 2026-01-31*
