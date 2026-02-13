---
name: cocosearch-onboarding
description: Use when onboarding to a new or unfamiliar codebase. Guides you through understanding architecture, key modules, and code patterns step-by-step using CocoSearch.
---

# Codebase Onboarding Workflow

Welcome to a new codebase. I'll guide you through understanding it step-by-step, like a senior developer giving you the tour. We'll use CocoSearch's semantic search to explore the architecture, key modules, and patterns without getting lost in the details.

## Pre-flight Check

Before we start exploring, let me check if we have a CocoSearch index for this codebase.

**I'll run:**

1. **Check for project config first:** Look for `cocosearch.yaml` in the project root. If it exists and has an `indexName` field, use that as the index name for all subsequent operations. **This is critical** — the MCP `index_codebase` tool auto-derives names from the directory path if `index_name` is not specified, which may not match the configured name. A mismatch causes "Index not found" errors from the CLI.
2. `list_indexes()` - Check what indexes exist
3. `index_stats(index_name="<configured-name>")` - Check index health and freshness

**What to look for:**

- **No index found:** I'll offer to run `index_codebase(path, index_name="<configured-name>")` to create one before we start. **Always pass `index_name` explicitly** to match the project config.
- **Index exists but stale (>7 days):** I'll mention the index might be outdated and ask if you want to reindex for the freshest results
- **Index fresh:** Great! We can start exploring immediately

**Why this matters:** Stale indexes might miss recent refactorings or new modules. A fresh index gives you the most accurate picture of the codebase.

## Step 1: Architecture Overview (10,000ft View)

Let me get the big picture first. I'll search for entry points and project organization to understand what this codebase does and how it's structured.

**I'll search for:**

- Entry points: `search_code("main entry point application startup", symbol_type="function")`
- Project structure: `search_code("module initialization configuration setup")`
- Core configuration: `search_code("config settings environment variables")`

**I'll synthesize findings into:**

- What kind of project is this? (Web app, CLI tool, library, service, etc.)
- What are the main modules and what does each do?
- How is the codebase organized? (By feature, by layer, monolithic, modular, etc.)

**Adaptive branching:**

- **If web app:** Look for routes, handlers, middleware
- **If CLI:** Look for command definitions, argument parsing
- **If library:** Look for public API surface, exported functions/classes
- **If service:** Look for API endpoints, background jobs, message handlers

**Before moving on:** I'll ask "Want me to drill deeper into any specific area?" You might already know where you need to focus.

## Step 2: Drill into Key Layers

Based on what I found in Step 1, I'll drill into 2-3 key architectural layers with concrete code examples. I'll use `smart_context=True` to show you full function bodies, not just snippets.

**Common layers to explore:**

**API/Interface Layer:**

- `search_code("API endpoint handler route", symbol_type=["function", "class"])`
- Shows: How external requests enter the system, what operations are exposed

**Business Logic Layer:**

- `search_code("service business logic core", symbol_type="class")`
- Shows: Where the real work happens, domain models, validation rules

**Data Layer:**

- `search_code("database model schema repository", symbol_type="class")`
- Shows: How data is stored and accessed, what entities exist

**Adaptive:** I'll skip layers that don't exist. A pure library won't have an API layer. A stateless service won't have a data layer.

**For each layer I find, I'll show you:**

- Concrete code examples from the codebase (not abstractions)
- How this layer interacts with others
- Key patterns or conventions used

**If I discover specific identifiers** (like class names or function signatures) in one layer, I'll use `use_hybrid_search=True` when searching related layers to find connections.

## Step 3: Patterns and Conventions

Now that you understand what the codebase does, let me show you how it does it. I'll search for common patterns to help you write code that fits in.

**Error Handling:**

- `search_code("error handling exception")`
- Shows: How errors are caught, logged, and communicated

**Testing Approach:**

- `search_code("test setup fixture mock")`
- Shows: Testing framework, how tests are structured, what's mocked vs integrated

**Configuration:**

- `search_code("configuration settings environment")`
- Shows: How config is loaded, environment-specific settings, secrets management

**I'll synthesize findings:**

- "This codebase uses X pattern for error handling"
- "Tests follow Y approach with Z testing library"
- "Configuration is managed via [environment variables / config files / remote config]"

**Adaptive:** If the codebase has unique patterns (custom decorators, specific architectural patterns like CQRS or event sourcing), I'll highlight those.

## Step 4: Optional Summary Document

Now you've seen the architecture, key layers, and conventions. Would you like me to generate a codebase summary document for future reference?

**If yes, I'll create `CODEBASE_OVERVIEW.md` in the project root with:**

**Contents:**

- Architecture overview (entry points, main modules, organization)
- Key modules and their responsibilities
- Important patterns and conventions
- Common workflows (how a request flows through the system)
- Testing approach and where to find examples
- Configuration and environment setup

**Freshness marker:**

- Date generated: [today's date]
- Index used: [index name]
- Index last updated: [from index_stats]

**Why this helps:** Future you (or future teammates) can read the overview without re-exploring. The freshness marker tells you when to regenerate if the codebase evolves significantly.

**If no:** That's fine. You now have a mental model of the codebase from our exploration. You can always run this workflow again later.

## Tips for Success

**During exploration:**

- I present synthesized summaries, not raw search results. If you want to see specific code, ask me to show it.
- At each step, you can redirect me: "Skip the data layer, show me the authentication flow instead."
- I adapt based on what I find. If a search returns no results, I'll try a different angle.

**After onboarding:**

- Use CocoSearch for intent-based discovery: "find rate limiting logic", "locate webhook handlers"
- Use grep/rg for exact identifiers you now know: `rg "processPayment"`
- Use your IDE for navigation once you know where things are

**Keeping fresh:**

- Reindex after major refactorings: `index_codebase(path)`
- Check staleness: `index_stats()` shows last update date
- Regenerate CODEBASE_OVERVIEW.md quarterly or after big changes

## Installation

**Claude Code (project-local, recommended for team-shared skills):**

```bash
mkdir -p .claude/skills
ln -sfn ../../skills/cocosearch-onboarding .claude/skills/cocosearch-onboarding
```

**Claude Code (global):**

```bash
mkdir -p ~/.claude/skills/cocosearch-onboarding
cp skills/cocosearch-onboarding/SKILL.md ~/.claude/skills/cocosearch-onboarding/SKILL.md
```

**OpenCode:**

```bash
mkdir -p ~/.config/opencode/skills/cocosearch-onboarding
cp skills/cocosearch-onboarding/SKILL.md ~/.config/opencode/skills/cocosearch-onboarding/SKILL.md
```

After installation, restart your AI coding assistant or run the skill activation command for your platform.
