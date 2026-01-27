# Phase 3: Flow Integration and Schema - Context

**Gathered:** 2026-01-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire metadata extraction (Phase 2) into the CocoIndex indexing pipeline and extend the PostgreSQL schema with three new columns (block_type, hierarchy, language_id). After this phase, running `cocosearch index` on DevOps files produces chunks with populated metadata stored in PostgreSQL. Only `flow.py` is modified — no new files.

</domain>

<decisions>
## Implementation Decisions

### Metadata step placement
- Metadata extraction runs as a separate CocoIndex op function (`@cocoindex.op.function()` decorator), not inline in flow.py
- The DevOpsMetadata dataclass maps to three individual collector fields (block_type, hierarchy, language_id) — not a nested struct
- Claude's discretion: how language_id reaches the metadata function (re-derive from filename vs carry through flow) and whether extraction runs on all chunks or conditionally on DevOps chunks only

### Schema migration behavior
- Re-index required after upgrading to v1.2 — document in release notes
- Table drop/recreate is acceptable since re-indexing is required anyway
- No explicit migration tooling — CocoIndex handles schema changes on next `cocosearch index` run
- Primary key stability ([filename, location]) validated during research phase, not enforced with a test

### Pipeline error handling
- Parsing edge cases (unexpected chunk format): log warning with filename and chunk, return empty strings — chunk still gets indexed
- Unhandled exceptions in metadata op function: crash the indexing run — bugs should not be silently swallowed
- Validate custom_languages at startup: check that HCL, Dockerfile, and Bash specs are present before starting the flow, fail early with clear message
- Empty/whitespace chunks: run extraction anyway (function naturally returns empty strings) — consistent code path

### Extension vs language_id
- Both extension and language_id populated for DevOps files (e.g., extension='tf', language_id='hcl')
- Dockerfiles: extension stays empty string (no file extension), language_id='dockerfile' handles identification
- Non-DevOps files: language_id remains empty string in v1.2 — it's a DevOps-only field for now

### Claude's Discretion
- How language identifier reaches the metadata extraction function (re-derive vs flow field)
- Whether metadata extraction runs on every chunk or conditionally
- Whether to flag extension/language_id relationship as future design debt (non-blocking)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The key constraint is that only `flow.py` is modified (metadata.py and languages.py already exist from Phases 1-2).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 10-flow-integration-and-schema*
*Context gathered: 2026-01-27*
