# Adding Language Support

## Chunking Tiers

Every indexed file is chunked by CocoIndex's `SplitRecursively`. The chunking strategy depends on what the `language` parameter resolves to:

| Tier | How it works | Languages |
|------|-------------|-----------|
| **Tree-sitter (CocoIndex built-in)** | `SplitRecursively` uses Tree-sitter internally to split at syntax boundaries (function/class edges) | Python, JS, TS, Go, Rust, Java, C, C++, C#, Ruby, PHP, and ~10 more in CocoIndex's [built-in list](https://cocoindex.io/docs/ops/functions#supported-languages) |
| **Custom handler regex** | `SplitRecursively` receives a `CustomLanguageSpec` with hierarchical regex separators | HCL, Dockerfile, Bash (language handlers) + GitHub Actions, GitLab CI, Docker Compose (grammar handlers) |
| **Plain-text fallback** | Splits on blank lines, newlines, whitespace | Everything not matched by either tier above |

## Systems Overview

CocoSearch has three independent systems for language support:

1. **Language Handlers** (`src/cocosearch/handlers/`) — custom chunking and metadata extraction for languages not in CocoIndex's built-in Tree-sitter list. Matched by file extension.
2. **Grammar Handlers** (`src/cocosearch/handlers/grammars/`) — domain-specific chunking for files that share a base language but have distinct structure (e.g., GitHub Actions is a grammar of YAML). Matched by file path + content patterns.
3. **Symbol Extraction** (`src/cocosearch/indexer/symbols.py`) — tree-sitter query-based extraction of functions, classes, methods, and other symbols for `--symbol-type` / `--symbol-name` filtering.

These systems are independent. A language can have:
- A handler only (e.g., Dockerfile, Bash)
- Symbol extraction only (e.g., Java, C, Ruby)
- Both (e.g., HCL/Terraform)
- A grammar handler (e.g., GitHub Actions, GitLab CI, Docker Compose)

## Checking Tree-sitter's Built-in Language List

Before adding a language, check if `tree-sitter-language-pack` already supports it:

```bash
uv run python -c "from tree_sitter_language_pack import SupportedLanguage; print(sorted(SupportedLanguage.__args__))"
```

This prints all language names accepted by `get_parser()` and `get_language()`. If the language is listed, you can write tree-sitter queries for symbol extraction (Path B). If not, you'll need a handler (Path A) for custom chunking.

You can also verify a specific language works:

```bash
uv run python -c "from tree_sitter_language_pack import get_parser; p = get_parser('hcl'); print(p)"
```

## Checking CocoIndex's Built-in Language List

CocoIndex's `SplitRecursively` has built-in chunking support for ~28 languages (C, C++, C#, CSS, Go, HTML, Java, JavaScript, Python, Rust, TypeScript, etc.). These are listed in the [CocoIndex docs](https://cocoindex.io/docs/ops/functions#supported-languages) and mapped in `LANGUAGE_EXTENSIONS` in `src/cocosearch/search/query.py`.

Languages in this list get language-aware chunking automatically — no handler needed. The `custom_languages` parameter on `SplitRecursively` (see `indexer/flow.py`) extends this with custom handlers (HCL, Dockerfile, Bash). If a language string doesn't match any built-in or custom language, CocoIndex falls back to plain-text splitting.

So to decide which path to take:
- Language in CocoIndex's built-in list → chunking works out of the box, add symbol extraction (Path B) if desired
- Language **not** in CocoIndex's list but in `tree-sitter-language-pack` → add a handler for chunking (Path A) and optionally symbol extraction (Path B)
- Language in neither → add a handler (Path A) only

## Path A: Adding a Language Handler (Chunking + Metadata)

Use this when the language is not in CocoIndex's built-in list and needs custom chunking logic (config formats, DevOps tools, etc.).

### Steps

1. **Copy the template:**
   ```bash
   cp src/cocosearch/handlers/_template.py src/cocosearch/handlers/<language>.py
   ```

2. **Implement the handler class:**
   - Set `EXTENSIONS` to the file extensions (with leading dot)
   - Define `SEPARATOR_SPEC` with `CustomLanguageSpec` — hierarchical regex separators from coarsest to finest
   - Implement `extract_metadata()` returning `block_type`, `hierarchy`, and `language_id`

3. **Important constraints:**
   - Separators must use standard regex only — no lookaheads/lookbehinds (CocoIndex uses Rust regex)
   - The handler is autodiscovered at import time; no registration code needed

