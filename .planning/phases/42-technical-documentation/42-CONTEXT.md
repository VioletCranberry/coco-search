# Phase 42: Technical Documentation - Context

**Gathered:** 2026-02-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Document retrieval logic and MCP tool usage so users and contributors understand the search pipeline and can use/extend CocoSearch effectively. Documentation must be accurate to the current post-cleanup implementation (post-Phase 40).

</domain>

<decisions>
## Implementation Decisions

### Document structure
- Dedicated `docs/` folder with separate .md files per topic
- No index page or docs/README.md — filenames are self-explanatory
- Three files: `docs/architecture.md` (high-level overview), `docs/retrieval.md` (search pipeline), `docs/mcp-tools.md` (tool reference)
- Main project README gets a "Documentation" section linking to docs/ files

### Audience & depth
- Retrieval logic docs serve both contributors and power users equally — conceptual overview first, then implementation details
- MCP tools reference primarily targets AI agents/LLMs consuming the tools — focus on parameters, return formats, when to use each tool
- Include a brief primer on core concepts (embeddings, vector search, RRF) before CocoSearch specifics — don't assume familiarity
- No diagrams — text descriptions only

### Code examples style
- MCP tool examples use both formats: natural language description, then JSON request, then JSON response
- One canonical example per tool showing the most common use case
- Happy path only — no error case examples
- No "when to use which tool" decision guide — each tool's section describes its own purpose

### Retrieval logic scope
- Full end-to-end pipeline coverage: query processing -> embedding -> vector search -> keyword search -> RRF fusion -> filtering -> ranking
- Include actual scoring/ranking numbers (RRF k parameter, weight ratios, formulas)
- Full query caching details: cache keys, TTL, eviction strategy, invalidation
- Cover both sides: indexing (how code gets into DB — parsing, chunking, embedding) AND search/query pipeline

### Claude's Discretion
- Exact section ordering within each doc
- How much detail per pipeline stage (proportional to complexity)
- Whether architecture.md duplicates content or cross-references the other two docs
- Tone and writing style within the "both audiences" constraint

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 42-technical-documentation*
*Context gathered: 2026-02-06*
