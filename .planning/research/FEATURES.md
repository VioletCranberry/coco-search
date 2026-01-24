# Feature Research

**Domain:** Code Indexing and Semantic Search (Local-First MCP Server)
**Researched:** 2026-01-24
**Confidence:** MEDIUM-HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Semantic search** | Core value proposition; users expect natural language queries like "where do we handle authentication?" | MEDIUM | CocoIndex + pgvector handles this; use cosine similarity |
| **File path in results** | Users need to know WHERE the code is; every code search tool shows this | LOW | Store as metadata during indexing |
| **Line numbers in results** | Standard for code navigation; allows jumping to exact location | LOW | Track start/end lines per chunk |
| **Language-aware chunking** | Code has structure (functions, classes); naive line splitting breaks context | MEDIUM | CocoIndex has Tree-sitter support for 15+ languages |
| **Gitignore respect** | Nobody wants node_modules or build artifacts indexed | LOW | Parse .gitignore before walking directory |
| **Multiple index support** | Users work on multiple projects; need isolation | LOW | Already in PROJECT.md; namespace by index name |
| **Progress indication** | Indexing can take minutes; users need feedback | LOW | Return status during index_codebase |
| **Basic file filtering** | Exclude binary files, respect common patterns (*.pyc, *.exe) | LOW | Configurable include/exclude globs |
| **Result relevance scores** | Users need to gauge confidence; standard in vector search | LOW | Cosine similarity scores from pgvector |
| **Clear/reindex capability** | Codebase changes; users need fresh indexes | LOW | Already in PROJECT.md requirements |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Fully local processing** | Privacy-first; no code leaves machine; differentiates from GitHub Copilot, Sourcegraph cloud | LOW | Core architecture; Ollama + PostgreSQL in Docker |
| **Incremental indexing** | Only reprocess changed files; critical for large codebases; CocoIndex's signature feature | MEDIUM | CocoIndex tracks data lineage; near-real-time updates possible |
| **Configurable embedding model** | Users can choose accuracy vs speed tradeoff; nomic-embed-text vs all-minilm | MEDIUM | Ollama supports multiple models; expose as config |
| **Language-specific search filters** | "Search only Python files" or "Search only TypeScript" | LOW | Filter by file extension or detected language |
| **Chunk context expansion** | Return surrounding code for better understanding; retrieve neighbors from same file | MEDIUM | Query neighboring chunks by file path + line proximity |
| **Search result deduplication** | Avoid returning near-identical chunks from same function | MEDIUM | Track chunk relationships; dedupe by file+function |
| **Symbol-aware indexing** | Index function/class names as first-class entities; enable "find function X" | HIGH | Requires AST parsing; Tree-sitter can extract |
| **Documentation co-indexing** | Index README, docs alongside code; holistic understanding | LOW | Same pipeline, different file patterns |
| **Configurable chunk sizing** | Tune for embedding model context window; 200-600 tokens typical | LOW | Expose chunk_size and overlap_ratio parameters |
| **Index statistics** | Show indexed file count, chunk count, languages detected | LOW | Aggregate metadata from index tables |

### Anti-Features (Deliberately NOT Building)

Features that seem good but create problems for this project.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Answer synthesis in MCP** | "Just give me the answer, not chunks" | Out of scope per PROJECT.md; adds complexity, model dependency; calling LLM (Claude) synthesizes better | Return ranked chunks; let caller synthesize |
| **Real-time file watching** | "Auto-update when I save files" | Adds daemon complexity; resource usage; edge cases with rapid saves; v1 should be simple | Manual reindex trigger; incremental update reduces pain |
| **Web UI** | "I want to search without Claude" | Scope creep; MCP is the interface; building UI is separate project | MCP only; other clients can wrap if needed |
| **Cloud sync/backup** | "Sync my indexes across machines" | Violates local-first principle; privacy concerns; complexity | Each machine maintains own index |
| **Full regex search** | "I need grep-like regex" | Not semantic search; grep exists; confuses value proposition | Use grep for regex; CocoSearch for semantic |
| **Code completion/generation** | "Suggest code based on search" | Out of scope; that's Copilot territory; MCP returns context, not generates | Return relevant chunks; calling LLM generates |
| **Cross-repository search** | "Search all my repos at once" | Named indexes provide isolation; cross-search adds complexity, performance issues | Index and search per-repository; compose at client level |
| **Hybrid keyword+semantic** | "Combine BM25 with vector search" | Adds complexity; most users want semantic or grep, not both blended | Pure semantic for v1; can add later if validated |
| **Custom embedding models** | "Let me plug in any embedding model" | Ollama provides sufficient variety; custom model support is rabbit hole | Support Ollama model selection; not arbitrary APIs |
| **Diff/commit search** | "Search through git history" | Sourcegraph territory; massively increases storage and complexity | Index current state only; historical search out of scope |

