# Phase 42: Technical Documentation - Research

**Researched:** 2026-02-06
**Domain:** Technical documentation for code search system (retrieval logic and MCP tools)
**Confidence:** HIGH

## Summary

Researched how to document CocoSearch's retrieval logic and MCP tools effectively for both contributors and AI agents. The system implements hybrid search combining vector similarity (via embeddings) with keyword matching (via PostgreSQL full-text search), fused using Reciprocal Rank Fusion (RRF). Documentation needs to serve dual audiences: contributors/power users understanding the architecture, and AI agents consuming MCP tools programmatically.

Key findings:
- Modern documentation favors separate topic-based files over monolithic documents
- API documentation requires structured parameter descriptions with both natural language and JSON formats
- Technical concepts (embeddings, RRF, vector search) should be explained before implementation details
- Code flows should be documented end-to-end with actual formulas/parameters
- Markdown is the standard format with clear hierarchy and consistent terminology

**Primary recommendation:** Create three focused docs files (architecture.md, retrieval.md, mcp-tools.md) with concept primers before implementation details, structured examples for MCP tools, and complete pipeline coverage including indexing and search flows.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Document structure:**
- Dedicated `docs/` folder with separate .md files per topic
- No index page or docs/README.md — filenames are self-explanatory
- Three files: `docs/architecture.md` (high-level overview), `docs/retrieval.md` (search pipeline), `docs/mcp-tools.md` (tool reference)
- Main project README gets a "Documentation" section linking to docs/ files

**Audience & depth:**
- Retrieval logic docs serve both contributors and power users equally — conceptual overview first, then implementation details
- MCP tools reference primarily targets AI agents/LLMs consuming the tools — focus on parameters, return formats, when to use each tool
- Include a brief primer on core concepts (embeddings, vector search, RRF) before CocoSearch specifics — don't assume familiarity
- No diagrams — text descriptions only

**Code examples style:**
- MCP tool examples use both formats: natural language description, then JSON request, then JSON response
- One canonical example per tool showing the most common use case
- Happy path only — no error case examples
- No "when to use which tool" decision guide — each tool's section describes its own purpose

**Retrieval logic scope:**
- Full end-to-end pipeline coverage: query processing -> embedding -> vector search -> keyword search -> RRF fusion -> filtering -> ranking
- Include actual scoring/ranking numbers (RRF k parameter, weight ratios, formulas)
- Full query caching details: cache keys, TTL, eviction strategy, invalidation
- Cover both sides: indexing (how code gets into DB — parsing, chunking, embedding) AND search/query pipeline

### Claude's Discretion

- Exact section ordering within each doc
- How much detail per pipeline stage (proportional to complexity)
- Whether architecture.md duplicates content or cross-references the other two docs
- Tone and writing style within the "both audiences" constraint

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

## Standard Stack

### Core Technologies

| Library/Tool | Version | Purpose | Why Standard |
|--------------|---------|---------|--------------|
| Markdown | N/A | Documentation format | Universal standard, version-controllable, readable as plain text, supported everywhere |
| Tree-sitter | Latest | Code parsing for chunking | Industry standard for language-aware code parsing, used by GitHub, Neovim, etc. |
| pgvector | 0.5+ | Vector similarity search | PostgreSQL native extension, production-proven, no separate vector DB needed |
| Ollama | Latest | Local embedding generation | Open source local LLM runner, privacy-preserving, supports nomic-embed-text |

### Supporting Tools

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| Markdown linters | Latest | Ensure consistent formatting | CI/CD integration for documentation quality |
| Vale | Latest | Style guide enforcement | Optional - for enforcing writing consistency |

### Documentation Framework

No framework needed - plain Markdown files with clear structure. Avoid over-engineering for 3 documentation files.

**Why not use a doc framework:**
- Frameworks like Sphinx, MkDocs, or Docusaurus add complexity for minimal benefit at this scale
- 3 files don't need a static site generator
- Markdown in GitHub/GitLab renders perfectly without build step
- Readers can view docs directly in repository without installing tooling

