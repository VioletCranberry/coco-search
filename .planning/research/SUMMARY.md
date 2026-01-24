# Project Research Summary

**Project:** CocoSearch
**Domain:** Local-first code indexing and semantic search with MCP interface
**Researched:** 2026-01-24
**Confidence:** HIGH

## Executive Summary

CocoSearch is a local-first semantic code search tool that indexes codebases using CocoIndex, stores embeddings in PostgreSQL with pgvector, and exposes search capabilities through the Model Context Protocol (MCP). Experts build this type of system with a clear separation between the indexing pipeline (source parsing, chunking, embedding generation) and the query layer (vector similarity search), ensuring that the same embedding model is used for both indexing and querying. The local-first approach using Ollama for embeddings differentiates CocoSearch from cloud-dependent alternatives like GitHub Copilot and Sourcegraph, providing full privacy without code leaving the developer's machine.

The recommended approach is to use CocoIndex with Tree-sitter for language-aware code chunking, `nomic-embed-text` via Ollama for 768-dimensional embeddings, and PostgreSQL 17 with pgvector 0.8.1 for vector storage and HNSW-based similarity search. The MCP server should use FastMCP from the official MCP Python SDK (v1.26.0) with stdio transport. This stack is well-documented, version-compatible, and provides incremental indexing capabilities out of the box.

Key risks include embedding dimension mismatches when models change (requires storing model metadata and validating on startup), fixed-size code chunking that destroys semantic meaning (solved by Tree-sitter language-aware chunking), and Docker volume data loss (mitigated by proper named volume configuration). MCP tool output volume must be limited to avoid overwhelming the calling LLM's context window. All critical pitfalls have clear prevention strategies that should be implemented from Phase 1.

## Key Findings

### Recommended Stack

The stack is centered on CocoIndex (v0.3.28) as the indexing engine, which provides built-in support for Tree-sitter parsing, incremental processing with data lineage tracking, and native PostgreSQL/pgvector export. All dependencies are available via UV package manager as required by project constraints.

**Core technologies:**
- **Python 3.11+**: Runtime requirement for CocoIndex; use 3.11 as minimum
- **CocoIndex 0.3.28**: Indexing engine with Tree-sitter support, incremental processing, pgvector export
- **MCP Python SDK 1.26.0**: Official SDK with FastMCP for tool definition; v1.x for production stability
- **PostgreSQL 17 + pgvector 0.8.1**: Vector storage with HNSW indexing; use `pgvector/pgvector:pg17` Docker image
- **Ollama + nomic-embed-text**: Local embedding generation; 768 dimensions, 8192 token context window
- **UV 0.9.26**: Package manager as specified in project requirements
- **psycopg 3.3.2**: PostgreSQL driver with connection pooling (`[binary,pool]` extras)

### Expected Features

**Must have (table stakes):**
- Semantic search with natural language queries
- File path and line numbers in results
- Language-aware chunking via Tree-sitter (15+ languages)
- Gitignore respect + basic file filtering
- Named index support for multiple codebases
- Result relevance scores (cosine similarity)
- Clear/reindex commands
- Local-only processing (no code leaves machine)

