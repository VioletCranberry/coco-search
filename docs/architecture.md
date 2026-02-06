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

**Tree-sitter:** Language-aware code parser supporting 31 programming languages. Used by CocoIndex's `SplitRecursively` function to chunk code at semantic boundaries (function definitions, class boundaries) rather than arbitrary byte offsets. Default chunk size: 1000 bytes with 300 byte overlap.

**FastMCP:** Model Context Protocol server framework exposing CocoSearch functionality as tools for AI assistants (Claude Code, Claude Desktop, OpenCode). Provides stdio, SSE, and HTTP transports for client integration. Implementation: `src/cocosearch/mcp/server.py`

## Data Flow — Indexing

The indexing pipeline transforms a codebase into searchable vector embeddings:

1. **File Discovery:** Read codebase files respecting `.gitignore` patterns and configured include/exclude filters
2. **Language Detection:** Identify programming language from file extension (handles special cases like Dockerfile)
3. **Semantic Chunking:** Tree-sitter parses code and splits at semantic boundaries (1000 bytes, 300 overlap)
4. **Embedding Generation:** Ollama's `nomic-embed-text` model converts each chunk to a 768-dimensional vector
5. **Metadata Extraction:** Extract DevOps block types (pipeline, job, stage), symbol information (function/class/method names, signatures), and language identifiers
6. **Text Preprocessing:** Generate tsvector representation for full-text search capabilities
7. **Storage:** Insert chunks into PostgreSQL with vector index (cosine distance) and GIN index (tsvector)

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

## MCP Integration

CocoSearch exposes five MCP tools for AI assistant integration:

- `search_code` — Semantic search with hybrid mode, symbol filtering, context expansion
- `index_codebase` — Create or update code index from directory path
- `list_indexes` — Show all available indexes with metadata
- `index_stats` — Get statistics (file count, chunk count, language breakdown, staleness)
- `clear_index` — Delete an index and all associated data

**Transport Support:** stdio (Claude Code), SSE (server-sent events), HTTP (Claude Desktop via mcp-remote bridge)

**Project Detection:** The `--project-from-cwd` flag enables automatic index detection from working directory. MCP clients can work across multiple projects without manual configuration per project.

See [MCP Tools Reference](mcp-tools.md) for complete parameter documentation, return formats, and usage examples.

## Key Design Decisions

**Local-first:** All processing happens on your machine. Ollama runs the embedding model locally, PostgreSQL stores data locally, no external API calls. Your code never leaves your environment.

**Hybrid search:** Combines vector similarity (semantic understanding) with PostgreSQL full-text search (keyword precision). Automatically enabled for identifier patterns, manually available for all queries. Solves the "exact function name match" problem that pure semantic search struggles with.

**RRF fusion:** Merges vector and keyword result lists using rank-based scoring rather than raw scores. Avoids score normalization issues when combining different search strategies. Each result's rank contributes inversely to final score: `score += 1 / (rank + 60)`.

**Definition boost:** Multiplies RRF scores by 2x for chunks marked as definitions (functions, classes, methods). Applied post-fusion to preserve ranking integrity. Prioritizes function/class definitions over usage examples.

**Two-level query cache:** Exact hash match for identical queries returns cached results immediately. Semantic similarity fallback (0.95 cosine threshold) catches near-duplicate queries with minor phrasing differences. Cleared automatically when index is updated.

**Reference storage:** Store file paths and byte offsets, not chunk text. Chunk content is read from source files at query time using byte offsets. Reduces database size and ensures search results reflect current file contents (not stale cached text).

**Semantic chunking:** Tree-sitter provides language-aware code splitting at function/class boundaries rather than arbitrary byte counts. Produces more coherent chunks that better represent logical code units. Falls back to simple splitting for unsupported languages.

**Symbol metadata:** Extract function/class/method names and signatures during indexing for precise filtering. Enables queries like "find all functions named `validate*`" or "show only class definitions". Currently supported for 10 languages (Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, Ruby, PHP).
