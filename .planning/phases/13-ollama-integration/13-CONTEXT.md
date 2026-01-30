# Phase 13: Ollama Integration - Context

**Gathered:** 2026-01-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Integration tests validating real Ollama embedding generation. Tests generate actual embeddings (not mocked) using either native Ollama or Docker container. Handles 30-second warmup timeout on first request. CLI/search integration with Ollama is separate (Phase 14 E2E flows).

</domain>

<decisions>
## Implementation Decisions

### Ollama Sourcing
- Native-first detection: check if Ollama responds on localhost:11434
- Docker fallback: start container only when native unavailable
- Fixture detects availability at session start, caches decision
- Tests skip with clear message if neither available

### Warmup Handling
- Session-scoped pre-warm fixture makes throwaway embedding request
- Extended timeout (60s) on httpx client for safety
- Both approaches: pre-warm AND extended timeout
- Warmup happens once per test session, not per test

### Embedding Validation
- Verify dimension count matches expected (768 for nomic-embed-text)
- Value range check (floats in reasonable range, not NaN/Inf)
- Similarity sanity tests: verify similar texts produce similar embeddings

### Container Lifecycle
- Add Ollama service to existing docker-compose.test.yml
- Share startup with PostgreSQL — single `docker-compose up -d`
- Model pulled during container startup (nomic-embed-text)
- Container persists for session (same pattern as PostgreSQL)

### Claude's Discretion
- Exact timeout values for warmup request
- Model pull retry logic
- Error message formatting for skip conditions
- httpx client configuration details

</decisions>

<specifics>
## Specific Ideas

- Follow same session-scoped fixture pattern established in Phase 12 for PostgreSQL
- Native detection should be fast (sub-second health check)
- Docker container should use same network as PostgreSQL container

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-ollama-integration*
*Context gathered: 2026-01-30*
