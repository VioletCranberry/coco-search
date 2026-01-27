# Phase 3: Flow Integration and Schema - Research

**Researched:** 2026-01-27
**Domain:** CocoIndex flow pipeline integration, PostgreSQL schema management
**Confidence:** HIGH

## Summary

This phase wires the metadata extraction function (`extract_devops_metadata` from Phase 2) into the existing CocoIndex indexing pipeline in `flow.py`, and extends the PostgreSQL schema with three new TEXT columns (`block_type`, `hierarchy`, `language_id`). Only `flow.py` is modified.

Research confirmed all three flagged questions with HIGH confidence:

1. **Schema migration behavior:** CocoIndex performs non-destructive `ALTER TABLE` on PostgreSQL when new columns are added and primary keys remain unchanged. Since our primary keys (`filename`, `location`) do not change, adding three new collected fields will trigger an `ALTER TABLE ADD COLUMN` -- no table drop/recreate needed. The CONTEXT.md decision that "table drop/recreate is acceptable" is a safe fallback, but in practice CocoIndex will take the non-destructive path.

2. **`@cocoindex.op.function()` dataclass-to-column mapping:** A function returning a `@dataclasses.dataclass` produces a Struct-typed DataSlice. Each dataclass field becomes an individually accessible sub-field via bracket notation (`chunk["metadata"]["block_type"]`). These sub-fields can be passed directly to `collector.collect()` as individual fields -- exactly the pattern needed.

3. **`collector.collect()` with struct field access:** The collect call accepts any DataSlice as a field value. Sub-fields of a Struct are accessed via `data_slice["field_name"]`, yielding a new DataSlice that can be passed to collect. The pattern `code_embeddings.collect(..., block_type=chunk["metadata"]["block_type"])` is standard CocoIndex usage, verified across multiple official examples.

**Primary recommendation:** The changes to `flow.py` are minimal and well-supported by CocoIndex's standard patterns. Add one import, one transform call, and three new fields to the existing collect call. No architectural risk.

## Standard Stack

### Core (no changes -- existing stack)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `cocoindex` | >=0.3.28 | Flow pipeline framework | Already in use; supports custom functions, struct returns, collectors |

### Supporting (already implemented in Phases 1-2)
| Module | Purpose | Used How |
|--------|---------|----------|
| `metadata.py` | `extract_devops_metadata` op function | Transform call in chunk processing loop |
| `languages.py` | `DEVOPS_CUSTOM_LANGUAGES` | Already passed to `SplitRecursively` (wired in Phase 1) |
| `embedder.py` | `extract_language`, `code_to_embedding` | Already used in flow (wired in Phase 1) |

### No New Dependencies
This phase adds zero new imports to the project. The only change is a new import line within `flow.py` itself.

## Architecture Patterns

### Current Flow Pipeline Structure (flow.py)

```
Source: LocalFile(codebase_path)
  |
  v
For each file:
  1. file["extension"] = file["filename"].transform(extract_language)
  2. file["chunks"] = file["content"].transform(SplitRecursively(custom_languages=DEVOPS_CUSTOM_LANGUAGES), language=file["extension"], ...)
  |
  For each chunk:
    3. chunk["embedding"] = chunk["text"].call(code_to_embedding)
    4. code_embeddings.collect(filename, location, embedding)
  |
  v
Export: code_embeddings.export("_chunks", Postgres(), primary_key_fields=["filename", "location"])
```

### Target Flow Pipeline Structure (after this phase)

```
Source: LocalFile(codebase_path)
  |
  v
For each file:
  1. file["extension"] = file["filename"].transform(extract_language)     [UNCHANGED]
  2. file["chunks"] = file["content"].transform(SplitRecursively(...))    [UNCHANGED]
  |
  For each chunk:
    3. chunk["embedding"] = chunk["text"].call(code_to_embedding)          [UNCHANGED]
    4. chunk["metadata"] = chunk["text"].transform(                        [NEW]
           extract_devops_metadata, language=file["extension"])
    5. code_embeddings.collect(                                            [MODIFIED]
           filename, location, embedding,
           block_type=chunk["metadata"]["block_type"],                     [NEW FIELD]
           hierarchy=chunk["metadata"]["hierarchy"],                       [NEW FIELD]
           language_id=chunk["metadata"]["language_id"],                   [NEW FIELD]
       )
  |
  v
Export: code_embeddings.export(...)                                        [UNCHANGED]
```

