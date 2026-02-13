---
name: cocosearch-new-feature
description: Use when adding new functionality — a new command, endpoint, module, handler, or capability. Guides placement, pattern matching, and integration using CocoSearch.
---

# Add New Features with CocoSearch

A systematic workflow for adding new code to an existing codebase. This skill uses semantic search to find existing patterns, conventions, and integration points so the new feature fits naturally into the project architecture.

**Philosophy:** New code should look like it was always there. Search the codebase for existing patterns before writing anything.

## Pre-flight Check

Before adding any feature, verify the index is healthy and current.

1. **Check for project config first:** Look for `cocosearch.yaml` in the project root. If it exists and has an `indexName` field, use that as the index name for all subsequent operations.
2. **Check available indexes:** Run `list_indexes()` to confirm the project is indexed.
3. **Check index freshness:** Run `index_stats(index_name="<configured-name>")` to get staleness information.
   - If index is stale (>7 days old), warn: "Index is X days old — I may miss recent patterns. Want me to reindex first?"
   - If no index exists, offer to run `index_codebase(path="<project-root>", index_name="<configured-name>")`.

## Step 1: Understand the Feature

Parse the user's request to identify what needs to be built and where it fits.

**Extract from the request:**

- **What:** The new capability (e.g., "a CLI command to export stats as CSV")
- **Where:** The subsystem it belongs to (e.g., CLI layer, API layer, indexer, search)
- **Interface:** How users/code will interact with it (e.g., CLI flag, function call, MCP tool, API endpoint)

**Classify the feature type:**

- **New command/endpoint:** Adds a new entry point (CLI subcommand, MCP tool, API route)
- **New module:** Adds a new subsystem or service (e.g., new handler, new search strategy)
- **Extension:** Adds capability to an existing module (e.g., new flag, new option, new format)
- **Cross-cutting:** Touches multiple subsystems (e.g., new data field flowing from indexer to search to output)

**Confirm with user:** "I understand you want to add [feature]. It fits as a [type] in the [subsystem] layer. Is that right?"

## Step 2: Find Existing Patterns

This is the most important step. Search for how similar things are already built. New code should follow established conventions.

### 2a. Find the Closest Analog

Every feature has a precedent. Search for the most similar existing implementation.

**Semantic search for similar functionality:**

```
search_code(
    query="<description of what the feature does>",
    use_hybrid_search=True,
    smart_context=True,
    limit=10
)
```

**Search for the subsystem's existing entry points:**

```
search_code(
    query="<subsystem> command handler endpoint",
    symbol_type=["function", "class"],
    use_hybrid_search=True,
    smart_context=True
)
```

**Find the registration/wiring pattern:**

How are existing features registered? Search for the glue code:

```
search_code(
    query="register add route subcommand handler",
    use_hybrid_search=True,
    smart_context=True,
    limit=10
)
```

**Present the analog:** "The closest existing feature to what you want is [analog] in `file:line`. Here's how it's structured: [brief description]. I'll use this as the template."

### 2b. Extract the Convention

From the analog and broader search, identify the project's conventions:

**File placement — where does new code go?**

```
search_code(
    query="<subsystem-name>",
    symbol_type="class",
    use_hybrid_search=True,
    limit=15
)
```

Look at the file paths in results. Is there a clear directory structure? (e.g., `handlers/*.py`, `commands/*.py`, `routes/*.py`)

**Naming conventions — what do things get called?**

```
search_code(
    query="<similar-feature-type>",
    symbol_name="*<pattern>*",
    use_hybrid_search=True
)
```

Look for naming patterns: `cmd_*`, `handle_*`, `test_*`, `*Handler`, `*Service`.

**Interface patterns — how are features exposed?**

```
search_code(
    query="<interface-type> definition",
    use_hybrid_search=True,
    smart_context=True
)
```

Look for: argument parsing patterns, decorator usage, protocol/interface definitions, configuration patterns.

**Testing patterns — how are similar features tested?**

```
search_code(
    query="test <analog-feature>",
    symbol_name="test_*<analog>*",
    symbol_type="function",
    use_hybrid_search=True
)
```

Identify: test file location, fixture usage, mocking patterns, assertion style.

**Present conventions:**

```
Conventions for [subsystem]:
- Files go in: src/<module>/<subsystem>/
- Naming: <verb>_<noun> for functions, <Noun><Role> for classes
- Registration: via <mechanism> in <file>
- Tests go in: tests/unit/<subsystem>/test_<feature>.py
- Test pattern: [mock X, call Y, assert Z]
```

### 2c. Map Integration Points

Find where the new feature needs to connect to existing code.

**Find imports/dependencies the feature will need:**

```
search_code(
    query="<analog-feature> import dependency",
    use_hybrid_search=True,
    smart_context=True
)
```

**Find where the feature needs to be registered/wired:**

```
search_code(
    query="<registration-mechanism>",
    symbol_name="<registration-function>*",
    use_hybrid_search=True,
    smart_context=True
)
```

**Find shared utilities or helpers the feature should reuse:**

