---
name: cocosearch-add-language
description: Use when adding support for a new programming language, config format, or grammar to CocoSearch. Guides through all paths (handler, symbol extraction, grammar, context expansion) with registration checklists.
---

# Add Language Support with CocoSearch

A structured workflow for adding language support to CocoSearch. Navigates up to 5 independent paths (handler, symbol extraction, grammar, context expansion, documentation) and ensures every registration point is covered.

**Philosophy:** The most common failure when adding language support is missing a registration step. This skill makes that impossible by tracking every step explicitly.

**Reference:** `docs/adding-languages.md` is the authoritative technical guide. This skill wraps it in an interactive workflow.

## Pre-flight Check

1. Read `cocosearch.yaml` for `indexName` (critical -- use this for all operations)
2. `list_indexes()` to confirm project is indexed
3. `index_stats(index_name="<configured-name>")` to check freshness
- No index -> offer to index before proceeding
- Stale (>7 days) -> warn: "Index is X days old -- I may miss recent patterns. Want me to reindex first?"

## Step 1: Identify the Language

Parse the user's request to determine what's being added.

**Extract from the request:**

- **Language name:** The language or format (e.g., "Kotlin", "Ansible", "Makefile")
- **File extensions:** What extensions it uses (e.g., `.kt`, `.kts`)
- **Desired capabilities:** Which paths the user wants (chunking, symbol filtering, context expansion, or all)

**Confirm with user:** "I'll add support for [language] with extensions [list]. Let me determine which paths apply."

## Step 2: Determine Applicable Paths

Check two things to decide which of the 5 paths (A-E) apply:

### 2a. Check CocoIndex's Built-in Language List

CocoIndex's `SplitRecursively` has built-in Tree-sitter chunking for ~28 languages. Search for the language mapping:

```
search_code(
    query="LANGUAGE_EXTENSIONS supported languages",
    use_hybrid_search=True,
    smart_context=True
)
```

Also check the CocoIndex docs: if the language is in the built-in list, chunking works automatically -- no handler (Path A) needed.

### 2b. Check tree-sitter-language-pack Support

If the user wants symbol extraction (Path B) or context expansion (Path E), the language must be in `tree-sitter-language-pack`:

```bash
uv run python -c "from tree_sitter_language_pack import SupportedLanguage; print(sorted(SupportedLanguage.__args__))"
```

Verify a specific language:

```bash
uv run python -c "from tree_sitter_language_pack import get_parser; p = get_parser('<language>'); print(p)"
```

### 2c. Decision Matrix

Present the applicable paths:

| Path | When to Use | Applies? |
|------|------------|----------|
| **A: Language Handler** | Language NOT in CocoIndex's built-in list -- needs custom chunking | ? |
| **B: Symbol Extraction** | Language IS in `tree-sitter-language-pack` -- enables `--symbol-type`/`--symbol-name` filtering | ? |
| **C: Both A + B** | Not built-in for chunking but has tree-sitter support | ? |
| **D: Grammar Handler** | Domain-specific schema sharing a base language (e.g., Ansible = YAML) | ? |
| **E: Context Expansion** | Language IS in `tree-sitter-language-pack` -- enables `smart_context=True` boundary expansion | ? |

**Present to user:** "Based on my checks, here are the paths that apply: [list]. Ready to proceed?"

## Step 3: Language Handler (Path A)

> **Skip this step** if the language is in CocoIndex's built-in list (no custom chunking needed).

### 3a. Find the Best Analog Handler

Choose the closest existing handler based on language type:

| Language Type | Analog Handler | Why |
|--------------|---------------|-----|
| Config format (key-value, blocks) | `hcl.py` | Block-based structure with labels |
| Template language | `gotmpl.py` | Template directives + content |
| Script / shell language | `bash.py` | Function definitions + commands |
| Containerization / CI | `dockerfile.py` | Directive-based, sequential |
| JVM / compiled language | `scala.py` or `groovy.py` | OOP with classes, methods, imports |

Search for the analog:

```
search_code(
    query="<analog-language> handler EXTENSIONS SEPARATOR_SPEC",
    symbol_type="class",
    use_hybrid_search=True,
    smart_context=True
)
```

Read the analog handler fully before proceeding.

### 3b. Create the Handler File

Copy from the template and implement:

1. **Create** `src/cocosearch/handlers/<language>.py` (copy `_template.py`)
2. **Set** `EXTENSIONS` to all file extensions (with leading dot)
3. **Define** `SEPARATOR_SPEC` with `CustomLanguageSpec` -- hierarchical regex separators from coarsest to finest
4. **Implement** `extract_metadata()` returning `block_type`, `hierarchy`, and `language_id`
5. **Constraint:** Separators must use standard regex only -- no lookaheads/lookbehinds (CocoIndex uses Rust regex)

