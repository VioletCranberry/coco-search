---
phase: 27-hybrid-search-foundation
plan: 01
subsystem: indexer
tags: [cocoindex, hybrid-search, text-storage, bm25]

dependency_graph:
  requires: []
  provides: [content_text_field, keyword_search_foundation]
  affects: [27-02, 27-03, 28-hybrid-search]

tech_stack:
  added: []
  patterns: [field_extension_for_hybrid_search]

key_files:
  created:
    - tests/unit/test_indexer_flow.py
  modified:
    - src/cocosearch/indexer/flow.py

decisions:
  - id: content_text_raw
    choice: "Store raw chunk text without transformation"
    reason: "PostgreSQL will convert to tsvector in later phase; keep separation"

metrics:
  duration: 2m
  completed: 2026-02-03
---

# Phase 27 Plan 01: Content Text Field Summary

**One-liner:** Added content_text field to CocoIndex flow to store chunk text for BM25-style keyword search in hybrid search (v1.7).

## What Was Built

### Content Text Field in Indexing Flow

Modified `create_code_index_flow()` to include `content_text=chunk["text"]` in the collector:

```python
# Collect with metadata (now includes content_text for hybrid search)
# content_text stores raw chunk text for keyword/BM25-style search (v1.7)
code_embeddings.collect(
    filename=file["filename"],
    location=chunk["location"],
    embedding=chunk["embedding"],
    content_text=chunk["text"],  # Store text for keyword indexing
    block_type=chunk["metadata"]["block_type"],
    hierarchy=chunk["metadata"]["hierarchy"],
    language_id=chunk["metadata"]["language_id"],
)
```

Key characteristics:
- Raw chunk text passed directly (no transformation)
- CocoIndex automatically creates TEXT column on next flow run
- Enables keyword search via PostgreSQL tsvector in Phase 27-03

### Unit Tests

Created `tests/unit/test_indexer_flow.py` with 3 tests:
1. `test_flow_source_code_contains_content_text_collection` - Verifies field exists
2. `test_flow_has_hybrid_search_documentation` - Ensures purpose is documented
3. `test_flow_collects_all_required_fields` - Validates complete field set

## Verification Results

```
tests/unit/test_indexer_flow.py - 3 passed
tests/unit/ - 623 passed (no regressions)
```

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Field receives raw text | `chunk["text"]` directly | PostgreSQL tsvector conversion happens in Phase 27-03; keep separation of concerns |
| No schema migration needed | CocoIndex auto-creates | Framework handles ALTER TABLE automatically on flow setup |

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 6981603 | feat | Add content_text field to indexing flow |
| a8d6269 | test | Add unit tests for content_text field in flow |

## Next Phase Readiness

**Ready for 27-02:** Content text is now collected. Next plan will modify the search module to use this field for keyword matching.

**Schema note:** Existing indexes will gain the `content_text` column on next re-index. The column will be NULL for existing chunks until re-indexed.
