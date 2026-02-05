# Phase 40: Code Cleanup - Research

**Researched:** 2026-02-05
**Domain:** Python code cleanup, safe deprecation removal, schema migration cleanup
**Confidence:** HIGH

## Summary

Phase 40 focuses on safely removing deprecated code and migration logic from a single-user Python tool that no longer needs backward compatibility. The primary areas for cleanup are: DB migrations module (schema_migration.py functions that add PostgreSQL-specific columns/indexes), deprecated function re-exports (languages.py and metadata.py modules), and v1.2 graceful degradation code (old index compatibility patterns).

Research confirms that CocoIndex natively creates all standard columns (TEXT, vector fields) via schema inference, but PostgreSQL-specific features (TSVECTOR generated columns, GIN indexes) still require SQL migrations. However, these are not "backward compatibility" migrations - they're necessary schema enhancements that must run after CocoIndex creates base tables. The term "migration" is misleading; this is actually schema enhancement for database-specific features.

The core strategy is removal-focused refactoring: group removals by related functionality, remove leaf code first (code with no dependencies), run tests after each logical grouping, and use ruff/mypy to catch orphaned imports and type errors. Track LOC reduction before/after for reporting impact.

**Primary recommendation:** Remove deprecated re-export modules (languages.py, metadata.py) first as they're pure compatibility shims, then evaluate schema_migration.py usage - it may be misnamed but still functionally necessary for PostgreSQL-specific features.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Removal Ordering:**
- Group removals logically by related functionality, not by type
- Remove leaf code first (unused code that nothing depends on), then work inward
- If code has no references found, remove it — tests will catch mistakes
- Remove related tests/fixtures together with the code they test in same commit

**Verification Approach:**
- Run full test suite after each removal grouping commit
- Run linters (ruff/mypy) to catch unused imports, type errors from removals
- Fix test issues inline in same commit as the removal that exposed them
- Track and report LOC reduction before/after at end of phase

**Documentation Handling:**
- Update comments/docstrings to reflect current behavior when removing code
- Update READMEs or external docs inline during this phase (not deferred to Phase 42)
- Resolve or remove TODO/FIXME comments that reference old patterns
- Clean up dead imports as part of cleanup — ruff will catch them

**Discovery Scope:**
- Include clearly dead code found during cleanup, even if not explicitly listed in requirements
- Removal only — don't fix unrelated code smells (keep concerns separate)
- Light restructuring OK if removal naturally simplifies code structure
- Review and address STATE.md blockers/concerns that are resolved by these removals

### Claude's Discretion

- Exact order of removal groupings within the "leaves first" strategy
- Judgement on what counts as "clearly dead" vs "uncertain"
- Deciding when removal naturally enables restructuring vs scope creep

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

## Standard Stack

This phase uses existing development tools, no new dependencies required.

### Core Tools

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| ruff | latest | Linting and autofix | Official Python linter from Astral, replaces flake8/black/isort, extremely fast |
| mypy | latest | Type checking | Catches type errors from removed code, Python standard type checker |
| pytest | current | Test suite | Already in project, validates safety of removals |
| ast-grep (optional) | latest | AST-based search | Safer than regex for finding code patterns, optional enhancement |

### Supporting Tools

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| git grep | N/A | Code search | Finding references to deprecated code |
| wc -l | N/A | Line counting | Track LOC reduction metric |

**No installation needed** - All tools already present in development environment.

## Architecture Patterns

### Recommended Removal Structure

```
Phase 40 Cleanup
├── Group 1: Deprecated re-export modules (CLEAN-02)
│   ├── Remove languages.py (re-exports from handlers)
│   ├── Remove metadata.py (re-exports from handlers)
│   └── Update test imports (CLEAN-04 prerequisite)
├── Group 2: Evaluate schema_migration.py (CLEAN-01)
│   ├── Verify what's actually "migration" vs "enhancement"
│   ├── Keep: ensure_hybrid_search_schema (PostgreSQL-specific GIN index)
│   ├── Keep: ensure_symbol_columns (adds columns CocoIndex doesn't know about)
│   └── Decision: This may not be "deprecated migration" but necessary functionality
└── Group 3: V1.2 graceful degradation (CLEAN-03)
    ├── Find old index compatibility code
    ├── Remove backward-compatible fallbacks
    └── Update related tests
```

