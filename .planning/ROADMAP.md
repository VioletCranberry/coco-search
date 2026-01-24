# Roadmap: CocoSearch

## Overview

CocoSearch delivers local-first semantic code search through a four-phase journey: establish infrastructure (PostgreSQL, Ollama), build the indexing pipeline (CocoIndex with Tree-sitter), implement vector search, and expose index management via MCP. Each phase delivers a coherent capability that depends on prior phases, culminating in a privacy-preserving code search tool that runs entirely on the developer's machine.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - PostgreSQL + pgvector and Ollama infrastructure with project scaffolding
- [ ] **Phase 2: Indexing Pipeline** - CocoIndex flow with Tree-sitter chunking and embedding generation
- [ ] **Phase 3: Search** - Vector similarity search with result formatting
- [ ] **Phase 4: Index Management** - Named index lifecycle and MCP server integration

## Phase Details

### Phase 1: Foundation
**Goal**: Development environment with all infrastructure dependencies running and verified
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03
**Success Criteria** (what must be TRUE):
  1. PostgreSQL container runs with pgvector extension enabled and persistent storage
  2. Ollama serves nomic-embed-text model and returns 768-dimensional embeddings
  3. Python project initializes with UV and all dependencies install successfully
  4. No network calls to external services during embedding generation
**Plans**: 2 plans

Plans:
- [ ] 01-01-PLAN.md — Infrastructure setup: Docker Compose, Ollama model, Python project
- [ ] 01-02-PLAN.md — Verification: pgvector extension, verification script, integration check

### Phase 2: Indexing Pipeline
**Goal**: Users can index a codebase directory and have it stored as searchable embeddings
**Depends on**: Phase 1
**Requirements**: INDEX-01, INDEX-02, INDEX-03, INDEX-04, INDEX-05, MCP-01, MCP-05
**Success Criteria** (what must be TRUE):
  1. User can index a directory and see chunks stored in PostgreSQL
  2. Code is chunked by language structure (functions, classes) not arbitrary byte boundaries
  3. Files matching .gitignore patterns are automatically excluded from indexing
  4. User can specify include/exclude patterns to filter which files get indexed
  5. Re-indexing a directory only processes files that changed since last index
**Plans**: TBD

Plans:
- [ ] 02-01: TBD

### Phase 3: Search
**Goal**: Users can search indexed code with natural language and receive relevant results
**Depends on**: Phase 2
**Requirements**: SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05, SRCH-06, MCP-02
**Success Criteria** (what must be TRUE):
  1. User can search with natural language query and receive semantically relevant code chunks
  2. Each result includes file path and line numbers for navigation
  3. Results include relevance scores showing match quality
  4. User can limit number of results returned to avoid context overflow
  5. User can filter search results by programming language
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

### Phase 4: Index Management
**Goal**: Users can manage multiple named indexes through MCP tools
**Depends on**: Phase 3
**Requirements**: MGMT-01, MGMT-02, MGMT-03, MGMT-04, MCP-03, MCP-04
**Success Criteria** (what must be TRUE):
  1. User can create and search multiple named indexes without conflicts
  2. User can clear a specific index without affecting others
  3. User can list all existing indexes
  4. User can see statistics for an index (file count, chunk count, size)
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/2 | Planned | - |
| 2. Indexing Pipeline | 0/TBD | Not started | - |
| 3. Search | 0/TBD | Not started | - |
| 4. Index Management | 0/TBD | Not started | - |

---
*Roadmap created: 2026-01-24*
*Last updated: 2026-01-24*
