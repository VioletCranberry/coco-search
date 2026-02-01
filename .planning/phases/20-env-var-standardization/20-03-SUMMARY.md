---
phase: 20-env-var-standardization
plan: 03
subsystem: cli
tags: [cli, config, environment-variables, validation, rich]

# Dependency graph
requires:
  - phase: 20-01
    provides: validate_required_env_vars and mask_password utilities in cocosearch.config
provides:
  - cocosearch config check command for environment variable validation
  - Lightweight troubleshooting tool for CI/CD and local development
affects: [20-04, documentation, ci-cd]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CLI config check commands for env var validation"
    - "Rich table display for env var status"

key-files:
  created: []
  modified:
    - src/cocosearch/cli.py

key-decisions:
  - "config check validates without connecting to services (lightweight)"
  - "Show all missing variables together (not fail on first)"
  - "Display source (environment vs default) for transparency"

patterns-established:
  - "Config check commands should mask sensitive values"
  - "Environment validation should provide helpful hints"

# Metrics
duration: 2min
completed: 2026-02-01
---

# Phase 20 Plan 03: Config Check Command Summary

**CLI command `cocosearch config check` validates COCOSEARCH_DATABASE_URL and COCOSEARCH_OLLAMA_URL without connecting to services**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-01T02:50:34Z
- **Completed:** 2026-02-01T02:52:30Z
- **Tasks:** 3 (2 with file changes, 1 verification)
- **Files modified:** 1

## Accomplishments
- Added config_check_command function with validation and table display
- Registered config check subcommand in CLI parser and routing
- Validated password masking and exit codes work correctly
- Provides lightweight env var troubleshooting without service connections

## Task Commits

Each task was committed atomically:

1. **Task 1: Add config check command function** - `d9ec4c5` (feat)
2. **Task 2: Register config check subcommand** - `652bf9e` (feat)
3. **Task 3: Test config check command** - No commit (verification only)

## Files Created/Modified
- `src/cocosearch/cli.py` - Added config_check_command function and registered config check subcommand

## Decisions Made

None - plan executed exactly as written.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Config check command is ready for use in CI/CD pipelines and local troubleshooting.
Enables users to validate environment setup before running indexing or search operations.
Ready for plan 20-04 to update remaining scripts and documentation.

---
*Phase: 20-env-var-standardization*
*Completed: 2026-02-01*
