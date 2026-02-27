---
name: cocosearch-deps
description: Use when exploring dependency relationships, tracing file connections, analyzing change impact, or identifying hub files. Guides dependency graph exploration using CocoSearch.
---

# Dependency Graph Exploration with CocoSearch

A guided workflow for understanding how files connect through dependencies. Use this skill when the goal is specifically about dependency relationships — impact analysis, connection tracing, or hub identification.

**When to use this skill vs. others:**

| Goal | Skill |
|------|-------|
| "What breaks if I change X?" | **cocosearch-deps** (this skill) |
| "How does X work?" | cocosearch-explore |
| "I need to safely refactor X" | cocosearch-refactoring (uses deps as part of impact analysis) |
| "Trace this bug through call chains" | cocosearch-debugging (uses deps for call tracing) |
| "What are the most connected files?" | **cocosearch-deps** (this skill) |
| "How are X and Y connected?" | **cocosearch-deps** (this skill) |

## Pre-flight Check

1. Read `cocosearch.yaml` for `indexName` (critical -- use this for all operations)
2. `list_indexes()` to confirm project is indexed
3. Verify dependency index exists -- call `get_file_dependencies` on any known file:

```
get_file_dependencies(file="<any-known-file>", depth=1)
```

- **If results returned:** Dependency index is ready, proceed.
- **If error or empty:** Dependency index is missing. Offer:
  - "No dependency data found. Want me to extract dependencies? This requires running `index_codebase` with deps extraction or `cocosearch deps extract .` via CLI."
  - Do NOT proceed without dependency data -- this skill relies entirely on it.

## Step 1: Classify Intent

Parse the user's request to determine the exploration mode:

| User says... | Mode | Primary tool |
|--------------|------|-------------|
| "What breaks if I change X?" / "Impact of modifying X" | **Impact Analysis** | `get_file_impact` |
| "What does X depend on?" / "X's dependencies" | **Dependency Exploration** | `get_file_dependencies` |
| "How are X and Y connected?" / "Path between X and Y" | **Connection Tracing** | Both tools |
| "Most connected files" / "Hub files" / "Critical files" | **Hub Identification** | Both tools, multiple files |
| "Show only imports" / "What references X?" | **Type Filtering** | Either tool with `dep_type` |

**If ambiguous:** Ask the user which mode they want. Present the five options.

**Confirm with user:** "I'll run [mode] on `<file>`. Proceed?"

## Step 2a: Impact Analysis

**Goal:** Answer "what would be affected if this file changes?"

**Run the impact query:**

```
get_file_impact(file="<target_file>", depth=3)
```

**Format results as a tree:**

```
<target_file>
  <- <direct_dependent_1> (import)
     <- <transitive_dependent_A> (import)
  <- <direct_dependent_2> (reference)
  <- <direct_dependent_3> (import)
     <- <transitive_dependent_B> (import)
        <- <transitive_dependent_C> (import)
```

**Assess risk level:**

| Dependents | Risk | Recommendation |
|-----------|------|----------------|
| 0 | None | File is a leaf -- change freely |
| 1-5 | Low | Review each dependent before changing |
| 6-15 | Medium | Consider incremental changes; check test coverage |
| 16+ | High | High-impact hub -- coordinate changes carefully |

**Present summary:**
"Changing `<target_file>` directly affects N files and transitively affects M more. Risk level: [LOW/MEDIUM/HIGH]."

**Checkpoint:** Offer follow-up actions:
- "Want me to trace deeper (increase depth)?"
- "Want me to filter by dependency type (imports only, references only)?"
- "Want me to pull up the code for any of these dependents?"
- "Want to see the reverse -- what does this file depend ON?"

## Step 2b: Dependency Exploration

**Goal:** Answer "what does this file depend on?"

**Start shallow:**

```
get_file_dependencies(file="<target_file>", depth=1)
```

**Separate internal vs. external dependencies:**

```
Internal dependencies (within project):
  - src/module_a/utils.py (import)
  - src/module_b/models.py (import)

External/unresolved:
  - os (import, stdlib)
  - requests (import, third-party)
```

**Present summary:**
"`<target_file>` depends on N internal files and M external modules."

**Checkpoint:** Offer follow-up actions:
- "Want to see the transitive dependency tree (depth=3)?"
- "Want to check the impact direction -- what depends on this file?"
- "Want me to search for the code in any of these dependencies?"

**If user wants transitive tree:**

```
get_file_dependencies(file="<target_file>", depth=3)
```

Format as indented tree showing the full dependency chain.

