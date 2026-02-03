# Technology Stack: v1.8 Feature Additions

**Project:** CocoSearch
**Researched:** 2026-02-03
**Scope:** Stack additions for stats dashboard, skills, symbol extraction, and query caching

## Executive Summary

v1.8 requires **minimal new dependencies** aligned with CocoSearch's local-first philosophy. The key additions are:

1. **FastAPI + Uvicorn** for HTTP stats API (optional feature)
2. **Rich** for terminal dashboard (already a dependency)
3. **tree-sitter-language-pack** migration for 5+ language support
4. **PostgreSQL JSONB** for query caching (no new dependencies)
5. **Skill files** are static markdown (no runtime dependencies)

**Philosophy:** Prefer built-in PostgreSQL features over external caching layers. Avoid JavaScript build tooling for web UI.

---

## 1. Stats Dashboard Stack

### HTTP API Layer

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **FastAPI** | 0.128.0+ | HTTP API framework | De-facto standard for Python HTTP APIs. Automatic OpenAPI docs, Pydantic validation, async-native. Integrates with existing async codebase. |
| **Uvicorn** | 0.40.0+ | ASGI server | Lightweight, production-ready ASGI server. No heavyweight deployment needed. |

**Why FastAPI over alternatives:**
- Flask: Not async-native, would block event loop
- aiohttp: More verbose, no automatic validation/docs
- Starlette: FastAPI is built on Starlette with better DX

**Installation:**
```bash
uv add "fastapi>=0.128.0"
uv add "uvicorn[standard]>=0.40.0"  # [standard] includes uvloop for performance
```

**Integration points:**
- FastAPI runs as separate process or embedded in Docker container
- Shares PostgreSQL connection pool with existing MCP server
- Optional dependency: Only installed if stats dashboard feature enabled

**Configuration:**
- Add `COCO_STATS_API_ENABLED` environment variable
- Default to disabled (CLI/MCP only mode)
- When enabled, expose `/stats` endpoint on configurable port (default 8765)

### Terminal Dashboard

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **Rich** | 14.3.2+ | Terminal UI library | **Already a dependency** (used for CLI output). No new installation needed. Supports tables, live updates, layouts. |

**Why Rich over alternatives:**
- Textual: Too heavyweight for simple stats dashboard. Textual is for complex TUI apps with widgets/events.
- Dashing: Unmaintained, last release 2019
- Curses: Low-level, requires significant boilerplate

**Implementation approach:**
- Use `rich.table.Table` for stats tables
- Use `rich.live.Live` for auto-refreshing dashboard
- Use `rich.layout.Layout` for multi-panel views (indexed files, queries, repo stats)

**No new dependencies required.**

### Web Dashboard UI

**Recommendation: Static HTML + Vanilla JS**

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| HTML/CSS | Tailwind CSS via CDN | Zero build tooling. Copy-paste from open-source templates. |
| JavaScript | Vanilla JS (ES6+) | No framework overhead. Fetch API for stats endpoint. |
| Charts | Chart.js via CDN | Lightweight charting library. No build step. |

**Why NOT to use:**
- React/Vue/Svelte: Requires build tooling (webpack/vite), npm dependencies, breaks local-first philosophy
- Server-side rendering: FastAPI Jinja2 templates add dependency and complexity
- Electron/Tauri: Massive overhead for simple stats dashboard

**Implementation:**
- Single `dashboard.html` file served from FastAPI static directory
- Fetch JSON from `/api/stats` endpoint every 5 seconds
- Self-contained file: All CSS/JS inline or from CDN
- Works offline after first load (cache CDN resources)

**Template starting point:** TailAdmin or Tabler free templates (MIT licensed)

---

## 2. Claude Code / OpenCode Skills Stack

### Skill File Format

**No runtime dependencies required.**

