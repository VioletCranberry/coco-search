# Architecture Integration: v1.8 Features

**Project:** CocoSearch v1.8
**Researched:** 2026-02-03
**Confidence:** HIGH

## Executive Summary

This document analyzes how four v1.8 features integrate with CocoSearch's existing architecture:

1. **Stats Dashboard** - Web UI for index visualization
2. **Developer Skills** - Reusable prompt files for LLM workflows
3. **Expanded Symbol Extraction** - Per-language tree-sitter query files
4. **Query Caching** - In-memory cache for repeated semantic searches

All four features integrate cleanly with minimal architectural changes. The existing module structure supports natural extension points.

## Current Architecture Overview

```
src/cocosearch/
├── cli.py              # Click-based CLI (argparse implementation)
├── mcp/
│   └── server.py       # FastMCP server (stdio/SSE/HTTP transports)
├── indexer/
│   ├── symbols.py      # Tree-sitter symbol extraction
│   └── flow.py         # CocoIndex integration
├── search/
│   ├── query.py        # Search execution
│   ├── hybrid.py       # Vector + keyword search
│   └── db.py           # PostgreSQL connection pool
├── management/
│   ├── stats.py        # Index statistics
│   └── context.py      # Auto-detection
└── config/
    ├── schema.py       # Pydantic config model
    └── loader.py       # YAML config loading

docker/
├── Dockerfile          # All-in-one container
└── rootfs/             # s6-overlay service definitions
```

**Key characteristics:**
- Modular package structure with clear boundaries
- PostgreSQL storage with pgvector for embeddings
- CocoIndex for indexing pipeline
- FastMCP server supports multiple transports
- s6-overlay for multi-process Docker supervision

## Feature 1: Stats Dashboard

### Integration Point

**Option A: Extend MCP Server (RECOMMENDED)**
- Add new HTTP routes to existing FastMCP server
- Leverage existing `/health` endpoint pattern
- Reuse `management/stats.py` functions
- No new process needed in Docker container

**Option B: Standalone Server**
- Separate HTTP server process
- Requires new s6-overlay service definition
- Additional port exposure (e.g., 8080)
- More complex but cleaner separation

**Option C: CLI-Only**
- `cocosearch stats --web` to spawn temporary server
- Similar to `python -m http.server`
- Good for development, poor for production

### Recommended Architecture: Extended MCP Server

```python
# src/cocosearch/mcp/server.py additions

@mcp.custom_route("/dashboard", methods=["GET"])
async def dashboard_ui(request):
    """Serve stats dashboard HTML."""
    return HTMLResponse(dashboard_html_template)

@mcp.custom_route("/api/stats", methods=["GET"])
async def stats_api(request):
    """JSON API for dashboard data."""
    indexes = mgmt_list_indexes()
    stats = [get_stats(idx["name"]) for idx in indexes]
    lang_stats = [get_language_stats(idx["name"]) for idx in indexes]
    return JSONResponse({
        "indexes": stats,
        "languages": lang_stats,
    })
```

**Rationale:**
- FastMCP already serves HTTP on port 3000
- Custom routes documented in FastMCP
- Reuses existing stats.py functions
- No new Docker service needed
- Dashboard accessible at `http://localhost:3000/dashboard`

### Component Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `mcp/server.py` | Modified | Add `/dashboard` and `/api/stats` routes |
| `mcp/templates.py` | New | HTML templates for dashboard UI |
| `management/stats.py` | Extended | Add aggregation functions for multi-index views |
| Docker Dockerfile | Unchanged | No new services required |

### Data Flow

```
Browser → HTTP GET /dashboard → FastMCP → HTMLResponse (static dashboard)
Browser → HTTP GET /api/stats → FastMCP → stats.py → PostgreSQL → JSON
Dashboard JS → Fetch /api/stats → Render charts/tables
```

### UI Technology Stack

Based on 2026 web dashboard trends, recommend:

**Minimal Dependencies (Recommended):**
- Vanilla JS + Fetch API for data loading
- Chart.js for visualizations (CDN)
- Tailwind CSS via CDN for styling
- Single HTML file with embedded CSS/JS

**Why minimal:**
- No build step required
- No npm dependencies in Docker image
- Faster development iteration
- Easier to maintain
- Fits "local-first" philosophy

