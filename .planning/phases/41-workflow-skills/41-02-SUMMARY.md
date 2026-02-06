---
phase: 41-workflow-skills
plan: 02
subsystem: developer-experience
tags: [cocosearch, mcp, debugging, workflow, claude-code, skills]

# Dependency graph
requires:
  - phase: 41-01
    provides: "CocoSearch onboarding skill with installation and usage patterns"
provides:
  - "Debugging workflow skill that guides systematic root cause analysis"
  - "Wide-net search pattern combining semantic + symbol search"
  - "Adaptive trace depth with user checkpoints"
  - "Opt-in fix suggestions based on codebase patterns"
affects: [documentation, user-workflows, debugging-patterns]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wide-net debugging: combine semantic search (symptom) with symbol search (identifiers)"
    - "Adaptive trace depth: one hop first, ask before expanding"
    - "Root cause first, fix suggestions opt-in"
    - "Pre-flight index health check before debugging session"

key-files:
  created:
    - skills/coco-debugging/SKILL.md
  modified: []

key-decisions:
  - "Combine semantic + symbol search in same step for richer context (not sequential)"
  - "Default to one-hop trace depth, expand only on user request"
  - "Fix suggestions are opt-in only - skill focuses on root cause identification"
  - "Pre-flight index health check warns about stale indexes before debugging"

patterns-established:
  - "Wide-net pattern: Run semantic search (query) + symbol search (symbol_name) simultaneously, synthesize overlapping results as strongest leads"
  - "Adaptive tracing: Present one-hop view (callers/callees), checkpoint with user before expanding to next level"
  - "Fix suggestion from patterns: Search codebase for correct implementations before suggesting fixes"

# Metrics
duration: 2min
completed: 2026-02-06
---

# Phase 41 Plan 02: Debugging Workflow Skill Summary

**Systematic debugging workflow combining semantic search for symptoms with symbol search for identifiers, adaptive call chain tracing, and opt-in fix suggestions**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-06T09:45:45Z
- **Completed:** 2026-02-06T09:47:55Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Created debugging workflow skill with 4-step systematic process (pre-flight, symptom analysis, wide-net search, adaptive trace, root cause)
- Implemented wide-net search pattern combining semantic and symbol searches simultaneously for strongest leads
- Established adaptive trace depth starting with one hop and expanding only on user request
- Added advanced debugging patterns: symbol type filtering, language filtering, wildcard symbol names, context expansion
- Included installation instructions for both Claude Code and OpenCode

## Task Commits

Each task was committed atomically:

1. **Task 1: Create debugging workflow skill** - `3eefdd2` (feat)

**Plan metadata:** `8097b00` (docs: complete plan)

## Files Created/Modified

- `skills/coco-debugging/SKILL.md` - Debugging workflow skill with systematic root cause analysis using CocoSearch

## Decisions Made

**1. Wide-net search combines semantic + symbol in same step**
- Rationale: Running both searches simultaneously and synthesizing overlapping results produces stronger leads than sequential searching
- Implementation: Step 2 runs `search_code(query=symptom)` + `search_code(symbol_name=identifier*)` in parallel, identifies files appearing in both

**2. Adaptive trace depth defaults to one hop**
- Rationale: Most debugging doesn't require full call graph. Start shallow, go deeper only when needed.
- Implementation: Step 3 finds immediate callers/callees, presents view, asks "Want me to trace deeper?" before expanding

**3. Fix suggestions are opt-in only**
- Rationale: Skill's core value is identifying root cause. Forcing fix suggestions dilutes focus.
- Implementation: Step 4 presents root cause clearly, asks "Want me to suggest a fix?" before searching for patterns

**4. Pre-flight index health check**
- Rationale: Stale indexes lead to frustrating debugging experiences with outdated results
- Implementation: Pre-flight step checks `index_stats()` for staleness, warns if >7 days old, offers to reindex

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for next plan.** Debugging workflow skill provides systematic approach to root cause analysis using CocoSearch. Combined with onboarding skill from 41-01, users now have comprehensive CocoSearch workflow guidance.

**Potential next skills:**
- Code exploration workflow (understanding unfamiliar codebases)
- Refactoring workflow (finding all usages before changing)
- Feature implementation workflow (finding similar patterns to follow)

## Self-Check: PASSED

All files and commits verified:
- ✓ skills/coco-debugging/SKILL.md
- ✓ Commit 3eefdd2

---
*Phase: 41-workflow-skills*
*Completed: 2026-02-06*
