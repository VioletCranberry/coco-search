# Architecture Research

**Domain:** Local code indexing with MCP interface
**Researched:** 2026-01-24
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MCP Client Layer                                   │
│                    (Claude Code, Cursor, other MCP hosts)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                              MCP Server                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                 │
│  │ index_codebase │  │  search_code   │  │  clear_index   │                 │
│  │     tool       │  │     tool       │  │     tool       │                 │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘                 │
│          │                   │                   │                           │
├──────────┴───────────────────┴───────────────────┴───────────────────────────┤
│                          CocoIndex Flow Layer                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Flow Manager (per named index)                  │    │
│  │  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────────┐   │    │
│  │  │  Source  │→ │ SplitRecurs- │→ │  Embed    │→ │  Collector   │   │    │
│  │  │LocalFile │  │    ively     │  │  (Ollama) │  │  & Export    │   │    │
│  │  └──────────┘  └──────────────┘  └───────────┘  └──────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────────────┤
│                            Storage Layer                                     │
│  ┌────────────────────────────┐  ┌────────────────────────────┐             │
│  │     PostgreSQL + pgvector  │  │         Ollama             │             │
│  │  ┌──────────────────────┐  │  │  ┌──────────────────────┐  │             │
│  │  │ cocoindex_internal   │  │  │  │ nomic-embed-text     │  │             │
│  │  │ (state tracking)     │  │  │  │ (embedding model)    │  │             │
│  │  ├──────────────────────┤  │  │  └──────────────────────┘  │             │
│  │  │ index_<name>_chunks  │  │  │                            │             │
│  │  │ (vector storage)     │  │  │                            │             │
│  │  └──────────────────────┘  │  │                            │             │
│  └────────────────────────────┘  └────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **MCP Server** | Expose tools to MCP clients, route requests | FastMCP Python SDK with stdio transport |
| **Flow Manager** | Manage CocoIndex flows per named index | CocoIndex flow definitions, one per index |
| **LocalFile Source** | Read files from codebase directory | CocoIndex `sources.LocalFile` with glob patterns |
| **SplitRecursively** | Chunk code respecting syntax boundaries | CocoIndex function with Tree-sitter, per-language |
| **Embed Function** | Generate embeddings for chunks | Ollama API or SentenceTransformerEmbed |
| **Collector/Export** | Aggregate chunks, write to PostgreSQL | CocoIndex collector + `targets.Postgres` |
| **PostgreSQL** | Store vectors, enable similarity search | Docker container with pgvector extension |
| **Ollama** | Serve local embedding model | Local Ollama server with nomic-embed-text |

## Recommended Project Structure

```
coco-search/
├── pyproject.toml           # UV project config, dependencies
├── src/
│   └── coco_search/
│       ├── __init__.py
│       ├── server.py        # MCP server entry point (FastMCP)
│       ├── tools/           # MCP tool implementations
│       │   ├── __init__.py
│       │   ├── index.py     # index_codebase tool
│       │   ├── search.py    # search_code tool
│       │   └── clear.py     # clear_index tool
│       ├── flows/           # CocoIndex flow definitions
│       │   ├── __init__.py
│       │   ├── code_flow.py # Flow definition for code indexing
│       │   └── embed.py     # Embedding transform flow (shared)
│       ├── storage/         # Database interaction
│       │   ├── __init__.py
│       │   ├── postgres.py  # PostgreSQL connection, queries
│       │   └── index_manager.py  # Named index management
│       └── config.py        # Configuration (DB URL, Ollama URL)
├── docker/
│   └── docker-compose.yml   # PostgreSQL + pgvector container
└── tests/
    └── ...
```

### Structure Rationale

- **tools/:** Each MCP tool isolated for clear boundaries; tools orchestrate flows but don't contain logic
- **flows/:** CocoIndex flow definitions separate from MCP layer; reusable and testable independently
- **storage/:** Database concerns isolated; index_manager handles named index lifecycle
- **config.py:** Single source for environment-dependent configuration

## Architectural Patterns

### Pattern 1: Flow-per-Index

**What:** Each named index gets its own CocoIndex flow definition with unique export table names
**When to use:** Always for this project (multiple named indexes requirement)
**Trade-offs:**
- Pro: Clean isolation between codebases, independent incremental updates
- Con: More flows to manage, need flow lifecycle management

**Example:**
```python
def create_code_flow(index_name: str, codebase_path: str):
    @cocoindex.flow_def(name=f"CodeIndex_{index_name}")
    def code_flow(flow_builder, data_scope):
        data_scope["files"] = flow_builder.add_source(
            cocoindex.sources.LocalFile(
                path=codebase_path,
                included_patterns=["*.py", "*.js", "*.ts", "*.rs", "*.go", "*.md"],
                excluded_patterns=[".*", "node_modules", "target", "__pycache__"]
            )
        )
        # ... transformations
        collector.export(
            f"{index_name}_chunks",  # Unique table per index
            cocoindex.targets.Postgres(),
            primary_key_fields=["filename", "chunk_location"],
            vector_indexes=[...]
        )
    return code_flow
```

