---
phase: 38-multi-repo-mcp-support
plan: 02
subsystem: docs
tags: [mcp, documentation, claude-code, claude-desktop, uvx, multi-repo]

# Dependency graph
requires:
  - phase: 38-01
    provides: "--project-from-cwd CLI flag implementation"
provides:
  - "User-scope MCP registration documentation"
  - "Single-registration pattern for multi-repo support"
  - "Troubleshooting for unindexed projects and stale indexes"
affects: [onboarding, mcp-setup, user-documentation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single registration via --scope user for multi-repo MCP access"
    - "User-friendly error messaging with actionable commands"

key-files:
  created: []
  modified:
    - README.md

key-decisions:
  - "Position single-registration as recommended, per-project as alternative"
  - "Document both CLI and JSON config patterns for Claude Code and Desktop"
  - "Include git+https pattern for uvx users installing from GitHub"

patterns-established:
  - "Error messages include exact command to fix the issue"
  - "Staleness threshold of 7 days for index warnings"

# Metrics
duration: 5min
completed: 2026-02-05
---

# Phase 38 Plan 02: Multi-Repo MCP Documentation Summary

**User-scope MCP registration documentation with --project-from-cwd for Claude Code/Desktop enabling single-registration multi-repo search**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-05T19:16:40Z
- **Completed:** 2026-02-05T19:21:40Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Documented single-registration MCP pattern as primary recommendation
- Added Claude Code and Claude Desktop configuration examples with --project-from-cwd
- Created troubleshooting section for "Index not found" and "Index may be stale" errors
- Updated table of contents with new sections

## Task Commits

Each task was committed atomically:

1. **Task 1: Document single-registration MCP pattern in README** - `835fc9d` (docs)
2. **Task 2: Add troubleshooting for unindexed project errors** - `0df472f` (docs)

## Files Created/Modified

- `README.md` - Added single-registration documentation and troubleshooting section

## Decisions Made

- **Single-registration as recommended:** Positioned user-scope registration as primary pattern for most users
- **Per-project as alternative:** Kept existing documentation but relabeled for CI/CD and Docker use cases
- **Error message format:** Used exact error text users will see with copy-paste ready solutions

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Documentation complete for --project-from-cwd feature
- Users can now register CocoSearch once and use across all projects
- Ready for Phase 38-03 (implementing project auto-detection in MCP tools)

---
*Phase: 38-multi-repo-mcp-support*
*Completed: 2026-02-05*
