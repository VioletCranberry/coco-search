---
name: cocosearch-explain
description: Use when a user asks how something works — a flow, logic path, subsystem, or concept. Guides targeted deep-dive explanations using CocoSearch semantic and hybrid search.
---

# Explain Code with CocoSearch

A focused workflow for answering "How does X work?" questions. Unlike onboarding (broad tour) or debugging (error-driven), this skill traces a specific flow, subsystem, or concept through the codebase and presents a clear narrative explanation with code references.

## Pre-flight Check

Before explaining anything, verify the index is healthy and current:

1. **Check for project config first:** Look for `cocosearch.yaml` in the project root. If it exists and has an `indexName` field, use that as the index name for all subsequent operations. **This is critical** — the MCP `index_codebase` tool auto-derives names from the directory path if `index_name` is not specified, which may not match the configured name. A mismatch causes "Index not found" errors from the CLI.
2. **Check available indexes:** Run `list_indexes()` to confirm the project is indexed.
3. **Check index freshness:** Run `index_stats(index_name="<configured-name>")` to get staleness information.
   - If index is stale (>7 days old), warn: "Index is X days old — explanation may not reflect recent code changes. Want me to reindex first?"
   - If no index exists, offer to run `index_codebase(path="<project-root>", index_name="<configured-name>")`.

## Step 1: Parse the Question

Identify what the user wants to understand. Different question types require different search strategies.

**Flow questions** — "How does X flow through the system?"

- Extract: starting point, ending point, data being transformed
- Strategy: trace entry → processing → output step-by-step
- Example: "How does a search query go from the CLI to results?"

**Logic questions** — "How does X decide/determine Y?"

- Extract: the decision point, inputs, possible outcomes
- Strategy: find the core function, examine branching logic, trace each path
- Example: "How does the config system resolve precedence?"

**Subsystem questions** — "How does the X subsystem work?"

- Extract: the subsystem name, its boundaries
- Strategy: find public API surface, then trace internal components
- Example: "How does the caching layer work?"

**Integration questions** — "How do X and Y interact?"

- Extract: the two components, their interface
- Strategy: find where they connect, trace data across the boundary
- Example: "How does the indexer feed data into the search engine?"

**Confirm understanding:** "You want to understand [rephrased question]. Let me trace through the codebase."

## Step 2: Find Entry Points

Cast a wide net to locate where the concept lives in the codebase. Run both semantic and hybrid searches to maximize recall.

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

If the question mentions specific names (functions, classes, modules), search for them directly:

```
search_code(
    query="<identifier>",
    symbol_name="<identifier>*",
    use_hybrid_search=True,
    smart_context=True,
    limit=5
)
```

**Type-filtered search for structural components:**

When looking for specific kinds of code:

```
# Find classes that implement the concept
search_code(
    query="<concept>",
    symbol_type="class",
    use_hybrid_search=True,
    smart_context=True
)

# Find functions that drive the flow
search_code(
    query="<concept>",
    symbol_type="function",
    use_hybrid_search=True,
    smart_context=True
)
```

**Synthesize entry points:**

- Which files appear across multiple searches? These are central to the concept.
- Which symbols have the highest relevance scores? These are the best starting points.
- Rank results: files appearing in both semantic AND hybrid results are strongest candidates.

**Branch based on findings:**

- **Clear entry point found:** Proceed to Step 3
- **Multiple candidates:** Pick the most upstream one (closest to the trigger/input) as the starting point
- **Nothing relevant:** Broaden the query — try synonyms, related terms, or drop specifics

## Step 3: Trace the Flow

Starting from the entry point(s) found in Step 2, trace how the concept works step-by-step. Adapt tracing strategy to the question type.

### For Flow Questions: Follow the Data

Trace data from input to output, one hop at a time.

**1. Start at the entry point:**

```
search_code(
    query="<entry-function>",
    symbol_name="<entry-function>",
    symbol_type="function",
    use_hybrid_search=True,
    smart_context=True
)
```

**2. For each function in the chain, find what it calls:**

Read the function body from `smart_context`, extract called functions, then search for each:

```
search_code(
    query="<called-function>",
    symbol_name="<called-function>",
    use_hybrid_search=True,
    smart_context=True
)
```

**3. Continue until you reach the output/end state.**

Build the chain: `A() → B() → C() → D() → result`

### For Logic Questions: Map the Decision Tree

**1. Find the core decision function:**

```
search_code(
    query="<decision-description>",
    use_hybrid_search=True,
    smart_context=True
)
```

**2. Examine branching logic in the function body.**

Look for: if/else chains, match/switch statements, strategy patterns, lookup tables.

**3. For each branch, trace what happens:**

```
search_code(
    query="<branch-handler>",
    symbol_name="<handler>*",
    use_hybrid_search=True,
    smart_context=True
)
```

### For Subsystem Questions: Map the Boundary

**1. Find the public API surface:**

