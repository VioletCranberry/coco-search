# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-30)

**Core value:** Semantic code search that runs entirely locally -- no data leaves your machine.
**Current focus:** v1.3 Docker Integration Tests & Infrastructure (Phase 15 next)

## Current Position

Phase: 14 of 15 (E2E Flows) - COMPLETE
Plan: 03 of 03 (DevOps File Validation)
Status: Phase complete
Last activity: 2026-01-30 -- Completed Phase 14

Progress: [██████████████████████████████████████░░░░░░░] 93% (40 plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 35
- Total execution time: ~5 days across 3 milestones

**By Milestone:**

| Milestone | Phases | Plans | Duration |
|-----------|--------|-------|----------|
| v1.0 | 1-4 | 12 | 2 days |
| v1.1 | 5-7 | 11 | 2 days |
| v1.2 | 8-10, 4-soi | 6 | 1 day |

**Current Milestone (v1.3):**
- Phases: 5 (11-15)
- Plans completed: 11 (phases 11-14 done, phase 15 remaining)
- Focus: Integration test infrastructure & CI/CD

## Milestones Shipped

| Milestone | Phases | Plans | Shipped |
|-----------|--------|-------|---------|
| v1.0 MVP | 1-4 | 12 | 2026-01-25 |
| v1.1 Docs & Tests | 5-7 | 11 | 2026-01-26 |
| v1.2 DevOps Language Support | 8-10, 4-soi | 6 | 2026-01-27 |

**Total shipped:** 11 phases, 29 plans

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v1.2: Zero-dependency DevOps pipeline using CocoIndex custom_languages and Python stdlib regex
- v1.2: Additive schema only (no primary key changes) for safe migration
- v1.2: Module-level graceful degradation flag prevents repeated failing SQL for pre-v1.2 indexes
- v1.3 (Phase 11): Default pytest run executes only unit tests via -m unit marker for fast feedback
- v1.3 (Phase 11): Integration tests require explicit -m integration flag to prevent accidental slow runs
- v1.3 (Phase 12): Port 5433 for test PostgreSQL to avoid conflict with local 5432
- v1.3 (Phase 12): Session-scoped container fixtures for performance (one container per test session)
- v1.3 (Phase 12): TRUNCATE CASCADE for test cleanup (fast, keeps schema)
- v1.3 (Phase 12): autouse cleanup fixture only runs for @pytest.mark.integration tests
- v1.3 (Phase 12): Fixed testcontainers API: user -> username parameter for compatibility
- v1.3 (Phase 13): Native-first Ollama detection checks localhost:11434 before Docker fallback
- v1.3 (Phase 13): Session-scoped warmup fixture prevents 30-second first-request timeout
- v1.3 (Phase 13): Similarity thresholds: > 0.8 for similar texts, < 0.7 for dissimilar, > 0.5 for code vs description
- v1.3 (Phase 13): Batch embedding pattern using DataSlice([text1, text2]) for efficiency
- v1.3 (Phase 14): E2E tests invoke CLI via subprocess with environment propagation
- v1.3 (Phase 14): OLLAMA_HOST explicitly passed to EmbedText(address=...) for container support
- v1.3 (Phase 14): Native Ollama recommended over containerized (session management issues)
- v1.3 (Phase 14): E2E fixtures use realistic code with predictable search terms
- v1.3 (Phase 14): CLI uses -n for index name (not --name), JSON output is default (no --json flag)
- v1.3 (Phase 14-02): CLI outputs file_path (not filename) and content (not chunk) in JSON results
- v1.3 (Phase 14-02): Function-scoped indexing fixtures work with autouse clean_tables cleanup
- v1.3 (Phase 14-02): E2E search tests use --min-score 0.2 for moderate semantic queries
- v1.3 (Phase 14-02): Native Ollama required for E2E tests (brew install ollama + ollama pull nomic-embed-text)

### Pending Todos

None -- Phase 14 complete. Ready for Phase 15 (CI/CD Integration).

### Blockers/Concerns

**Containerized Ollama limitation:**
- OllamaContainer has API endpoint compatibility issues (calls /api/embed instead of /api/embeddings)
- Native Ollama installation works correctly (brew install ollama)
- Status: Native Ollama installed and working for E2E tests
- Impact: CI/CD environments need native Ollama setup, not containerized

## Session Continuity

Last session: 2026-01-30
Stopped at: Completed Phase 14 (E2E Flows)
Resume file: None

---
*Updated: 2026-01-30 after Phase 14 completion*