### Pattern 1: Leaves-First Removal

**What:** Remove code that nothing depends on, then work inward to dependencies.

**When to use:** Always. Prevents cascading breakage.

**Example:**
```python
# Step 1: Remove leaf re-exports (nothing depends on these specific imports)
# languages.py - DELETE FILE
# metadata.py - DELETE FILE

# Step 2: Update consumers to import from canonical source
# Before:
from cocosearch.indexer.languages import DEVOPS_CUSTOM_LANGUAGES
# After:
from cocosearch.handlers import get_custom_languages
custom_langs = get_custom_languages()

# Step 3: Tests will catch any missed references
```

### Pattern 2: Commit-Per-Logical-Group

**What:** Each removal commit contains one logical unit (related code + tests + imports).

**When to use:** Every removal in this phase.

**Example commit structure:**
```
refactor(cleanup): remove deprecated languages.py re-exports

- Delete src/cocosearch/indexer/languages.py
- Update test imports to use handlers directly
- Update tests/unit/indexer/test_languages.py imports
- Update tests/unit/indexer/test_flow.py imports
- Remove dead imports caught by ruff

Tests pass: pytest tests/unit/indexer/
LOC removed: 26
```

### Pattern 3: Lint-Driven Cleanup

**What:** Use ruff and mypy to find orphaned imports and type issues after removal.

**When to use:** After each removal commit, before committing.

**Example:**
```bash
# After removing deprecated module
ruff check --fix .           # Auto-remove unused imports
mypy src/                    # Check for type errors from missing imports
pytest tests/                # Verify functionality

# Fix issues found, then commit as single unit
```

### Anti-Patterns to Avoid

- **Big Bang Removal:** Don't remove all deprecated code in one commit. Impossible to debug when tests fail.
- **Removing by Type:** Don't remove "all deprecated functions" together. Group by feature domain instead.
- **Deferred Import Updates:** Don't leave old imports pointing to deleted code "to fix later". Fix inline or tests will break.
- **Uncertain Deletions:** If unsure whether code is dead, grep for references first. Tests alone may not cover it.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Finding unused imports | Manual grep/search | `ruff check --select F401` | Ruff has AST-based analysis, catches imports in try/except, conditional imports |
| Removing unused code | Manual deletion | `ruff check --fix` | Safe autofix for F401 (unused imports), avoids breaking multi-line imports |
| Finding references | Text search with grep | `git grep` or `ast-grep` | git grep searches tracked files only, ast-grep understands Python AST structure |
| Verifying type safety | Manual review | `mypy src/` | Type checker catches missing imports that tests might not exercise |
| LOC counting | Manual counting | `find src -name "*.py" -exec wc -l {} + | tail -1` | Automated, consistent, excludes tests |

**Key insight:** Code cleanup benefits enormously from automated tooling. Python's ecosystem has mature tools (ruff, mypy) that catch 90% of cleanup issues automatically. Use them after each removal before committing.

## Common Pitfalls

### Pitfall 1: Removing "Migration" Code That's Actually Feature Code

**What goes wrong:** schema_migration.py is named like backward-compatibility migration logic, but actually contains necessary PostgreSQL feature enhancement. Removing it breaks hybrid search.

**Why it happens:** Naming confusion. CocoIndex creates base columns (TEXT, vectors) via schema inference, but PostgreSQL-specific features (TSVECTOR generated columns, GIN indexes) require SQL commands that CocoIndex doesn't support natively.

**How to avoid:**
- Grep for actual usage: `grep -r "ensure_hybrid_search_schema\|ensure_symbol_columns" src/`
- Check if code runs in production flow (not just during migration)
- Verify what CocoIndex creates vs what needs SQL: CocoIndex creates TEXT/vector columns, SQL adds TSVECTOR generated columns + GIN indexes

