# Phase 41: Workflow Skills - Research

**Researched:** 2026-02-06
**Domain:** Multi-step workflow skill authoring for Claude Code/OpenCode
**Confidence:** HIGH

## Summary

Phase 41 creates three multi-step workflow skills (onboarding, debugging, refactoring) delivered as Claude Code skill files that guide users through common codebase tasks. Research reveals that Claude Code skills use YAML frontmatter with markdown content, support adaptive branching through natural language, and auto-execute tool calls when properly structured. The existing superpowers plugin demonstrates proven patterns for multi-step workflows with conditional logic, user checkpoints, and context management. CocoSearch MCP tools (search_code, index_codebase, list_indexes, index_stats) provide all necessary codebase search capabilities. Skills should be conversational and adaptive rather than rigid step-by-step procedures.

**Primary recommendation:** Follow the superpowers skill format (YAML frontmatter + markdown) with adaptive branching described in prose rather than rigid flowcharts. Each skill becomes a guided conversation that auto-executes CocoSearch searches and adapts based on findings.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Skill step structure:**
- Adaptive branching flow — each skill starts with step 1, then branches based on what was found (not rigid linear)
- Skills auto-execute CocoSearch searches at each step and present results to user (no manual search triggering)
- Each skill has domain-specific structure tailored to its task (not a shared template)
- Delivered as Claude Code skill files (.md) in the repo with installation instructions for Claude Code and OpenCode

**Onboarding skill flow:**
- Starts with architecture overview — search for entry points, main modules, codebase organization (10,000ft view)
- After overview, drills into key architectural layers (API, business logic, data) with code examples from the codebase
- If no CocoSearch index exists, offer to run indexing as the first step before starting the onboarding flow
- Optionally generates a summary document at the end — ask user if they want it
- Summary doc includes a date/index-version marker so user can tell if it's stale

**Debugging skill flow:**
- Entry point: user provides an error message, stack trace, or description of unexpected behavior
- First action: cast wide net — semantic search for the symptom AND symbol search for any mentioned identifiers, then synthesize
- Trace depth is adaptive — start with one hop (error origin + immediate callers/callees), present findings, offer to trace deeper
- Default to locating root cause, then ask "Want me to suggest a fix?" — doesn't force fix suggestions

**Refactoring skill flow:**
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

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

## Standard Stack

### Core Components

| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| Claude Code Skills | Current | Skill delivery format | Official Anthropic format for Claude Code |
| YAML Frontmatter | 1.2 | Skill metadata | Required by Claude Code skill system |
| Markdown | CommonMark | Skill content format | Human-readable, LLM-friendly |
| CocoSearch MCP | v1.7+ | Codebase search engine | Already integrated, provides semantic + symbol search |

### Supporting Tools

| Tool | Purpose | When to Use |
|------|---------|-------------|
| tree-sitter | AST parsing for context | Smart context expansion in debugging |
| symbol filtering | Find functions/classes | Debugging and refactoring skills |
| hybrid search | Semantic + keyword | All search operations for better precision |

### Installation Pattern

Skills are delivered as `.md` files in repository with installation instructions for both platforms:

**Claude Code:**
```bash
# Copy skill to user directory
cp skills/coco-onboarding/SKILL.md ~/.claude/skills/coco-onboarding/
```

**OpenCode:**
```bash
# Copy skill to OpenCode directory
cp skills/coco-onboarding/SKILL.md ~/.config/opencode/skills/coco-onboarding/
# OR project-local
cp skills/coco-onboarding/SKILL.md .opencode/skills/coco-onboarding/
```

**Why this approach:** Both platforms auto-discover skills from these directories. No plugin system needed.

## Architecture Patterns

### Recommended Skill Structure

```
skills/
├── coco-onboarding/
│   └── SKILL.md              # Onboarding workflow skill
├── coco-debugging/
│   └── SKILL.md              # Debugging workflow skill
└── coco-refactoring/
    └── SKILL.md              # Refactoring workflow skill

docs/
└── skills/
    └── installation.md       # Installation instructions for both platforms
```

**Rationale:** Flat structure with one skill per directory, following superpowers pattern. Each skill is self-contained with all instructions inline.

### Pattern 1: YAML Frontmatter for Skill Metadata

**What:** Required metadata block at top of SKILL.md

**When to use:** Every skill file

**Example:**
```markdown
---
name: coco-onboarding
description: Use when exploring a new codebase or need to understand project architecture, entry points, or code organization
---

# Codebase Onboarding with CocoSearch

## Overview
[Skill content...]
```

