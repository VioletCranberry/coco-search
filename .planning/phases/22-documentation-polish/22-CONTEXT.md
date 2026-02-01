# Phase 22: Documentation Polish - Context

**Gathered:** 2026-02-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Add clickable table of contents to README for professional navigation. Includes reorganizing sections for user journey flow and standardizing headings. No new documentation content — focus is navigability and structure.

</domain>

<decisions>
## Implementation Decisions

### TOC Structure
- Comprehensive TOC — every section and subsection gets an entry
- Match document order — TOC mirrors exact order sections appear in README
- No numbering — clean list without numbers
- Claude's discretion on nesting depth based on README content

### TOC Format
- Emoji/icon prefixes — each section gets a unique, fitting emoji
- 2-space indentation for nested items
- No visual separators between groups — clean continuous list
- Standard markdown links: `[Section Name](#section-name)`

### Section Organization
- Full reorganize — restructure sections for optimal TOC experience
- User journey ordering: overview → install → quick start → config → advanced
- Standardize headings to action-oriented style ("Installing", "Configuring", "Running Queries")

### TOC Placement
- After project intro — Title → brief description → TOC → everything else
- Always visible — no collapsible container
- With heading — "## Table of Contents" or similar
- Back-to-top links after major sections: `[↑ Back to top](#table-of-contents)`

### Claude's Discretion
- Exact emoji selection for each section
- Nesting depth determination based on content
- Specific heading rewrites within action-oriented constraint
- Which sections qualify as "major" for back-to-top links

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 22-documentation-polish*
*Context gathered: 2026-02-01*
