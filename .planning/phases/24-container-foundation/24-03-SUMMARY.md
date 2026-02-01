---
phase: 24-container-foundation
plan: 03
subsystem: infra
tags: [docker, healthcheck, s6-overlay, ready-signal, process-supervision]

# Dependency graph
requires:
  - phase: 24-01
    provides: Multi-stage Dockerfile with s6-overlay, PostgreSQL, Ollama
  - phase: 24-02
    provides: s6-rc service definitions for all services
  - phase: 23-01
    provides: MCP server /health endpoint
provides:
  - Combined health check script checking all three services
  - Ready signal oneshot printing COCOSEARCH_READY marker
  - Docker HEALTHCHECK with 90s start-period for orchestration
  - STOPSIGNAL SIGTERM for graceful shutdown
affects: [25-auto-detect, 26-cli-integration, deployment-docs]

# Tech tracking
tech-stack:
  added: []
  patterns: [docker-healthcheck, ready-marker-pattern, s6-oneshot-services]

key-files:
  created:
    - docker/rootfs/etc/s6-overlay/scripts/health-check
    - docker/rootfs/etc/s6-overlay/scripts/ready-signal
    - docker/rootfs/etc/s6-overlay/s6-rc.d/init-ready/type
    - docker/rootfs/etc/s6-overlay/s6-rc.d/init-ready/up
    - docker/rootfs/etc/s6-overlay/s6-rc.d/init-ready/dependencies.d/svc-mcp
    - docker/rootfs/etc/s6-overlay/s6-rc.d/user/contents.d/init-ready
  modified:
    - docker/Dockerfile

key-decisions:
  - "Use script-based HEALTHCHECK instead of inline commands for maintainability"
  - "STOPSIGNAL SIGTERM cascades through s6-overlay to services"
  - "init-ready depends on svc-mcp to ensure all services are ready"

patterns-established:
  - "Ready marker pattern: COCOSEARCH_READY for scripting integration"
  - "Health check returns 0 only when ALL services pass"
  - "s6 oneshot services for startup signaling"

# Metrics
duration: 2min
completed: 2026-02-01
---

# Phase 24 Plan 03: Health Check Infrastructure Summary

**Docker HEALTHCHECK using combined health-check script, COCOSEARCH_READY stdout marker via init-ready oneshot, STOPSIGNAL for graceful shutdown**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-01T19:38:56Z
- **Completed:** 2026-02-01T19:41:03Z
- **Tasks:** 3
- **Files modified:** 7 (created 6, modified 1)

## Accomplishments
- Health check script validates PostgreSQL, Ollama, and MCP server health
- Ready signal oneshot prints COCOSEARCH_READY marker after all services are up
- Docker HEALTHCHECK uses health-check script with 90s startup grace period
- STOPSIGNAL SIGTERM ensures graceful shutdown through s6-overlay

## Task Commits

Each task was committed atomically:

1. **Task 1: Create combined health check script** - `8043508` (feat)
2. **Task 2: Create ready signal oneshot service** - `2b75e61` (feat)
3. **Task 3: Add Docker HEALTHCHECK to Dockerfile** - `b3fb8a4` (feat)

## Files Created/Modified
- `docker/rootfs/etc/s6-overlay/scripts/health-check` - Combined health check for all services
- `docker/rootfs/etc/s6-overlay/scripts/ready-signal` - Ready signal script printing COCOSEARCH_READY
- `docker/rootfs/etc/s6-overlay/s6-rc.d/init-ready/type` - oneshot type declaration
- `docker/rootfs/etc/s6-overlay/s6-rc.d/init-ready/up` - Path to ready-signal script
- `docker/rootfs/etc/s6-overlay/s6-rc.d/init-ready/dependencies.d/svc-mcp` - Dependency on MCP service
- `docker/rootfs/etc/s6-overlay/s6-rc.d/user/contents.d/init-ready` - User bundle registration
- `docker/Dockerfile` - Updated HEALTHCHECK to use script, added STOPSIGNAL

## Decisions Made
- **Script-based HEALTHCHECK:** Changed from inline commands to dedicated health-check script for maintainability and environment variable expansion
- **SIGTERM for graceful shutdown:** s6-overlay handles signal cascading to services, PostgreSQL finish script handles fast shutdown
- **init-ready depends on svc-mcp:** Since svc-mcp depends on both PostgreSQL and Ollama, init-ready transitively ensures all services are ready

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Container foundation complete with all three plans
- Docker image builds and contains health check infrastructure
- Ready for Phase 25: Auto-detect project from working directory
- Container can be verified with `docker run` (COCOSEARCH_READY in logs, healthy status)

---
*Phase: 24-container-foundation*
*Completed: 2026-02-01*