## Architecture Patterns

### Recommended Documentation Structure

```
docs/
├── architecture.md        # High-level system overview
├── retrieval.md          # Search pipeline deep dive
└── mcp-tools.md          # MCP tool reference
```

README.md gets new section:
```markdown
## Documentation

- [Architecture Overview](docs/architecture.md) - System components and data flow
- [Retrieval Logic](docs/retrieval.md) - Hybrid search, RRF fusion, and caching
- [MCP Tools Reference](docs/mcp-tools.md) - Tool parameters and examples
```

### Pattern 1: Concept-First Documentation

**What:** Explain abstract concepts before implementation details
**When to use:** Technical systems with non-obvious algorithms (like RRF, embeddings)
**Structure:**

```markdown
## Hybrid Search

### What It Does
[2-3 sentence user-facing explanation]

### How It Works
[Conceptual explanation with formula]

### Implementation
[Actual code flow with file references]
```

**Rationale:** Readers build mental model before diving into specifics. Matches user decision: "Include a brief primer on core concepts before CocoSearch specifics."

### Pattern 2: Dual-Format MCP Examples

**What:** Show both natural language description and structured JSON for each tool
**When to use:** API/tool documentation consumed by both humans and LLMs
**Structure:**

```markdown
## search_code

Search indexed code using natural language queries.

**Example:**

Find authentication logic in Python files:

**Request:**
```json
{
  "query": "user authentication logic",
  "language": "python",
  "limit": 5
}
```

**Response:**
```json
[
  {
    "file_path": "src/auth/login.py",
    "start_line": 45,
    "end_line": 67,
    "score": 0.89,
    "content": "def authenticate_user(...)..."
  }
]
```

**Source:** [API Documentation Best Practices (Postman)](https://www.postman.com/api-platform/api-documentation/), [Stoplight API Guide](https://stoplight.io/api-documentation-guide)

### Pattern 3: End-to-End Flow Documentation

**What:** Document complete pipeline from input to output with all intermediate steps
**When to use:** Complex multi-stage systems (indexing, search pipelines)
**Structure:**

```markdown
## Search Pipeline

1. **Query Processing**
   - Input: User query string
   - Process: Identifier pattern detection (camelCase/snake_case)
   - Output: Normalized query + hybrid flag
   - File: `src/cocosearch/search/query_analyzer.py`

2. **Embedding Generation**
   [etc.]
```

**Rationale:** Matches user requirement "Full end-to-end pipeline coverage" with file references for code navigation.

### Pattern 4: Formula-First Explanations

**What:** Show the actual formula/algorithm before prose explanation
**When to use:** Quantitative algorithms (RRF, scoring, ranking)
**Structure:**

```markdown
### RRF Fusion Algorithm

**Formula:**
```
RRF_score = sum(1 / (k + rank)) for each matching result list
where k = 60 (standard RRF constant)
```

