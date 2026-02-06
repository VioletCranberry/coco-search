---
phase: 41-workflow-skills
verified: 2026-02-06T10:50:00Z
status: passed
score: 7/7 must-haves verified
re_verification: false
---

# Phase 41: Workflow Skills Verification Report

**Phase Goal:** Users have multi-step workflow guidance for common tasks
**Verified:** 2026-02-06T10:50:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Onboarding workflow skill guides users through understanding a new codebase step-by-step | ✓ VERIFIED | skills/coco-onboarding/SKILL.md exists with 162 lines, contains multi-step workflow (pre-flight → architecture overview → layer drill-down → patterns → optional summary) |
| 2 | Debugging workflow skill guides users through finding root cause of issues | ✓ VERIFIED | skills/coco-debugging/SKILL.md exists with 298 lines, contains systematic root cause workflow (symptom analysis → wide-net search → adaptive trace → root cause + opt-in fixes) |
| 3 | Refactoring workflow skill guides users through safe code changes with impact analysis | ✓ VERIFIED | skills/coco-refactoring/SKILL.md exists with 313 lines, contains impact analysis workflow (dependency map → test coverage → downstream effects → ordered plan → execution gates) |
| 4 | Skills follow consistent multi-step format with clear when-to-use guidance | ✓ VERIFIED | All three skills have "Use when..." descriptions in frontmatter, multi-step structure, adaptive branching, and installation instructions |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `skills/coco-onboarding/SKILL.md` | Multi-step onboarding workflow with search_code, list_indexes, adaptive branching, summary generation | ✓ VERIFIED | 162 lines, contains 15 MCP tool refs, 19 adaptive branching phrases, 7 freshness/summary refs |
| `skills/coco-debugging/SKILL.md` | Multi-step debugging workflow with search_code, wide-net pattern, adaptive trace depth, opt-in fixes | ✓ VERIFIED | 298 lines, contains 17 MCP tool refs, 9 wide-net/trace refs, 5 opt-in/confirmation refs, 9 "root cause" mentions |
| `skills/coco-refactoring/SKILL.md` | Multi-step refactoring workflow with impact analysis, confirmation gates, leaf-first ordering | ✓ VERIFIED | 313 lines, contains 10 MCP tool refs, 27 impact/dependency/confirmation refs, 11 ordered/plan/step refs |

**All artifacts:** ✓ VERIFIED

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| coco-onboarding/SKILL.md | CocoSearch MCP tools | search_code, list_indexes, index_stats, index_codebase | ✓ WIRED | 15 tool references found, includes pre-flight checks, architecture search queries, pattern discovery |
| coco-debugging/SKILL.md | CocoSearch MCP tools | search_code, list_indexes, index_stats | ✓ WIRED | 17 tool references found, includes wide-net search pattern (semantic + symbol), adaptive trace depth |
| coco-refactoring/SKILL.md | CocoSearch MCP tools | search_code, list_indexes, index_stats | ✓ WIRED | 10 tool references found, includes usage search, test coverage search, downstream effects search |

**All key links:** ✓ WIRED

### Requirements Coverage

| Requirement | Status | Supporting Truths |
|-------------|--------|-------------------|
| DOC-01: Create onboarding workflow skill (multi-step) | ✓ SATISFIED | Truth 1, 4 — onboarding skill exists with multi-step workflow, adaptive branching, "Use when" description |
| DOC-02: Create debugging workflow skill (multi-step) | ✓ SATISFIED | Truth 2, 4 — debugging skill exists with systematic root cause workflow, wide-net pattern, opt-in fixes |
| DOC-03: Create refactoring workflow skill (multi-step) | ✓ SATISFIED | Truth 3, 4 — refactoring skill exists with full impact analysis, confirmation gates, leaf-first ordering |

**All requirements:** ✓ SATISFIED

### Anti-Patterns Found

None. All three skills are well-formed, substantive, and follow consistent patterns.

### Detailed Verification

#### Skill 1: coco-onboarding/SKILL.md

**Level 1 (Existence):** ✓ VERIFIED
- File exists at skills/coco-onboarding/SKILL.md
- 162 lines (exceeds 100-line minimum)

**Level 2 (Substantive):** ✓ VERIFIED
- Valid YAML frontmatter with "Use when..." description
- Multi-step workflow: pre-flight → architecture → layers → patterns → summary
- Adaptive branching: 19 instances of conditional logic (web app vs CLI vs library)
- Auto-executes MCP tools: 15 search_code/list_indexes/index_stats/index_codebase references
- Summary document generation with freshness marker: 7 references to staleness/freshness/CODEBASE_OVERVIEW
- No stub patterns or TODO comments

**Level 3 (Wired):** ✓ VERIFIED
- References CocoSearch MCP tools throughout workflow
- Includes specific query examples with parameters
- Installation instructions for Claude Code and OpenCode (8 path references)

#### Skill 2: coco-debugging/SKILL.md