The handler is autodiscovered at import time; no registration code needed.

### 3c. Register File Extensions

Add the new extensions to `include_patterns` so CocoIndex picks up the files:

```
search_code(
    query="include_patterns file extensions indexing config",
    use_hybrid_search=True,
    smart_context=True
)
```

Modify `src/cocosearch/indexer/config.py` -- add glob patterns for the new extensions (e.g., `"**/*.kt"`).

### 3d. Update CLI Display Name

Check if the language name needs a display override in `cli.py`:

```
search_code(
    query="display_names languages_command",
    symbol_name="languages_command",
    use_hybrid_search=True,
    smart_context=True
)
```

Add to the `display_names` dict only if `.title()` casing is wrong (e.g., `"hcl": "HCL"`, `"gotmpl": "Go Template"`).

### 3e. Create Handler Tests

Find the analog's test file for the pattern:

```
search_code(
    query="test <analog-language> handler EXTENSIONS SEPARATOR_SPEC",
    symbol_type="class",
    use_hybrid_search=True,
    smart_context=True
)
```

Create `tests/unit/handlers/test_<language>.py` covering:
- Extension registration
- Separator spec structure
- Metadata extraction (block type, hierarchy, language ID)
- Edge cases (empty content, malformed input)

**Checkpoint with user:** "Handler created at `src/cocosearch/handlers/<language>.py` with [N] extensions and [N] separator levels. Tests pass. Ready for the next path?"

## Step 4: Symbol Extraction (Path B)

> **Skip this step** if the language is NOT in `tree-sitter-language-pack`.

### 4a. Find the Best Analog Query

Choose based on language similarity:

| Language Type | Analog Query | Why |
|--------------|-------------|-----|
| Python-like (indent-based) | `python.scm` | function/class definitions |
| C-like (braces) | `go.scm` or `java.scm` | declaration patterns |
| Config (blocks with labels) | `hcl.scm` | block-based structures |
| Functional | `rust.scm` | items, traits, impls |

Search for the analog:

```
search_code(
    query="<analog-language> tree-sitter query definition function class",
    use_hybrid_search=True,
    smart_context=True
)
```

Read the analog `.scm` file to understand the capture patterns.

### 4b. Explore the AST

Before writing the query, explore the language's tree-sitter AST to find the correct node types:

```bash
uv run python -c "
from tree_sitter_language_pack import get_parser
parser = get_parser('<language>')
tree = parser.parse(b'''<sample-code>''')
def show(node, indent=0):
    print(' ' * indent + f'{node.type} [{node.start_point[0]}:{node.start_point[1]}-{node.end_point[0]}:{node.end_point[1]}]')
    for child in node.children:
        show(child, indent + 2)
show(tree.root_node)
"
```

Identify the node types for functions, classes, methods, interfaces, etc.

### 4c. Create the Query File

Create `src/cocosearch/indexer/queries/<language>.scm` with S-expression patterns:

- Use `@definition.<type>` captures for symbol types (function, class, method, interface)
- Use `@name` for symbol name captures
- Match patterns from the analog query file

### 4d. Register in LANGUAGE_MAP

Add extension-to-language mappings:

```
search_code(
    query="LANGUAGE_MAP extension mapping",
    symbol_name="LANGUAGE_MAP",
    use_hybrid_search=True,
    smart_context=True
)
```

Add entries to `LANGUAGE_MAP` in `src/cocosearch/indexer/symbols.py`:
```python
"ext": "language_name",
```

### 4e. Register in SYMBOL_AWARE_LANGUAGES

Add the language to the symbol-aware set:

```
search_code(
    query="SYMBOL_AWARE_LANGUAGES",
    use_hybrid_search=True,
    smart_context=True
)
```

Add the language name to `SYMBOL_AWARE_LANGUAGES` in `src/cocosearch/search/query.py`.

### 4f. Update Symbol Type Mapping (If Needed)

Check if the language introduces new AST node types that need mapping to standard types:

```
search_code(
    query="_map_symbol_type node type mapping",
    symbol_name="_map_symbol_type",
    use_hybrid_search=True,
    smart_context=True
)
```

Add mappings in `_map_symbol_type` if the language uses non-standard node names for standard concepts (e.g., HCL uses `"block"` for what maps to `"class"`).

### 4g. Update Qualified Name Builder (If Needed)

Check if the language needs special qualified name logic:

```
search_code(
    query="_build_qualified_name qualified name",
    symbol_name="_build_qualified_name",
    use_hybrid_search=True,
    smart_context=True
)
```

Add language-specific logic to `_build_qualified_name` in `symbols.py` if the language has special naming patterns (e.g., Go receiver methods, HCL block labels).

