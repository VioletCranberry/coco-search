---
name: cocosearch-explore
description: Use for codebase exploration — answering questions about how code works, tracing flows, or researching a topic. Two modes: autonomous (subagent/plan mode, structured output) and interactive (user-facing, narrative with checkpoints).
---

# Codebase Exploration with CocoSearch

A unified exploration skill with two modes:

- **Autonomous mode** — non-interactive, structured output. For subagent invocation (Task tool), plan mode research, or when you need findings another agent can consume.
- **Interactive mode** — checkpoints at each step, narrative explanations. For direct user questions like "how does X work?"

## When to Use This vs Other Skills

| Skill | Goal | Best for |
|-------|------|----------|
| **cocosearch-explore** | Answer a question about the codebase | "How does X work?", "Go figure out X", subagent research |
| cocosearch-onboarding | Broad codebase understanding | First time in a codebase |
| cocosearch-debugging | Find root cause of a bug | Error-driven investigation |

## Mode Selection

**Use autonomous mode when:**
- A subagent needs to research something (via Task tool)
- Plan mode needs codebase context before proposing changes
- You need structured findings another agent can consume
- The question is specific enough for 3-7 searches to answer

**Use interactive mode when:**
- The user directly asks "how does X work?"
- The user wants to understand a flow, subsystem, or concept
- You want to offer "go deeper" follow-ups

## Pre-flight Check

1. Read `cocosearch.yaml` for `indexName` (critical -- use this for all operations)
2. `list_indexes()` to confirm project is indexed
3. `index_stats(index_name="<configured-name>")` to check freshness
- No index → **Autonomous:** return FAILED status immediately. **Interactive:** offer to index.
- Stale (>7 days) → note in output, proceed with warning

---

## Autonomous Mode

Run to completion without user interaction. Return structured findings.

### Phase 1: Broad Discovery (1-2 searches)

Cast a wide net to locate where the concept lives.

**Semantic search for the concept:**

```
search_code(
    query="<question rephrased as a natural description>",
    use_hybrid_search=True,
    smart_context=True,
    limit=10
)
```

**Symbol search if the question mentions specific identifiers:**

```
search_code(
    query="<identifier>",
    symbol_name="<identifier>*",
    use_hybrid_search=True,
    smart_context=True,
    limit=5
)
```

**After Phase 1, assess:**
- Which files appear across searches? These are central.
- Are there clear entry points, or is the concept spread across many files?
- What gaps remain?

If Phase 1 fully answers the question (rare), skip to Output.

### Phase 2: Targeted Follow-up (1-3 searches)

Fill gaps identified in Phase 1. Choose searches based on what's missing.

**Trace a specific function or class:**

```
search_code(
    query="<function-name>",
    symbol_name="<function-name>",
    symbol_type="function",
    use_hybrid_search=True,
    smart_context=True
)
```

**Find related components not yet discovered:**

```
search_code(
    query="<aspect of question not covered by Phase 1>",
    use_hybrid_search=True,
    smart_context=True,
    limit=5
)
```

**Find callers or consumers of a key function:**

```
search_code(
    query="<function-name> call invoke use",
    use_hybrid_search=True,
    smart_context=True,
    limit=5
)
```

**Trace dependencies for a key file** (if dependency index exists):

```
get_file_dependencies(file="<file-path>", depth=2)
get_file_impact(file="<file-path>", depth=2)
```

Dependency tools provide instant, complete file-level dependency data. Use them to map how modules connect without needing multiple search hops.

**Search budget:** 3-5 total searches across Phases 1-2. If you need more than 7, split the question.

### Phase 3: Verify

For the 2-3 most important findings, ensure you have full function/class bodies via `smart_context=True`. If earlier searches already returned sufficient context, this phase may be a no-op.

### Output Format

Return findings in this exact structure. This is what consuming agents expect.

```
## Findings

**Question:** <original question, verbatim>
**Status:** COMPLETED | PARTIAL | FAILED
**Index:** <index-name> (last indexed: <date or "unknown">)
<if stale>**Warning:** Index is <N> days old -- findings may not reflect recent changes.</if>

### Summary
<2-4 sentences directly answering the question. Be specific -- reference files, functions, patterns. No filler.>

### Key Files
| File | Role | Key Symbols |
|------|------|-------------|
| `src/module/file.py` | <what this file does for the question> | `func_a`, `ClassB` |

### Code References
**<descriptive title>** (`file:line`)
<1-2 sentence explanation of why this code matters>

\```python
<relevant code snippet from smart_context>
\```

### Connections
- <bullet showing how piece A connects to piece B>
- <bullet showing data flow or dependency>

### Gaps
<what couldn't be determined -- omit this section entirely if there are no gaps>
```