4. **Add tests:**
   ```bash
   # Create test file
   touch tests/unit/handlers/test_<language>.py

   # Run tests
   uv run pytest tests/unit/handlers/test_<language>.py -v
   ```

5. **Update `cli.py` `languages_command`** — add a display name to the `display_names` dict in `languages_command` if the default `.title()` casing isn't right (e.g., `"hcl": "HCL"`). Extensions are derived from the handler's `EXTENSIONS` automatically.

### Files to Create/Modify

| File | Action |
|------|--------|
| `src/cocosearch/handlers/<language>.py` | Create — handler class |
| `tests/unit/handlers/test_<language>.py` | Create — handler tests |
| `src/cocosearch/cli.py` | Modify — `display_names` in `languages_command` (only if `.title()` casing is wrong) |

See [handlers/README.md](../src/cocosearch/handlers/README.md) for the full handler protocol, separator design, and testing checklist.

## Path B: Adding Symbol Extraction (Tree-sitter Queries)

Use this for languages already supported by Tree-sitter where you want `--symbol-type` and `--symbol-name` filtering.

### Steps

1. **Create a tree-sitter query file:**
   ```bash
   touch src/cocosearch/indexer/queries/<language>.scm
   ```

   Write S-expression patterns matching the language's AST. Use `@definition.<type>` captures for symbol types and `@name` for symbol names.

   Example (Python):
   ```scheme
   (function_definition name: (identifier) @name) @definition.function
   (class_definition name: (identifier) @name) @definition.class
   ```

2. **Add extension mappings to `LANGUAGE_MAP`** in `src/cocosearch/indexer/symbols.py`:
   ```python
   LANGUAGE_MAP = {
       # ...existing...
       "ext": "language_name",
   }
   ```

3. **Add the language to `SYMBOL_AWARE_LANGUAGES`** in `src/cocosearch/search/query.py`:
   ```python
   SYMBOL_AWARE_LANGUAGES = {"python", "javascript", ..., "new_language"}
   ```

4. **Update `_map_symbol_type`** in `symbols.py` if the language introduces new AST node types that need mapping (e.g., `"block" -> "class"` for HCL).

5. **Update `_build_qualified_name`** in `symbols.py` if the language needs special qualified name logic (e.g., Go receiver methods, HCL block labels).

6. **Add tests:**
   ```bash
   # Add test cases to tests/unit/indexer/test_symbols.py
   uv run pytest tests/unit/indexer/test_symbols.py -v
   ```

### Files to Create/Modify

| File | Action |
|------|--------|
| `src/cocosearch/indexer/queries/<language>.scm` | Create — tree-sitter query |
| `src/cocosearch/indexer/symbols.py` | Modify — `LANGUAGE_MAP`, possibly `_map_symbol_type` and `_build_qualified_name` |
| `src/cocosearch/search/query.py` | Modify — `SYMBOL_AWARE_LANGUAGES` |
| `tests/unit/indexer/test_symbols.py` | Modify — add test cases |

### Query file resolution

Query files are resolved with priority: project-level (`.cocosearch/queries/`) > user-level (`~/.cocosearch/queries/`) > built-in (`src/cocosearch/indexer/queries/`). Users can override built-in queries without modifying the package.

## Path C: Both Handler + Symbol Extraction (HCL Example)

HCL/Terraform is a worked example of a language with both systems.

### Handler (`src/cocosearch/handlers/hcl.py`)

- `EXTENSIONS = [".tf", ".hcl", ".tfvars"]`
- `SEPARATOR_SPEC` with regex separators for HCL blocks
- `extract_metadata()` recognizing 12 block keywords (resource, data, variable, output, locals, module, provider, terraform, import, moved, removed, check)

### Symbol extraction

- Query files: `src/cocosearch/indexer/queries/hcl.scm` and `terraform.scm` (identical AST)
- `LANGUAGE_MAP` entries: `"tf" -> "terraform"`, `"hcl" -> "hcl"`, `"tfvars" -> "hcl"`
- `_map_symbol_type`: `"block" -> "class"` mapping added
- `_build_qualified_name`: HCL-specific logic to build names from block type + labels (e.g., `resource.aws_s3_bucket.data`)

### Registration

- `SYMBOL_AWARE_LANGUAGES` in `search/query.py` includes `"hcl"`
- `cli.py` `languages_command` shows HCL with checkmark and all three extensions

## Path D: Adding a Grammar Handler (Domain-Specific Schema)