### 4h. Create Symbol Extraction Tests

Find the analog's test file:

```
search_code(
    query="test <analog-language> symbol extraction",
    symbol_type="class",
    use_hybrid_search=True,
    smart_context=True
)
```

Create `tests/unit/indexer/symbols/test_<language>.py` covering:
- Function definitions (name, type, qualified name)
- Class/struct definitions
- Method definitions (including qualified names)
- Edge cases (nested definitions, anonymous functions, generics)

**Checkpoint with user:** "Symbol extraction configured for [language] with [N] query patterns. Tests pass. Ready for the next path?"

## Step 5: Grammar Handler (Path D)

> **Skip this step** unless the language is a domain-specific schema sharing a base language extension.

### 5a. Find the Best Analog Grammar

| Grammar Type | Analog | Why |
|-------------|--------|-----|
| CI/CD pipeline (YAML) | `github_actions.py` or `gitlab_ci.py` | Jobs/stages/steps structure |
| Container orchestration (YAML) | `docker_compose.py` or `kubernetes.py` | Services/resources structure |
| Template (YAML) | `helm_template.py` or `helm_values.py` | Template directives + values |

Search for the analog:

```
search_code(
    query="<analog-grammar> grammar handler GRAMMAR_NAME matches",
    symbol_type="class",
    use_hybrid_search=True,
    smart_context=True
)
```

### 5b. Create the Grammar Handler File

1. **Create** `src/cocosearch/handlers/grammars/<grammar>.py` (copy `_template.py`)
2. **Set** `GRAMMAR_NAME` -- unique lowercase hyphenated identifier
3. **Set** `BASE_LANGUAGE` -- the base language (e.g., `"yaml"`)
4. **Set** `PATH_PATTERNS` -- glob patterns matching file paths
5. **Implement** `matches(filepath, content)` -- path + content detection
6. **Define** `SEPARATOR_SPEC` with `CustomLanguageSpec` (or `None` for base language defaults)
7. **Implement** `extract_metadata(text)` returning `block_type`, `hierarchy`, and `language_id`

The grammar is autodiscovered at import time; no registration code needed.

### 5c. Create Grammar Tests

Create `tests/unit/handlers/grammars/test_<grammar>.py` covering:
- Grammar properties (name, base language, path patterns)
- Separator spec
- Path matching (positive and negative cases)
- Content matching (positive and negative cases)
- Metadata extraction
- Edge cases (no content provided, wrong path, wrong content markers)

**Checkpoint with user:** "Grammar handler created for [grammar]. Tests pass. Ready for documentation updates?"

## Step 6: Context Expansion (Path E)

> **Skip this step** unless the language is in `tree-sitter-language-pack` AND context expansion is desired.

### 6a. Identify Definition Node Types

Explore the AST (same technique as Step 4b) to find which node types represent function/class definitions.

### 6b. Add to DEFINITION_NODE_TYPES

```
search_code(
    query="DEFINITION_NODE_TYPES context expansion node types",
    use_hybrid_search=True,
    smart_context=True
)
```

Add the language entry to `DEFINITION_NODE_TYPES` in `src/cocosearch/search/context_expander.py`:

```python
"<language>": {"<function_node_type>", "<class_node_type>"},
```

### 6c. Add to EXTENSION_TO_LANGUAGE

Add file extension mappings to `EXTENSION_TO_LANGUAGE` in the same file:

```python
".<ext>": "<language>",
```

`CONTEXT_EXPANSION_LANGUAGES` updates automatically -- it's derived from `DEFINITION_NODE_TYPES.keys()`.

### 6d. Update Documentation

The `CONTEXT_EXPANSION_LANGUAGES` set is exported and referenced in search docs. Update any docs listing supported context expansion languages.

**Checkpoint with user:** "Context expansion added for [language]. `smart_context=True` will now expand to [node types] boundaries."

## Step 7: Update Count Assertions

> **This is the most commonly missed step.** Do not skip.

### 7a. Handler Count (If Path A was done)

```
search_code(
    query="test registry handler count _HANDLER_REGISTRY",
    use_hybrid_search=True,
    smart_context=True
)
```

Update in `tests/unit/handlers/test_registry.py`:
- `len(_HANDLER_REGISTRY) >= N` -- increment by number of new extensions
- `len(specs) == N` -- increment by 1 (one `CustomLanguageSpec` per handler)

### 7b. Grammar Count (If Path D was done)

```
search_code(
    query="test grammar registry count _GRAMMAR_REGISTRY",
    use_hybrid_search=True,
    smart_context=True
)
```

Update in `tests/unit/handlers/test_grammar_registry.py`:
- `len(_GRAMMAR_REGISTRY) == N` -- increment by 1
- `len(grammars) == N` -- increment by 1