**Warning signs:**
- Code called from main indexing flow (flow.py line 210)
- Tests verify functionality (test_hybrid_schema.py), not just migration
- Comments mention "PostgreSQL-specific" not "backward compatibility"

**Verdict:** schema_migration.py is misnamed. It's schema enhancement for database-specific features, NOT deprecated migration logic. KEEP this module, possibly rename in separate cleanup task.

### Pitfall 2: Breaking Tests by Removing Compatibility Re-exports

**What goes wrong:** Tests import from deprecated modules (languages.py, metadata.py). Removing modules breaks tests even though production code is fine.

**Why it happens:** CLEAN-04 requirement exists for this reason: "Update test imports before module removal".

**How to avoid:**
1. Find all test imports: `grep -r "from cocosearch.indexer.languages\|from cocosearch.indexer.metadata" tests/`
2. Update imports to canonical source (cocosearch.handlers) FIRST
3. Verify tests pass with new imports
4. Then remove deprecated modules in separate commit

**Warning signs:**
- Test file imports from deprecated module
- Test uses re-exported constants (DEVOPS_CUSTOM_LANGUAGES, DevOpsMetadata)

### Pitfall 3: Incomplete Reference Removal

**What goes wrong:** Remove deprecated module but miss an import in obscure test file or planning doc example. Code breaks unexpectedly.

**Why it happens:** Not all references are caught by naive grep. Need to check tests, docs, planning files.

**How to avoid:**
```bash
# Comprehensive reference search before removal
git grep "module_name" -- "*.py"           # Python code
git grep "module_name" -- "*.md"           # Documentation
git grep "module_name" .planning/          # Planning docs
```

**Warning signs:**
- Import statement in any .py file
- Code examples in .md files
- Planning phase verification docs

### Pitfall 4: Losing Track of LOC Reduction Metric

**What goes wrong:** User requested LOC tracking ("Track LOC count before and after for reporting") but you forget to capture baseline.

**Why it happens:** Easy to focus on removal work and forget tracking requirement.

**How to avoid:**
- Capture baseline at phase start: `find src -name "*.py" -exec wc -l {} + | tail -1`
- Add LOC delta to each commit message: "LOC removed: 26"
- Report total at phase completion

**Warning signs:**
- No baseline recorded at phase start
- Commit messages don't mention LOC impact

### Pitfall 5: Scope Creep During Cleanup

**What goes wrong:** While removing deprecated code, you notice code smells (bad naming, poor structure) and start refactoring unrelated code.

**Why it happens:** Cleanup phase makes you read old code carefully. Natural to want to improve what you see.

**How to avoid:** User decision: "Removal only — don't fix unrelated code smells (keep concerns separate)". Light restructuring OK if removal naturally simplifies structure, but no general refactoring.

**Warning signs:**
- Renaming functions not related to removals
- Restructuring modules that aren't being deleted
- "While I'm here" changes

## Code Examples

### Example 1: Safe Re-export Module Removal

```python
# Step 1: Find all imports of deprecated module
$ git grep "from cocosearch.indexer.languages" -- "*.py"
tests/unit/indexer/test_flow.py:from cocosearch.indexer.languages import DEVOPS_CUSTOM_LANGUAGES
tests/unit/indexer/test_languages.py:from cocosearch.indexer.languages import (

# Step 2: Update to canonical imports (in test files)
# Before:
from cocosearch.indexer.languages import DEVOPS_CUSTOM_LANGUAGES
# After:
from cocosearch.handlers import get_custom_languages
DEVOPS_CUSTOM_LANGUAGES = get_custom_languages()

# Step 3: Run tests to verify
pytest tests/unit/indexer/test_flow.py tests/unit/indexer/test_languages.py

# Step 4: Remove deprecated module
rm src/cocosearch/indexer/languages.py

# Step 5: Verify no orphaned imports
ruff check --select F401 --fix tests/

# Step 6: Commit as atomic unit
git add tests/unit/indexer/test_flow.py tests/unit/indexer/test_languages.py
git add src/cocosearch/indexer/languages.py  # deletion
git commit -m "refactor(cleanup): remove deprecated languages.py re-exports

- Delete src/cocosearch/indexer/languages.py (CLEAN-02)
- Update test imports to use handlers.get_custom_languages() (CLEAN-04)
- Remove orphaned imports via ruff

Tests pass: pytest tests/unit/indexer/
LOC removed: 26"
```