**How it works:** Results appearing in both vector and keyword searches get contributions from both ranks...
```

**Source:** [OpenSearch RRF](https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/), [Azure AI Hybrid Search](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking)

### Anti-Patterns to Avoid

- **Assuming prerequisite knowledge:** Don't use "embeddings" or "RRF" without defining first
- **Example overload:** User specified "one canonical example per tool" — resist adding edge cases
- **Duplicate content:** Don't repeat implementation details across multiple docs (cross-reference instead)
- **Diagrams:** User explicitly excluded diagrams — use text descriptions with ASCII art at most
- **Version-specific details:** Document current behavior only, not historical evolution (unless critical for understanding)

## Don't Hand-Roll

Problems that have existing documentation solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Interactive API explorer | Custom UI for trying MCP tools | JSON examples in markdown | User specified no decision guide, happy path only |
| Documentation site generator | MkDocs/Sphinx setup | Plain Markdown files | 3 files don't justify build tooling |
| Glossary of terms | Separate glossary page | Inline definitions in context | Easier to maintain with small doc set |
| Version tracking | Custom versioning system | Git history | Docs live in repo, version control is free |

**Key insight:** For small documentation sets (3 files), simplicity beats sophistication. Markdown + Git provides versioning, diffs, and collaboration without additional tooling.

## Common Pitfalls

### Pitfall 1: Audience Mismatch

**What goes wrong:** Writing for contributors when AI agents need to consume the docs, or vice versa
**Why it happens:** Mixed audience (contributors + AI agents) for retrieval.md, different audience (AI agents) for mcp-tools.md
**How to avoid:**
- retrieval.md: Conceptual overview → implementation details (serves both)
- mcp-tools.md: Structured parameter descriptions + JSON examples (AI-first)
- Use consistent field names between prose and JSON
**Warning signs:**
- Parameters described in prose but not in JSON example
- JSON example has fields not documented in parameter table
- Inconsistent terminology between natural language and structured data

### Pitfall 2: Missing Implementation Details

**What goes wrong:** Explaining what system does without how it does it
**Why it happens:** Tendency to write user-facing docs instead of contributor docs
**How to avoid:**
- Include file paths for every major component mentioned
- Document actual parameter values (RRF k=60, cache TTL=24h, etc.)
- Show SQL queries or algorithm pseudocode for complex logic
**Warning signs:**
- "The system uses caching" without TTL/eviction strategy
- "Hybrid search combines results" without RRF formula
- Module names without file paths

### Pitfall 3: Concept Dumping

**What goes wrong:** Defining embeddings/vector search in excessive detail
**Why it happens:** Trying to be comprehensive about prerequisites
**How to avoid:**
- User decision: "brief primer" not comprehensive tutorial
- 2-3 sentences per concept with link to authoritative source
- Focus on "what CocoSearch does with it" not "what is it"
**Warning signs:**
- Multi-paragraph explanation of Word2Vec or transformers
- Deep dive into cosine similarity math
- History of embedding models

### Pitfall 4: Inconsistent Terminology

**What goes wrong:** Using different terms for same concept (chunks vs blocks, embeddings vs vectors)
**Why it happens:** Multiple contributors, evolving codebase
**How to avoid:**
- Define canonical terms in architecture.md introduction
- Use find/replace to ensure consistency across all 3 docs
- Match terminology to actual code variable names
**Warning signs:**
- "chunks" in retrieval.md but "blocks" in architecture.md
- "embedding vector" vs "semantic vector" vs "vector embedding"
- Parameter names in examples don't match actual MCP tool signatures

## Code Examples

### Example 1: MCP Tool Documentation (Dual Format)

From user decision: "natural language description, then JSON request, then JSON response"

```markdown
## search_code

Search indexed code using natural language queries. Returns semantically similar code chunks ranked by relevance.

**Parameters:**
- `query` (string, required): Natural language search query
- `index_name` (string, optional): Index to search (auto-detected from cwd if omitted)
- `limit` (integer, optional): Max results to return (default: 10)
- `language` (string, optional): Filter by language (e.g., "python", "typescript")

**Example:**

Find error handling code in Python files:

**Request:**
```json
{
  "query": "error handling and retry logic",
  "language": "python",
  "limit": 5
}
```

**Response:**
```json
[
  {
    "file_path": "src/api/client.py",
    "start_line": 34,
    "end_line": 52,
    "score": 0.87,
    "content": "@retry(max_attempts=3)\ndef fetch_data(url):\n    try:\n        response = requests.get(url)\n        response.raise_for_status()\n    except requests.exceptions.RequestException as e:\n        logger.error(f\"Request failed: {e}\")\n        raise"
  }
]
```
```

**Source:** Synthesized from [Postman API Docs](https://www.postman.com/api-platform/api-documentation/), [Kong API Guide](https://konghq.com/blog/learning-center/guide-to-api-documentation)

### Example 2: RRF Algorithm Documentation

From user decision: "Include actual scoring/ranking numbers (RRF k parameter, weight ratios, formulas)"

```markdown
### Reciprocal Rank Fusion (RRF)

CocoSearch merges vector similarity results and keyword search results using the RRF algorithm.