### 7c. Combined Spec Count (If Path A or D was done)

Both `test_registry.py` and `test_grammar_registry.py` assert `len(specs) == N` from `get_all_custom_language_specs()`. This is the combined total of all language handler specs + grammar handler specs. Increment by 1 for each new handler or grammar added.

## Step 8: Update Documentation

### 8a. CLAUDE.md

Update module descriptions and counts:
- Handler count in Architecture section (e.g., "Total custom language specs: N")
- Context expansion language list in the `search/` module description
- Any handler/grammar counts mentioned

### 8b. README.md

```
search_code(
    query="Supported Languages README badges",
    use_hybrid_search=True,
    smart_context=True
)
```

Update:
- Supported Languages count/table
- Language badges section (if applicable)
- Any feature lists mentioning language counts

### 8c. docs/adding-languages.md

If the new language introduces a new pattern worth documenting, add it as a worked example (like the HCL example in Path C).

## Step 9: Verify

### 9a. Run Tests

```bash
# Handler tests (if Path A)
uv run pytest tests/unit/handlers/test_<language>.py -v

# Symbol extraction tests (if Path B)
uv run pytest tests/unit/indexer/symbols/test_<language>.py -v

# Grammar tests (if Path D)
uv run pytest tests/unit/handlers/grammars/test_<grammar>.py -v

# Registry count assertions
uv run pytest tests/unit/handlers/test_registry.py -v
uv run pytest tests/unit/handlers/test_grammar_registry.py -v

# Full handler test suite
uv run pytest tests/unit/handlers/ -v
```

### 9b. Lint

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

### 9c. Present Summary

```
Language support added for [language]!

Paths completed:
  [x] Path A: Language Handler -- src/cocosearch/handlers/<language>.py
  [x] Path B: Symbol Extraction -- src/cocosearch/indexer/queries/<language>.scm
  [ ] Path D: Grammar Handler -- not applicable
  [x] Path E: Context Expansion -- added to context_expander.py

Registration points:
  [x] Handler file created (autodiscovered)
  [x] Extensions in include_patterns (config.py)
  [x] LANGUAGE_MAP entries (symbols.py)
  [x] Query file created (queries/<language>.scm)
  [x] SYMBOL_AWARE_LANGUAGES updated (query.py)
  [x] DEFINITION_NODE_TYPES updated (context_expander.py)
  [x] EXTENSION_TO_LANGUAGE updated (context_expander.py)
  [x] Test count assertions updated
  [x] Documentation updated

Tests: PASS
Lint: PASS

To try it out:
  uv run cocosearch languages          # Verify language appears
  uv run cocosearch index .            # Reindex with new language support
  uv run cocosearch search "query" --language <language>
```

## Registration Checklist

Complete checklist of all registration points. Check off each one as you complete it:

**Language Handler (Path A):**
- [ ] `src/cocosearch/handlers/<language>.py` created
- [ ] Extensions added to `include_patterns` in `src/cocosearch/indexer/config.py`
- [ ] Display name added to `cli.py` `languages_command` (if `.title()` casing is wrong)
- [ ] `tests/unit/handlers/test_<language>.py` created

**Symbol Extraction (Path B):**
- [ ] `src/cocosearch/indexer/queries/<language>.scm` created
- [ ] Extension mappings added to `LANGUAGE_MAP` in `src/cocosearch/indexer/symbols.py`
- [ ] Language added to `SYMBOL_AWARE_LANGUAGES` in `src/cocosearch/search/query.py`
- [ ] `_map_symbol_type` updated (if new AST node types need mapping)
- [ ] `_build_qualified_name` updated (if special naming logic needed)
- [ ] `tests/unit/indexer/symbols/test_<language>.py` created

**Grammar Handler (Path D):**
- [ ] `src/cocosearch/handlers/grammars/<grammar>.py` created
- [ ] `tests/unit/handlers/grammars/test_<grammar>.py` created

**Context Expansion (Path E):**
- [ ] `DEFINITION_NODE_TYPES` updated in `src/cocosearch/search/context_expander.py`
- [ ] `EXTENSION_TO_LANGUAGE` updated in `src/cocosearch/search/context_expander.py`

**Count Assertions:**
- [ ] `tests/unit/handlers/test_registry.py` -- handler count and spec count updated
- [ ] `tests/unit/handlers/test_grammar_registry.py` -- grammar count and spec count updated

**Documentation:**
- [ ] `CLAUDE.md` -- module descriptions and counts updated
- [ ] `README.md` -- supported languages section updated
- [ ] `docs/adding-languages.md` -- new example added (if novel pattern)

For common search tips (hybrid search, smart_context, symbol filtering), see `skills/README.md`.

For installation instructions, see `skills/README.md`.