```
search_code(
    query="<subsystem> public interface API",
    symbol_type=["function", "class"],
    use_hybrid_search=True,
    smart_context=True
)
```

**2. For each public function, trace the internal implementation:**

```
search_code(
    query="<internal-function>",
    symbol_name="<internal>*",
    use_hybrid_search=True,
    smart_context=True
)
```

**3. Identify key data structures:**

```
search_code(
    query="<subsystem> data model state",
    symbol_type="class",
    use_hybrid_search=True,
    smart_context=True
)
```

### For Integration Questions: Find the Seam

**1. Search for component A's outbound interface:**

```
search_code(
    query="<component-A> output emit send",
    use_hybrid_search=True,
    smart_context=True
)
```

**2. Search for component B's inbound interface:**

```
search_code(
    query="<component-B> input receive consume",
    use_hybrid_search=True,
    smart_context=True
)
```

**3. Find the glue — where they connect:**

```
search_code(
    query="<component-A> <component-B>",
    use_hybrid_search=True,
    smart_context=True
)
```

## Step 4: Synthesize the Explanation

Present a clear, structured narrative. Not a list of search results — a coherent explanation that a developer can follow.

**Structure the explanation as:**

1. **One-sentence summary:** "Here's how [concept] works in this codebase: [summary]."

2. **Step-by-step walkthrough:** For each step in the flow/logic:
   - What happens at this step
   - Where it happens (`file:line` reference)
   - Key code snippet (from `smart_context`)
   - Why it matters (connects to the next step)

3. **Key design decisions:** Call out notable patterns, trade-offs, or architectural choices you noticed during tracing.

**Example explanation format:**

"Here's how search queries flow from CLI to results:

**1. CLI parses the query** (`src/cli.py:145`)
The `search` subcommand extracts the query string and options (hybrid, limit, language filter).

```python
def cmd_search(args):
    query = args.query
    results = search_engine.search(query, hybrid=args.hybrid)
```

**2. Search engine runs hybrid retrieval** (`src/search/engine.py:67`)
The query goes through two paths simultaneously — vector similarity and keyword matching — then fuses results via RRF.

```python
def search(self, query, hybrid=False):
    vector_results = self._vector_search(query)
    if hybrid:
        keyword_results = self._keyword_search(query)
        return self._rrf_fusion(vector_results, keyword_results)
```

**3. Results get context-expanded** (`src/search/context.py:23`)
Each result snippet is expanded to full function boundaries using Tree-sitter parse data.

**Design note:** The RRF fusion uses k=60, which biases toward vector results while still boosting exact keyword matches."

## Step 5: Offer to Go Deeper

After presenting the explanation, offer focused follow-ups.

**Always ask:** "Want me to go deeper into any of these steps, or explore a related area?"

**Common follow-ups:**

- "Show me the full code for step N" → Use `smart_context=True` with the specific function
- "How does [sub-component mentioned in explanation] work?" → Recurse into Step 2 with narrower focus
- "What calls this flow?" → Trace callers of the entry point
- "What are the edge cases?" → Search for error handling and validation in the traced functions:

```
search_code(
    query="<function> error edge case validation",
    use_hybrid_search=True,
    smart_context=True
)
```

- "Where is this tested?" → Find test coverage:

```
search_code(
    query="test <concept>",
    symbol_name="test_*<concept>*",
    symbol_type="function",
    use_hybrid_search=True
)
```

## Tips for Best Results

**Hybrid search is the default.** Every search in this skill uses `use_hybrid_search=True`. This combines semantic understanding ("what does this code do?") with keyword precision ("find this exact function name"). For code explanation, you need both.

**Use `smart_context=True` everywhere.** Explanations need full function bodies, not truncated snippets. Smart context expands results to Tree-sitter boundaries automatically.

**Follow identifiers across hops.** When a function body references another function, search for it by name using `symbol_name` for precision. Use semantic queries for intent-based discovery.

**Trace breadth-first for subsystems, depth-first for flows.** When explaining a subsystem, map all public functions first, then drill into each. When explaining a flow, follow one path end-to-end before exploring branches.

**Keep explanations narrative, not listy.** The goal is understanding, not a raw dump of search results. Connect the dots between code locations. Explain *why*, not just *what*.

## Installation

**Claude Code (project-local):**

```bash
mkdir -p .claude/skills
ln -sfn ../../skills/cocosearch-explain .claude/skills/cocosearch-explain
```

**Claude Code (global):**

```bash
mkdir -p ~/.claude/skills/cocosearch-explain
cp skills/cocosearch-explain/SKILL.md ~/.claude/skills/cocosearch-explain/SKILL.md
```

**OpenCode:**

```bash
mkdir -p ~/.config/opencode/skills/cocosearch-explain
cp skills/cocosearch-explain/SKILL.md ~/.config/opencode/skills/cocosearch-explain/SKILL.md
```

After installation, restart your AI coding assistant or run the skill activation command for your platform.
