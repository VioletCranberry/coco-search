---
name: cocosearch-refactoring
description: Use when planning a refactoring, extracting code into a new module, renaming across the codebase, or splitting a large file. Guides impact analysis and safe step-by-step execution using CocoSearch.
---

# CocoRefactoring Skill

A systematic workflow for safe code refactoring. This skill guides you through complete impact analysis using semantic search, then executes changes step-by-step with your confirmation at each gate.

**Philosophy:** Refactoring on incomplete information is risky. This workflow ensures you see the full picture before touching any code.

## Pre-flight Check

1. Read `cocosearch.yaml` for `indexName` (critical -- use this for all operations)
2. `list_indexes()` to confirm project is indexed
3. `index_stats(index_name="<configured-name>")` to check freshness
- No index → indexing is REQUIRED. Refactoring needs 100% accurate dependency data.
- Stale (>7 days) → **strongly recommend reindexing**. Stale data can miss critical dependencies.

## Step 1: Understand the Refactoring Goal

Parse the user's description to identify the refactoring type and target.

**Common refactoring types:**

- **Extract:** Move code into new module/service/class
- **Rename:** Change symbol name across codebase (function, class, variable)
- **Split:** Break large file into smaller focused files
- **Move:** Relocate code between existing modules
- **Signature change:** Modify function/method interface or API contract

**Identify the target:**

- Which file(s) contain the code being refactored?
- Which symbol(s) are the primary focus? (function name, class name, module name)
- What is the current scope? (single file, module, cross-cutting concern)

**Confirm with user:** "I understand you want to [refactoring type] [target symbol/file]. Is this correct?"

## Step 2: Impact Analysis (Full Dependency Map)

This is the most critical step. Build a complete picture of what will be affected by the change.

### 2a. Dependency Graph Analysis (Fast Path)

**Start here.** If the project has a dependency index (`cocosearch index . --deps`), use the dependency MCP tools for instant, complete impact analysis:

**Forward dependencies (what does the target depend on):**

```
get_file_dependencies(file="<target_file>", depth=2)
```

**Reverse impact (what depends on the target):**

```
get_file_impact(file="<target_file>", depth=3)
```

These tools return transitive dependency/impact trees — far more complete than search-based heuristics. The impact tree shows the full blast radius of changing a file.

**If dependency tools return results:** You already have the complete impact map. Skip to 2b (test coverage) and use the dependency data as your primary source. The search-based approaches below become supplementary.

