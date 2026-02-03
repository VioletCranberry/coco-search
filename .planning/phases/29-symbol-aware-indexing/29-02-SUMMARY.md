---
phase: 29-symbol-aware-indexing
plan: 02
subsystem: indexer
tags: [symbol-indexing, schema-migration, cocoindex, postgresql]

# Dependency graph
requires:
  - phase: 29-01
    provides: extract_symbol_metadata function
  - phase: 27-keyword-search
    provides: schema_migration.py pattern
provides:
  - Symbol metadata extraction integrated into indexing flow
  - Idempotent symbol columns schema migration
  - Backward-compatible nullable symbol columns
affects: [30-symbol-search]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Schema migration called after flow.setup() but before flow.update()
    - Nullable TEXT columns for backward compatibility
    - CocoIndex table naming convention handling (codeindex_{name}__{name}_chunks)

key-files:
  created: []
  modified:
    - src/cocosearch/indexer/flow.py
    - src/cocosearch/indexer/schema_migration.py
    - tests/unit/indexer/test_flow.py

key-decisions:
  - "Call ensure_symbol_columns() after flow.setup() but before flow.update()"
  - "Use CocoIndex table naming: codeindex_{index_name}__{index_name}_chunks"
  - "Symbol columns as nullable TEXT (no defaults) for backward compatibility"
  - "Schema migration is idempotent (safe to run multiple times)"

patterns-established:
  - "Schema migration timing: after table creation, before data insertion"
  - "Direct psycopg connection for schema operations during flow orchestration"
  - "Test mocking pattern for database operations in flow tests"

# Metrics
duration: 3min 46sec
completed: 2026-02-03
---

# Phase 29 Plan 02: Symbol Indexing Integration Summary

**Symbol metadata extraction integrated into indexing flow with idempotent schema migration for backward-compatible nullable columns**

## Performance

- **Duration:** 3 min 46 sec
- **Started:** 2026-02-03T10:16:27Z
- **Completed:** 2026-02-03T10:20:14Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Integrated symbol extraction into CocoIndex indexing flow
- Added ensure_symbol_columns() and verify_symbol_columns() to schema_migration.py
- Schema migration runs after flow.setup() but before flow.update()
- Symbol columns (symbol_type, symbol_name, symbol_signature) are nullable TEXT
- Idempotent migration safe to run multiple times
- Added 8 new unit tests for symbol integration
- Updated 6 existing tests to mock database operations
- All 28 flow tests pass

## Key Implementation Details

### Flow Integration

**Symbol extraction transform:**
```python
chunk["symbol_metadata"] = chunk["text"].transform(
    extract_symbol_metadata,
    language=file["extension"],
)
```

**Symbol fields collection:**
```python
code_embeddings.collect(
    # ... existing fields ...
    symbol_type=chunk["symbol_metadata"]["symbol_type"],
    symbol_name=chunk["symbol_metadata"]["symbol_name"],
    symbol_signature=chunk["symbol_metadata"]["symbol_signature"],
)
```

**Schema migration timing:**
```python
# After flow.setup() creates tables
flow.setup()

# Before flow.update() inserts data
with psycopg.connect(db_url) as conn:
    ensure_symbol_columns(conn, table_name)

# Now safe to insert symbol data
update_info = flow.update()
```

### Schema Migration

**ensure_symbol_columns():**
- Checks which columns exist using information_schema
- Adds missing columns as TEXT NULL (no default)
- Idempotent: returns early if all columns exist
- Commits transaction after adding columns
- Returns dict with migration results

**verify_symbol_columns():**
- Checks if all three symbol columns exist
- Returns True only if complete set present
- Used for verification/testing

**Column properties:**
- Type: TEXT (stores function/class/method names and signatures)
- Constraint: NULL (no NOT NULL constraint)
- Default: None (no default value)
- Benefits: Fast ALTER TABLE, backward compatible, no data migration needed

## Testing

**New TestSymbolIntegration class (8 tests):**
- Verify imports of extract_symbol_metadata and ensure_symbol_columns
- Check flow source has symbol extraction transform
- Check flow source collects symbol fields
- Check flow source calls ensure_symbol_columns after setup
- Verify create_code_index_flow succeeds with symbols

**Updated TestRunIndex tests (6 tests):**
- Mock os.getenv for COCOSEARCH_DATABASE_URL
- Mock psycopg.connect to avoid database connection
- Mock ensure_symbol_columns to isolate flow logic
- All tests pass without database dependency

## Deviations from Plan

None - plan executed exactly as written.

## Technical Notes

### CocoIndex Table Naming

CocoIndex uses this naming convention:
```
{flow_name}__{target_name}
```

For our code indexing:
- Flow name: CodeIndex_{index_name} → lowercased to codeindex_{index_name}
- Target name: {index_name}_chunks
- Result: codeindex_{index_name}__{index_name}_chunks

Example: index_name="myproject" → table="codeindex_myproject__myproject_chunks"

### Backward Compatibility

Pre-v1.7 indexes work without re-indexing:
- Symbol columns don't exist on old indexes
- Search queries need to check column existence before querying
- Phase 30 will implement graceful degradation in search

### Migration Safety

The migration is safe to run multiple times:
1. Checks existing columns first
2. Only adds missing columns
3. Fast operation (no table rewrite)
4. No data transformation needed

## Next Phase Readiness

**Ready for Phase 30 (Symbol Search):**
- Symbol columns exist in schema after indexing
- NULL for non-Python files and non-symbol chunks
- Populated for Python functions, classes, and methods
- Indexed data includes symbol_type, symbol_name, symbol_signature

**Search needs:**
- Check column existence before querying symbols
- Handle NULL values gracefully
- Support symbol_type filtering (function, class, method)
- Support symbol_name pattern matching

## Files Changed

**src/cocosearch/indexer/flow.py:**
- Import extract_symbol_metadata and ensure_symbol_columns
- Add symbol metadata extraction transform
- Collect symbol fields in code_embeddings
- Call ensure_symbol_columns after flow.setup()

**src/cocosearch/indexer/schema_migration.py:**
- Add ensure_symbol_columns() function
- Add verify_symbol_columns() function
- Follow pattern from ensure_hybrid_search_schema()

**tests/unit/indexer/test_flow.py:**
- Add TestSymbolIntegration class with 8 tests
- Update TestRunIndex tests to mock database operations
- All 28 tests pass

## Success Criteria

✓ flow.py extracts symbol metadata using extract_symbol_metadata transform
✓ flow.py collects symbol_type, symbol_name, symbol_signature fields
✓ schema_migration.py has ensure_symbol_columns() function
✓ Schema migration is idempotent (can run multiple times safely)
✓ Symbol columns are nullable TEXT (no defaults)
✓ Flow unit tests pass including new symbol tests