### Pattern 2: Shared Transform Flow for Embeddings

**What:** Define embedding transformation once, reuse in both indexing and query
**When to use:** Always when you need to query with the same embedding model
**Trade-offs:**
- Pro: Guarantees consistent embeddings between index and query
- Con: Minor additional abstraction

**Example:**
```python
@cocoindex.transform_flow()
def text_to_embedding(text: cocoindex.DataSlice[str]) -> cocoindex.DataSlice[list[float]]:
    return text.transform(
        cocoindex.functions.SentenceTransformerEmbed(
            model="sentence-transformers/all-MiniLM-L6-v2"
        )
    )

# In query code:
query_embedding = text_to_embedding.eval(query_text)
```

### Pattern 3: MCP Tool as Orchestrator

**What:** MCP tools are thin orchestration layers that delegate to flows/storage
**When to use:** All MCP tool implementations
**Trade-offs:**
- Pro: Testable business logic, swappable MCP layer
- Con: One more layer of indirection

**Example:**
```python
@mcp.tool()
async def index_codebase(index_name: str, path: str) -> str:
    """Index a codebase directory under a named index."""
    # Validate inputs
    if not os.path.isdir(path):
        return f"Error: {path} is not a valid directory"

    # Delegate to flow manager
    flow = create_code_flow(index_name, path)
    result = await run_indexing_flow(flow)

    return f"Indexed {result.files_processed} files into '{index_name}'"
```

## Data Flow

### Indexing Flow

```
User calls index_codebase(name="myproject", path="/path/to/code")
    │
    ▼
MCP Server receives tool call
    │
    ▼
Flow Manager creates/retrieves flow for "myproject"
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ CocoIndex Flow Execution                                        │
│                                                                 │
│   LocalFile Source                                              │
│   └── Reads: *.py, *.js, *.ts, *.rs, *.go, *.md                │
│       Excludes: node_modules, .git, __pycache__                │
│       │                                                         │
│       ▼                                                         │
│   For each file:                                                │
│   ├── Extract extension → detect language                       │
│   ├── SplitRecursively(language, chunk_size=1000, overlap=200) │
│   │   └── Tree-sitter parses AST, chunks at function/class     │
│   ├── For each chunk:                                           │
│   │   └── Generate embedding via Ollama API                     │
│   └── Collector gathers: filename, location, text, embedding   │
│       │                                                         │
│       ▼                                                         │
│   Export to PostgreSQL table: myproject_chunks                  │
│   └── Vector index created with COSINE_SIMILARITY              │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
Return success message to MCP client
```

### Search Flow

```
User calls search_code(index_name="myproject", query="authentication logic")
    │
    ▼
MCP Server receives tool call
    │
    ▼
Search handler:
    │
    ├── 1. Generate query embedding
    │      └── text_to_embedding.eval("authentication logic")
    │          └── Ollama: nomic-embed-text → [0.123, -0.456, ...]
    │
    ├── 2. Execute similarity search
    │      └── SQL: SELECT filename, location, text,
    │                      embedding <=> query_vector AS distance
    │               FROM myproject_chunks
    │               ORDER BY distance LIMIT 10
    │
    └── 3. Return results
           └── [{filename, location, text, score}, ...]
    │
    ▼
MCP returns chunks to client (Claude synthesizes answer)
```

### Key Data Flows

1. **Indexing:** File → AST Parse → Chunks → Embeddings → PostgreSQL (one-time or on-demand)
2. **Query:** Query text → Embedding → Vector similarity → Ranked chunks → MCP response
3. **Clear:** Delete from PostgreSQL tables + CocoIndex internal state for named index

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-10k files | Current architecture fine; single PostgreSQL, single Ollama |
| 10k-100k files | Increase PostgreSQL resources; HNSW index parameters; batch embedding |
| 100k+ files | Shard by directory; consider parallel flow execution; GPU for embeddings |

### Scaling Priorities

1. **First bottleneck: Embedding generation** — Ollama CPU inference is slow for large codebases. Mitigation: Use GPU if available; batch embedding calls; consider pre-computed models.
2. **Second bottleneck: PostgreSQL vector search** — Default HNSW works to ~1M vectors. Mitigation: Tune ef_construction and m parameters; ensure adequate memory.

**Note:** For a local-first code search tool, most codebases will be well under 100k files. Optimize for developer experience first, not theoretical scale.

## Anti-Patterns

### Anti-Pattern 1: Fixed-Token Chunking for Code

**What people do:** Split code every N tokens regardless of syntax
**Why it's wrong:** Functions/classes split mid-way lose semantic meaning; retrieval returns nonsensical fragments
**Do this instead:** Use SplitRecursively with language parameter — Tree-sitter respects AST boundaries