**Should have (v1.x, add after validation):**
- Incremental indexing (CocoIndex's signature feature)
- Language-specific search filters
- Chunk context expansion
- Configurable embedding model selection
- Index statistics

**Defer (v2+):**
- Symbol-aware indexing (HIGH complexity, requires AST parsing)
- Search result deduplication
- Hybrid keyword + semantic search

### Architecture Approach

The architecture follows a three-layer pattern: MCP Server (tool exposure), CocoIndex Flow Layer (indexing pipeline), and Storage Layer (PostgreSQL + Ollama). Each named index gets its own CocoIndex flow definition with unique table names for isolation. MCP tools are thin orchestrators that delegate to flows and storage modules, keeping business logic testable and the MCP layer swappable.

**Major components:**
1. **MCP Server** — Expose index_codebase, search_code, clear_index tools via FastMCP with stdio transport
2. **Flow Manager** — Create/retrieve CocoIndex flows per named index, manage flow lifecycle
3. **LocalFile Source** — Read files with configurable include/exclude patterns, respect gitignore
4. **SplitRecursively Transform** — Language-aware chunking using Tree-sitter for code, fallback for other files
5. **Embed Transform** — Generate embeddings via Ollama (nomic-embed-text) or SentenceTransformer
6. **PostgreSQL + pgvector** — Store vectors with HNSW index, serve similarity queries
7. **Query Handler** — Generate query embedding, execute vector search, format results

### Critical Pitfalls

1. **Embedding dimension mismatch** — Store model name and dimensions in index metadata; validate on every operation; require explicit clear + reindex if model changes
2. **Fixed-size chunking destroys code semantics** — Use CocoIndex's SplitRecursively with Tree-sitter; never split on token count alone; include 10-15% chunk overlap
3. **pgvector performance cliff at scale** — Calculate memory requirements (vectors x dimensions x 4 bytes x 3 HNSW overhead); monitor PostgreSQL memory; set appropriate Docker limits
4. **MCP tool returns overwhelm context window** — Default to 5-10 results maximum; include limit parameter in tool schema; provide relevance scores
5. **Docker volume data loss** — Use named volumes in docker-compose; never use anonymous volumes; test persistence after container restart
6. **Ollama model breaks after upgrade** — Pin model versions where possible; test embedding on startup; fail fast if broken

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Foundation
**Rationale:** PostgreSQL and Ollama are dependencies for all other components. Schema design must include model metadata tracking from day one to prevent dimension mismatch issues. Docker volume persistence must be verified before any real indexing work.
**Delivers:** Working development environment with PostgreSQL + pgvector, Ollama with nomic-embed-text, Docker Compose configuration with persistent volumes, project structure with configuration
**Addresses:** Local-only processing foundation, data persistence
**Avoids:** Docker volume data loss, embedding model version issues

### Phase 2: Indexing Pipeline
**Rationale:** Indexing must work before search. CocoIndex flow definition determines chunking strategy which directly impacts search quality. Tree-sitter integration is critical for code comprehension.
**Delivers:** CocoIndex flow that reads codebase, chunks with Tree-sitter, generates embeddings, exports to PostgreSQL
**Uses:** CocoIndex, SentenceTransformerEmbed (or Ollama embedding), pgvector
**Implements:** LocalFile Source, SplitRecursively Transform, Embed Transform, Collector/Export
**Addresses:** Language-aware chunking, gitignore respect, file filtering
**Avoids:** Code chunking destroying semantic meaning

### Phase 3: Search Implementation
**Rationale:** Search depends on indexed data. Query must use the same embedding transform as indexing. HNSW index tuning needed for performance.
**Delivers:** Vector similarity search with relevance scores, query embedding generation, result formatting
**Uses:** psycopg with connection pooling, pgvector cosine similarity, shared embedding transform
**Implements:** Query Handler, PostgreSQL vector search
**Addresses:** Semantic search, file path in results, line numbers, relevance scores
**Avoids:** Embedding model mismatch between index and query, pgvector performance issues

### Phase 4: MCP Server
**Rationale:** MCP layer is the interface; core functionality must work first. Tool design must consider context window limits.
**Delivers:** FastMCP server with index_codebase, search_code, clear_index tools; stdio transport for Claude Code integration
**Uses:** MCP Python SDK 1.26.0 FastMCP
**Implements:** MCP Server, all tool definitions
**Addresses:** Named index support, clear/reindex commands, result limiting
**Avoids:** MCP tool returns overwhelming context window

### Phase 5: Integration and Polish
**Rationale:** After core functionality works, integrate components, add named index management, handle edge cases, improve error messages.
**Delivers:** End-to-end working system, named index lifecycle management, progress feedback, error handling
**Addresses:** Multiple index support, progress indication, error messages
**Avoids:** Named index collisions, cryptic error messages

### Phase Ordering Rationale

- **Foundation before Pipeline:** CocoIndex requires PostgreSQL connection; Ollama must be available for embeddings
- **Pipeline before Search:** Search queries indexed data; chunking strategy directly impacts retrieval quality
- **Search before MCP:** MCP tools are thin wrappers around search/index functionality
- **Integration last:** Ensures each component works independently before combining

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Indexing Pipeline):** CocoIndex Tree-sitter integration specifics, optimal chunk sizes for different languages, handling of large files
- **Phase 3 (Search):** pgvector HNSW parameter tuning (ef_construction, m), query performance optimization

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** Docker Compose, PostgreSQL setup are well-documented standard patterns
- **Phase 4 (MCP Server):** FastMCP has clear tutorials and examples; straightforward tool definitions

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified from PyPI, official docs; CocoIndex 0.3.28, MCP SDK 1.26.0, pgvector 0.8.1 confirmed |
| Features | MEDIUM-HIGH | Based on competitor analysis and industry patterns; validated against Cursor, Sourcegraph, GitHub Copilot |
| Architecture | HIGH | CocoIndex examples, MCP SDK docs, reference implementations reviewed; clear patterns established |
| Pitfalls | MEDIUM-HIGH | Sourced from multiple production experiences; CocoIndex-specific details verified in official docs |

**Overall confidence:** HIGH

### Gaps to Address

- **Ollama embedding integration specifics:** CocoIndex docs show EmbedText with Ollama but SentenceTransformerEmbed is better documented. May need to validate Ollama integration during Phase 2 or use SentenceTransformerEmbed as primary.
- **Large codebase performance:** Research indicates architecture works to ~100K files but real-world validation needed for specific chunk sizes and indexing time.
- **MCP tool concurrency:** Research doesn't cover concurrent index + search operations; may need validation during Phase 5.

## Sources

### Primary (HIGH confidence)
- [CocoIndex PyPI](https://pypi.org/project/cocoindex/) — Version 0.3.28, Python 3.11+
- [MCP Python SDK PyPI](https://pypi.org/project/mcp/) — Version 1.26.0
- [pgvector GitHub](https://github.com/pgvector/pgvector) — Extension v0.8.1, HNSW indexing
- [CocoIndex Code Indexing Example](https://cocoindex.io/docs/examples/code_index) — Reference implementation
- [MCP Python SDK GitHub](https://github.com/modelcontextprotocol/python-sdk) — FastMCP documentation

### Secondary (MEDIUM confidence)
- [Continue.dev Top Ollama Models](https://resources.continue.dev/top-ollama-coding-models-q4-2025/) — nomic-embed-text recommended for code
- [Cursor Codebase Indexing](https://docs.cursor.com/context/codebase-indexing) — Chunking and embedding patterns
- [Pinecone Chunking Strategies](https://www.pinecone.io/learn/chunking-strategies/) — RAG chunking best practices

### Tertiary (LOW confidence)
- Community reports on pgvector performance at scale — needs validation for specific use case
- Ollama model versioning behavior — based on GitHub issues, may vary by version

---
*Research completed: 2026-01-24*
*Ready for roadmap: yes*