## Feature Dependencies

```
[Core Pipeline]
Language-aware chunking
    |---> Semantic search
    |         |---> File path in results
    |         |---> Line numbers in results
    |         |---> Result relevance scores
    |
    |---> Incremental indexing (requires tracking chunk sources)

[Filtering Layer]
Gitignore respect ---> Basic file filtering ---> Language-specific search filters

[Enhancement Layer - Requires Core]
Symbol-aware indexing --requires--> Language-aware chunking (Tree-sitter AST)
Chunk context expansion --requires--> Line numbers in results
Search result deduplication --requires--> File path + function tracking

[Configuration]
Configurable embedding model --independent
Configurable chunk sizing --independent

[Metadata]
Index statistics --requires--> All indexing features
```

### Dependency Notes

- **Semantic search requires chunking:** Can't embed without chunks; chunking strategy directly impacts search quality
- **Line numbers enable context expansion:** Must track positions to fetch neighbors
- **Tree-sitter enables both chunking and symbol extraction:** Single investment, multiple features
- **Filtering is layered:** Gitignore is base, then file patterns, then language filters
- **Incremental indexing requires lineage tracking:** Must know which chunks came from which files to update correctly

## MVP Definition

### Launch With (v1)

Minimum viable product - what's needed to validate the concept.

- [x] **Semantic search with natural language queries** - Core value; "where is authentication handled?"
- [x] **File path and line numbers in results** - Essential for navigation
- [x] **Language-aware chunking via Tree-sitter** - Quality differentiator; code structure matters
- [x] **Gitignore respect + basic file filtering** - Don't index garbage
- [x] **Named index support** - Multiple codebases without conflicts
- [x] **Result relevance scores** - Users need confidence indicator
- [x] **Clear/reindex commands** - Basic index management
- [x] **Local-only processing** - Core differentiator; Ollama + PostgreSQL

### Add After Validation (v1.x)

Features to add once core is working and users provide feedback.

- [ ] **Incremental indexing** - Add when users complain about reindex time on large codebases
- [ ] **Language-specific search filters** - Add when users want to narrow search scope
- [ ] **Chunk context expansion** - Add when users say "I need more surrounding code"
- [ ] **Configurable embedding model** - Add when users want speed/accuracy tradeoff
- [ ] **Index statistics** - Add for observability; helps debug indexing issues
- [ ] **Documentation co-indexing** - Add when users want holistic project understanding

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **Symbol-aware indexing** - HIGH complexity; validate simpler search first
- [ ] **Search result deduplication** - Nice-to-have; not blocking adoption
- [ ] **Configurable chunk sizing** - Power user feature; defaults should work

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Semantic search | HIGH | MEDIUM | P1 |
| File path in results | HIGH | LOW | P1 |
| Line numbers in results | HIGH | LOW | P1 |
| Language-aware chunking | HIGH | MEDIUM | P1 |
| Gitignore respect | MEDIUM | LOW | P1 |
| Named index support | HIGH | LOW | P1 |
| Result relevance scores | MEDIUM | LOW | P1 |
| Clear/reindex commands | MEDIUM | LOW | P1 |
| Local-only processing | HIGH | LOW | P1 |
| Incremental indexing | HIGH | MEDIUM | P2 |
| Language-specific filters | MEDIUM | LOW | P2 |
| Chunk context expansion | MEDIUM | MEDIUM | P2 |
| Configurable embedding model | MEDIUM | LOW | P2 |
| Index statistics | LOW | LOW | P2 |
| Documentation co-indexing | MEDIUM | LOW | P2 |
| Symbol-aware indexing | MEDIUM | HIGH | P3 |
| Search result deduplication | LOW | MEDIUM | P3 |
| Configurable chunk sizing | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for launch - without these, the product doesn't deliver value
- P2: Should have, add when possible - enhances value, validates with users first
- P3: Nice to have, future consideration - defer until core is proven

## Competitor Feature Analysis

