---
name: cocosearch-quickstart
description: Use when setting up CocoSearch for the first time or indexing a new project. Guides through infrastructure check, indexing, and verification in under 2 minutes.
---

# CocoSearch Quick Start

Get a project indexed and searchable in under 2 minutes. This skill checks prerequisites, indexes the codebase, and verifies everything works.

## Step 1: Check Infrastructure

Before indexing, verify the required services are running. The checks depend on which embedding provider is configured.

**First, determine the provider:** Check `cocosearch.yaml` for `embedding.provider` (or the `COCOSEARCH_EMBEDDING_PROVIDER` env var). If neither is set, the default is `ollama`. Also check for `embedding.baseUrl` (or `COCOSEARCH_EMBEDDING_BASE_URL`).

**All providers need PostgreSQL:**

1. **PostgreSQL (pgvector):**
   ```bash
   docker ps --filter "name=postgres" --format "{{.Names}} {{.Status}}"
   ```
   - If not running: `docker compose up -d` (from the CocoSearch project root)

**Then check the embedding provider:**

2a. **If provider is `ollama` (default):**
   ```bash
   curl -s http://localhost:11434/api/tags | head -c 200
   ```
   - If not running: `docker compose --profile ollama up -d` or `ollama serve`
   - If running but no model: `ollama pull nomic-embed-text`
   - If `baseUrl` is set, check that URL instead of localhost:11434

2b. **If provider is `openai` or `openrouter`:**
   - **Without `baseUrl`:** Verify `COCOSEARCH_EMBEDDING_API_KEY` is set:
     ```bash
     echo ${COCOSEARCH_EMBEDDING_API_KEY:+"API key is set"}
     ```
     If not set: `export COCOSEARCH_EMBEDDING_API_KEY=sk-...`
     No Ollama needed.
   - **With `baseUrl`:** Verify the custom endpoint is reachable:
     ```bash
     curl -s <baseUrl>/v1/models | head -c 200
     ```
     API key is not required (local OpenAI-compatible servers typically don't need one).

**If PostgreSQL + provider checks pass:** Proceed to Step 2.

**If nothing is running and user has CocoSearch cloned (Ollama provider):**
```bash
cd /path/to/cocosearch && docker compose --profile ollama up -d
```
This starts both PostgreSQL and Ollama in one command.

## Step 2: Index the Project

**First, check for project config:** Look for `cocosearch.yaml` in the project root. If it exists and has an `indexName` field, use that as the index name for all subsequent operations. **This is critical** — the MCP `index_codebase` tool auto-derives names from the directory path if `index_name` is not specified, which may not match the configured name. A mismatch causes "Index not found" errors from the CLI.

**Check if an index already exists for this project:**

```
list_indexes()
```

**If index exists:**
- Run `index_stats(index_name="<configured-name>")` to check freshness
- If stale (>7 days): ask "Index is X days old. Reindex to pick up recent changes?"
- If fresh: skip to Step 3

**If no index exists, create one:**

```
index_codebase(path="<current-project-root>", index_name="<configured-name>")
```

**Always pass `index_name` explicitly** to match the project config. If no `cocosearch.yaml` exists, the auto-derived name is fine. Indexing will:
- Discover all supported files (Python, TypeScript, Go, Rust, Java, C/C++, HCL, Dockerfile, Bash, Markdown, YAML)
- Parse symbols via Tree-sitter (functions, classes, methods)
- Generate embeddings via the configured provider (ollama/nomic-embed-text by default)
- Store everything in PostgreSQL with pgvector

**Typical timing:** ~30s for small projects (<100 files), 1-2 min for medium (100-500 files), 3-5 min for large (500+ files).

## Step 3: Verify the Index

After indexing completes, verify it worked:

```
index_stats(index_name="<name>")
```

**Check these indicators:**

- **File count:** Should roughly match your source file count (excluding gitignored files)
- **Parse health:** >80% is good. <80% means some files couldn't be parsed
- **Symbol count:** Should have functions and classes if the project has them
- **Languages:** Verify your primary language appears

**If parse health is low:**
- Run `index_stats(index_name="<name>", include_failures=True)` to see which files failed
- Common causes: unsupported file types (expected), syntax errors in source files

## Step 4: Test a Search

Run a quick semantic search to confirm results are meaningful:

```
search_code(query="main entry point", index_name="<name>")
```

**Good result:** Returns the project's main function, CLI entry point, or app initialization — something clearly relevant.

**Bad result:** Returns unrelated code or no results.

**If results are poor:**
- **Ollama provider:** Check that Ollama is running and the embedding model is loaded (`curl -s http://localhost:11434/api/tags`)
- **Remote provider (openai/openrouter):** Verify `COCOSEARCH_EMBEDDING_API_KEY` is set correctly
- **Any provider with `baseUrl`:** Verify the custom endpoint is reachable
- Try reindexing: `index_codebase(path="<path>", index_name="<configured-name>")`
- Try a more specific query related to your project

## Done!

Your project is indexed and ready for semantic search. Here's what you can do now:

**From the CLI:**
```bash
cocosearch search "your query"              # Basic semantic search
cocosearch search "query" --hybrid          # Hybrid (semantic + keyword)
cocosearch search "query" -i                # Interactive REPL
cocosearch stats                            # Check index health
```

**From MCP (Claude Code / OpenCode):**
```
search_code(query="your query")
search_code(query="authenticate", symbol_type="function", use_hybrid_search=True)
search_code(query="error handling", language="python", smart_context=True)
```

**Recommended next steps:**
- Try the `cocosearch-onboarding` skill for a guided tour of the codebase
- Use `cocosearch-debugging` when investigating bugs
- Use `cocosearch-refactoring` before large code changes

For installation instructions, see `skills/README.md`.
