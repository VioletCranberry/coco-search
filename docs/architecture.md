# CocoSearch Architecture Overview

CocoSearch is a hybrid semantic code search system that runs entirely locally. This document provides a high-level overview of the system's components, data flow, and design decisions.

## Core Concepts

**Embeddings:** Machine learning models convert text (code chunks) into high-dimensional vectors that capture semantic meaning. Similar code produces similar vectors, even when written differently. CocoSearch uses 768-dimensional embeddings to represent code chunks.

**Vector Search:** Finding relevant code by computing cosine similarity between the query embedding and stored chunk embeddings. High similarity scores (close to 1.0) indicate semantically related code, regardless of exact keyword matches.

**Reciprocal Rank Fusion (RRF):** A rank-based method for merging multiple ranked result lists without requiring score normalization. Each search strategy (vector similarity, keyword matching) produces a ranked list; RRF combines them by summing reciprocal ranks. See [Retrieval Logic](retrieval.md) for formula and implementation details.

## System Components

**Ollama:** Local embedding model server running `nomic-embed-text`, which generates 768-dimensional vectors from code chunks. No external API calls — everything runs on your machine. Implementation: `src/cocosearch/indexer/embedder.py`

**PostgreSQL + pgvector:** Database storing code chunks with their vector embeddings. The pgvector extension enables efficient cosine similarity search over embedding vectors. Also provides full-text search via tsvector columns for keyword matching. Implementation: `src/cocosearch/search/db.py`

**CocoIndex:** Python framework orchestrating the indexing pipeline. Handles file reading, language-aware chunking via Tree-sitter, embedding generation, metadata extraction, and PostgreSQL storage. The flow definition coordinates all processing steps. Implementation: `src/cocosearch/indexer/flow.py`

**Tree-sitter:** Language-aware code parser. Used in two independent roles: (1) **chunking** — CocoIndex's `SplitRecursively` uses Tree-sitter internally for ~20 built-in languages to split at syntax boundaries; languages not in CocoIndex's built-in list use custom handler regex separators or plain-text fallback; (2) **symbol extraction** — CocoSearch runs Tree-sitter queries (`.scm` files) to extract function/class/method names for 13 languages. Default chunk size: 1000 bytes with 300 byte overlap.

**FastMCP:** Model Context Protocol server framework exposing CocoSearch functionality as tools for AI assistants (Claude Code, Claude Desktop, OpenCode). Provides stdio, SSE, and HTTP transports for client integration. Supports the MCP Roots capability for automatic project detection in clients that support it (such as Claude Code). Implementation: `src/cocosearch/mcp/server.py`

## Data Flow — Indexing

The indexing pipeline transforms a codebase into searchable vector embeddings:

1. **File Discovery:** Read codebase files respecting `.gitignore` patterns and configured include/exclude filters
2. **Language Detection:** Identify language from grammar handlers (path + content matching), filename patterns (Dockerfile), or file extension. Grammar match takes priority over extension.
3. **Semantic Chunking:** `SplitRecursively` routes to Tree-sitter (built-in languages), custom handler regex separators (HCL, Dockerfile, Bash, grammars), or plain-text splitting (everything else). Default: 1000 bytes, 300 overlap.
4. **Embedding Generation:** File path prepended to chunk text for context, then Ollama's `nomic-embed-text` model converts each chunk to a 768-dimensional vector
5. **Metadata Extraction:** Extract DevOps block types (pipeline, job, stage), symbol information (function/class/method names, signatures), and language identifiers
6. **Text Preprocessing:** Generate tsvector representation for full-text search, including filename-derived tokens for path-aware keyword matching
7. **Storage:** Insert chunks into PostgreSQL with vector index (cosine distance) and GIN index (tsvector)
8. **Parse Tracking:** After indexing completes, parse results are recorded per file (ok, partial, error, no_grammar). This non-fatal tracking provides observability into tree-sitter parse health.

See [Retrieval Logic](retrieval.md) for complete pipeline details including error handling and performance optimizations.

## Data Flow — Search

The search pipeline combines semantic understanding with keyword precision:

1. **Query Analysis:** Detect identifier patterns (camelCase, snake_case) to auto-enable hybrid search
2. **Embedding Generation:** Convert query to 768-dimensional vector using same Ollama model as indexing
3. **Vector Similarity Search:** Find chunks with highest cosine similarity to query embedding
4. **Keyword Search (Optional):** Full-text search via PostgreSQL tsvector for exact identifier matches
5. **RRF Fusion:** Merge vector and keyword result lists using Reciprocal Rank Fusion
6. **Definition Boost:** Apply 2x score multiplier to definition chunks (functions, classes) post-fusion
7. **Filtering:** Apply symbol type filters (function/class/method) and symbol name patterns (glob matching)
8. **Language Filtering:** Restrict results to specified programming languages if requested
9. **Context Expansion:** Expand matched chunks to enclosing function/class boundaries for better understanding
10. **Query Caching:** Store results with exact hash match and semantic similarity fallback (0.95 threshold)

See [Retrieval Logic](retrieval.md) for scoring formulas, cache implementation, and performance characteristics.

## Data Flow — Dependency Graph

The dependency graph captures import/call/reference relationships between files, enabling "who depends on this?" and "what does this depend on?" queries.

