# Phase 30: Symbol Search Filters + Language Expansion - Context

**Gathered:** 2026-02-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can filter searches by symbol type (function/class/method/variable/interface) and name patterns. Symbol extraction extends to JavaScript, TypeScript, Go, and Rust. Function and class definitions rank higher than references in search results.

</domain>

<decisions>
## Implementation Decisions

### Filter syntax & behavior
- Five symbol types filterable: function, class, method, variable/constant, interface/type
- `--symbol-name` supports glob patterns (e.g., `get*`, `User*Service`)
- Symbol name matching is case-insensitive
- When both `--symbol-type` and `--symbol-name` provided, they combine with AND (both must match)

### Search result ranking
- Definitions get 2x score boost over references (but very relevant references can still rank higher)
- When symbol filters match zero results, return empty with hint: "Try removing --symbol-type filter"
- Exact symbol name matches rank higher than partial/glob matches
- Definition boost applied after RRF fusion (compute hybrid score first, then boost)

### Language-specific extraction
- Go methods use qualified names: `StructName.MethodName` (e.g., `Server.Start`)
- Rust impl blocks extracted — methods become `TypeName.method_name`
- JS/TS: only named arrow functions extracted (e.g., `const fetchUser = () => {}` → symbol 'fetchUser')

### MCP interface design
- Parameter names: `symbol_type`, `symbol_name` (matches CLI flags)
- Response always includes symbol metadata: `symbol_type`, `symbol_name`, `symbol_signature`
- `symbol_type` accepts array for OR filtering: `['function', 'method']`
- Pre-v1.7 indexes with symbol filters → error with guidance: "Re-index with v1.7+ to enable symbol filtering"

### Claude's Discretion
- TypeScript: whether both interfaces and type aliases become symbols (lean toward yes)
- Exact boost multiplier tuning if 2x doesn't feel right
- Error message wording and hint formatting

</decisions>

<specifics>
## Specific Ideas

- Qualified method names provide consistent pattern across Python (already `ClassName.method_name`), Go, and Rust
- Case-insensitive matching is forgiving for code search (developers don't always remember exact casing)
- Glob patterns familiar from shell usage, lower learning curve than regex

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 30-symbol-search-filters*
*Context gathered: 2026-02-03*