### Anti-Pattern 2: Embedding at Query Time with Different Model

**What people do:** Use one embedding model during indexing, different model/version at query time
**Why it's wrong:** Vector spaces don't align; similarity search returns poor results
**Do this instead:** Use `@cocoindex.transform_flow()` to share exact same embedding logic between index and query

### Anti-Pattern 3: Monolithic MCP Tool Logic

**What people do:** Put all indexing logic directly in MCP tool function
**Why it's wrong:** Untestable; couples MCP protocol to business logic; hard to debug
**Do this instead:** MCP tools are thin orchestrators; delegate to flows and storage modules

### Anti-Pattern 4: Storing All Metadata in Vector Table

**What people do:** Add many metadata columns (author, date, imports, etc.) to the chunks table
**Why it's wrong:** Bloats storage; most metadata unused in similarity search; slows queries
**Do this instead:** Store minimal metadata (filename, location, text, embedding); add filtering columns only when needed for search

### Anti-Pattern 5: Synchronous Indexing in MCP Tool

**What people do:** Block MCP tool call until entire codebase indexed
**Why it's wrong:** Large codebases take minutes; MCP clients may timeout; poor UX
**Do this instead:** For v1 with manual triggers, this is acceptable. For production, consider async with status polling.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| PostgreSQL | `COCOINDEX_DATABASE_URL` env var | CocoIndex manages connection; also used for internal state |
| Ollama | HTTP API at `localhost:11434` | Or `OLLAMA_HOST` env var if different |
| File System | `LocalFile` source with path | Ensure read permissions on target directories |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| MCP Server ↔ Flow Manager | Direct Python calls | Same process; flow manager owns flow lifecycle |
| Flow Manager ↔ CocoIndex | CocoIndex Python API | Declarative flow definitions; CocoIndex handles execution |
| CocoIndex ↔ PostgreSQL | Internal (handled by CocoIndex) | User provides connection URL; CocoIndex manages tables |
| Search Tool ↔ PostgreSQL | Direct SQL via psycopg2/asyncpg | Query flow bypasses CocoIndex; direct vector search |
| Embedding ↔ Ollama | HTTP POST to /api/embed | Or use SentenceTransformerEmbed for local inference |

## Build Order Dependencies

Based on component dependencies, suggested implementation order:

```
Phase 1: Foundation
├── PostgreSQL Docker setup (no dependencies)
├── Ollama configuration (no dependencies)
└── Basic project structure with config

Phase 2: Indexing Pipeline
├── CocoIndex flow definition (depends: PostgreSQL, Ollama)
├── Embedding function setup (depends: Ollama)
└── Verify flow runs independently

Phase 3: MCP Server
├── FastMCP server skeleton (no dependencies)
├── index_codebase tool (depends: Phase 2 flow)
├── search_code tool (depends: PostgreSQL, embedding function)
└── clear_index tool (depends: PostgreSQL)

Phase 4: Integration
├── Named index management (depends: Phase 2, 3)
├── End-to-end testing
└── Error handling and edge cases
```

**Critical path:** PostgreSQL → CocoIndex flow → MCP integration

## Ollama Embedding Integration

CocoIndex provides two embedding options relevant to local-first:

1. **SentenceTransformerEmbed** — Uses HuggingFace models locally; model downloaded on first use
2. **EmbedText with Ollama** — Uses Ollama's API (not documented in CocoIndex, may need custom function)

For true local-first with Ollama:

```python
# Option A: Use SentenceTransformerEmbed (simpler, well-documented)
chunk["embedding"] = chunk["text"].transform(
    cocoindex.functions.SentenceTransformerEmbed(
        model="sentence-transformers/all-MiniLM-L6-v2"
    )
)

# Option B: Custom Ollama embedding function (if SentenceTransformer insufficient)
@cocoindex.op.function()
def ollama_embed(text: str) -> list[float]:
    response = requests.post(
        "http://localhost:11434/api/embed",
        json={"model": "nomic-embed-text", "input": text}
    )
    return response.json()["embeddings"][0]
```

**Recommendation:** Start with SentenceTransformerEmbed (well-documented, proven). Switch to custom Ollama function only if specific model needed.

## Sources

- [CocoIndex GitHub Repository](https://github.com/cocoindex-io/cocoindex)
- [CocoIndex Real-time Codebase Indexing Example](https://cocoindex.io/docs/examples/code_index)
- [CocoIndex Functions Documentation](https://cocoindex.io/docs/ops/functions)
- [MCP Architecture Overview](https://modelcontextprotocol.io/docs/learn/architecture)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [aanno/cocoindex-code-mcp-server](https://github.com/aanno/cocoindex-code-mcp-server) — Reference implementation
- [AmanMCP Local RAG Architecture](https://dev.to/nirajkvinit1/building-a-local-first-rag-engine-for-ai-coding-assistants-okp)

---
*Architecture research for: CocoSearch local code indexing system*
*Researched: 2026-01-24*