**Level 1 (Existence):** ✓ VERIFIED
- File exists at skills/coco-debugging/SKILL.md
- 298 lines (exceeds 100-line minimum)

**Level 2 (Substantive):** ✓ VERIFIED
- Valid YAML frontmatter with "Use when..." description (debugging errors, tracing flows)
- Multi-step workflow: pre-flight → symptom → wide-net → adaptive trace → root cause
- Wide-net search pattern: 9 references to combining semantic + symbol search, simultaneous execution
- Adaptive trace depth: starts with one hop, checkpoints with user before expanding
- Opt-in fix suggestions: 5 "Want me to suggest a fix?" / confirmation phrases, NOT auto-suggested
- Root cause focus: 9 mentions of "root cause" throughout
- No stub patterns or TODO comments

**Level 3 (Wired):** ✓ VERIFIED
- References CocoSearch MCP tools throughout: 17 tool references
- Includes specific query examples (semantic, symbol_name, symbol_type, language filtering)
- Installation instructions for Claude Code and OpenCode (4 path references)

#### Skill 3: coco-refactoring/SKILL.md

**Level 1 (Existence):** ✓ VERIFIED
- File exists at skills/coco-refactoring/SKILL.md
- 313 lines (exceeds 100-line minimum)

**Level 2 (Substantive):** ✓ VERIFIED
- Valid YAML frontmatter with "Use when..." description (planning refactoring, extracting, renaming, splitting)
- Multi-step workflow: pre-flight → goal → impact analysis → plan → execute
- Impact analysis: 27 references to impact/dependency/downstream/confirmation/leaf-first
- Full dependency map: usages + test coverage + downstream effects
- Ordered plan: 11 references to ordered/plan/step-by-step execution
- Confirmation gates: user confirmation required before every code change
- Leaf-first ordering: callees before callers for safety
- No stub patterns or TODO comments

**Level 3 (Wired):** ✓ VERIFIED
- References CocoSearch MCP tools throughout: 10 tool references
- Includes specific query examples (use_hybrid_search, symbol_name globs, smart_context)
- Installation instructions for Claude Code and OpenCode (4 path references)

### Consistency Verification

All three skills follow the same format pattern:

1. **Frontmatter:** YAML with `name` and `description` (starts with "Use when...")
2. **Multi-step workflow:** Pre-flight check → multiple adaptive steps → outcome
3. **Adaptive branching:** Conditional logic based on discoveries, not rigid linear steps
4. **Auto-execute MCP tools:** Skills instruct Claude to call CocoSearch directly
5. **User control:** Checkpoints and confirmations throughout (debugging: trace depth, refactoring: every change)
6. **Installation section:** Both Claude Code and OpenCode paths

**Consistency check:** ✓ PASSED

### Must-Haves Verification Summary

From PLAN frontmatter must_haves:

**Onboarding (41-01):**
- ✓ Guides users through understanding codebase step-by-step
- ✓ Starts with architecture overview (entry points, modules, organization)
- ✓ Drills into key layers with code examples
- ✓ Offers to index if no CocoSearch index exists
- ✓ Optionally generates summary document with freshness marker
- ✓ Auto-executes searches without manual triggering
- ✓ Uses adaptive branching (not rigid linear)

**Debugging (41-02):**
- ✓ Guides users through finding root cause
- ✓ Accepts error message, stack trace, or behavior description
- ✓ Casts wide net first: semantic + symbol search combined
- ✓ Adaptive trace depth: one hop first, ask before going deeper
- ✓ Defaults to locating root cause, asks before suggesting fixes (opt-in)
- ✓ Auto-executes searches without manual triggering
- ✓ Uses adaptive branching based on findings

**Refactoring (41-03):**
- ✓ Guides users through safe code changes with impact analysis
- ✓ Accepts refactoring goal description
- ✓ Impact analysis produces full dependency map (usages + tests + downstream)
- ✓ Produces ordered refactoring plan (leaf-first)
- ✓ Executes step-by-step with user confirmation before each change
- ✓ Auto-executes searches without manual triggering
- ✓ Uses adaptive branching based on impact level

**Overall:** 7/7 success criteria verified

---

## Verification Complete

**Status:** passed
**Score:** 7/7 must-haves verified

All must-haves verified. Phase goal achieved. Ready to proceed.

### Summary

Phase 41 successfully delivered three comprehensive workflow skills:

1. **coco-onboarding**: Guides users through understanding new codebases with adaptive architecture discovery
2. **coco-debugging**: Guides systematic root cause analysis with wide-net search and adaptive tracing
3. **coco-refactoring**: Guides safe refactoring with full impact analysis and confirmation gates

All skills follow consistent patterns, auto-execute CocoSearch MCP tools, use adaptive branching, and provide clear when-to-use guidance. Requirements DOC-01, DOC-02, and DOC-03 are fully satisfied.

---
_Verified: 2026-02-06T10:50:00Z_
_Verifier: Claude (gsd-verifier)_