### Pattern 1: Multi-argument transform with @cocoindex.op.function()

**What:** The first argument of the decorated function receives the DataSlice being transformed. Additional arguments are passed as positional or keyword arguments in the `transform()` call.

**When to use:** When a transform needs context beyond the data slice itself (e.g., language identifier for routing).

**Example:**
```python
# Source: https://cocoindex.io/docs/core/flow_def
# Function signature:
@cocoindex.op.function()
def extract_devops_metadata(text: str, language: str) -> DevOpsMetadata:
    ...

# Flow usage -- text is the first arg (the DataSlice), language is a kwarg:
chunk["metadata"] = chunk["text"].transform(
    extract_devops_metadata,
    language=file["extension"],
)
```

**Key detail:** `file["extension"]` is a DataSlice (produced by `extract_language` transform), not a Python string. CocoIndex resolves DataSlice values at execution time. Passing a DataSlice as a keyword argument to `transform()` is the standard pattern -- verified in the `SplitRecursively` call which already passes `language=file["extension"]` on line 69 of the current `flow.py`.

### Pattern 2: Struct Sub-field Access via Bracket Notation

**What:** When a transform returns a Struct type (dataclass), sub-fields are accessed with `data_slice["field_name"]`, which returns a new DataSlice for that sub-field.

**When to use:** When collecting individual fields from a struct return type into separate collector columns.

**Example:**
```python
# Source: https://cocoindex.io/examples/academic_papers_index
# After transform returns a dataclass:
doc["metadata"] = doc["first_page_md"].transform(extract_metadata_fn)

# Access sub-fields:
paper_metadata.collect(
    title=doc["metadata"]["title"],
    authors=doc["metadata"]["authors"],
    abstract=doc["metadata"]["abstract"],
)
```

This is exactly the pattern we use. `chunk["metadata"]` is a Struct-typed DataSlice with sub-fields `block_type`, `hierarchy`, and `language_id`. Each is accessed with bracket notation and passed to `collect()`.

### Pattern 3: DataSlice Cross-Scope Access in Nested Loops

**What:** A DataSlice from an outer scope (e.g., `file["extension"]`) can be referenced inside an inner scope (e.g., within the `with file["chunks"].row() as chunk:` block).

**When to use:** When inner-loop transforms need context from the parent (e.g., passing language to metadata extraction within the chunk loop).

**Example (already in flow.py):**
```python
with data_scope["files"].row() as file:
    file["extension"] = file["filename"].transform(extract_language)
    file["chunks"] = file["content"].transform(
        cocoindex.functions.SplitRecursively(custom_languages=DEVOPS_CUSTOM_LANGUAGES),
        language=file["extension"],  # <-- outer scope DataSlice used in transform
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    with file["chunks"].row() as chunk:
        # file["extension"] is also accessible here
        chunk["metadata"] = chunk["text"].transform(
            extract_devops_metadata,
            language=file["extension"],  # <-- same pattern, outer scope reference
        )
```

**Confidence: HIGH** -- This exact pattern (outer scope DataSlice in inner loop) is already used in our flow.py for the `SplitRecursively` call.

### Anti-Patterns to Avoid

- **Passing Python strings instead of DataSlices:** Do NOT do `language="py"`. Always pass the DataSlice: `language=file["extension"]`. CocoIndex resolves values at execution time, not definition time.
- **Conditional branching in flows:** CocoIndex flow definitions are declarative graph builders, not imperative code. There is no `if` statement for "run metadata extraction only for DevOps files". The function runs for ALL chunks and returns empty strings for non-DevOps files.
- **Collecting a whole Struct:** The CONTEXT.md decision says "three individual collector fields, not a nested struct". Do NOT do `metadata=chunk["metadata"]`. Instead, spread the sub-fields individually.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema migration | Manual ALTER TABLE statements | CocoIndex `flow.setup()` | Automatically infers schema from flow definition, adds columns non-destructively on PostgreSQL |
| Language routing to metadata | Custom conditional logic in flow | `file["extension"]` DataSlice + `language` kwarg | Already computed by `extract_language`; pass as DataSlice to `transform()` |
| Column type specification | Explicit PostgreSQL type annotations | CocoIndex type inference from dataclass fields | `str` fields in DevOpsMetadata automatically become TEXT columns |
| Struct-to-individual-fields mapping | Manual extraction/conversion code | Bracket notation `chunk["metadata"]["field"]` | Standard CocoIndex struct sub-field access |