## Step 2c: Connection Tracing

**Goal:** Answer "how are X and Y connected?"

**Multi-call orchestration:**

1. **Forward from X:**

```
get_file_dependencies(file="<file_X>", depth=3)
```

2. **Reverse from Y:**

```
get_file_impact(file="<file_Y>", depth=3)
```

3. **Check for overlap:** Compare the two result sets. Any file appearing in BOTH the forward tree from X and the reverse tree from Y is on the connection path.

**If structural path found:**
"Files X and Y are connected through: X -> A -> B -> Y (via import chains)."

Show the full path with edge types.

**If no structural path:**
"No direct dependency path found between X and Y."

Offer fallback:
- "Want me to try deeper traversal (increase depth)?"
- "Want me to search semantically for connections? Files may be related through shared concepts rather than direct imports."

```
search_code(
    query="<concept connecting X and Y>",
    use_hybrid_search=True,
    smart_context=True,
    include_deps=True
)
```

## Step 2d: Hub Identification

**Goal:** Find the most connected files in the project.

**Strategy:** Probe candidate files with both forward and reverse queries, then rank by total connections.

**Step 1: Identify candidates.** Good candidates include:
- Entry points (main files, CLI entrypoints, server files)
- Init files (`__init__.py`, `index.ts`, `mod.rs`)
- Config/model files (often imported by many modules)
- Files the user suspects are hubs

Ask the user: "Which files should I check, or want me to probe common entry points and init files?"

**Step 2: For each candidate, run both queries at depth=1:**

```
get_file_dependencies(file="<candidate>", depth=1)
get_file_impact(file="<candidate>", depth=1)
```

**Step 3: Present ranked table:**

```
| File | Depends On | Depended By | Total | Role |
|------|-----------|-------------|-------|------|
| src/core/models.py | 2 | 18 | 20 | Data hub (heavily imported) |
| src/cli.py | 12 | 1 | 13 | Orchestrator (imports many) |
| src/utils/helpers.py | 1 | 9 | 10 | Utility hub |
```

**Interpret roles:**
- **High "Depended By":** Data hubs, shared utilities -- changes here have wide impact
- **High "Depends On":** Orchestrators, entry points -- aggregate functionality
- **High both:** Central nodes -- critical to architecture, change with caution

**Checkpoint:** "Want me to run full impact analysis on any of these hubs?"

## Step 2e: Type Filtering

**Goal:** Filter dependencies by edge type for focused analysis.

**Edge types in CocoSearch:**

| Type | Meaning | Example |
|------|---------|---------|
| `import` | Code imports (Python `import`, JS `require`/`import`, Go `import`) | `from utils import helper` |
| `call` | Symbol-level calls | `helper.process()` |
| `reference` | Grammar-level references (metadata.kind for specifics) | Helm `chart_member`, `subchart_of` |

**Run filtered query:**

```
get_file_dependencies(file="<target_file>", depth=2, dep_type="import")
```

or

```
get_file_impact(file="<target_file>", depth=2, dep_type="import")
```

**Compare by type:** Run the same query with different `dep_type` values and present side-by-side:

```
Import dependencies:
  - module_a.py, module_b.py

Reference dependencies:
  - config.yaml (chart_member)
  - parent/Chart.yaml (subchart_of)
```

## Step 3: Follow-Up Actions

After completing any mode, offer these follow-ups:

- **Deeper trace:** "Increase depth to see more transitive connections?"
- **Code context:** "Pull up the actual code for any file using `search_code` with `include_deps=True`?"
- **Reverse direction:** "Check the opposite direction (impact -> dependencies or vice versa)?"
- **Cross-reference with search:** "Search for semantic connections beyond structural dependencies?"

```
search_code(
    query="<relevant concept>",
    use_hybrid_search=True,
    smart_context=True,
    include_deps=True
)
```

## Tips

- **Start shallow (depth=1), go deeper on request.** Deep traversals on hub files can return very large trees.
- **External dependencies are leaves.** They won't resolve to project files -- this is expected.
- **Cycle detection is built in.** The query layer handles circular dependencies automatically; you won't get infinite loops.
- **Combine with search for full understanding.** Dependencies show structural connections; search finds semantic relationships. Use both for a complete picture.
- **Dependency data requires extraction.** Unlike search (which works immediately after indexing), dependencies need explicit extraction via `--deps` flag or `deps extract` command.

For common search tips (hybrid search, smart_context, symbol filtering), see `skills/README.md`.

For installation instructions, see `skills/README.md`.
