# Phase 4: Search and Output Integration - Context

**Gathered:** 2026-01-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Users and calling LLMs see DevOps metadata in search results and can filter by DevOps language. Extends SearchResult, SQL queries, CLI output (pretty + JSON), and MCP server responses to surface block_type, hierarchy, and language_id populated by Phases 1-3. No new indexing logic -- this phase is read-side only.

</domain>

<decisions>
## Implementation Decisions

### Result presentation (pretty output)
- Prefix annotation format: show metadata as a tag before the code block, e.g. `[hcl] resource.aws_s3_bucket.data`
- Hierarchy only in annotation -- do not show block_type separately (hierarchy already encodes it)
- Show language tag for ALL files, including non-DevOps (e.g. `[python]`, `[javascript]`) using existing extension info
- Use language_id field (not file extension) for syntax highlighting of DevOps code

### Language filtering UX
- Canonical names only: `hcl`, `dockerfile`, `bash` -- no aliases (no terraform, docker, shell, sh)
- Dockerfile filtering uses language_id column match (not basename SQL LIKE pattern)
- Comma-separated multi-language support: `--lang hcl,bash` filters across multiple languages in one query
- Unrecognized --lang values produce an error with available language suggestions

### Graceful degradation (pre-v1.2 indexes)
- Auto-detect missing metadata columns and show a one-time warning per session: "Index lacks metadata columns. Run `cocosearch index` to upgrade."
- Language filter on pre-v1.2 index produces a clear error: "Language filtering requires v1.2 index. Run `cocosearch index` to upgrade."
- JSON output includes metadata keys with empty string values (not null, not omitted) for pre-v1.2 indexes -- consistent shape
- Warning appears once per session, suppressed on subsequent searches

### MCP response shape
- Add optional `language` parameter to MCP `search_code` tool definition, mirroring CLI `--lang`
- Metadata fields always included in MCP response with empty strings when unavailable -- consistent shape
- Pre-v1.2 index behavior matches CLI: empty strings for metadata fields

### Claude's Discretion
- Whether MCP metadata fields are flat (top-level) or nested in a metadata sub-object
- Whether to include a pre-formatted annotation string in MCP response for LLM convenience
- Exact wording of upgrade warnings and error messages
- Syntax highlighting library/method selection for HCL, Dockerfile, Bash

</decisions>

<specifics>
## Specific Ideas

- Pretty output annotation format: `[hcl] resource.aws_s3_bucket.data` -- compact, scannable, mirrors how developers think about infrastructure code
- Non-DevOps files should also get language tags (e.g. `[python]`) for visual consistency across all results
- Error messages for invalid --lang should list all available languages to help discovery

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 04-search-and-output-integration*
*Context gathered: 2026-01-27*