**Status definitions:**
- **COMPLETED** -- the question is fully answered with code references
- **PARTIAL** -- the question is partially answered; Gaps section explains what's missing
- **FAILED** -- could not answer (no index, no relevant results, question too broad)

### Usage Patterns

**Invoked by a subagent via Task tool:**

```
Task(
    subagent_type="general-purpose",
    prompt="Use the cocosearch-explore skill to answer: How does the config precedence system resolve conflicts? Return the structured findings.",
    description="Explore config precedence"
)
```

**Invoked in plan mode:** Use this skill to understand the area you'll be modifying before proposing changes.

---

## Interactive Mode

Step-by-step narrative exploration with user checkpoints and "go deeper" offers.

### Step 1: Parse the Question

Identify what the user wants to understand. Different question types need different strategies:

**Flow questions** -- "How does X flow through the system?"
- Extract: starting point, ending point, data being transformed
- Strategy: trace entry -> processing -> output step-by-step

**Logic questions** -- "How does X decide/determine Y?"
- Extract: the decision point, inputs, possible outcomes
- Strategy: find the core function, examine branching logic, trace each path

**Subsystem questions** -- "How does the X subsystem work?"
- Extract: the subsystem name, its boundaries
- Strategy: find public API surface, then trace internal components

**Integration questions** -- "How do X and Y interact?"
- Extract: the two components, their interface
- Strategy: find where they connect, trace data across the boundary

**Confirm understanding:** "You want to understand [rephrased question]. Let me trace through the codebase."

### Step 2: Find Entry Points

Cast a wide net with semantic and symbol searches.

**Semantic search for the concept:**

```
search_code(
    query="<user's concept described naturally>",
    use_hybrid_search=True,
    smart_context=True,
    limit=10
)
```

**Symbol search for key identifiers:**

```
search_code(
    query="<identifier>",
    symbol_name="<identifier>*",
    use_hybrid_search=True,
    smart_context=True,
    limit=5
)
```

**Synthesize entry points:**
- Which files appear across multiple searches? These are central.
- Which symbols have the highest relevance? Best starting points.
- Files in both semantic AND hybrid results are strongest candidates.

**Branch:**
- Clear entry point → proceed to Step 3
- Multiple candidates → pick the most upstream one
- Nothing relevant → broaden the query with synonyms or related terms

### Step 3: Trace the Flow

Starting from entry points, trace how the concept works. Adapt strategy to question type:

**For flow questions:** Follow the data from input to output, one hop at a time. Build the chain: `A() -> B() -> C() -> result`. Use `get_file_dependencies(file, depth=2)` to quickly map how files connect.

**For logic questions:** Find the core decision function, examine branching logic (if/else, match, strategy patterns), trace each branch.

**For subsystem questions:** Map public API surface first (breadth-first), then drill into each function (depth-first). Use `get_file_impact(file, depth=2)` to see what depends on a key file.

**For integration questions:** Find component A's outbound interface, component B's inbound interface, then the glue where they connect. Dependency tools can reveal cross-module connections instantly.

### Step 4: Synthesize the Explanation

Present a clear, structured narrative -- not raw search results.

**Structure:**

1. **One-sentence summary:** "Here's how [concept] works: [summary]."

2. **Step-by-step walkthrough:** For each step:
   - What happens
   - Where (`file:line` reference)
   - Key code snippet (from `smart_context`)
   - Why it matters (connects to next step)

3. **Key design decisions:** Notable patterns, trade-offs, or architectural choices.

**Keep explanations narrative, not listy.** Connect the dots between code locations. Explain *why*, not just *what*.

### Step 5: Offer to Go Deeper

After presenting the explanation, offer focused follow-ups.

**Always ask:** "Want me to go deeper into any of these steps, or explore a related area?"

**Common follow-ups:**
- "Show me the full code for step N" -> use `smart_context=True` with the specific function
- "How does [sub-component] work?" -> recurse into Step 2 with narrower focus
- "What calls this flow?" -> trace callers of the entry point
- "What are the edge cases?" -> search for error handling and validation
- "Where is this tested?" -> `search_code(query="test <concept>", symbol_name="test_*<concept>*", symbol_type="function")`

## Tips

For common search tips (hybrid search, smart_context, symbol filtering), see `skills/README.md`.

**Autonomous-mode specific:**
- **3-5 searches is the sweet spot** -- under 3 risks missing context, over 7 means the question is too broad.
- **No user interaction** -- run to completion and return findings. Do not ask "want me to go deeper?"

**Interactive-mode specific:**
- **Trace breadth-first for subsystems, depth-first for flows.** Map all public functions first for subsystems; follow one path end-to-end for flows.
- **Follow identifiers across hops.** When a function body references another function, search for it by name.
