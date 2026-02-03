# Phase 28: Hybrid Search Query - Context

**Gathered:** 2026-02-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can search using both vector similarity and keyword matching with RRF fusion. This phase adds hybrid search capability to existing vector search — CLI flag, MCP parameter, auto-detection of identifier patterns, and result fusion. Symbol filtering (Phase 30) and context expansion (Phase 31) are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Result fusion & ranking
- Favor keyword matches when vector and keyword scores are close (tie-breaking)
- Fixed RRF balance — no user-adjustable weighting parameter
- Double-match boost: results found by both vector and keyword rank notably higher
- Silent fallback: show vector-only results gracefully when keyword returns 0 (no warning)

### Keyword matching behavior
- Substring matching: 'user' matches anywhere in 'getUserName'
- Normalize naming conventions: camelCase and snake_case treated as equivalent ('get_user_name' matches 'getUserName')
- Common programming keywords (function, class, return) match but rank lower than identifiers

### Output presentation
- Show match type indicator: display [semantic], [keyword], or [both] for each result
- In JSON output (MCP): include detailed breakdown — vector_score, keyword_score, combined_score, matched_terms
- Distinguish match quality: indicate if match was exact or via normalization (camelCase→snake_case)

### Claude's Discretion
- Case sensitivity for keyword search
- Keyword highlighting in terminal output (based on terminal compatibility)
- RRF k parameter tuning

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

*Phase: 28-hybrid-search-query*
*Context gathered: 2026-02-03*