1. **File Enumeration:** Query the chunks table for all indexed files with known language IDs
2. **Extraction:** For each file with a registered extractor, parse the source and emit `DependencyEdge` objects. 8 extractors cover: Python imports (tree-sitter), JavaScript/TypeScript (ES6 imports, CommonJS require, re-exports via tree-sitter), Go imports (tree-sitter), Docker Compose (YAML-parsed: image refs, depends_on, extends), GitHub Actions (YAML-parsed: uses action/workflow refs), Terraform (regex-based: module source attributes), Helm (template includes, values image refs, Chart.yaml subchart dependencies).
3. **Module Resolution:** After all extractors finish, a pluggable resolver framework (`resolver.py`) resolves module names to file paths. Four resolvers: **Python** (dotted modules, `__init__.py` packages, relative imports, `src/`/`lib/` prefix stripping), **JavaScript** (extension probing `.js/.ts/.jsx/.tsx` + index files, bare specifiers → None), **Go** (import path suffix matching against indexed directories), **Terraform** (local `./`/`../` module sources). Unresolvable modules (third-party packages) keep `target_file=None`.
4. **Storage:** Resolved edges are batch-inserted into a per-index table (`cocosearch_deps_{index_name}`) with columns for source/target file, source/target symbol, dependency type, and JSON metadata.
5. **Transitive Queries:** BFS-based traversal for forward dependencies (`get_dependency_tree`) and reverse impact analysis (`get_impact`). Both support configurable depth limits (default 5) and cycle detection via visited sets. Returns `DependencyTree` structures for tree visualization.

Extraction runs as a separate pass after CocoIndex indexing — triggered by `--deps` flag on `index` or standalone via `deps extract`.

**Implementation:** `src/cocosearch/deps/` — `extractor.py` (orchestrator), `resolver.py` (module resolution framework), `extractors/` (8 language/grammar extractors), `db.py` (storage), `query.py` (direct + transitive lookups), `models.py` (DependencyEdge, DependencyTree, DepType), `registry.py` (autodiscovery)

## MCP Integration

CocoSearch exposes seven MCP tools for AI assistant integration:

- `search_code` — Async semantic search with hybrid mode, symbol filtering, context expansion. Optional `include_deps` parameter attaches dependency info to results. Accepts Context for Roots-based project detection.
- `index_codebase` — Create or update code index from directory path
- `list_indexes` — Show all available indexes with metadata
- `index_stats` — Get statistics including parse health data and optional `include_failures` parameter for detailed failure listing
- `clear_index` — Delete an index and all associated data (including parse results)
- `get_file_dependencies` — Forward dependency query: what does a file depend on? `depth=1` returns flat edge list, `depth>1` returns transitive tree with cycle detection.
- `get_file_impact` — Reverse impact query: what depends on this file? Returns transitive impact tree for change analysis.

**Transport Support:** stdio (Claude Code), SSE (server-sent events), HTTP (Claude Desktop via mcp-remote bridge)

**Project Detection:** CocoSearch uses a priority chain for automatic index detection: MCP Roots (automatic in Claude Code) > `--project-from-cwd` environment variable > current working directory. In clients that support Roots (like Claude Code), the project is detected automatically with no configuration needed.

See [MCP Tools Reference](mcp-tools.md) for complete parameter documentation, return formats, and usage examples.

## Key Design Decisions

**Local-first:** All processing happens on your machine. Ollama runs the embedding model locally, PostgreSQL stores data locally, no external API calls. Your code never leaves your environment.

**Infra-only Docker:** Docker provides PostgreSQL+pgvector and Ollama infrastructure only. CocoSearch runs natively via `uvx` for faster iteration and simpler updates. This keeps the Docker image lightweight and avoids Python dependency management inside containers.

**Hybrid search:** Combines vector similarity (semantic understanding) with PostgreSQL full-text search (keyword precision). Automatically enabled for identifier patterns, manually available for all queries. Solves the "exact function name match" problem that pure semantic search struggles with.

**RRF fusion:** Merges vector and keyword result lists using rank-based scoring rather than raw scores. Avoids score normalization issues when combining different search strategies. Each result's rank contributes inversely to final score: `score += 1 / (rank + 60)`.

**Definition boost:** Multiplies RRF scores by 2x for chunks marked as definitions (functions, classes, methods). Applied post-fusion to preserve ranking integrity. Prioritizes function/class definitions over usage examples.

**Two-level query cache:** Exact hash match for identical queries returns cached results immediately. Semantic similarity fallback (0.95 cosine threshold) catches near-duplicate queries with minor phrasing differences. Cleared automatically when index is updated.

**Reference storage:** Store file paths and byte offsets, not chunk text. Chunk content is read from source files at query time using byte offsets. Reduces database size and ensures search results reflect current file contents (not stale cached text).

**Semantic chunking:** Three-tier strategy: (1) Tree-sitter via CocoIndex's built-in list for ~20 languages — splits at function/class boundaries; (2) Custom regex separators for handler languages (HCL, Dockerfile, Bash, Go Template, Scala) and grammar handlers (GitHub Actions, GitLab CI, Docker Compose); (3) Plain-text fallback for everything else. Produces more coherent chunks that better represent logical code units.

**Symbol metadata:** Extract function/class/method names and signatures during indexing for precise filtering. Enables queries like "find all functions named `validate*`" or "show only class definitions". Currently supported for 13 languages (Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, Ruby, PHP, Scala, HCL, Bash).

**Parse tracking:** Non-fatal parse status tracking per file provides observability without blocking indexing. Each file receives a status (ok, partial, error, no_grammar) based on tree-sitter results. Parse failures are surfaced in stats output and available via the MCP `index_stats` tool.