| Feature | Sourcegraph | GitHub Copilot | Cursor @codebase | CocoSearch (Our Approach) |
|---------|-------------|----------------|------------------|---------------------------|
| Semantic search | Yes (Deep Search) | Yes (instant indexing) | Yes (embeddings) | Yes - core feature |
| Local processing | Enterprise only | No (cloud) | Partial (local + remote) | Yes - fully local |
| Line numbers | Yes | Yes | Yes | Yes |
| Language support | 30+ via SCIP | Wide | Wide | Tree-sitter (15+) |
| Incremental index | Yes (database stacking) | Yes (fast re-index) | Yes (Merkle trees) | Yes via CocoIndex |
| Regex search | Yes | Limited | No | No (out of scope) |
| Diff/commit search | Yes | No | No | No (out of scope) |
| Multiple repos | Yes | Yes (org-wide) | Per-project | Yes (named indexes) |
| Privacy | Enterprise | None (cloud) | Partial | Full - nothing leaves machine |
| MCP interface | Yes (recently added) | No | No | Yes - primary interface |
| Cost | Paid/seat | Free tier + paid | Paid | Free (self-hosted) |

**Competitive positioning:** CocoSearch differentiates on privacy (fully local) and simplicity (MCP-first, no cloud dependencies). We don't compete on breadth of features with Sourcegraph, but on trust and simplicity for individual developers and privacy-conscious teams.

## MCP Interface Design Considerations

Based on MCP best practices research:

| Aspect | Recommendation | Rationale |
|--------|----------------|-----------|
| **Error handling** | Use `isError` flag in results, not protocol errors | LLM can see and handle errors; enables retry logic |
| **Result format** | Return structured JSON with chunks, paths, lines, scores | LLM needs structured data to synthesize answers |
| **Chunk content** | Include actual code text, not just references | LLM needs to see code to answer questions |
| **Progress** | Return indexing status/progress in responses | Long operations need feedback |
| **Validation** | Validate inputs early; return clear error messages | Help LLM correct invalid requests |

## Sources

**Code Search Tools & Features:**
- [GitHub Copilot Instant Semantic Indexing](https://github.blog/changelog/2025-03-12-instant-semantic-code-search-indexing-now-generally-available-for-github-copilot/)
- [Sourcegraph Code Search Features](https://sourcegraph.com/docs/code-search/features)
- [Cursor Semantic Search](https://cursor.com/blog/semsearch)
- [Cursor Codebase Indexing](https://docs.cursor.com/context/codebase-indexing)
- [GitLab Semantic Code Search](https://docs.gitlab.com/development/ai_features/semantic_search/)

**Chunking & Embeddings:**
- [Pinecone Chunking Strategies](https://www.pinecone.io/learn/chunking-strategies/)
- [Weaviate Chunking for RAG](https://weaviate.io/blog/chunking-strategies-for-rag)
- [Qdrant Code Search Tutorial](https://qdrant.tech/documentation/advanced-tutorials/code-search/)
- [Chroma Evaluating Chunking](https://research.trychroma.com/evaluating-chunking)

**Local/Self-Hosted:**
- [Ollama Embeddings](https://ollama.com/blog/embedding-models)
- [Weaviate Local RAG with Ollama](https://weaviate.io/blog/local-rag-with-ollama-and-weaviate)
- [Qdrant + Ollama Integration](https://qdrant.tech/documentation/embeddings/ollama/)

**MCP Patterns:**
- [MCP Tools Specification](https://modelcontextprotocol.io/docs/concepts/tools)
- [MCP Error Handling Best Practices](https://mcpcat.io/guides/error-handling-custom-mcp-servers/)
- [MCP Architecture Guide](https://modelcontextprotocol.info/docs/best-practices/)

**Incremental Indexing:**
- [How Cursor Indexes Codebases Fast](https://read.engineerscodex.com/p/how-cursor-indexes-codebases-fast)
- [Meta's Glean Code Indexing](https://engineering.fb.com/2024/12/19/developer-tools/glean-open-source-code-indexing/)
- [CocoIndex Real-Time Indexing](https://cocoindex.io/examples/code_index)

**Code Search Research:**
- [10 Years Later: Revisiting How Developers Search for Code](https://doi.org/10.1145/3715774)
- [Google Code Search Reference](https://developers.google.com/code-search/reference)

---
*Feature research for: Code Indexing and Semantic Search (Local-First MCP Server)*
*Researched: 2026-01-24*
