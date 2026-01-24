# Stack Research

**Domain:** Local-first code/documentation indexer with semantic search, exposed via MCP
**Researched:** 2026-01-24
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | Runtime | CocoIndex requires 3.11+. MCP SDK supports 3.10+. Use 3.11 as the minimum for best compatibility. |
| UV | 0.9.26 | Package manager | Project requirement. 10-100x faster than pip, universal lockfile, replaces pip/pipx/poetry/virtualenv. |
| CocoIndex | 0.3.28 | Indexing engine | Core requirement. Production-ready incremental processing, Tree-sitter parsing, native pgvector support. |
| MCP Python SDK | 1.26.0 | MCP server | Official SDK with FastMCP high-level framework. Stable v1.x recommended (v2 in pre-alpha). |
| PostgreSQL | 17 | Database | Required by CocoIndex for incremental processing. Use latest stable (17) with pgvector. |
| pgvector | 0.8.1 | Vector search | Extension for PostgreSQL. Supports HNSW indexing, cosine/L2/IP distance, up to 2000 dimensions. |
| Ollama | latest | Local LLM runtime | Runs embedding models locally. No API keys, full privacy, OpenAI-compatible API. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| psycopg | 3.3.2 | PostgreSQL driver | Required for database queries. Install with `psycopg[binary,pool]` for connection pooling. |
| pgvector (Python) | 0.4.2 | Vector type support | Required for registering vector types with psycopg. |
| ollama | 0.6.1 | Ollama client | Optional - CocoIndex has native Ollama support via `EmbedText`. Use for direct API access if needed. |
| pydantic | 2.x | Data validation | Required by MCP SDK. Automatic with `mcp[cli]` install. |

### Embedding Model

| Model | Dimensions | Context | Why Recommended |
|-------|------------|---------|-----------------|
| nomic-embed-text | 768 | 8192 tokens | **Primary recommendation.** Best balance of quality and performance for code. Used by Continue.dev for codebase indexing. Outperforms OpenAI ada-002. |
| mxbai-embed-large | 1024 | 512 tokens | Alternative for highest quality. 334M parameters, state-of-the-art performance. |
| all-minilm | 384 | 256 tokens | Lightweight option. 23M parameters, good for resource-constrained environments. |

**Recommendation:** Use `nomic-embed-text` as primary. 768 dimensions, 8192 token context handles entire code files.

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Docker / Docker Compose | PostgreSQL + pgvector | Use `pgvector/pgvector:pg17` image. Simplest setup, no manual extension install. |
| MCP Inspector | Debug MCP server | Built into FastMCP. Run `mcp dev` to test tools interactively. |
| pytest | Testing | Standard Python testing. Use with `uv run pytest`. |
| ruff | Linting/formatting | Fast, replaces flake8/black/isort. Configure in pyproject.toml. |

## Installation

```bash
# Initialize project with UV
uv init cocosearch
cd cocosearch

# Core dependencies
uv add cocoindex[embeddings]
uv add "mcp[cli]"
uv add "psycopg[binary,pool]"
uv add pgvector

# Dev dependencies
uv add --dev pytest ruff

# Pull embedding model in Ollama
ollama pull nomic-embed-text
```

### Docker Compose for PostgreSQL + pgvector

```yaml
# docker-compose.yml
services:
  db:
    image: pgvector/pgvector:pg17
    container_name: cocosearch-db
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: cocoindex
      POSTGRES_PASSWORD: cocoindex
      POSTGRES_DB: cocoindex
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Environment Configuration

```bash
# .env
COCOINDEX_DATABASE_URL=postgresql://cocoindex:cocoindex@localhost:5432/cocoindex
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| CocoIndex + pgvector | LanceDB | Simpler setup (no PostgreSQL). Use if you want embedded DB and don't need incremental processing. |
| CocoIndex + pgvector | Qdrant | Better for cloud deployment. CocoIndex supports Qdrant natively. |
| nomic-embed-text | sentence-transformers/all-MiniLM-L6-v2 | Smaller model (384 dim). Use if 768 dim is too large for your setup. |
| MCP SDK FastMCP | Standalone fastmcp | MCP SDK includes FastMCP. Only use standalone `fastmcp` (v2.14.4) if you need features not in SDK. |
| Ollama | Direct HuggingFace | If you want finer control over model loading. Ollama is simpler for this use case. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| pip / pipenv / poetry | Project requires UV | UV - specified in project constraints |
| ChromaDB | Not supported by CocoIndex natively | pgvector - CocoIndex has first-class support |
| OpenAI embeddings | Not local - violates local-first requirement | Ollama with nomic-embed-text |
| fastmcp v3 beta | Pre-release, unstable | MCP SDK 1.26.0 with built-in FastMCP |
| text-embedding-ada-002 | Cloud API, costs money | nomic-embed-text via Ollama (free, local) |
| asyncpg | Requires separate async setup | psycopg 3.x - supports both sync/async, simpler |

## Stack Patterns