**Modern Alternative:**
- HTMX + Alpine.js for reactive UI
- Still no build step
- Progressive enhancement pattern

### Build Order

1. **Phase 1: API endpoints** - Add JSON endpoints to MCP server
2. **Phase 2: Static dashboard** - Create HTML template with Chart.js
3. **Phase 3: Real-time updates** - Add WebSocket support for live stats
4. **Phase 4: CLI integration** - `cocosearch stats --web` alias

## Feature 2: Developer Skills

### Integration Point

Skills are prompt templates for LLM workflows. Similar to Claude Code's SKILL.md format.

**Storage location:** User's home directory
- `~/.cocosearch/skills/` - Default skill library
- Project-level: `.cocosearch/skills/` - Project-specific skills

**File format:** Markdown with YAML frontmatter

```markdown
---
name: code-review
description: Perform comprehensive code review
version: 1.0.0
tags: [review, quality, security]
---

# Code Review Skill

Review the following code for:
- Technical correctness
- Security issues
- Performance concerns
- Code style

{CODE_CONTEXT}
```

### Architecture Pattern

**Discovery mechanism:**
1. Check `.cocosearch/skills/` (project-level, highest priority)
2. Check `~/.cocosearch/skills/` (user-level)
3. Built-in skills bundled with installation

**Implementation:**

```python
# src/cocosearch/skills/
├── __init__.py         # Skill discovery and loading
├── loader.py           # Parse markdown + YAML frontmatter
├── registry.py         # Skill registry with caching
└── builtin/            # Bundled skills
    ├── code-review.md
    ├── explain.md
    └── refactor.md
```

### Component Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `skills/` module | New | Complete skills system |
| `cli.py` | Extended | `cocosearch skills list/show/install` commands |
| `mcp/server.py` | Extended | Optional MCP tool for skill execution |
| `config/schema.py` | Extended | Add `skills.path` config option |

### Skills CLI Commands

```bash
# List available skills
cocosearch skills list

# Show skill details
cocosearch skills show code-review

# Install skill from URL or file
cocosearch skills install https://example.com/skill.md
cocosearch skills install ./custom-skill.md

# Create new skill from template
cocosearch skills new my-skill
```

### Installation Flow

```
User runs: cocosearch skills install <url>
    ↓
Download skill file
    ↓
Validate YAML frontmatter + markdown
    ↓
Copy to ~/.cocosearch/skills/<name>.md
    ↓
Update registry cache
```

### MCP Integration (Optional)

```python
@mcp.tool()
def apply_skill(
    skill_name: str,
    code_context: str,
    index_name: str | None = None,
) -> dict:
    """Apply a developer skill to code context."""
    skill = load_skill(skill_name)
    if index_name:
        # Augment context with search results
        relevant_code = search(code_context, index_name)
        context = format_code_context(relevant_code)
    else:
        context = code_context

    prompt = skill.render(CODE_CONTEXT=context)
    return {"prompt": prompt, "skill": skill_name}
```

### Build Order

1. **Phase 1: Skill loader** - Parse markdown + YAML, validation
2. **Phase 2: Discovery system** - Search paths, registry
3. **Phase 3: CLI commands** - list, show, install
4. **Phase 4: Built-in skills** - Bundle 3-5 common skills
5. **Phase 5: MCP integration** - Optional tool for skill execution

## Feature 3: Expanded Symbol Extraction

### Current State

Symbol extraction in `indexer/symbols.py`:
- Hardcoded tree-sitter queries in Python
- Supports Python, JS, TS, Go, Rust
- Query logic embedded in `_extract_*_symbols()` functions

### Target Architecture: Query Files

Move tree-sitter queries to external `.scm` files per language:

```
src/cocosearch/queries/
├── python.scm
├── javascript.scm
├── typescript.scm
├── go.scm
├── rust.scm
└── README.md           # Query file format documentation
```

**Example: `queries/python.scm`**

```scheme
; Function definitions
(function_definition
  name: (identifier) @function.name
  parameters: (parameters) @function.params
  return_type: (type)? @function.return
) @function

; Class definitions
(class_definition
  name: (identifier) @class.name
  superclasses: (argument_list)? @class.bases
) @class

; Methods (functions inside classes)
(class_definition
  body: (block
    (function_definition
      name: (identifier) @method.name
      parameters: (parameters) @method.params
    ) @method
  )
)
```