**If dependency tools are unavailable** (no deps index, or the file isn't tracked): Fall back to the search-based approaches below.

### 2a-fallback. Find All Usages (Search-Based)

**Direct symbol references:**

```
search_code(
    query="<target_symbol>",
    symbol_name="<target_symbol>*",
    use_hybrid_search=True,
    smart_context=True
)
```

Use glob patterns in `symbol_name` to catch variants. For example:

- Target: "User" → `symbol_name="User*"` finds User, UserProfile, UserService, UserRepository
- Target: "authenticate" → `symbol_name="authenticate*"` finds authenticate, authenticate_user, authenticate_request

**Import references (Python):**

```
search_code(query="import <target_module>", use_hybrid_search=True)
search_code(query="from <target_module> import", use_hybrid_search=True)
```

**Import references (JavaScript/TypeScript):**

```
search_code(query="import { <target_symbol> }", use_hybrid_search=True)
search_code(query="from '<target_module>'", use_hybrid_search=True)
```

**Include references (C/C++):**

```
search_code(query="#include \"<target_file>\"", use_hybrid_search=True)
```

### 2b. Find Test Coverage

**Test files referencing target:**

```
search_code(
    query="test <target_symbol>",
    symbol_name="test_*<target>*",
    symbol_type="function",
    use_hybrid_search=True
)
```

**Filter results to test directories:** Look for paths containing `test_/`, `tests/`, `__tests__/`, `spec/`.

**Coverage assessment:**

- High coverage: Multiple test files, integration + unit tests
- Medium coverage: Some test files, unit tests only
- Low coverage: Few or no tests found
- Risk indicator: No tests = high refactoring risk

### 2c. Find Downstream Effects

For each caller found in step 2a, check what THEY export or provide. Changing your target will affect their behavior.

**With dependency tools (preferred):** If you have the impact tree from step 2a, depth=2+ already shows transitive downstream effects. Each level of the tree represents one hop of propagation.

**With search (fallback):**

```
search_code(
    query="<caller_function>",
    symbol_name="<caller>*",
    use_hybrid_search=True,
    smart_context=True
)
```

Look for:

- Public API exports (appears in `__all__`, `export`, `public`)
- Used by other modules (appears in other search results)
- External interfaces (API routes, CLI commands, event handlers)

### 2d. Present the Dependency Map

**Format:**

```
Target: [symbol/file name]
Direct usages: N files
  - file1.py:123 (in function X)
  - file2.py:456 (in class Y)
  - ...

Test coverage: M test files
  - test_feature.py (unit tests for X)
  - test_integration.py (integration tests)
  - Coverage assessment: [High/Medium/Low]

Downstream effects:
  - Caller A (file3.py) is a public API route → affects external consumers
  - Caller B (file4.py) is used by 5 other modules → cascade risk
  - ...

Risk assessment: [LOW/MEDIUM/HIGH]
  - LOW: 1-3 usages, high test coverage, no public APIs affected
  - MEDIUM: 4-10 usages, medium test coverage, internal-only changes
  - HIGH: 10+ usages, low test coverage, OR affects public APIs
```

### 2e. Branch Based on Impact

**Low impact (proceed):**

- Show dependency map
- Move directly to Step 3 (generate plan)

**Medium impact (confirm scope):**

- Show dependency map with details
- Ask: "This affects N files and M tests. Proceed with full refactoring, or want to reduce scope?"
- Wait for user confirmation

**High impact (warn + suggest incremental):**

- Show dependency map with warning
- Suggest: "High-impact change detected. Consider incremental approach:"
  - Phase 1: Add new API alongside old (deprecate, don't remove)
  - Phase 2: Migrate callers one-by-one
  - Phase 3: Remove old API after full migration
- Ask: "Proceed with full refactoring, incremental migration, or abort?"

## Step 3: Generate Refactoring Plan

Produce an ordered list of changes for safe execution.

**Ordering principle: Leaf-first dependency order**

- Change callees before callers
- Create new code before modifying old
- Update imports after moving code
- Remove old code last

**Plan structure:**

```
Refactoring Plan for [target]
============================

Step 1: [Create new structure]
  File: [new_file.py]
  Action: Create new module with [extracted code]
  Reason: Establish new location before migration

Step 2: [Move/copy target code]
  File: [new_file.py]
  Action: Copy [target function/class] from [old_file.py]
  Reason: New code in place, old code still works (safe state)

Step 3: [Update leaf dependencies]
  Files: [file1.py, file2.py] (lowest-level callers)
  Action: Update imports from old_file to new_file
  Reason: Migrate leaf nodes first to prevent cascade failures

Step 4: [Update higher-level dependencies]
  Files: [file3.py, file4.py]
  Action: Update imports and refactor any API usage changes
  Reason: Work up dependency tree

Step 5: [Update tests]
  Files: [test_feature.py, test_integration.py]
  Action: Update imports, adjust test setup if needed
  Reason: Ensure tests pass before removing old code

Step 6: [Remove old code]
  File: [old_file.py]
  Action: Delete [target function/class]
  Reason: Final cleanup after successful migration

Step 7: [Verify]
  Action: Run full test suite
  Reason: Confirm no regressions
```

**Present to user:** "Here's the refactoring plan. Ready to execute step-by-step, or want to adjust?"

**Handle adjustments:** If user wants changes, update plan and re-present.

## Step 4: Execute with Confirmation Gates

For each step in the plan, execute with user confirmation.

**For each step:**

1. **Show what will change:**

   ```
   Step N: [step name]
   File: [filename]

   Changes:
   - [Line X]: Remove: import old_module
   - [Line Y]: Add: import new_module
   - [Line Z]: Change: old_function() → new_function()

   Preview:
   [Show before/after diff or code snippet]
   ```

2. **Request confirmation:** "Proceed with this change? (yes/no/skip)"
   - yes: Execute the change
   - no: Stop execution, return to plan adjustment
   - skip: Skip this step, continue to next

3. **Make the change:** Apply the modification using file editing tools

4. **Verify the change:**
   - If tests are available: "Running tests..."
   - Show test results (pass/fail)
   - If tests fail: STOP, show failures, ask how to proceed

5. **Commit the change (optional):** Ask if user wants to commit each step, or commit all at end

**After all steps:**

```
Refactoring complete!

Summary:
- N files modified
- M imports updated
- Tests: [PASS/FAIL]

Recommended next steps:
1. Run full test suite: [test command]
2. Manual verification: [areas to check]
3. Commit changes: git add [files] && git commit -m "refactor: [description]"
```

**If any step fails:**

- STOP execution immediately
- Show error details (test failures, syntax errors, etc.)
- Ask: "Fix this step and retry, skip this step, or abort refactoring?"
- Wait for user decision

## Key Design Principles

**Impact analysis is critical:** Spend time searching for all dependencies. Missing a usage creates bugs.

**Leaf-first ordering:** Prevents cascading import failures and broken intermediate states.

**User confirmation required:** Every code change requires explicit approval. User stays in control.

**Test early and often:** Suggest running tests after each change, not just at the end. Catch failures early.

**Safe intermediate states:** After each step, code should still compile/import (even if not fully migrated).

For common search tips (hybrid search, smart_context, symbol filtering), see `skills/README.md`.

For installation instructions, see `skills/README.md`.