### Example 2: Using Ruff for Import Cleanup

```bash
# After removing deprecated module, find all broken imports
ruff check --select F401 src/ tests/

# Sample output:
# tests/unit/indexer/test_metadata.py:3:5: F401 [*] `cocosearch.indexer.metadata.DevOpsMetadata` imported but unused
# tests/unit/indexer/test_metadata.py:4:5: F401 [*] `cocosearch.indexer.metadata.extract_hcl_metadata` imported but unused

# Auto-fix unused imports
ruff check --select F401 --fix src/ tests/

# Verify no other issues
ruff check src/ tests/
mypy src/
```

### Example 3: Tracking LOC Reduction

```bash
# Capture baseline at phase start
$ find src -name "*.py" -exec wc -l {} + | tail -1
    9274 total

# After removals
$ find src -name "*.py" -exec wc -l {} + | tail -1
    9136 total

# Calculate reduction
$ echo "9274 - 9136" | bc
138

# Report in phase completion: "Phase 40 removed 138 LOC (1.5% reduction)"
```

## Codebase Analysis

### Current State (verified via code inspection)

**Total LOC (baseline):** 9,274 lines in `src/` directory

**Deprecated modules identified:**

1. **`src/cocosearch/indexer/languages.py` (26 lines)**
   - Pure re-export module from handlers
   - Used by: tests/unit/indexer/test_flow.py, tests/unit/indexer/test_languages.py
   - Safe to remove after updating test imports

2. **`src/cocosearch/indexer/metadata.py` (111 lines)**
   - Re-exports from handlers: extract_hcl_metadata, extract_dockerfile_metadata, extract_bash_metadata
   - Legacy DevOpsMetadata dataclass wrapper
   - Used by: tests/unit/indexer/test_metadata.py
   - Safe to remove after updating test imports

