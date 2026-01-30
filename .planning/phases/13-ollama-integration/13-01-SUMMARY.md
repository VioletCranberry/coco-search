---
phase: 13-ollama-integration
plan: 01
subsystem: testing
tags: [ollama, testcontainers, pytest, fixtures, embeddings, integration-tests]

# Dependency graph
requires:
  - phase: 12-container-infrastructure
    provides: Session-scoped container fixture patterns with testcontainers
provides:
  - Ollama integration fixtures with native detection and Docker fallback
  - Session-scoped warmup to prevent first-request timeout
  - Fixture infrastructure for real embedding generation tests
affects: [13-02-ollama-integration-tests, 14-e2e-flows]

# Tech tracking
tech-stack:
  added: [testcontainers[ollama]]
  patterns: [native-first service detection, session-scoped warmup fixture]

key-files:
  created:
    - tests/fixtures/ollama_integration.py
  modified:
    - pyproject.toml
    - tests/integration/conftest.py

key-decisions:
  - "Native-first detection checks localhost:11434 before Docker fallback"
  - "Session scope for ollama_service and warmed_ollama fixtures prevents repeated container starts"
  - "Warmup fixture makes throwaway embedding request to pre-load nomic-embed-text model"
  - "Environment variable OLLAMA_HOST set for CocoIndex integration"

patterns-established:
  - "Pattern 1: Native-first detection via httpx GET to /api/tags with 2s timeout"
  - "Pattern 2: Docker fallback with OllamaContainer and nomic-embed-text model"
  - "Pattern 3: Session-scoped warmup using cocoindex.transform_flow() with DataSlice"

# Metrics
duration: 195s
completed: 2026-01-30
---

# Phase 13 Plan 01: Ollama Integration Fixtures Summary

**Native-first Ollama fixtures with session-scoped Docker fallback and pre-warmup to prevent 30-second first-request timeout**

## Performance

- **Duration:** 3m 15s
- **Started:** 2026-01-30T13:17:26Z
- **Completed:** 2026-01-30T13:20:41Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Session-scoped Ollama fixtures enable integration tests with real embedding generation
- Native detection (localhost:11434) checks before Docker container startup
- Pre-warmup fixture loads nomic-embed-text model once per session, preventing 30s timeout on first test
- Following Phase 12 container patterns for consistency

## Task Commits

Each task was committed atomically:

1. **Task 1: Add testcontainers[ollama] dependency** - `59f15e5` (chore)
2. **Task 2: Create Ollama integration fixtures** - `9cf1a15` (feat)

## Files Created/Modified
- `pyproject.toml` - Added testcontainers[ollama] to dev dependencies
- `tests/fixtures/ollama_integration.py` - New fixture module with is_ollama_available(), ollama_service, warmed_ollama
- `tests/integration/conftest.py` - Registered ollama_integration fixtures

## Decisions Made

**1. Native-first detection approach**
- Check localhost:11434/api/tags before starting Docker
- Respects existing Ollama installations, uses Docker only as fallback
- 2-second timeout sufficient for local health check

**2. Session-scoped warmup strategy**
- Warmup runs once per test session (not per test)
- Prevents 30-second timeout on first embedding request in each test
- Uses throwaway embedding via cocoindex.transform_flow()

**3. Environment variable integration**
- Set OLLAMA_HOST for CocoIndex to use correct service URL
- Restore original value after warmup to avoid side effects

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Implementation followed research patterns from Phase 13 RESEARCH.md. EmbedText doesn't accept timeout parameter directly, so relying on httpx defaults with generous warmup buffer.

## User Setup Required

None - no external service configuration required. Tests will use native Ollama if available or fall back to Docker automatically.

## Next Phase Readiness

Ready for Phase 13 Plan 02: Ollama integration tests. Fixture infrastructure complete with:
- is_ollama_available() for native detection
- ollama_service fixture providing URL (native or Docker)
- warmed_ollama fixture with pre-loaded model
- Registered in integration conftest.py

No blockers. Integration tests can now generate real embeddings using these fixtures.

---
*Phase: 13-ollama-integration*
*Completed: 2026-01-30*