```
search_code(
    query="<operation the feature needs> utility helper",
    use_hybrid_search=True,
    limit=10
)
```

**Present integration points:**

```
Integration points:
1. Register in: <file>:<line> (add to <mechanism>)
2. Import from: <module> (for <dependency>)
3. Reuse: <utility> from <file> (don't reinvent)
4. Expose via: <interface> in <file>
```

## Step 3: Design the Feature

Using the patterns, conventions, and integration points found, produce a concrete implementation plan.

**Plan structure:**

```
Feature: [name]
Analog: [closest existing feature] in [file]

New files:
  - src/<path>/<feature>.py — [purpose]
  - tests/unit/<path>/test_<feature>.py — [what it tests]

Modified files:
  - <file> — [what changes: add import, register command, wire route]
  - <file> — [what changes]

Implementation order:
  1. Create <new-file> with <core-logic> (modeled on <analog>)
  2. Add tests in <test-file> (modeled on <analog-tests>)
  3. Wire into <registration-file>
  4. Update <config/docs> if needed

Key decisions:
  - [Decision 1: e.g., "Use existing FooService rather than creating new one"]
  - [Decision 2: e.g., "Follow handler autodiscovery pattern — no manual registration needed"]
```

**Present to user:** "Here's the plan based on existing patterns. Ready to implement, or want to adjust?"

**Handle adjustments:** If user wants changes, update the plan and re-present.

## Step 4: Implement with Pattern Matching

For each step in the plan, implement by closely following the analog.

**For each file to create/modify:**

1. **Show the analog code:**

   ```
   search_code(
       query="<analog-function>",
       symbol_name="<analog-function>",
       use_hybrid_search=True,
       smart_context=True
   )
   ```

   "Here's the existing pattern I'm following from `<analog-file>`:"

2. **Write the new code modeled on the analog.** Match:
   - Function signatures and return types
   - Error handling patterns
   - Logging conventions
   - Docstring format
   - Import style

3. **Show the change and request confirmation:**

   ```
   New file: <path>
   Based on: <analog-file>

   [code]

   Proceed? (yes/no/adjust)
   ```

4. **After creating the core code, write tests:**
   - Follow the analog's test pattern exactly
   - Same fixture usage, same assertion style
   - Cover the same categories: happy path, error cases, edge cases

5. **Wire the feature in:**
   - Add to registration mechanism
   - Update imports
   - Add to any manifests, configs, or __init__.py exports

## Step 5: Verify Integration

After all code is written, verify the feature integrates correctly.

**Run the tests:**

```
[project-specific test command for the new test file]
```

**Check for import/lint issues:**

```
[project-specific lint command]
```

**Verify registration:**

If the feature should appear in help text, command lists, or API docs, check that it does.

**Present results:**

```
Feature implementation complete!

Created:
  - <new-file-1> — [description]
  - <new-file-2> — [description]

Modified:
  - <file> — [what changed]

Tests: [PASS/FAIL]
Lint: [PASS/FAIL]

Based on patterns from: <analog-feature>

Recommended next steps:
1. Try it out: [example usage command]
2. Run full test suite: [command]
3. Commit: git add <files> && git commit -m "feat: <description>"
```

**If tests fail:**

- STOP and show failures
- Search for how the analog handles the same scenario
- Fix and re-run
- Ask user before proceeding if fix is non-obvious

## Key Design Principles

**Pattern-first development.** Always find the analog before writing code. The codebase IS the specification for how new code should look.

**Use hybrid search everywhere.** Feature development involves both concept searches ("how does authentication work") and identifier searches ("find AuthService"). Hybrid search covers both.

**Use `smart_context=True` for analogs.** You need full function/class bodies to properly replicate patterns, not truncated snippets.

**Reuse, don't reinvent.** Before creating any utility, helper, or abstraction, search for existing ones. Duplicating functionality creates maintenance burden.

**Match conventions exactly.** If existing functions use `snake_case`, don't introduce `camelCase`. If existing tests use `pytest.fixture`, don't use `setUp/tearDown`. Consistency matters more than personal preference.

**Test analog first.** Find how the closest feature is tested before writing your own tests. Match the coverage level, fixture pattern, and assertion style.

**Wire last.** Create the core code and tests first. Registration and wiring are the final step — they're easy to do but hard to undo if the core design changes.

## Installation

**Claude Code (project-local):**

```bash
mkdir -p .claude/skills
ln -sfn ../../skills/cocosearch-new-feature .claude/skills/cocosearch-new-feature
```

**Claude Code (global):**

```bash
mkdir -p ~/.claude/skills/cocosearch-new-feature
cp skills/cocosearch-new-feature/SKILL.md ~/.claude/skills/cocosearch-new-feature/SKILL.md
```

**OpenCode:**

```bash
mkdir -p ~/.config/opencode/skills/cocosearch-new-feature
cp skills/cocosearch-new-feature/SKILL.md ~/.config/opencode/skills/cocosearch-new-feature/SKILL.md
```

After installation, restart your AI coding assistant or run the skill activation command for your platform.