Skills are static markdown files following the [Agent Skills](https://agentskills.io) open standard.

**File structure:**
```
.claude/skills/coco-explore/
├── SKILL.md          # Main skill (YAML frontmatter + markdown)
├── examples.md       # Optional: Usage examples
└── scripts/          # Optional: Helper scripts
    └── index_repo.sh
```

**Format:**
```yaml
---
name: coco-explore
description: Search codebase semantically with CocoSearch
disable-model-invocation: false
allowed-tools: Bash(cocosearch *)
---

When exploring a codebase, use `cocosearch query "semantic query"` to find relevant code.
```

**Integration with CocoSearch:**
- Skills invoke `cocosearch` CLI via Bash tool
- No MCP integration needed (skills use CLI, not MCP server directly)
- Skills can run `cocosearch stats` for context before querying

**Skill file locations:**
1. **Personal skills:** `~/.claude/skills/coco-*/SKILL.md` (global)
2. **Project skills:** `.claude/skills/coco-*/SKILL.md` (per-repo)
3. **Plugin skills:** Distribute via CocoSearch plugin (future)

**Distribution strategy:**
- Ship example skills in `examples/claude-skills/` directory
- Installation: User copies to `~/.claude/skills/` manually
- No automated installation (respects Claude Code's security model)

**Files to create:**
- `coco-explore.md`: Search codebase semantically
- `coco-index.md`: Index current repository
- `coco-stats.md`: Show indexing statistics
- `coco-context.md`: Extract context around code blocks

---

## 3. Symbol Extraction: Language Support Expansion

### Current State (v1.7)

```toml
# pyproject.toml
dependencies = [
    "tree-sitter>=0.21.0,<0.22.0",
    "tree-sitter-languages>=1.10.0,<1.11.0",  # 5 languages: Python, JS, TS, Go, Rust
]
```

**Supported languages (v1.7):** Python, JavaScript, TypeScript, Go, Rust

### Migration Required: tree-sitter-language-pack

| Package | Status | Action |
|---------|--------|--------|
| `tree-sitter-languages` | **Unmaintained** (last update 2024-02-04) | Replace |
| `tree-sitter-language-pack` | **Actively maintained** (165+ languages, updated 2026) | Migrate to |

**Why migrate:**
1. `tree-sitter-languages` is unmaintained (explicitly recommends `tree-sitter-language-pack`)
2. `tree-sitter-language-pack` includes all 5 languages needed (Java, C, C++, Ruby, PHP) plus existing ones
3. Pre-built wheels, zero compilation required
4. Full typing support (better IDE experience)
5. Aligns with tree-sitter 0.25.x (latest)

**Compatibility:**
- API is nearly identical: `get_language()`, `get_parser()`
- Requires Python 3.10+ (CocoSearch already requires 3.11)
- Tree-sitter 0.25.x drops Python 3.9 (not a concern)

**Migration:**
```toml
# pyproject.toml - UPDATE
dependencies = [
    "tree-sitter>=0.25.0,<0.26.0",  # Updated from 0.21.x
    "tree-sitter-language-pack>=0.2.0",  # Replaces tree-sitter-languages
]
```

**Code changes required:**
```python
# Before (v1.7)
from tree_sitter_languages import get_language, get_parser

# After (v1.8)
from tree_sitter_language_pack import get_language, get_parser
# Same API, zero refactoring needed
```

### New Language Support

All 5 new languages are included in `tree-sitter-language-pack`:

| Language | Grammar Status | Symbol Types |
|----------|---------------|--------------|
| **Java** | Official tree-sitter grammar, updated Jan 2026 | class, interface, method, field, enum |
| **C** | Official tree-sitter grammar, updated Feb 2026 | function, struct, typedef, enum |
| **C++** | Official tree-sitter grammar, updated Feb 2026 | class, function, method, namespace, template |
| **Ruby** | Official tree-sitter grammar, updated Jan 2026 | class, module, method, singleton_method |
| **PHP** | Official tree-sitter grammar, updated Feb 2026 | class, interface, trait, function, method |

**Implementation:**
- Add language handlers to `src/cocosearch/handlers/` (e.g., `java.py`, `c.py`, etc.)
- Update symbol extraction logic to recognize node types for each language
- Follow existing pattern from `python.py`, `javascript.py`, etc.

**No breaking changes:** Existing 5-language support remains unchanged.

---

## 4. Query Caching / History Stack

### Storage Strategy: PostgreSQL JSONB

**No new dependencies required.**

Use existing PostgreSQL with JSONB columns for query caching and history.

| Feature | Technology | Rationale |
|---------|-----------|-----------|
| **Cache storage** | PostgreSQL JSONB column | Already have PostgreSQL. JSONB supports fast lookups, partial indexes, JSON queries. |
| **Cache key** | MD5 hash of (query + filters + top_k) | Deterministic cache key for exact match lookups. |
| **Expiration** | PostgreSQL TTL + cleanup job | Native timestamp-based expiration. No external cache layer. |

**Why NOT external caching:**
- Redis: Adds deployment complexity, requires Docker container, breaks local-first philosophy
- Memcached: Same issues as Redis
- SQLite: Already have PostgreSQL, no need for second database
- In-memory: Doesn't persist across MCP server restarts

**Schema:**
```sql
CREATE TABLE query_cache (
    id SERIAL PRIMARY KEY,
    cache_key TEXT UNIQUE NOT NULL,
    query TEXT NOT NULL,
    filters JSONB,
    results JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    accessed_at TIMESTAMP DEFAULT NOW(),
    access_count INTEGER DEFAULT 1
);

CREATE INDEX idx_cache_key ON query_cache(cache_key);
CREATE INDEX idx_created_at ON query_cache(created_at);
```

**Query history:**
```sql
CREATE TABLE query_history (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    filters JSONB,
    result_count INTEGER,
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_history_created_at ON query_history(created_at);
```

**Cache invalidation strategies:**
1. **Time-based TTL:** Delete entries older than 24 hours (configurable)
2. **LRU eviction:** Keep top 1000 most-accessed queries
3. **Manual clear:** `cocosearch clear --cache` command

**Performance:**
- JSONB indexing: Use GIN index for filter queries (if needed)
- Partial index: Only index recent entries (last 7 days)
- Vacuum: PostgreSQL auto-vacuum handles cleanup

**Configuration:**
```yaml
# .cocosearch.yml
cache:
  enabled: true
  ttl_hours: 24
  max_entries: 1000
```

---

## What NOT to Add

### Explicitly Rejected Dependencies

| Technology | Why NOT |
|-----------|---------|
| **Redis** | Adds deployment complexity. PostgreSQL JSONB handles caching. Local-first philosophy: don't require external services. |
| **React/Vue/Svelte** | Requires build tooling (npm, webpack, vite). Breaks local-first philosophy. Static HTML + vanilla JS is sufficient. |
| **Electron/Tauri** | Massive overhead (100+ MB). Web dashboard via FastAPI is lighter and simpler. |
| **GraphQL** | Overkill for simple stats API. REST endpoints are sufficient. |
| **WebSockets** | Not needed. HTTP polling every 5 seconds is sufficient for stats dashboard. |
| **Celery** | No background job queue needed. Stats are computed on-demand. |
| **Message brokers (RabbitMQ, Kafka)** | No distributed architecture. Single-node deployment only. |

---

## Installation Summary

### Required for v1.8 Features

```bash
# Stats Dashboard (optional feature)
uv add "fastapi>=0.128.0"
uv add "uvicorn[standard]>=0.40.0"

# Symbol Extraction (MIGRATION REQUIRED)
uv remove tree-sitter-languages
uv add "tree-sitter>=0.25.0,<0.26.0"
uv add "tree-sitter-language-pack>=0.2.0"

# Query Caching
# No new dependencies - uses existing PostgreSQL

# Skills
# No new dependencies - static markdown files
```

### Updated pyproject.toml

```toml
[project]
dependencies = [
    "cocoindex[embeddings]>=0.3.28",
    "mcp[cli]>=1.26.0",
    "pathspec>=1.0.3",
    "pgvector>=0.4.2",
    "psycopg[binary,pool]>=3.3.2",
    "pyyaml>=6.0.2",
    "rich>=13.0.0",
    "tree-sitter>=0.25.0,<0.26.0",           # UPDATED
    "tree-sitter-language-pack>=0.2.0",      # REPLACED tree-sitter-languages
]

[project.optional-dependencies]
stats = [
    "fastapi>=0.128.0",
    "uvicorn[standard]>=0.40.0",
]
```

**Installation:**
```bash
# Full install with stats dashboard
uv sync --extra stats

# Minimal install (CLI/MCP only)
uv sync
```

---

## Docker Integration

### Updated docker-compose.yml

```yaml
services:
  db:
    image: pgvector/pgvector:pg17
    # ... existing config ...

  ollama:
    image: ollama/ollama:latest
    # ... existing config ...

  # NEW: Stats API (optional)
  stats-api:
    build: .
    container_name: cocosearch-stats
    ports:
      - "8765:8765"
    environment:
      COCO_STATS_API_ENABLED: "true"
      POSTGRES_HOST: db
      OLLAMA_HOST: http://ollama:11434
    depends_on:
      db:
        condition: service_healthy
      ollama:
        condition: service_healthy
    profiles:
      - stats  # Only start if --profile stats is used
```

**Usage:**
```bash
# Start with stats dashboard
docker-compose --profile stats up

# Start without stats dashboard (CLI/MCP only)
docker-compose up
```

---

## Feature Flags

Control which v1.8 features are enabled via environment variables:

| Feature | Env Var | Default | Impact |
|---------|---------|---------|--------|
| Stats API | `COCO_STATS_API_ENABLED` | `false` | Requires FastAPI/Uvicorn |
| Query Cache | `COCO_CACHE_ENABLED` | `true` | No new dependencies |
| Query History | `COCO_HISTORY_ENABLED` | `true` | No new dependencies |

**Rationale:** Users who only want CLI/MCP don't pay the cost of FastAPI/Uvicorn.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| **FastAPI/Uvicorn** | HIGH | De-facto standard for Python HTTP APIs. Current versions verified. |
| **Rich** | HIGH | Already a dependency. No migration risk. |
| **tree-sitter-language-pack** | HIGH | Actively maintained, API-compatible, all 5 languages included. Official grammars verified. |
| **PostgreSQL JSONB caching** | HIGH | Standard pattern. No new dependencies. Well-documented. |
| **Static HTML dashboard** | HIGH | No build tooling required. Proven approach. |
| **Skills integration** | HIGH | Standard Claude Code skill format. No runtime dependencies. |

**Overall confidence:** HIGH

All recommendations based on:
- Official documentation (FastAPI, Rich, tree-sitter)
- PyPI package status (verified unmaintained status of tree-sitter-languages)
- Current version numbers (verified via PyPI and GitHub releases)
- Integration with existing stack (PostgreSQL, Docker, Python 3.11+)

---

## Migration Checklist

Before implementing v1.8:

- [ ] Migrate tree-sitter-languages to tree-sitter-language-pack
- [ ] Update tree-sitter from 0.21.x to 0.25.x
- [ ] Test existing 5-language symbol extraction still works
- [ ] Add FastAPI/Uvicorn as optional dependencies
- [ ] Create PostgreSQL schema for query cache and history
- [ ] Create example skill files in `examples/claude-skills/`
- [ ] Create static HTML dashboard template
- [ ] Update Docker Compose with optional stats-api service
- [ ] Document feature flags in README

---

## Sources

**FastAPI and Uvicorn:**
- [FastAPI PyPI](https://pypi.org/project/fastapi/)
- [FastAPI Official Documentation](https://fastapi.tiangolo.com/)
- [Uvicorn Release Notes](https://uvicorn.dev/release-notes/)
- [FastAPI GitHub Releases](https://github.com/fastapi/fastapi/releases)

**Rich Terminal Library:**
- [Rich PyPI](https://pypi.org/project/rich/)
- [Rich GitHub Repository](https://github.com/Textualize/rich)
- [Building Rich Terminal Dashboards](https://www.willmcgugan.com/blog/tech/post/building-rich-terminal-dashboards/)
- [Real Python: Rich Package Tutorial](https://realpython.com/python-rich-package/)

**Tree-sitter Language Support:**
- [tree-sitter-language-pack PyPI](https://pypi.org/project/tree-sitter-language-pack/)
- [tree-sitter-language-pack GitHub](https://github.com/Goldziher/tree-sitter-language-pack)
- [tree-sitter-languages PyPI (unmaintained)](https://pypi.org/project/tree-sitter-languages/)
- [Tree-sitter Official Site](https://tree-sitter.github.io/tree-sitter/)
- [Tree-sitter Grammars Organization](https://github.com/tree-sitter-grammars)

**Claude Code Skills:**
- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills)
- [Agent Skills Open Standard](https://agentskills.io)
- [Anthropic Skills Repository](https://github.com/anthropics/skills)

**PostgreSQL Caching:**
- [PostgreSQL JSON Optimization 2025](https://markaicode.com/postgres-json-optimization-techniques-2025/)
- [PostgreSQL as Cache Service](https://martinheinz.dev/blog/105)
- [AWS: PostgreSQL as JSON Database](https://aws.amazon.com/blogs/database/postgresql-as-a-json-database-advanced-patterns-and-best-practices/)

**Web Dashboard Templates:**
- [TailAdmin Free Templates](https://tailadmin.com)
- [Tabler Admin Template](https://tabler.io/)
- [Free HTML5 Admin Templates 2026](https://colorlib.com/wp/free-html5-admin-dashboard-templates/)