### CocoIndex Embedding Pattern

**For local embeddings with Ollama:**
```python
import cocoindex

# Use CocoIndex's native EmbedText with Ollama
embedding_fn = cocoindex.functions.EmbedText(
    api_type=cocoindex.LlmApiType.OLLAMA,
    model="nomic-embed-text",
    address="http://localhost:11434",  # Optional, default port
)
```

**Alternative with SentenceTransformer (requires `cocoindex[embeddings]`):**
```python
# For HuggingFace models directly
embedding_fn = cocoindex.functions.SentenceTransformerEmbed(
    model="sentence-transformers/all-MiniLM-L6-v2"
)
```

**Recommendation:** Use `EmbedText` with Ollama. Ollama handles model management, GPU acceleration, and provides consistent API.

### MCP Server Pattern

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("CocoSearch")

@mcp.tool()
async def search_code(query: str, top_k: int = 5) -> list[dict]:
    """Search indexed codebase semantically."""
    # Implementation with CocoIndex
    pass

@mcp.tool()
async def index_codebase(path: str) -> dict:
    """Index a codebase directory."""
    pass

@mcp.tool()
async def clear_index() -> dict:
    """Clear the current index."""
    pass

if __name__ == "__main__":
    mcp.run()
```

### Vector Search Query Pattern

```python
from psycopg_pool import ConnectionPool
import cocoindex

def search(pool: ConnectionPool, query: str, top_k: int = 5):
    # Get table name from CocoIndex flow
    table_name = cocoindex.utils.get_target_storage_default_name(
        code_embedding_flow, "code_embeddings"
    )

    # Generate query embedding
    query_vector = code_to_embedding.eval(query)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT filename, code, embedding <=> %s::vector AS distance
                FROM {table_name}
                ORDER BY distance
                LIMIT %s
            """, (query_vector, top_k))

            return [
                {"filename": row[0], "code": row[1], "score": 1.0 - row[2]}
                for row in cur.fetchall()
            ]
```

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| cocoindex 0.3.28 | Python 3.11-3.14 | Released 2026-01-21 |
| mcp 1.26.0 | Python 3.10-3.13 | Use v1.x for production |
| psycopg 3.3.2 | Python 3.10-3.14 | Install with `[binary,pool]` extras |
| pgvector 0.4.2 | Python 3.9+ | Works with psycopg 3.x |
| pgvector extension 0.8.1 | PostgreSQL 13-17 | Use pg17 for latest features |
| nomic-embed-text | Ollama (any recent) | 768 dimensions, 8192 context |

## Confidence Assessment

| Component | Confidence | Rationale |
|-----------|------------|-----------|
| CocoIndex | HIGH | Official PyPI, verified version 0.3.28, well-documented Ollama support |
| MCP SDK | HIGH | Official Anthropic SDK, verified version 1.26.0, FastMCP integrated |
| PostgreSQL + pgvector | HIGH | Standard stack, official Docker image, verified compatibility |
| Ollama + nomic-embed-text | HIGH | Multiple sources confirm best-in-class for code, verified dimensions |
| UV | HIGH | Project requirement, verified version 0.9.26 |
| psycopg | HIGH | Verified 3.3.2, documented pgvector integration |

## Sources

**Official Documentation:**
- [CocoIndex PyPI](https://pypi.org/project/cocoindex/) - Version 0.3.28, Python 3.11+
- [MCP Python SDK PyPI](https://pypi.org/project/mcp/) - Version 1.26.0
- [pgvector GitHub](https://github.com/pgvector/pgvector) - Extension v0.8.1
- [pgvector Python PyPI](https://pypi.org/project/pgvector/) - Version 0.4.2
- [psycopg PyPI](https://pypi.org/project/psycopg/) - Version 3.3.2
- [Ollama Embeddings Docs](https://docs.ollama.com/capabilities/embeddings) - Embedding generation
- [UV PyPI](https://pypi.org/project/uv/) - Version 0.9.26

**CocoIndex Resources:**
- [CocoIndex GitHub](https://github.com/cocoindex-io/cocoindex) - Source code and examples
- [CocoIndex Code Indexing Example](https://cocoindex.io/docs/examples/code_index) - Reference implementation
- [CocoIndex LLM Support](https://cocoindex.io/docs/ai/llm) - EmbedText API types including Ollama

**MCP Resources:**
- [MCP Python SDK GitHub](https://github.com/modelcontextprotocol/python-sdk) - FastMCP documentation
- [FastMCP Tutorial](https://gofastmcp.com/tutorials/create-mcp-server) - Server creation patterns

**Embedding Model Resources:**
- [Ollama nomic-embed-text](https://ollama.com/library/nomic-embed-text) - 768 dimensions, 8192 context
- [Continue.dev Top Ollama Models](https://resources.continue.dev/top-ollama-coding-models-q4-2025/) - nomic-embed-text recommended for code

---
*Stack research for: CocoSearch - Local-first code/documentation indexer with MCP interface*
*Researched: 2026-01-24*