**Formula:**
```
Combined_score = sum(1 / (k + rank))
where:
  k = 60 (standard RRF constant)
  rank = position in result list (1-indexed)
```

**Example calculation:**

Result appears at rank 3 in vector search and rank 1 in keyword search:
```
RRF_score = (1 / (60 + 3)) + (1 / (60 + 1))
          = 0.0159 + 0.0164
          = 0.0323
```

Results appearing in both lists naturally score higher than results in only one list.

**Implementation:** `src/cocosearch/search/hybrid.py:rrf_fusion()`
```

**Source:** [OpenSearch RRF Blog](https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/), [Azure AI Hybrid Search Ranking](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking)

### Example 3: Cache Behavior Documentation

From user decision: "Full query caching details: cache keys, TTL, eviction strategy, invalidation"

```markdown
### Query Caching

CocoSearch caches search results in memory using a two-level cache.

**Cache Levels:**

1. **Exact Match (L1):**
   - Key: SHA256 hash of (query, index, limit, filters)
   - Hit condition: Identical query parameters

2. **Semantic Match (L2):**
   - Key: Query embedding vector
   - Hit condition: Cosine similarity ≥ 0.95 with cached embedding
   - Purpose: Cache hits for paraphrased queries

**Cache Parameters:**
- TTL: 24 hours (86400 seconds)
- Eviction: Time-based (no size limit)
- Invalidation: On reindex (`invalidate_index_cache(index_name)`)

**Implementation:** `src/cocosearch/search/cache.py:QueryCache`

