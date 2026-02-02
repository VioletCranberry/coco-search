# Phase 26: Documentation & Polish - Context

**Gathered:** 2026-02-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Complete documentation for Docker deployment and MCP client configuration. Documentation enables users to deploy CocoSearch and connect it to Claude Code or Claude Desktop with minimal friction.

</domain>

<decisions>
## Implementation Decisions

### Audience assumptions
- Docker experience: Knows `docker run` — understands images, containers, ports, volumes
- MCP familiarity: Already uses Claude Code/Desktop — just needs config snippet
- OS focus: Linux primary, note macOS differences where relevant
- Use cases: Both personal local dev AND team/shared server documented equally

### Quick start structure
- Goal: Full MCP integration working (container running AND connected to Claude)
- Split by transport: One quick start for Claude Code (stdio), another for Claude Desktop (SSE)
- Prerequisites: Assume met, link to external install docs if needed
- Location: Everything in README.md only, no docs/ folder

### Example depth
- Docker examples: Minimal working command with inline `#` comments
- MCP config: Clean JSON that can be copy-pasted, separate prose explaining fields
- Volume mounts: One recommended pattern (named volume), mention alternatives briefly
- Values: Use realistic defaults that work as-is; use repo-local folder for volumes (add to .gitignore)

### Troubleshooting approach
- Organization: Component-first (PostgreSQL issues, Ollama issues, MCP issues)
- Detail level: Fix with brief explanation ("This happens because X. Fix with Y.")
- Logs: Show `docker logs` commands prominently as first diagnostic step
- MCP issues: Brief mentions only, link to MCP docs for client-side issues

### Claude's Discretion
- Exact section ordering in README
- Whether to use collapsible sections for advanced topics
- Formatting choices (tables vs lists)
- Which specific error messages to document

</decisions>

<specifics>
## Specific Ideas

- Use a repo-local folder for volume mounts that gets added to .gitignore (keeps examples copy-paste ready)
- Realistic defaults that work immediately without substitution

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 26-documentation-polish*
*Context gathered: 2026-02-02*
