# Phase 32: Full Language Coverage + Documentation - Context

**Gathered:** 2026-02-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Enable all 30+ CocoIndex languages with a `stats` command and `languages` command, plus comprehensive README documentation for all v1.7 features (hybrid search, symbol filtering, context expansion).

</domain>

<decisions>
## Implementation Decisions

### Stats command output
- Show three metrics per language: line count, file count, chunk count
- Default output is ASCII table (human-readable, like git/docker)
- Support `--json` flag for programmatic/scripted use
- Include total summary row at bottom summing all languages

### Documentation structure
- All docs in README.md (expand existing, single file)
- Include Quick Start section for new users (5-minute: install, index, search)
- Include MCP integration section with Claude Desktop configuration
- Complete examples showing command + expected output for each feature

### Language list presentation
- Table format: Language | Extensions (e.g., Python | .py)
- Mark symbol-aware languages with column/badge showing which have symbol extraction
- New `cocosearch languages` CLI command to print supported languages
- Languages command shows: Language | Extensions | Symbols (✓/✗)

### Feature documentation
- Use case driven: start with "When to use X", then show example
- Include before/after comparison examples to highlight improvement
- Document CLI flags and MCP parameters together (inline, not separate)
- Include recipes section with common use cases:
  - "Find all Python functions that handle errors"
  - "Search for API endpoints"
  - Combining features effectively

### Claude's Discretion
- Exact ASCII table styling and column widths
- Order of languages in table (alphabetical vs by file count)
- Specific recipe examples to include
- README section ordering

</decisions>

<specifics>
## Specific Ideas

- Stats command should feel familiar like `git status` or `docker ps` table output
- Languages command similar to `cocosearch stats` in table style for consistency

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 32-full-language-coverage-documentation*
*Context gathered: 2026-02-03*