**Cache key example:**
```python
# Query: "error handling", index: myproject, limit: 10
# SHA256("query=error handling|index=myproject|limit=10|...")
# → "a3f2bc..."
```
```

**Source:** Pattern synthesized from codebase analysis

## State of the Art

### Documentation Trends (2026)

| Approach | Status | Adoption | Impact |
|----------|--------|----------|--------|
| AI-generated docs | Emerging | Experimental | Not reliable for technical accuracy yet |
| Docs-as-code | Standard | Universal | Markdown in Git is de facto standard |
| Interactive examples | Growing | Common for APIs | User excluded interactive explorer |
| Concept-first structure | Established | Best practice | Matches user decision for primers |

**Source:** [Imaginary Cloud Architecture Docs](https://www.imaginarycloud.com/blog/software-architecture-documentation), [bool.dev Best Practices](https://bool.dev/blog/detail/architecture-documentation-best-practice)

### Vector Search Documentation Evolution

| Old Approach | Current Approach (2026) | When Changed | Impact |
|--------------|------------------------|--------------|--------|
| Dense mathematical formulas | Formula + plain language explanation | ~2024 | More accessible to practitioners |
| Single metric (cosine only) | Multiple metrics explained | ~2025 | Users understand tradeoffs |
| Assume ML knowledge | Concept primers for all terms | 2025-2026 | Broader audience reach |

**Source:** [Meilisearch Vector Embeddings Guide](https://www.meilisearch.com/blog/what-are-vector-embeddings), [OpenSearch Vector Search Basics](https://www.instaclustr.com/education/opensearch/opensearch-vector-search-the-basics-and-a-quick-tutorial-2026-guide/)

**Deprecated/outdated:**
- Separate API explorers: Modern practice favors copy-paste JSON examples over interactive UIs for simple tools
- Architecture decision records (ADRs): Useful for complex systems, overkill for 3-file documentation set
- UML diagrams: User explicitly excluded diagrams; text descriptions are sufficient

## Open Questions

### Question 1: Cross-referencing vs. Duplication

**What we know:**
- architecture.md provides high-level overview
- retrieval.md provides deep dive on search pipeline
- Some overlap inevitable (e.g., RRF mentioned in both)

**What's unclear:**
- How much detail should architecture.md include before saying "see retrieval.md for details"?
- Should architecture.md duplicate RRF formula or just link to retrieval.md?

**Recommendation:**
- architecture.md: One-line description + link to retrieval.md
- retrieval.md: Full formula and explanation
- Principle: "Brief mention in architecture, full detail in specialized doc"

### Question 2: MCP Tool Parameter Completeness

**What we know:**
- User wants "complete examples" but "happy path only"
- Real tools have many optional parameters

**What's unclear:**
- Should examples show all parameters (even optional ones) or just commonly-used subset?
- How to indicate which parameters are optional vs required?

**Recommendation:**
- Show required parameters + 1-2 most common optional parameters in example
- List all parameters in "Parameters" section with required/optional marker
- Example focuses on common use case, parameter list shows complete interface

## Sources

### Primary (HIGH confidence)

**Codebase Analysis:**
- `/src/cocosearch/mcp/server.py` - MCP tool definitions and signatures
- `/src/cocosearch/search/query.py` - Search function with all parameters
- `/src/cocosearch/search/hybrid.py` - RRF implementation with k=60 constant
- `/src/cocosearch/search/cache.py` - Cache TTL, similarity threshold (0.95)
- `/src/cocosearch/indexer/flow.py` - Indexing pipeline end-to-end
- `README.md` - Existing user-facing documentation patterns

**Official Documentation Standards:**
- [OpenSearch RRF Introduction](https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/) - RRF algorithm explanation
- [Azure AI Hybrid Search Ranking](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking) - RRF formula and parameters
- [Meilisearch Vector Embeddings Guide](https://www.meilisearch.com/blog/what-are-vector-embeddings) - Concept primer pattern
- [OpenSearch Vector Search Basics](https://www.instaclustr.com/education/opensearch/opensearch-vector-search-the-basics-and-a-quick-tutorial-2026-guide/) - Technical concept explanations

### Secondary (MEDIUM confidence)

**Documentation Best Practices:**
- [Postman API Documentation Guide](https://www.postman.com/api-platform/api-documentation/) - API reference structure
- [Stoplight API Documentation Guide](https://stoplight.io/api-documentation-guide) - Parameter documentation patterns
- [Kong API Documentation Guide](https://konghq.com/blog/learning-center/guide-to-api-documentation) - Implementation tips
- [Imaginary Cloud Architecture Docs](https://www.imaginarycloud.com/blog/software-architecture-documentation) - Architecture documentation structure
- [bool.dev Architecture Best Practices](https://bool.dev/blog/detail/architecture-documentation-best-practice) - Documentation hierarchy
- [Working Software Architecture Guide](https://www.workingsoftware.dev/software-architecture-documentation-the-ultimate-guide/) - Complete architecture docs

**Vector Search References:**
- [OpenSearch Vector Search Concepts](https://docs.opensearch.org/latest/vector-search/getting-started/concepts/) - Vector search fundamentals
- [Azure AI Vector Search](https://learn.microsoft.com/en-us/azure/search/vector-search-overview) - Vector search overview
- [Google Cloud BigQuery Vector Search](https://docs.cloud.google.com/bigquery/docs/vector-search-intro) - Embeddings introduction

### Tertiary (LOW confidence)

None - all findings verified with authoritative sources or codebase analysis.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Markdown is universal, codebase uses established tools
- Architecture patterns: HIGH - Patterns verified in multiple authoritative sources and align with user decisions
- Pitfalls: HIGH - Derived from codebase analysis showing actual implementation patterns
- Code examples: HIGH - Directly extracted from codebase with verified parameter values
- State of the art: MEDIUM - Based on 2026 industry sources but documentation trends evolve quickly

**Research date:** 2026-02-06
**Valid until:** 30 days (stable domain - documentation best practices change slowly)

**Key codebase insights:**
- RRF k parameter: 60 (standard value, verified in `hybrid.py`)
- Cache TTL: 24 hours, semantic threshold: 0.95 (verified in `cache.py`)
- Chunk size: 1000 bytes, overlap: 300 bytes (verified in `flow.py`)
- Symbol-aware languages: python, javascript, typescript, go, rust (verified in `query.py`)
- MCP tools: 5 total (search_code, index_codebase, list_indexes, index_stats, clear_index)
