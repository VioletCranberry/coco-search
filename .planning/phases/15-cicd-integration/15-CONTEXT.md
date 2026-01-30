# Phase 15: CI/CD Integration - Context

**Gathered:** 2026-01-30
**Status:** Ready for planning

<domain>
## Phase Boundary

GitHub Actions workflow running integration tests with Docker services on every push. Environment-based hostname detection for CI vs local execution. Tests skip gracefully when Docker unavailable locally.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

User delegated all implementation choices to Claude. Standard CI/CD patterns apply:

**Workflow triggers:**
- Run on push to main and pull requests
- Manual dispatch for debugging

**Service strategy:**
- GitHub Actions services for PostgreSQL+pgvector
- Native Ollama setup required (per Phase 14 decision about containerized Ollama limitations)

**Environment detection:**
- Use CI environment variable to detect GitHub Actions
- Hostname resolution: localhost for local, service names for CI
- pytest marker skip behavior when Docker unavailable locally

**Failure handling:**
- Standard GitHub Actions timeout (30-60 minutes)
- No custom retry logic beyond pytest defaults
- Artifact collection for test reports

</decisions>

<specifics>
## Specific Ideas

Constraints from earlier phases:
- Native Ollama required (OllamaContainer has API endpoint compatibility issues — Phase 14 decision)
- Port 5433 for test PostgreSQL to avoid conflict with local 5432 (Phase 12 decision)
- Integration tests require explicit -m integration flag (Phase 11 decision)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-cicd-integration*
*Context gathered: 2026-01-30*
