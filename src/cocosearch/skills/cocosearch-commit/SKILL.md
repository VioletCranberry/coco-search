---
name: cocosearch-commit
description: Use when committing changes — analyzes staged (or unstaged) diffs with CocoSearch semantic search and dependency impact to generate comprehensive Conventional Commit messages. Reviews changes thoroughly, then asks user to approve, edit, or abort the commit.
---

# Smart Commit with CocoSearch

A structured workflow for generating comprehensive commit messages. Uses CocoSearch's semantic search and dependency analysis to understand what changed, why it matters, and what it affects — producing commit messages that go far beyond surface-level diff summaries.

**What this adds over generic commit message generators:**

- **Semantic understanding:** Knows what the changed code *does*, not just what lines changed
- **Blast radius awareness:** Flags when changes affect high-impact files with many dependents
- **Dependency context:** Understands what the changed code relies on
- **Cross-cutting synthesis:** Detects when changes span multiple subsystems and summarizes coherently
- **Conventional Commits:** Automatically determines type, scope, and breaking changes

## Pre-flight Check

1. Read `cocosearch.yaml` for `indexName` (critical -- use this for all operations)
2. `list_indexes()` to confirm project is indexed
3. `index_stats(index_name="<configured-name>")` to check freshness
   - No index -> warn: "No CocoSearch index found. I'll generate a commit message from diffs alone, but semantic analysis won't be available. Want me to index first?"
   - Stale (>7 days) -> warn: "Index is X days old -- semantic context may not reflect recent changes."
4. Check dependency freshness -- call `get_file_dependencies` on any known file:

   ```
   get_file_dependencies(file="<any-known-file>", depth=1)
   ```

   - **If response contains `warnings`** with type `deps_outdated` or `deps_branch_drift`:
     Note: "Dependency data is outdated -- impact analysis may be incomplete."
   - **If response contains `warnings`** with type `deps_not_extracted`:
     Note: "No dependency data found. Blast radius analysis will be skipped."
   - **If no warnings:** Proceed with full analysis.

## Step 1: Collect Changes

Determine what the user wants to commit.

### 1a. Check for Staged Changes

```bash
git diff --cached --stat
```

**If staged changes exist:** Use staged changes. Inform: "Analyzing N staged files (+X -Y lines)."

**If nothing is staged:** Fall back to unstaged changes:

```bash
git diff --stat
git ls-files --others --exclude-standard
```

Inform: "No staged changes found. Analyzing N unstaged/untracked files instead. I'll offer to stage them before committing."

### 1b. Get Full Diffs

**For staged changes:**

```bash
git diff --cached
```

**For unstaged fallback:**

```bash
git diff
```

For untracked files, read the file contents to understand what's being added.

### 1c. Handle Edge Cases

- **No changes at all** (clean working directory): "Working directory is clean. Nothing to commit." Stop.
- **Only untracked files:** Treat as new files. These will need `git add` before committing.
- **Binary files:** Note "binary file changed" in the file list. Skip CocoSearch analysis for these.
- **Submodule changes:** Note the submodule pointer change. Skip deep analysis.

## Step 2: Triage Changed Files

Categorize files to prioritize analysis effort.

| Priority | File types | Examples |
|----------|-----------|---------|
| **HIGH** | Source code | `.py`, `.js`, `.ts`, `.go`, `.rs`, `.java`, `.rb`, `.scala`, `.kt` |
| **MEDIUM** | Tests, config, CI/CD | `test_*.py`, `*.test.ts`, `*.yaml`, `Dockerfile`, `.github/workflows/` |
| **LOW** | Docs, changelog, assets | `.md`, `CHANGELOG`, `.png`, `.svg`, `LICENSE` |

**Present the triage:**

```
Changes to analyze:
  HIGH (source): N files
    - src/module/core.py (+45 -12)
    - src/module/utils.py (+8 -3)
  MEDIUM (tests/config): M files
    - tests/test_core.py (+20 -5)
  LOW (docs): K files
    - README.md (+10 -2)
```

**For large changesets (20+ files):** Warn: "Large changeset with {count} files. Full analysis may take a moment."

## Step 3: Per-File Analysis

For each HIGH and MEDIUM priority file, run CocoSearch analysis. Run independent queries in parallel where possible.

**If no CocoSearch index exists:** Skip to Step 3e (diff analysis only) for all files.

### 3a. Semantic Context

Understand what the changed code does in the broader codebase:

```
search_code(
    query="<description of what the changed function/class does>",
    use_hybrid_search=True,
    smart_context=True,
    limit=5
)
```

> **Cross-project search:** If `linkedIndexes` is configured in `cocosearch.yaml`, searches automatically expand to linked indexes. For commits affecting shared code, pass `index_names=["project1", "project2"]` to capture cross-project impact.

Use the diff to identify the *key symbols* that changed (new functions, modified classes, renamed variables), then search for them:

```
search_code(
    query="<changed_symbol_name>",
    symbol_name="<changed_symbol>*",
    use_hybrid_search=True,
    smart_context=True,
    limit=5
)
```

**Extract:** What does this code do? What subsystem does it belong to? Is it a public API or internal utility?

### 3b. Blast Radius

Check what depends on each changed file:

```
get_file_impact(file="<changed_file>", depth=1)
```

**Classify impact:**

| Dependents | Level | Note for commit message |
|-----------|-------|------------------------|
| 0 | Leaf | No downstream impact |
| 1-5 | Moderate | Mention affected area |
| 6-15 | High | Flag in commit body |
| 16+ | Critical | Warn prominently |