**Key insight:** Every building block for this phase already exists. The metadata extraction function, the language routing, the custom languages, and the collector pattern are all in place. This phase is pure wiring -- connecting existing pieces with standard CocoIndex patterns.

## Common Pitfalls

### Pitfall 1: Wrong argument name in transform() call
**What goes wrong:** Using `filename=file["filename"]` instead of `language=file["extension"]` as the second argument to `extract_devops_metadata`.
**Why it happens:** The earlier ARCHITECTURE.md research document incorrectly showed `filename=file["filename"]` as the kwarg. The actual function signature is `extract_devops_metadata(text: str, language: str)`.
**How to avoid:** Match the kwarg name exactly to the function parameter name: `language=file["extension"]`.
**Warning signs:** Runtime error about unexpected keyword argument, or `language` always being the filename string.

### Pitfall 2: Struct collected as a single nested column
**What goes wrong:** Passing `metadata=chunk["metadata"]` to `collect()` creates a single nested Struct column in PostgreSQL instead of three individual TEXT columns.
**Why it happens:** CocoIndex will happily collect a Struct as a single field. The schema would have a composite type column instead of three flat TEXT columns.
**How to avoid:** Always access sub-fields individually: `block_type=chunk["metadata"]["block_type"]`, etc.
**Warning signs:** PostgreSQL table has one column named `metadata` of composite type instead of three TEXT columns.

### Pitfall 3: Missing import of extract_devops_metadata
**What goes wrong:** `NameError: name 'extract_devops_metadata' is not defined` at flow definition time.
**Why it happens:** Forgetting to add the import to the top of flow.py.
**How to avoid:** Add `from cocosearch.indexer.metadata import extract_devops_metadata` to flow.py imports.
**Warning signs:** Import error when `create_code_index_flow` is called.

### Pitfall 4: Ordering metadata extraction after collect
**What goes wrong:** The metadata transform must happen BEFORE the collect call. If placed after, the DataSlice `chunk["metadata"]` doesn't exist yet when collect tries to reference it.
**Why it happens:** CocoIndex flow definitions build a computation graph. References must be defined before use.
**How to avoid:** Place the transform call between the embedding and the collect call.
**Warning signs:** Runtime error about undefined field or DataSlice.

### Pitfall 5: Schema migration destroys existing indexes
**What goes wrong:** (RESOLVED) Adding columns could theoretically cause a table drop/recreate, destroying embeddings.
**Why it happens:** Would happen if primary keys changed or CocoIndex chose destructive path.
**How to avoid:** Primary keys remain `["filename", "location"]` -- unchanged. CocoIndex uses non-destructive `ALTER TABLE` on PostgreSQL for new columns. Per CONTEXT.md, re-index is required anyway, so even if drop/recreate occurred, it would be acceptable.
**Warning signs:** N/A -- this is a resolved concern. Verified that CocoIndex takes non-destructive path when primary keys are stable.

## Code Examples

### The Complete Modified flow.py (Minimal Changes)

Three changes needed, annotated with `# NEW` and `# MODIFIED`:

```python
# Source: Current flow.py + CocoIndex patterns from official docs
"""CocoIndex flow definition for code indexing."""

import cocoindex

from cocosearch.indexer.config import IndexingConfig
from cocosearch.indexer.embedder import code_to_embedding, extract_extension, extract_language
from cocosearch.indexer.languages import DEVOPS_CUSTOM_LANGUAGES
from cocosearch.indexer.metadata import extract_devops_metadata  # NEW (Change 1)
from cocosearch.indexer.file_filter import build_exclude_patterns


def create_code_index_flow(
    index_name: str,
    codebase_path: str,
    include_patterns: list[str],
    exclude_patterns: list[str],
    chunk_size: int = 1000,
    chunk_overlap: int = 300,
) -> cocoindex.Flow:
    """Create a CocoIndex flow for indexing a codebase."""

    @cocoindex.flow_def(name=f"CodeIndex_{index_name}")
    def code_index_flow(
        flow_builder: cocoindex.FlowBuilder,
        data_scope: cocoindex.DataScope,
    ) -> None:
        data_scope["files"] = flow_builder.add_source(
            cocoindex.sources.LocalFile(
                path=codebase_path,
                included_patterns=include_patterns,
                excluded_patterns=exclude_patterns,
                binary=False,
            )
        )

        code_embeddings = data_scope.add_collector()

        with data_scope["files"].row() as file:
            file["extension"] = file["filename"].transform(extract_language)

            file["chunks"] = file["content"].transform(
                cocoindex.functions.SplitRecursively(
                    custom_languages=DEVOPS_CUSTOM_LANGUAGES,
                ),
                language=file["extension"],
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

            with file["chunks"].row() as chunk:
                chunk["embedding"] = chunk["text"].call(code_to_embedding)

                # Extract DevOps metadata for each chunk (Change 2 - NEW)
                chunk["metadata"] = chunk["text"].transform(
                    extract_devops_metadata,
                    language=file["extension"],
                )

                # Collect with metadata (Change 3 - MODIFIED: added 3 new fields)
                code_embeddings.collect(
                    filename=file["filename"],
                    location=chunk["location"],
                    embedding=chunk["embedding"],
                    block_type=chunk["metadata"]["block_type"],
                    hierarchy=chunk["metadata"]["hierarchy"],
                    language_id=chunk["metadata"]["language_id"],
                )

        code_embeddings.export(
            f"{index_name}_chunks",
            cocoindex.storages.Postgres(),
            primary_key_fields=["filename", "location"],
            vector_indexes=[
                cocoindex.VectorIndexDef(
                    field_name="embedding",
                    metric=cocoindex.VectorSimilarityMetric.COSINE_SIMILARITY,
                )
            ],
        )

    return code_index_flow
```

### How language_id Flows Through the Pipeline

```
filename (e.g., "main.tf", "Dockerfile", "deploy.sh")
  |
  v  extract_language(filename)  [already in flow, line 62]
  |
  = file["extension"]  (e.g., "tf", "dockerfile", "sh")
  |
  v  Passed to SplitRecursively as language= kwarg  [already in flow, line 69]
  |  AND
  v  Passed to extract_devops_metadata as language= kwarg  [NEW]
  |
  = chunk["metadata"]  (DevOpsMetadata dataclass)
  |
  v  chunk["metadata"]["language_id"]  (e.g., "hcl", "dockerfile", "bash", "")
```

**Key insight:** `file["extension"]` already contains the language identifier produced by `extract_language()`. It is NOT a file extension -- it was renamed in Phase 1 but kept the field name "extension" for backward compatibility. This same DataSlice is passed to both `SplitRecursively` and `extract_devops_metadata`. No re-derivation needed.

### PostgreSQL Schema Before and After

**Before (v1.1):**
```sql
-- Table: codeindex_{name}__{name}_chunks
CREATE TABLE ... (
    filename TEXT,          -- Primary key part 1
    location INT4RANGE,     -- Primary key part 2 (byte range)
    embedding VECTOR(768),  -- Ollama nomic-embed-text
    PRIMARY KEY (filename, location)
);
```

