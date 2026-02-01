---
phase: 24-container-foundation
plan: 01
subsystem: infra
tags: [docker, s6-overlay, postgresql, ollama, multi-stage-build]

# Dependency graph
requires:
  - phase: 23-mcp-transport
    provides: MCP server with /health endpoint and transport configuration
provides:
  - Multi-stage Dockerfile bundling PostgreSQL, Ollama, and Python app
  - Pre-baked nomic-embed-text model (no runtime download)
  - s6-overlay v3.2.2.0 as PID 1 init system
  - Service registration files for s6-rc user bundle
  - /data directory structure for volume mounts
affects: [24-02, 24-03, 25-auto-detect, 26-cli-integration]

# Tech tracking
tech-stack:
  added: [s6-overlay, multi-stage-docker-build]
  patterns: [model-baking, architecture-mapping]

key-files:
  created:
    - docker/Dockerfile
    - docker/rootfs/etc/s6-overlay/s6-rc.d/user/contents.d/svc-postgresql
    - docker/rootfs/etc/s6-overlay/s6-rc.d/user/contents.d/svc-ollama
    - docker/rootfs/etc/s6-overlay/s6-rc.d/user/contents.d/svc-mcp
    - docker/rootfs/etc/s6-overlay/s6-rc.d/user/contents.d/init-warmup
  modified: []

key-decisions:
  - "Copy Ollama binary from model-downloader stage instead of downloading separately"
  - "Map TARGETARCH to s6-overlay naming (arm64->aarch64, amd64->x86_64)"
  - "Use official ollama/ollama image for multi-arch model baking"

patterns-established:
  - "Multi-stage build: model-downloader -> python-builder -> final"
  - "Architecture mapping for cross-platform s6-overlay installation"

# Metrics
duration: 16min
completed: 2026-02-01
---

# Phase 24 Plan 01: Container Foundation Summary

**Multi-stage Dockerfile with s6-overlay v3.2.2.0, PostgreSQL 16+pgvector, Ollama with pre-baked nomic-embed-text model, and Python app under process supervision**

## Performance

- **Duration:** 16 min
- **Started:** 2026-02-01T19:18:09Z
- **Completed:** 2026-02-01T19:34:37Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Multi-stage Dockerfile building in ~5 minutes with all components bundled
- nomic-embed-text model pre-baked into image (274MB, no runtime download needed)
- s6-overlay installed as PID 1 with proper architecture mapping
- Service registration files ready for s6-rc (actual definitions in Plan 02)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create multi-stage Dockerfile with all components** - `cdb567f` (feat)
2. **Task 2: Create s6 service registration files** - `2efdad5` (feat)

## Files Created/Modified
- `docker/Dockerfile` - Multi-stage build with s6-overlay, PostgreSQL, Ollama, Python app
- `docker/rootfs/etc/s6-overlay/s6-rc.d/user/contents.d/svc-postgresql` - PostgreSQL service registration
- `docker/rootfs/etc/s6-overlay/s6-rc.d/user/contents.d/svc-ollama` - Ollama service registration
- `docker/rootfs/etc/s6-overlay/s6-rc.d/user/contents.d/svc-mcp` - MCP server service registration
- `docker/rootfs/etc/s6-overlay/s6-rc.d/user/contents.d/init-warmup` - Warmup oneshot registration

## Decisions Made
- **Ollama binary from model-downloader stage:** Instead of downloading Ollama separately, copy binary from the model-downloader stage which already has the correct architecture
- **Architecture mapping for s6-overlay:** Docker's TARGETARCH uses arm64/amd64 but s6-overlay uses aarch64/x86_64, added mapping in shell
- **Official ollama/ollama image for model baking:** gerke74/ollama-model-loader is amd64-only; using official image supports arm64/amd64

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] s6-overlay architecture naming mismatch**
- **Found during:** Task 1 (Dockerfile creation)
- **Issue:** s6-overlay uses aarch64/x86_64 but Docker TARGETARCH provides arm64/amd64
- **Fix:** Added shell case statement to map architectures before download
- **Files modified:** docker/Dockerfile
- **Verification:** Build succeeds on arm64 (M1/M2 Mac)
- **Committed in:** cdb567f (Task 1 commit)

**2. [Rule 3 - Blocking] Model loader image amd64-only**
- **Found during:** Task 1 (Dockerfile creation)
- **Issue:** gerke74/ollama-model-loader only supports linux/amd64
- **Fix:** Switched to official ollama/ollama image with inline model pull
- **Files modified:** docker/Dockerfile
- **Verification:** Model downloads successfully on arm64
- **Committed in:** cdb567f (Task 1 commit)

**3. [Rule 3 - Blocking] Missing README.md in build context**
- **Found during:** Task 1 (Dockerfile creation)
- **Issue:** pyproject.toml references README.md but it wasn't copied to build stage
- **Fix:** Added README.md to COPY command in python-builder stage
- **Files modified:** docker/Dockerfile
- **Verification:** UV install succeeds
- **Committed in:** cdb567f (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (3 blocking issues)
**Impact on plan:** All fixes necessary for multi-arch build support. No scope creep.

## Issues Encountered
- Initial Ollama download URL returned 404 due to curl not following redirect properly; resolved by copying binary from model-downloader stage instead

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Dockerfile builds and contains all components
- Service registration files in place for s6-rc
- Ready for Plan 02: s6 service run scripts and dependencies
- Plan 03 will add startup scripts and healthcheck

---
*Phase: 24-container-foundation*
*Completed: 2026-02-01*