**Source:** [Claude Code Docs - Extend Claude with skills](https://code.claude.com/docs/en/skills)

**Critical fields:**
- `name`: Lowercase with hyphens (matches directory name)
- `description`: Starts with "Use when..." describing triggering conditions, NOT workflow summary
- Character limit: 1024 chars total frontmatter

**Why this matters:** The description field is how Claude decides when to load the skill. User-facing symptom descriptions (e.g., "exploring a new codebase") are more discoverable than process descriptions (e.g., "searches entry points then drills into layers").

### Pattern 2: Adaptive Branching Through Prose

**What:** Describe branching logic in natural language rather than rigid steps

**When to use:** All workflow skills with conditional paths

**Example:**
```markdown
## Workflow

1. **Check Index Status**
   - First, check if codebase is indexed using `list_indexes()`
   - If not indexed, ask user: "Would you like me to index this codebase first?"
   - If yes, run `index_codebase(path=<current-dir>)`

2. **Architecture Overview**
   - Search for entry points: "main function application entry point"
   - Search for project structure: "README configuration setup"
   - Present findings as high-level architecture summary

3. **Drill Down (User Choice)**
   - Ask: "Which layer would you like to explore? (API/Business Logic/Data)"
   - Based on choice, execute targeted searches with examples
   - Continue drilling until user signals completion
```

**Why:** LLMs excel at following prose instructions with decision points. Rigid step numbers or flowcharts constrain natural conversation flow.

**Source:** Analysis of [superpowers systematic-debugging skill](https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md)

### Pattern 3: Auto-Execute CocoSearch Tools

**What:** Skills directly call MCP tools rather than instructing user to call them

**When to use:** All search operations in workflow skills

**Example:**
```markdown
## Step 1: Locate Error Source

Execute these searches automatically:

1. **Semantic search for error message:**
   ```
   search_code(
     query="<user-provided-error-message>",
     use_hybrid_search=true
   )
   ```

2. **Symbol search for identifiers in stack trace:**
   ```
   search_code(
     query="<function-name-from-stacktrace>",
     symbol_type=["function", "method"],
     use_hybrid_search=true
   )
   ```

3. **Synthesize findings** and present to user before suggesting next steps.
```

**Why:** Skills control the workflow. Manual tool triggering breaks conversational flow and adds cognitive overhead.

### Pattern 4: User Checkpoints for Depth Control

**What:** Ask permission before going deeper or changing direction

**When to use:** Before expensive operations or direction changes

**Example:**
```markdown
## Adaptive Depth

After presenting immediate callers and callees:

"I found X callers of this function. Would you like me to:
1. Trace deeper into the call chain
2. Look at how these callers are invoked
3. Focus on a specific caller
4. Move on to suggesting fixes"

Based on user choice, execute next search or transition to fix suggestions.
```

**Why:** Prevents runaway searches and keeps user in control. Matches locked decision for "adaptive trace depth."

### Pattern 5: Staleness Detection

**What:** Check index freshness before operations

**When to use:** Beginning of onboarding and debugging workflows

**Example:**
```markdown
## Index Health Check

Before starting workflow:

1. Call `index_stats(index_name=<detected>)`
2. Check staleness_days in response
3. If > 7 days old:
   "The index is X days old. Would you like me to refresh it before we start?"
```

**Why:** CocoSearch warns about stale indexes. Proactive check avoids misleading results.

**Source:** CocoSearch MCP server staleness_warning implementation (server.py:384-395)

## Don't Hand-Roll

### Problems with Existing Solutions

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Semantic code search | Custom embeddings + vector db | CocoSearch MCP tools | Already integrated, handles indexing, context expansion, hybrid search |
| Symbol lookup | Regex or grep-based parsing | CocoSearch symbol_type/symbol_name filters | Tree-sitter AST parsing more accurate |
| Context expansion | Manual line counting | CocoSearch smart_context | Expands to function/class boundaries automatically |
| Index staleness | Manual timestamp tracking | CocoSearch staleness warnings | Built into search responses |
| Multi-file search orchestration | Custom search loop | Sequential MCP tool calls | Skills naturally orchestrate tool calls |

**Key insight:** CocoSearch v1.7 provides all search primitives needed. Skills orchestrate these primitives into workflows rather than reimplementing search.

## Common Pitfalls

### Pitfall 1: Rigid Step Sequences

**What goes wrong:** Skills written as numbered steps (1, 2, 3) feel mechanical and break when reality doesn't match expected path

**Why it happens:** Traditional documentation mindset (procedures, SOPs)

**How to avoid:** Write skills as adaptive conversations. Use "If... then..." prose instead of step numbers. Let Claude's reasoning handle branching.

**Warning signs:**
- "Step 1, Step 2, Step 3" structure
- No conditional logic or user choice points
- Assumes happy path only

**Example - Bad:**
```markdown
1. Search for main function
2. Search for API routes
3. Search for database layer
```

**Example - Good:**
```markdown
Start with entry points. If the codebase has a main function, search for "main entry point".
If results show API routes, drill into route handlers. If results show CLI, explore command structure.
Ask user which area they want to explore first.
```

### Pitfall 2: Description Summarizes Workflow

**What goes wrong:** Skill descriptions that explain what the skill DOES cause Claude to follow the description instead of reading full skill content

**Why it happens:** Natural instinct to summarize functionality

**How to avoid:** Description must ONLY describe WHEN to use (triggering conditions), never HOW (workflow steps)

**Warning signs:**
- Description mentions specific steps or actions
- Description explains the process
- User feedback: "Claude isn't following the full workflow"

**Example - Bad:**
```yaml
description: Use for onboarding - searches entry points then API routes then database layer
```

**Example - Good:**
```yaml
description: Use when exploring a new codebase, understanding project structure, or need to learn how a project is organized
```

**Source:** [superpowers writing-skills documentation](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md) - Claude Search Optimization section

### Pitfall 3: Not Checking Index Existence

**What goes wrong:** Skill attempts searches on non-existent index, returns empty results, user gets frustrated

**Why it happens:** Assuming index is always present

**How to avoid:** First action in onboarding/debugging skills should be `list_indexes()` check. Offer to index if missing.

**Warning signs:**
- Empty search results on known codebases
- Error messages about missing indexes
- User has to manually index before using skill

**Example - Fix:**
```markdown
## Prerequisites Check

Before starting, verify index exists:
1. Call `list_indexes()`
2. If current project not listed, ask: "Would you like me to index this codebase?"
3. If yes, call `index_codebase(path=<project-root>)`
```

### Pitfall 4: Overwhelming Results Without Synthesis

**What goes wrong:** Presenting 10 raw search results dumps too much information, user can't process it

**Why it happens:** Tool calls return data, skill doesn't specify synthesis step

**How to avoid:** After each search, explicitly instruct synthesis before presenting to user

**Warning signs:**
- User says "too much information"
- User asks "what does this mean?"
- Search results shown without interpretation

**Example:**
```markdown
## Search and Synthesize Pattern

1. Execute search: `search_code(query=..., limit=10)`
2. **Synthesize findings:**
   - What patterns emerge across results?
   - Which files are architectural entry points vs helpers?
   - What's the main organizational structure?
3. Present summary (2-3 sentences) + top 3 most relevant results
4. Ask: "Would you like details on any specific area?"
```

### Pitfall 5: Forgetting Symbol Filtering

**What goes wrong:** Semantic search alone returns too many noise results when looking for specific functions/classes

**Why it happens:** Not leveraging CocoSearch v1.7 symbol filters

**How to avoid:** Use `symbol_type` and `symbol_name` filters when searching for specific code elements

**Warning signs:**
- Debugging searches return variable assignments instead of function definitions
- Refactoring impact analysis includes string literals matching the name
- Too many false positives in results

**Example - Debugging Error:**
```markdown
If stack trace mentions function name `validateUser`:

1. **Find function definition:**
   ```
   search_code(
     query="validateUser function authentication",
     symbol_type="function",
     symbol_name="validateUser",
     use_hybrid_search=true
   )
   ```

2. **Find callers:**
   ```
   search_code(
     query="calls validateUser invokes validation",
     use_hybrid_search=true
   )
   ```
```

**Source:** CocoSearch MCP server.py:161-176 symbol filtering parameters

## Code Examples

### Example 1: Onboarding Skill Structure

Verified pattern from research synthesis:

```markdown
---
name: coco-onboarding
description: Use when exploring a new codebase, understanding project structure, identifying entry points, or learning how code is organized
---

# Codebase Onboarding with CocoSearch

## Overview

Walk through a new codebase systematically, starting with high-level architecture and drilling into specific layers based on what you find. This skill uses CocoSearch to search semantically and show code examples from the actual codebase.

**Core principle:** Start at 10,000ft view, then drill down based on findings and user interest.

## When to Use

Use this skill when:
- First time exploring a new codebase
- Need to understand how a project is architected
- Want to find entry points and main modules
- Preparing to contribute to an unfamiliar project

## Workflow

### 1. Prerequisites Check

First, verify the codebase is indexed:

```
Call: list_indexes()
```

If current project not in list, ask user:
"I don't see an index for this project. Would you like me to index it first? This will take a few minutes but enables much better search."

If yes:
```
Call: index_codebase(path=<current-working-directory>)
```

### 2. Architecture Overview

Start with broad searches to understand organization:

**Entry Points:**
```
search_code(
  query="main function application entry point startup",
  limit=5,
  use_hybrid_search=true
)
```

**Project Structure:**
```
search_code(
  query="README project structure architecture overview",
  limit=3
)
```

**Synthesize:** What did we learn?
- What's the main entry point?
- What language/framework?
- What's the high-level architecture?

Present 2-3 sentence summary + key files found.

### 3. Drill Down (Adaptive)

Ask user: "Which area would you like to explore deeper?"
- API layer (routes, endpoints, handlers)
- Business logic (core domain functions)
- Data layer (database, storage, models)
- Testing approach
- Something specific (user describes)

Based on choice, execute targeted searches with code examples.

**For API Layer:**
```
search_code(
  query="API routes endpoints handlers controllers",
  symbol_type=["function", "method", "class"],
  limit=10,
  use_hybrid_search=true,
  context_before=3,
  context_after=3
)
```

**For Business Logic:**
```
search_code(
  query="business logic domain core operations",
  symbol_type=["function", "class"],
  limit=10,
  use_hybrid_search=true,
  smart_context=true
)
```

Present findings with actual code snippets. Continue drilling based on user questions.

### 4. Summary Document (Optional)

Ask: "Would you like me to generate an onboarding summary document?"

If yes, create markdown file with:
- Architecture overview (from step 2)
- Key files and their purposes
- Entry points and main flows
- Areas explored with code examples
- Timestamp: "Generated on [date] using index last updated [staleness_days] days ago"

Save as `ONBOARDING.md` in project root or `.cocosearch/` directory.

## Tips

- If searches return too many results, ask user to narrow scope
- Use symbol filtering for code-specific elements
- Smart context shows full function/class for better understanding
- Staleness warning? Offer to refresh index mid-workflow
```

### Example 2: Debugging Skill Structure

```markdown
---
name: coco-debugging
description: Use when encountering errors, unexpected behavior, test failures, or need to trace bug root cause in codebase
---

# Bug Hunting with CocoSearch

## Overview

Systematically locate bug root cause by casting a wide net initially, then narrowing based on findings. Combines semantic search for symptoms with symbol search for specific identifiers.

**Core principle:** Find WHERE it breaks before suggesting HOW to fix it.

## Workflow

### 1. Capture Error Details

Ask user for:
- Error message or stack trace
- Description of unexpected behavior
- Steps to reproduce (if known)

### 2. Cast Wide Net

Execute searches in parallel:

**Semantic search for symptom:**
```
search_code(
  query="<error-message-text> <behavior-description>",
  limit=10,
  use_hybrid_search=true,
  context_before=5,
  context_after=5
)
```

**Symbol search for identifiers in stack trace:**
Extract function/class names from stack trace, then:
```
search_code(
  query="<extracted-identifier>",
  symbol_type=["function", "method", "class"],
  symbol_name="<identifier>",
  use_hybrid_search=true,
  smart_context=true
)
```

**Synthesize:** Present findings showing:
- Where error likely originates (file + line)
- What function/class contains the issue
- Immediate context around error site

### 3. Trace Call Chain (Adaptive Depth)

**One hop (default):**

Find immediate callers:
```
search_code(
  query="calls <error-function> invokes <error-function>",
  limit=10,
  use_hybrid_search=true,
  smart_context=true
)
```

Present findings. Ask: "Would you like me to trace deeper into the call chain?"

**If yes, trace upstream:**
Repeat caller search for next level. Continue until user says stop or reach entry point.

### 4. Root Cause Conclusion

Present analysis:
- Error location (file + function)
- Call chain showing how we got there
- Likely root cause hypothesis

Ask: "Want me to suggest a fix?"

If yes, propose fix with test case. If no, end here (user may want to investigate manually).

## Tips

- Use symbol filtering to avoid noise (e.g., string literals matching function names)
- Smart context shows full function for understanding
- If multiple potential causes, list them and ask user which to explore
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Rigid step-by-step procedures | Adaptive conversational workflows | 2025 (LLM workflows) | Skills feel natural, handle unexpected paths |
| Manual tool invocation | Auto-execute MCP tools in skills | 2025 (Claude Code skills) | Seamless experience, less cognitive overhead |
| Keyword-only search | Hybrid semantic + keyword search | 2024-2025 (CocoSearch v1.7) | Better precision for identifier searches |
| Fixed context windows | Smart AST-based context expansion | 2025 (tree-sitter) | Show complete functions instead of arbitrary line ranges |
| Global skill installation | Project-local skills | 2025 (OpenCode) | Project-specific workflows colocated with code |

**Deprecated/outdated:**
- Flowchart-heavy skill documentation (2024) - Prose with conditional logic more flexible for LLM interpretation
- Step-numbered procedures (2024) - Break down with unexpected paths
- Description fields that summarize workflow (2025) - Claude follows description instead of reading full skill

## Open Questions

### 1. Symbol Availability Across Languages

**What we know:** CocoSearch v1.7 supports symbol extraction for Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, Ruby, PHP (10 languages). Other languages indexed without symbol metadata.

**What's unclear:** Should debugging/refactoring skills warn when working with non-symbol languages? Or gracefully degrade to semantic-only search?

**Recommendation:** Add language detection in skills. If language not symbol-aware, inform user: "This is a [language] project. Symbol filtering not available, using semantic search only."

### 2. Multi-Repo Workflow Coordination

**What we know:** Phase 38 (multi-repo) enables searching across repositories. Each repo has its own index.

**What's unclear:** How should onboarding skill handle multi-repo projects? Search each repo independently, or federated search across all?

**Recommendation:** For Phase 41, focus on single-repo workflows. Multi-repo orchestration can be Phase 42+ enhancement based on Phase 38 capabilities.

### 3. Summary Document Storage Location

**What we know:** Onboarding skill should optionally generate summary document with timestamp/staleness marker.

**What's unclear:** Best location for generated docs? Project root (visible, might clutter), `.cocosearch/` directory (hidden, might be ignored in git), or user's choice?

**Recommendation:** Ask user: "Where would you like me to save the onboarding summary? (project root / .cocosearch directory / specify path)". Default to `.cocosearch/ONBOARDING.md`.

## Sources

### Primary (HIGH confidence)

- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills) - Official skill format specification
- [Claude Skills Deep Dive](https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/) - Skill authoring best practices
- [Anthropic Skills Repository](https://github.com/anthropics/skills) - skill-creator reference
- CocoSearch MCP server implementation (server.py) - Tool capabilities, parameters, response formats
- [superpowers systematic-debugging skill](https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md) - Multi-step workflow pattern
- [superpowers writing-skills guide](https://github.com/obra/superpowers/blob/main/skills/writing-skills/SKILL.md) - Claude Search Optimization, description best practices

### Secondary (MEDIUM confidence)

- [OpenCode Skills Documentation](https://opencode.ai/docs/skills) - OpenCode skill format (similar to Claude Code)
- [Multi-Step LLM Chains Best Practices](https://www.deepchecks.com/orchestrating-multi-step-llm-chains-best-practices/) - Conditional branching patterns
- [LLM Agentic Workflows Guide](https://www.codeant.ai/blogs/evaluate-llm-agentic-workflows) - Multi-step evaluation approaches
- [Addy Osmani LLM Workflow 2026](https://medium.com/@addyosmani/my-llm-coding-workflow-going-into-2026-52fe1681325e) - Breaking work into AI-manageable chunks

### Tertiary (LOW confidence)

- [AI Workflow Builders 2026](https://www.vellum.ai/blog/best-ai-workflow-builders-for-automating-business-processes) - General workflow patterns (not skill-specific)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Claude Code skill format well-documented, CocoSearch MCP tools verified in codebase
- Architecture: HIGH - superpowers skills provide proven multi-step workflow patterns
- Pitfalls: HIGH - Derived from superpowers writing-skills guide (tested with subagents)
- Multi-repo coordination: MEDIUM - Phase 38 capabilities not fully explored yet
- Summary document storage: MEDIUM - User preference question, no established convention

**Research date:** 2026-02-06
**Valid until:** ~2026-03-06 (30 days - skill format stable, workflow patterns mature)
