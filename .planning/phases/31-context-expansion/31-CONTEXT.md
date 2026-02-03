# Phase 31: Context Expansion Enhancement - Context

**Gathered:** 2026-02-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Search results show surrounding code context with smart boundaries and performance optimization. Users can request context via CLI flags (-A/-B/-C) or MCP parameters. Context automatically expands to function/class boundaries by default.

</domain>

<decisions>
## Implementation Decisions

### Output presentation
- Use grep-style line markers: `:` prefix for context lines, `>` prefix for matched chunk
- Always show line numbers for all lines (context and match)
- JSON output uses inline fields: `context_before` and `context_after` as strings

### Boundary behavior
- Smart expansion to enclosing function/class is always on by default
- Hard limit of 50 lines maximum per result (even if function is longer)
- `--no-smart` flag available to disable smart expansion and use raw line counts
- Fallback behavior for non-code files (JSON, Markdown) is Claude's discretion

### Default values
- Smart expansion by default (no flags needed) — expand to function boundary
- MCP uses same defaults as CLI (smart expansion on)
- `-A/-B/-C` flags override smart expansion (explicit lines, ignore boundaries)
- Maximum 50 lines per result

### Edge cases
- Show BOF/EOF markers when context hits file start/end
- Skip results entirely if source file has been deleted/moved since indexing
- Truncate long lines at reasonable length with `...` suffix
- Binary files: show indexed chunk only, don't attempt to read context

### Claude's Discretion
- Grouping strategy for multiple results from same file (merge overlapping or separate)
- Specific fallback behavior for non-code file types
- Exact line truncation length (e.g., 200 chars)
- BOF/EOF marker format

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

*Phase: 31-context-expansion*
*Context gathered: 2026-02-03*