3. **`src/cocosearch/indexer/schema_migration.py` (188 lines)**
   - **VERDICT: NOT deprecated migration, but necessary schema enhancement**
   - `ensure_hybrid_search_schema()`: Creates TSVECTOR generated column + GIN index (PostgreSQL-specific, CocoIndex can't do this)
   - `ensure_symbol_columns()`: Adds symbol columns to existing indexes (called from flow.py line 210)
   - Used in production flow, not just migration
   - **DO NOT REMOVE** - Rename to schema_enhancement.py if name is confusing

**V1.2 graceful degradation patterns found:**
- cli.py line 325: "For interactive mode, use context value for backward compatibility"
- search/db.py, search/hybrid.py, search/formatter.py: Comments mention "old index compat"
- Actual removal targets need deeper investigation (see Open Questions)

### STATE.md Blockers Analysis

**Blocker:** "CocoIndex schema completeness: Verify CocoIndex natively creates all columns before removing migration functions."

**Resolution:** Research confirms:
- CocoIndex DOES natively create: TEXT columns, vector fields, primary keys (via schema inference from collect() fields)
- CocoIndex DOES NOT create: PostgreSQL-specific features (TSVECTOR generated columns, GIN indexes)
- schema_migration.py functions are NOT backward-compatibility migrations, they're PostgreSQL feature enhancements
- **Blocker is resolved with clarification:** Keep schema_migration.py, possibly rename

## Open Questions

Things that couldn't be fully resolved:

1. **V1.2 graceful degradation code location**
   - What we know: Requirements CLEAN-03 targets "v1.2 graceful degradation (old index compat)". Search found comments in cli.py, search/db.py, search/hybrid.py, search/formatter.py mentioning "backward compatibility" or "old index"
   - What's unclear: Need to read actual code to determine if these are true v1.2 compatibility patterns or just general defensive coding
   - Recommendation: Plan phase should include "Discovery Task" to grep for specific patterns (check for column existence, try/except for missing columns, fallback logic for old schema) and categorize each finding as "v1.2 compat" vs "general defensive code"

2. **Old index prevalence (user impact)**
   - What we know: STATE.md notes "Old index prevalence unknown: May need migration guidance before removing graceful degradation"
   - What's unclear: How many users have pre-v1.8 indexes? Single-user tool suggests low impact, but uncertain
   - Recommendation: This is a documentation/communication issue, not technical. If removing v1.2 compat, add migration note to CHANGELOG: "v1.9 drops support for pre-v1.8 indexes. Re-index your codebase with `coco index <path>` if you have old indexes."

3. **schema_migration.py naming confusion**
   - What we know: Module is named like backward-compatibility migration logic, but functions are necessary for PostgreSQL-specific features
   - What's unclear: Should we rename in this phase or defer?
   - Recommendation: User decision is "Light restructuring OK if removal naturally simplifies code structure". Renaming doesn't naturally follow from removals. Keep name for now, document true purpose, consider rename in future refactor phase.

## Sources

### Primary (HIGH confidence)

- **Codebase inspection:**
  - `src/cocosearch/indexer/schema_migration.py` (188 lines) - Verified actual functionality vs naming
  - `src/cocosearch/indexer/flow.py` lines 22, 210 - Verified schema_migration usage in production flow
  - `src/cocosearch/indexer/languages.py` (26 lines) - Verified pure re-export module
  - `src/cocosearch/indexer/metadata.py` (111 lines) - Verified re-export functions
  - `tests/integration/test_hybrid_schema.py` - Verified schema_migration is feature code, not migration-only

- **Planning documentation:**
  - `.planning/phases/27-hybrid-search-foundation/27-VERIFICATION.md` - CocoIndex creates TEXT/vector columns automatically, SQL needed for TSVECTOR/GIN
  - `.planning/STATE.md` - Blocker about CocoIndex schema completeness
  - `.planning/phases/40-code-cleanup/40-CONTEXT.md` - User decisions for this phase

### Secondary (MEDIUM confidence)

- [GitHub: Clean Code Python](https://github.com/zedr/clean-code-python) - General Python cleanup patterns
- [Astral: Ruff Linter Documentation](https://docs.astral.sh/ruff/linter/) - Autofix capabilities, unused import detection
- [Python ast-grep Catalog](https://ast-grep.github.io/catalog/python/) - AST-based code search tool
- [Harness: Database Rollback Strategies](https://www.harness.io/harness-devops-academy/database-rollback-strategies-in-devops) - Why roll forward vs rollback for schema changes
- [pgroll: Database Rollback Strategy Levels](https://pgroll.com/blog/levels-of-a-database-rollback-strategy) - Forward migration patterns

### Tertiary (LOW confidence)

- Web search results on Python deprecation libraries (deprecation, pyDeprecate) - Not applicable, this phase is removal not deprecation
- Python PEP 702 (type-based deprecation) - Not applicable, removing code entirely not marking as deprecated

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Existing tools (ruff, mypy, pytest), no new dependencies
- Architecture: HIGH - Leaves-first removal, commit-per-group verified via git history research and planning docs
- Pitfalls: HIGH - schema_migration.py naming confusion discovered via code inspection, other pitfalls derived from user decisions
- V1.2 graceful degradation patterns: MEDIUM - Comments found, actual code patterns need investigation in planning phase

**Research date:** 2026-02-05
**Valid until:** 30 days (stable domain - code cleanup patterns don't change rapidly)

**LOC baseline recorded:** 9,274 lines in src/ directory (verified 2026-02-05)