### Integration Point

**Loader mechanism:**

```python
# src/cocosearch/indexer/symbols.py

import importlib.resources
from tree_sitter import Query

_QUERY_CACHE: dict[str, Query] = {}

def _load_query(language: str) -> Query:
    """Load tree-sitter query from .scm file."""
    if language in _QUERY_CACHE:
        return _QUERY_CACHE[language]

    # Load from package data
    query_text = importlib.resources.read_text(
        "cocosearch.queries",
        f"{language}.scm"
    )

    lang_obj = get_language(language)
    query = Query(lang_obj, query_text)
    _QUERY_CACHE[language] = query
    return query

def _extract_symbols_generic(chunk_text: str, language: str) -> list[dict]:
    """Generic symbol extraction using query files."""
    parser = _get_parser(language)
    tree = parser.parse(bytes(chunk_text, "utf8"))
    query = _load_query(language)

    captures = query.captures(tree.root_node)
    symbols = []

    for node, capture_name in captures:
        if capture_name.endswith(".name"):
            symbol_type = capture_name.split(".")[0]
            symbol_name = _get_node_text(chunk_text, node)
            # Find signature from parent node
            signature = _extract_signature(tree, node, symbol_type)
            symbols.append({
                "symbol_type": symbol_type,
                "symbol_name": symbol_name,
                "symbol_signature": signature,
            })

    return symbols
```

### Component Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `queries/` package | New | Tree-sitter query files (.scm) |
| `indexer/symbols.py` | Refactored | Remove hardcoded queries, add query loader |
| `pyproject.toml` | Modified | Add `queries/*.scm` to package_data |

### Benefits

1. **Extensibility** - Users can add new languages without Python code
2. **Maintainability** - Query syntax is declarative, easier to read
3. **Community contribution** - Non-Python developers can add language support
4. **Testability** - Test queries independently of Python code

### Custom Query Override

Allow users to override built-in queries:

```yaml
# cocosearch.yaml
indexing:
  customQueries:
    python: ./.cocosearch/queries/python.scm
    rust: ./.cocosearch/queries/rust.scm
```

**Loader priority:**
1. Custom queries from config (project-specific)
2. Built-in queries from package (defaults)

### Build Order

1. **Phase 1: Extract existing queries** - Convert Python functions to .scm files
2. **Phase 2: Query loader** - Add loader with caching
3. **Phase 3: Generic extraction** - Refactor to use query files
4. **Phase 4: Custom query support** - Add config option for overrides
5. **Phase 5: Documentation** - Query file format guide

## Feature 4: Query Caching

### Problem Statement

Repeated semantic searches generate duplicate embeddings and database queries:
- Same query string → Generate embedding (Ollama call) → Vector search (PostgreSQL)
- Embedding generation is expensive (network + compute)
- Vector similarity search is fast but still a DB round-trip

### Caching Strategy: Hybrid Approach