**After (v1.2) -- three new TEXT columns added via ALTER TABLE:**
```sql
CREATE TABLE ... (
    filename TEXT,          -- Primary key part 1 (UNCHANGED)
    location INT4RANGE,     -- Primary key part 2 (UNCHANGED)
    embedding VECTOR(768),  -- Ollama nomic-embed-text (UNCHANGED)
    block_type TEXT,        -- NEW: e.g., "resource", "FROM", "function", ""
    hierarchy TEXT,         -- NEW: e.g., "resource.aws_s3_bucket.main", ""
    language_id TEXT,       -- NEW: e.g., "hcl", "dockerfile", "bash", ""
    PRIMARY KEY (filename, location)
);
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `extract_extension` for language routing | `extract_language` for language routing | Phase 1 (this project) | Handles extensionless files like Dockerfile |
| No custom languages in SplitRecursively | `DEVOPS_CUSTOM_LANGUAGES` passed to constructor | Phase 1 (this project) | DevOps files get structural chunking |
| No metadata extraction | `extract_devops_metadata` op function | Phase 2 (this project) | Chunks get block_type, hierarchy, language_id |
| 3 columns in chunks table | 6 columns in chunks table | Phase 3 (this phase) | Metadata stored in PostgreSQL |

## Open Questions

### Resolved (no remaining open questions)

All three research flags from the roadmap have been answered with HIGH confidence:

1. **Schema migration behavior:** Non-destructive ALTER TABLE for PostgreSQL when primary keys unchanged. RESOLVED.
2. **Dataclass-to-column mapping:** Bracket notation on Struct DataSlice extracts sub-fields. RESOLVED.
3. **collector.collect() with struct fields:** Pass sub-field DataSlices as named kwargs. RESOLVED.

### Discretion Decisions (for planner to codify)

1. **How language_id reaches metadata function:** Use `file["extension"]` (the DataSlice from `extract_language`). No re-derivation. Pass as `language=file["extension"]` kwarg to `transform()`. This is the simplest approach -- it reuses an existing DataSlice and follows the same pattern already used by `SplitRecursively`.

2. **Whether extraction runs conditionally:** Run for ALL chunks unconditionally. The function returns empty strings for non-DevOps files. This avoids conditional branching (which CocoIndex flow definitions do not support) and keeps the schema consistent.

## Sources

### Primary (HIGH confidence)
- [CocoIndex Custom Functions](https://cocoindex.io/docs/custom_ops/custom_functions) -- `@cocoindex.op.function()` decorator, type annotations, return types
- [CocoIndex Data Types](https://cocoindex.io/docs/core/data_types) -- Struct type represented by dataclass, sub-field access
- [CocoIndex Flow Definition](https://cocoindex.io/docs/core/flow_def) -- `transform()` multi-arg pattern, `collector.collect()` API, DataSlice sub-field access
- [CocoIndex Flow Methods](https://cocoindex.io/docs/core/flow_methods) -- `flow.setup()` schema management, non-destructive ALTER TABLE
- [CocoIndex Functions (SplitRecursively)](https://cocoindex.io/docs/ops/functions) -- `custom_languages` parameter, `language` kwarg, chunk structure
- [CocoIndex Academic Papers Example](https://cocoindex.io/examples/academic_papers_index) -- Complete example of dataclass return -> struct sub-field access -> collect individual fields
- [CocoIndex Code Index Example](https://cocoindex.io/docs/examples/code_index) -- Baseline flow pattern with collect and export
- [CocoIndex Schema Inference for Qdrant](https://cocoindex.io/blogs/schema-inference-for-qdrant) -- Non-destructive vs destructive schema update conditions

### Local (HIGH confidence -- direct code inspection)
- `/Users/fzhdanov/GIT/personal/coco-s/src/cocosearch/indexer/flow.py` -- Current pipeline structure (156 lines)
- `/Users/fzhdanov/GIT/personal/coco-s/src/cocosearch/indexer/metadata.py` -- `extract_devops_metadata(text: str, language: str) -> DevOpsMetadata` (253 lines)
- `/Users/fzhdanov/GIT/personal/coco-s/src/cocosearch/indexer/languages.py` -- `DEVOPS_CUSTOM_LANGUAGES` list (72 lines)
- `/Users/fzhdanov/GIT/personal/coco-s/src/cocosearch/indexer/embedder.py` -- `extract_language(filename: str) -> str` (76 lines)
- `/Users/fzhdanov/GIT/personal/coco-s/src/cocosearch/indexer/__init__.py` -- `extract_devops_metadata` already exported
- `/Users/fzhdanov/GIT/personal/coco-s/tests/indexer/test_flow.py` -- Existing test patterns (233 lines)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new libraries, all existing
- Architecture: HIGH - All patterns verified against official CocoIndex docs and examples; the exact patterns (struct sub-field access in collect, multi-arg transform, outer-scope DataSlice in inner loop) are demonstrated in official examples
- Pitfalls: HIGH - Primary pitfalls identified from code inspection and ARCHITECTURE.md analysis; schema migration concern resolved with documentation evidence
- Code examples: HIGH - The complete modified flow.py is derivable from current code + standard patterns; only 3 localized changes needed

**Research date:** 2026-01-27
**Valid until:** 2026-02-27 (stable -- no API changes expected; CocoIndex patterns are well-established)

**Diff summary for planner:**
- Lines added: ~1 import + ~5 lines (transform + 3 collect fields)
- Lines modified: 0 (the collect call gains 3 new kwargs but no lines are deleted)
- Lines deleted: 0
- Risk: Minimal -- declarative wiring of existing components