### 3c. Dependencies

Understand what the changed file relies on:

```
get_file_dependencies(file="<changed_file>", depth=1)
```

Look for: changes that modify how a file interacts with its dependencies (changed imports, different API calls, new dependencies added).

### 3d. Breaking Change Detection

From the diff, check for:

- **Removed or renamed public functions/classes** (anything exported or used by dependents from 3b)
- **Changed function signatures** (new required parameters, changed return types)
- **Removed or changed configuration keys**
- **Changed database schemas or data models**

If any are detected, flag as `BREAKING CHANGE` for the commit message.

### 3e. Diff Analysis

Review the actual patch content for each file:

- **New code:** New functions, classes, methods, endpoints
- **Modified code:** What specifically changed (logic, error handling, interface)
- **Removed code:** What was deleted and why it's safe (check dependents from 3b)
- **Pattern changes:** Refactored patterns, style changes, moved code

### Per-File Summary (Internal)

Build an internal summary for each file:

```
File: path/to/file.py
Type: source (HIGH)
Changes: +45 -12
What changed: Added new validate_input() function, modified process() to call it
Semantic context: Part of the input processing pipeline in the CLI layer
Impact: 3 dependents (moderate) — test_cli.py, main.py, server.py
Breaking: No
```

## Step 4: Synthesize Intent

From all per-file summaries, determine the overall commit intent.

### 4a. Determine Commit Type

| Type | When to use |
|------|-------------|
| `feat` | New functionality, new files with features, new commands/endpoints |
| `fix` | Bug fixes, error corrections, edge case handling |
| `refactor` | Code restructuring without behavior change |
| `test` | Adding/modifying tests only |
| `docs` | Documentation only changes |
| `chore` | Maintenance, dependency updates, tooling |
| `perf` | Performance improvements |
| `style` | Formatting, whitespace, code style |
| `ci` | CI/CD pipeline changes |
| `build` | Build system, dependency management |

**Rules:**
- If changes span source + tests for the same feature → `feat` (or `fix`), not `test`
- If changes span source + docs → use the source type, mention docs in body
- If multiple types truly apply (e.g., a fix + a separate refactor in the same commit) → use the dominant type, mention others in body

### 4b. Determine Scope

The scope is the primary module/subsystem affected:

- Single directory of changes → use that directory name (e.g., `dashboard`, `search`, `deps`)
- Single file → use the module name
- Cross-cutting changes → use the dominant area, or omit scope if truly cross-cutting

### 4c. Detect Multi-Concern Changes

If the changeset includes genuinely separate concerns (e.g., a feature + an unrelated doc fix), note this in the body. Do NOT suggest splitting the commit — just document all changes comprehensively.

### 4d. Compose Subject Line

- Under 72 characters
- Imperative mood ("add", "fix", "refactor", not "added", "fixes")
- Specific: "add input validation to CLI process command" not "update processing"
- No period at the end

### 4e. Compose Body

- Blank line after subject
- Each significant change as a bullet point
- Explain *why*, not just *what* (use semantic context from Step 3a)
- Note blast radius for high-impact changes
- Group related changes together
- End with `BREAKING CHANGE:` footer if applicable

## Step 5: Generate and Present

### 5a. Present the Commit Message

```
## Proposed Commit Message

type(scope): subject line here

- First significant change and why
- Second significant change and why
- Updated tests for new functionality
- Updated docs to reflect API changes

BREAKING CHANGE: description (if applicable)

---

Files: N changed (+X -Y)
Impact: [summary of blast radius findings]
```

### 5b. Offer Options

Present three choices:

- **Commit** — Execute `git commit` with the generated message. If in unstaged fallback mode, stage the analyzed files first with `git add`.
- **Edit** — User modifies the message. Regenerate or adjust as requested.
- **Abort** — Cancel. No commit, no staging changes.

### 5c. Execute Commit

If the user approves:

**If changes were staged (normal mode):**

```bash
git commit -m "<generated message>"
```

**If changes were unstaged (fallback mode):**

```bash
git add <analyzed files>
git commit -m "<generated message>"
```

Confirm: "Committed: `<short hash>` — `<subject line>`"

### 5d. Post-Commit Note

If the analysis found notable patterns, mention them:

- "Note: `core/models.py` has 18 dependents. Consider running the full test suite."
- "Note: This commit includes both a feature and a documentation update."

## Diff-Only Fallback

When no CocoSearch index is available, the skill operates in reduced mode:

1. **Collect changes** — same as Step 1
2. **Triage** — same as Step 2
3. **Diff analysis only** — parse diffs for new/modified/removed code (Step 3e only)
4. **Synthesize** — determine type/scope from file paths and diff content (Steps 4a-4e)
5. **Generate** — produce commit message without semantic context or impact data
6. **Present** — same as Step 5, but note: "Generated from diffs only. Index the project with CocoSearch for richer commit messages."

## Tips

- **Best for focused commits.** The skill works best when changes are related. If you have unrelated changes, consider staging and committing separately.
- **Staged changes are preferred.** Stage what you want to commit first for the most accurate messages.
- **Trust the type detection.** The skill uses semantic understanding to classify — a renamed file with logic changes is a `refactor`, not just a "rename".
- **Review the body.** The subject line is usually accurate; the body is where you might want to add context about *why* you made the change.
- **Works without CocoSearch.** The skill degrades gracefully — diff-only mode still produces decent Conventional Commit messages.

For common search tips (hybrid search, smart_context, symbol filtering), see `skills/README.md`.

For installation instructions, see `skills/README.md`.
