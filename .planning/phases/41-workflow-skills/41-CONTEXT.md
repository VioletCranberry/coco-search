# Phase 41: Workflow Skills - Context

**Gathered:** 2026-02-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Create three multi-step workflow skills that guide users through common developer tasks using CocoSearch: onboarding to a new codebase, debugging issues, and refactoring code safely. Skills are delivered as Claude Code skill files (.md) with installation instructions for Claude Code and OpenCode.

</domain>

<decisions>
## Implementation Decisions

### Skill step structure
- Adaptive branching flow — each skill starts with step 1, then branches based on what was found (not rigid linear)
- Skills auto-execute CocoSearch searches at each step and present results to user (no manual search triggering)
- Each skill has domain-specific structure tailored to its task (not a shared template)
- Delivered as Claude Code skill files (.md) in the repo with installation instructions for Claude Code and OpenCode

### Onboarding skill flow
- Starts with architecture overview — search for entry points, main modules, codebase organization (10,000ft view)
- After overview, drills into key architectural layers (API, business logic, data) with code examples from the codebase
- If no CocoSearch index exists, offer to run indexing as the first step before starting the onboarding flow
- Optionally generates a summary document at the end — ask user if they want it
- Summary doc includes a date/index-version marker so user can tell if it's stale

### Debugging skill flow
- Entry point: user provides an error message, stack trace, or description of unexpected behavior
- First action: cast wide net — semantic search for the symptom AND symbol search for any mentioned identifiers, then synthesize
- Trace depth is adaptive — start with one hop (error origin + immediate callers/callees), present findings, offer to trace deeper
- Default to locating root cause, then ask "Want me to suggest a fix?" — doesn't force fix suggestions

### Refactoring skill flow
- Entry point: user describes refactoring goal ("extract this into a service", "rename across codebase", "split this module")
- Impact analysis is full dependency map: all usages + test coverage + downstream effects
- Produces a step-by-step refactoring plan (ordered changes to make safely)
- Can execute each step with user confirmation before each change (not plan-only)

### Claude's Discretion
- Exact branching logic within each skill
- How to present search results at each step (summarized vs raw)
- Skill file naming conventions
- How to detect whether CocoSearch index exists/is stale
- Specific CocoSearch queries to use at each step

</decisions>

<specifics>
## Specific Ideas

- Skills should feel like having a senior developer walk you through the codebase/problem — not like reading docs
- Onboarding summary doc freshness: include index timestamp or version so user knows when to re-run
- Debugging should combine semantic search + symbol filtering in the same step for richer context
- Refactoring execution: each step gets user confirmation, so user stays in control of actual code changes

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 41-workflow-skills*
*Context gathered: 2026-02-06*