Use this when multiple domain syntaxes share the same file extension and you want structured chunking and metadata for a specific schema. For example, GitHub Actions, GitLab CI, and Docker Compose are all YAML files, but each has distinct structure.

**Language vs Grammar:**
- A **language** is matched by file extension (1:1 mapping, e.g., `.tf` -> HCL)
- A **grammar** is matched by file path + content patterns (e.g., `.github/workflows/*.yml` with `on:` + `jobs:` -> GitHub Actions)

Priority: Grammar match > Language match > TextHandler fallback.

### How it works

`extract_language()` in `indexer/embedder.py` checks grammar handlers first. If a grammar matches, it returns the grammar name (e.g., `"github-actions"`) instead of the file extension. This grammar name flows through the pipeline:
- `SplitRecursively` uses the grammar's `CustomLanguageSpec` for chunking
- `extract_chunk_metadata` dispatches to the grammar handler for metadata

### Steps

1. **Copy the template:**
   ```bash
   cp src/cocosearch/handlers/grammars/_template.py src/cocosearch/handlers/grammars/<grammar>.py
   ```

2. **Implement the grammar handler class:**
   - Set `GRAMMAR_NAME` to a unique identifier (lowercase, hyphenated, e.g., `"github-actions"`)
   - Set `BASE_LANGUAGE` to the base language (e.g., `"yaml"`)
   - Set `PATH_PATTERNS` to glob patterns matching the file paths
   - Define `SEPARATOR_SPEC` with `CustomLanguageSpec` (or `None` for default)
   - Implement `matches(filepath, content)` for path + content detection
   - Implement `extract_metadata(text)` returning `block_type`, `hierarchy`, and `language_id`

3. **Important constraints:**
   - Separators must use standard regex only — no lookaheads/lookbehinds (CocoIndex uses Rust regex)
   - The grammar is autodiscovered at import time; no registration code needed
   - `matches()` should check path first, then optionally validate content markers

4. **Add tests:**
   ```bash
   touch tests/unit/handlers/grammars/test_<grammar>.py
   uv run pytest tests/unit/handlers/grammars/test_<grammar>.py -v
   ```

### Files to Create/Modify

| File | Action |
|------|--------|
| `src/cocosearch/handlers/grammars/<grammar>.py` | Create — grammar handler class |
| `tests/unit/handlers/grammars/test_<grammar>.py` | Create — grammar handler tests |

### Existing grammar handlers

| Grammar | Base Language | Path Patterns | Content Markers |
|---------|-------------|---------------|-----------------|
| `github-actions` | yaml | `.github/workflows/*.yml` | `on:` + `jobs:` |
| `gitlab-ci` | yaml | `.gitlab-ci.yml` | `stages:` or (`script:` + `image:`/`stage:`) |
| `docker-compose` | yaml | `docker-compose*.yml`, `compose*.yml` | `services:` |

## Registration Checklist

When adding a new language handler, verify all registrations are complete:

- [ ] **Handler** (if applicable): `handlers/<language>.py` created, extensions registered via autodiscovery
- [ ] **LANGUAGE_MAP** (if symbol extraction): all file extensions mapped to tree-sitter language name
- [ ] **Query file** (if symbol extraction): `indexer/queries/<language>.scm` created
- [ ] **SYMBOL_AWARE_LANGUAGES**: language added to set in `search/query.py`
- [ ] **_map_symbol_type**: any new AST node types mapped to standard types
- [ ] **_build_qualified_name**: special qualified name logic added if needed
- [ ] **cli.py languages_command**: display name override added if needed (extensions are derived from handler)
- [ ] **Tests**: handler tests and/or symbol extraction tests added
- [ ] **README.md**: Supported Languages section updated (count, table, lists)

When adding a new grammar handler:

- [ ] **Grammar handler**: `handlers/grammars/<grammar>.py` created with `GRAMMAR_NAME`, `BASE_LANGUAGE`, `PATH_PATTERNS`, `matches()`, `extract_metadata()`
- [ ] **Tests**: `tests/unit/handlers/grammars/test_<grammar>.py` created
- [ ] **README.md**: Supported Grammars section updated

## Reference

- [handlers/README.md](../src/cocosearch/handlers/README.md) — handler protocol, separator design, testing
- [handlers/grammars/_template.py](../src/cocosearch/handlers/grammars/_template.py) — grammar handler template
- [CLAUDE.md](../CLAUDE.md) — quick handler steps, architecture overview
