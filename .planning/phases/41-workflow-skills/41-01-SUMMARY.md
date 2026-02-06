---
phase: 41-workflow-skills
plan: 01
subsystem: skills
tags: [cocosearch, mcp, onboarding, workflow, semantic-search]

# Dependency graph
requires:
  - phase: 40-code-cleanup
    provides: Clean codebase foundation
provides:
  - Codebase onboarding workflow skill for CocoSearch
  - Adaptive architecture discovery workflow
  - Pattern and convention exploration workflow
affects: [user-documentation, skill-distribution]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Adaptive workflow branching based on discovered codebase characteristics"
    - "Staleness detection with >7 day threshold for index freshness"
    - "Optional artifact generation with freshness markers"

key-files:
  created:
    - skills/coco-onboarding/SKILL.md
  modified: []

key-decisions:
  - "Use 'Use when...' trigger description format for skill discovery"
  - "Auto-execute MCP tools without requiring user CLI commands"
  - "Adaptive branching (web app vs CLI vs library) based on entry point discovery"
  - "Staleness threshold of 7 days for suggesting reindex"
  - "Optional CODEBASE_OVERVIEW.md with date and index version for freshness tracking"
  - "Conversational tone like senior developer walkthrough (not documentation-style)"

patterns-established:
  - "Skill workflows guide Claude through multi-step explorations with adaptive branching"
  - "Pre-flight checks validate tool readiness before beginning workflow"
  - "Synthesized summaries presented to users instead of raw search results"

# Metrics
duration: 2min
completed: 2026-02-06
---

# Phase 41 Plan 01: Workflow Skills Summary

**Adaptive codebase onboarding workflow using CocoSearch semantic search with staleness detection, layer drill-down, and optional summary generation**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-06T09:44:58Z
- **Completed:** 2026-02-06T09:46:35Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Created onboarding workflow skill guiding users through unfamiliar codebases step-by-step
- Implemented pre-flight index check with staleness detection (>7 days triggers reindex suggestion)
- Built adaptive architecture discovery branching on codebase type (web app, CLI, library, service)
- Designed layer drill-down workflow (API, business logic, data) with smart context for code examples
- Added pattern discovery for error handling, testing, and configuration conventions
- Included optional CODEBASE_OVERVIEW.md generation with freshness markers (date + index version)
- Auto-executes CocoSearch MCP tools without manual user CLI commands
- Conversational senior developer walkthrough tone throughout

## Task Commits

Each task was committed atomically:

1. **Task 1-2: Create and validate onboarding workflow skill** - `4e3e520` (feat)

**Plan metadata:** (pending final commit)

## Files Created/Modified
- `skills/coco-onboarding/SKILL.md` - Adaptive workflow skill for codebase onboarding using CocoSearch (162 lines)

## Decisions Made

**Skill description format:**
- Used "Use when..." trigger pattern to indicate when Claude should activate this skill
- Focused on triggering condition (onboarding to unfamiliar codebase) not workflow steps

**Auto-execution design:**
- Skill instructs Claude to execute CocoSearch MCP tools directly
- No user CLI commands required - Claude calls search_code(), list_indexes(), index_stats(), index_codebase()

**Adaptive branching:**
- Workflow branches based on discovered codebase characteristics
- Web app → routes/handlers, CLI → commands, library → public API, service → endpoints
- Not rigid numbered steps - adapts to what searches find

**Staleness detection:**
- 7-day threshold for suggesting reindex
- index_stats() provides staleness_days metric
- User asked if they want to reindex when stale

**Summary document:**
- Optional CODEBASE_OVERVIEW.md generation
- Includes freshness marker: date generated + index name + index last updated
- Helps future readers know when to regenerate

**Tone:**
- Conversational like senior developer giving a tour
- Second person imperative ("I'll search for...", "I'll show you...")
- Not documentation-style or formal

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

Skill installation is optional and documented in the skill itself (copy to ~/.claude/skills/ or ~/.config/opencode/skills/).

## Next Phase Readiness

- Onboarding workflow skill ready for distribution and use
- Pattern established for future workflow skills (pre-flight checks, adaptive branching, auto-execution)
- No blockers for next phase

---
*Phase: 41-workflow-skills*
*Completed: 2026-02-06*

## Self-Check: PASSED