**Layer 1: Embedding Cache (In-Memory)**
- Cache query text → embedding vector mapping
- Avoids redundant Ollama calls
- LRU eviction policy
- TTL: 1 hour (embeddings don't change for same text)

**Layer 2: Result Cache (Optional, PostgreSQL-backed)**
- Cache (embedding, filters) → search results
- Semantic similarity threshold (0.98+) for cache hits
- TTL: 5 minutes (results may change as index updates)
- Invalidation on index updates

### Architecture: In-Memory First

```python
# src/cocosearch/search/cache.py

from functools import lru_cache
from dataclasses import dataclass
from typing import Any
import hashlib
import time

@dataclass
class CacheEntry:
    """Cache entry with TTL."""
    value: Any
    expires_at: float

class EmbeddingCache:
    """LRU cache for query embeddings with TTL."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, CacheEntry] = {}

    def get(self, query: str) -> list[float] | None:
        """Get cached embedding if exists and not expired."""
        if query not in self._cache:
            return None

        entry = self._cache[query]
        if time.time() > entry.expires_at:
            del self._cache[query]
            return None

        return entry.value

    def set(self, query: str, embedding: list[float]) -> None:
        """Cache embedding with TTL."""
        if len(self._cache) >= self.max_size:
            self._evict_oldest()

        self._cache[query] = CacheEntry(
            value=embedding,
            expires_at=time.time() + self.ttl_seconds
        )

    def clear(self) -> None:
        """Clear all cached embeddings."""
        self._cache.clear()

    def _evict_oldest(self) -> None:
        """Evict oldest entry (simple FIFO for now)."""
        if self._cache:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

# Global cache instance
_embedding_cache = EmbeddingCache()
```

### Integration with Search Flow

```python
# src/cocosearch/search/query.py (modified)

def search(
    query: str,
    index_name: str,
    limit: int = 10,
    use_cache: bool = True,
    **kwargs
) -> list[SearchResult]:
    """Execute semantic search with optional caching."""

    # Check embedding cache
    if use_cache:
        embedding = _embedding_cache.get(query)
        if embedding is None:
            # Cache miss - generate and cache
            embedding = generate_embedding(query)
            _embedding_cache.set(query, embedding)
    else:
        # Cache disabled
        embedding = generate_embedding(query)

    # Execute vector search
    results = vector_search(embedding, index_name, limit, **kwargs)
    return results
```

### Cache Invalidation

**Trigger: Index update**

```python
# src/cocosearch/indexer/flow.py (modified)

def run_index(index_name: str, codebase_path: str, config: IndexingConfig):
    """Run indexing with cache invalidation."""

    # ... existing indexing logic ...

    update_info = cocoindex.update(...)

    # Invalidate query cache for this index
    if update_info.stats.get("files", {}).get("num_updates", 0) > 0:
        # Content changed - clear embedding cache
        from cocosearch.search.cache import _embedding_cache
        _embedding_cache.clear()

    return update_info
```

### Component Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `search/cache.py` | New | Embedding cache implementation |
| `search/query.py` | Modified | Add cache lookup before embedding generation |
| `indexer/flow.py` | Modified | Clear cache on index updates |
| `config/schema.py` | Extended | Add `cache.enabled`, `cache.maxSize`, `cache.ttl` |
| `cli.py` | Extended | `cocosearch cache clear/stats` commands |

### Configuration

```yaml
# cocosearch.yaml
cache:
  enabled: true
  maxSize: 1000          # Max cached embeddings
  ttl: 3600              # Seconds (1 hour)
```

### Advanced: Redis-backed Cache (Optional)

For multi-process deployments (Docker with multiple MCP instances):

```python
# src/cocosearch/search/cache.py (extended)

class RedisEmbeddingCache(EmbeddingCache):
    """Redis-backed embedding cache for multi-process deployments."""

    def __init__(self, redis_url: str, **kwargs):
        super().__init__(**kwargs)
        import redis
        self.redis = redis.from_url(redis_url)

    def get(self, query: str) -> list[float] | None:
        """Get from Redis."""
        key = f"embed:{hashlib.sha256(query.encode()).hexdigest()}"
        data = self.redis.get(key)
        if data is None:
            return None
        import json
        return json.loads(data)

    def set(self, query: str, embedding: list[float]) -> None:
        """Set in Redis with TTL."""
        key = f"embed:{hashlib.sha256(query.encode()).hexdigest()}"
        import json
        self.redis.setex(key, self.ttl_seconds, json.dumps(embedding))
```

**Note:** Redis support is optional. Start with in-memory, add Redis only if needed.

### Build Order

1. **Phase 1: In-memory cache** - EmbeddingCache class with LRU + TTL
2. **Phase 2: Search integration** - Modify search() to use cache
3. **Phase 3: Invalidation** - Clear cache on index updates
4. **Phase 4: Configuration** - Add cache config section
5. **Phase 5: CLI commands** - `cocosearch cache` subcommands
6. **Phase 6: Redis support** (optional) - For multi-process deployments

## Recommended Build Order Across Features

### Phase Structure

**Phase 1: Query Caching (Highest ROI)**
- Immediate performance improvement
- Simple to implement (in-memory)
- No UI dependencies
- Foundation for other features

**Phase 2: Expanded Symbol Extraction**
- Natural extension of existing symbols.py
- Enables community contributions
- Unblocks language expansion
- Clear migration path from current code

**Phase 3: Developer Skills**
- Independent of other features
- CLI-first approach
- User-facing value
- Foundation for MCP enhancements

**Phase 4: Stats Dashboard**
- Builds on stable search/stats APIs
- Requires UI development skills
- Lower priority for CLI-first users
- High value for Docker deployments

### Dependency Graph

```
Query Caching (independent)
    └─> Stats Dashboard (shows cache hit rates)

Symbol Extraction (independent)
    └─> Skills (skills can reference symbol types)

Developer Skills (independent)
    └─> MCP Integration (skills as tools)

Stats Dashboard (independent)
    └─> MCP Server (reuses HTTP transport)
```

## Integration Testing Strategy

### Query Caching Tests

```python
def test_embedding_cache_hit():
    """Verify cache returns same embedding without Ollama call."""
    cache = EmbeddingCache()
    query = "find authentication logic"

    # First call - cache miss
    embed1 = cache.get(query)
    assert embed1 is None

    embedding = [0.1, 0.2, 0.3]
    cache.set(query, embedding)

    # Second call - cache hit
    embed2 = cache.get(query)
    assert embed2 == embedding

def test_cache_invalidation_on_update():
    """Verify cache clears when index updates."""
    cache = _embedding_cache
    cache.set("test query", [0.1, 0.2])

    # Simulate index update
    run_index("test_index", "/path", config)

    # Cache should be cleared
    assert cache.get("test query") is None
```

### Symbol Query File Tests

```python
def test_query_file_loading():
    """Verify query files load correctly."""
    query = _load_query("python")
    assert query is not None
    assert isinstance(query, Query)

def test_custom_query_override():
    """Verify custom queries override built-in."""
    config = CocoSearchConfig(
        indexing=IndexingSection(
            customQueries={"python": "./custom-python.scm"}
        )
    )
    # Query loader should prefer custom over built-in
```

### Skills Discovery Tests

```python
def test_skill_discovery_priority():
    """Verify project skills override user skills."""
    # Create project skill: .cocosearch/skills/test.md
    # Create user skill: ~/.cocosearch/skills/test.md
    skill = load_skill("test")
    # Should load from project directory
    assert skill.path.startswith(".cocosearch")

def test_skill_validation():
    """Verify invalid skills are rejected."""
    with pytest.raises(SkillValidationError):
        install_skill("invalid-skill.md")
```

### Stats Dashboard Tests

```python
def test_dashboard_api_response():
    """Verify /api/stats returns correct format."""
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "indexes" in data
    assert "languages" in data

def test_dashboard_html_render():
    """Verify dashboard HTML renders."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"<html>" in response.content
```

## Architectural Principles Applied

1. **Modularity** - Each feature is a self-contained module
2. **Minimal coupling** - Features don't depend on each other
3. **Extend, don't modify** - Existing modules extended, not rewritten
4. **Configuration-driven** - Behavior controlled via cocosearch.yaml
5. **Progressive enhancement** - Basic features work without advanced dependencies
6. **Local-first** - All features work offline except dashboard (optional)

## Docker Integration

### No New Services Required

All features integrate with existing Docker services:

| Feature | Docker Impact |
|---------|---------------|
| Query Caching | In-memory cache in MCP process, no new service |
| Symbol Extraction | Query files bundled in image, no runtime changes |
| Developer Skills | Skills directory mounted as volume |
| Stats Dashboard | Served by existing MCP HTTP transport |

### Volume Mounts

```yaml
# docker-compose.yml (extended)
services:
  cocosearch:
    image: cocosearch:v1.8
    volumes:
      - ./codebase:/mnt/repos:ro
      - ~/.cocosearch/skills:/root/.cocosearch/skills:ro
      - cocosearch-data:/data
    ports:
      - "3000:3000"        # MCP + Dashboard
      - "5432:5432"        # PostgreSQL (optional)
      - "11434:11434"      # Ollama (optional)
```

## Performance Considerations

### Query Caching Impact

**Before caching:**
- Query latency: ~200-500ms (embedding generation + vector search)
- Ollama embedding: 150-300ms per query
- PostgreSQL vector search: 50-200ms

**After caching (cache hit):**
- Query latency: ~50-200ms (vector search only)
- 60-75% latency reduction for repeated queries
- 3-5x throughput improvement

### Symbol Extraction Performance

**Query files vs. hardcoded:**
- Minimal performance difference
- Query compilation cached in memory
- File I/O only on first load
- Tree-sitter query engine highly optimized

### Dashboard Overhead

**Static dashboard:**
- No polling - dashboard fetches on page load
- Minimal server load (1-2 API calls per page view)
- No persistent connections

**With live updates (future):**
- WebSocket for real-time stats
- Server-sent events (SSE) alternative
- 1 connection per browser tab

## Migration Path

### Backward Compatibility

All v1.8 features are additive:

1. **Query Caching** - Opt-in via config, defaults to disabled
2. **Symbol Extraction** - Falls back to existing hardcoded queries
3. **Skills** - Optional feature, no impact if unused
4. **Dashboard** - Optional HTTP route, CLI unchanged

### Upgrade Steps

```bash
# 1. Update codebase
git pull origin main

# 2. Rebuild Docker image
docker build -t cocosearch:v1.8 .

# 3. Enable new features in config
cat >> cocosearch.yaml <<EOF
cache:
  enabled: true
  maxSize: 1000
  ttl: 3600
EOF

# 4. Restart services
docker-compose down
docker-compose up -d

# 5. Access dashboard
open http://localhost:3000/dashboard
```

## Security Considerations

### Skills System

**Risks:**
- Skills execute arbitrary prompts
- User-installed skills from untrusted sources
- Potential for prompt injection

**Mitigations:**
1. Skills don't execute code - only generate prompts
2. Validate YAML frontmatter schema
3. Sandbox skill rendering (no template execution)
4. Display skill source before installation
5. Require explicit user confirmation for installs

### Dashboard Access

**Risks:**
- Dashboard exposes index statistics
- Potential information disclosure

**Mitigations:**
1. Dashboard bound to localhost by default
2. Add optional authentication (future)
3. Read-only API endpoints
4. No index deletion via dashboard

### Cache Poisoning

**Risks:**
- Malicious queries cached
- Cache size exhaustion

**Mitigations:**
1. LRU eviction prevents unbounded growth
2. TTL ensures cache freshness
3. Cache clear on index updates
4. Configurable max size limit

## Open Questions

1. **Dashboard authentication** - Add basic auth or OAuth?
2. **Redis cache** - Support Redis out of the box or require manual setup?
3. **Skills marketplace** - Central registry for community skills?
4. **Query file validation** - Compile-time checks for query syntax?

## References

### Web Dashboard Architecture
- [TailAdmin Dashboard Templates](https://tailadmin.com/blog/saas-dashboard-templates) - Modern SaaS dashboard patterns
- [Web Application Architecture Guide](https://www.clickittech.com/software-development/web-application-architecture/) - 2026 architecture trends
- [React Dashboards Guide](https://www.untitledui.com/blog/react-dashboards) - Modern dashboard components

### Developer Skills Systems
- [Claude Code Skills Guide](https://vertu.com/lifestyle/claude-code-skills-the-complete-guide-to-automating-your-development-workflow/) - SKILL.md format and best practices
- [install.md Specification](https://www.installmd.org) - Standardized installation files for AI agents

### Tree-sitter Query Systems
- [Tree-sitter Query Documentation](https://tree-sitter.github.io/tree-sitter/cli/query.html) - Official query system guide
- [Neovim Treesitter Guide](https://neovim.io/doc/user/treesitter.html) - Query file organization patterns
- [Zed Syntax-Aware Editing](https://zed.dev/blog/syntax-aware-editing) - Tree-sitter queries for language features

### Semantic Caching
- [Redis Semantic Caching Guide](https://redis.io/blog/what-is-semantic-caching/) - Semantic cache architecture
- [Context-Enabled Semantic Cache](https://redis.io/blog/building-a-context-enabled-semantic-cache-with-redis/) - Multi-layer caching patterns
- [Semantic Cache Optimization](https://redis.io/blog/10-techniques-for-semantic-cache-optimization/) - Performance tuning techniques
- [Prompt vs Semantic Caching](https://redis.io/blog/prompt-caching-vs-semantic-caching/) - Caching strategy comparison

## Conclusion

All four v1.8 features integrate cleanly with minimal architectural disruption:

1. **Stats Dashboard** extends MCP server with HTTP routes
2. **Developer Skills** adds new module with file-based storage
3. **Symbol Extraction** refactors existing code to use query files
4. **Query Caching** adds in-memory layer before embedding generation

**Recommended build order:** Cache → Symbols → Skills → Dashboard

**Total estimated effort:** 4-6 phases of development

**Breaking changes:** None - all features are backward compatible
