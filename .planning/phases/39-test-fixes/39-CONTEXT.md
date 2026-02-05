# Phase 39: Test Fixes - Context

**Gathered:** 2026-02-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix test suite to pass reliably with correct signature format expectations. Tests define correctness — if a test reveals implementation behavior is wrong, fix the implementation.

</domain>

<decisions>
## Implementation Decisions

### Signature Format Expectations
- Update tests to match current implementation (impl is source of truth for format)
- Use exact string match assertions — catches unintended format changes
- Batch commits by issue type (e.g., all signature format fixes together)
- If tests reveal impl behavior is wrong (not just format), fix the implementation

### Test Maintenance Approach
- Test data (expected signatures) should be inline in test functions — easy to see what's tested
- Multi-line signature expectations use triple-quoted strings for visual clarity
- Every assertion gets a comment explaining WHY that signature format is expected
- Normalize all signature tests to follow same pattern, even if currently passing

### Coverage Scope
- Audit all tests systematically — run full suite, identify all failures
- Add tests for untested signature edge cases discovered during fixes
- Fix all test failures found, not just signature-related ones
- Local pytest pass is sufficient — no CI verification required

### Claude's Discretion
- Order of test fixes (which files/modules first)
- Specific comment wording for assertions
- How to organize commits within "issue type" batches

</decisions>

<specifics>
## Specific Ideas

- Green test suite is the goal — phase is complete when pytest passes
- Implementation is authoritative for format; tests should be updated to match
- But tests are authoritative for correctness — if behavior seems wrong, fix impl

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 39-test-fixes*
*Context gathered: 2026-02-05*
