---
name: cocosearch-add-extractor
description: Use when adding a dependency extractor for a language or grammar. Guides through pre-checks, extractor implementation, optional module resolver, tests, and registration. Enables `deps tree`, `deps impact`, and dependency-enriched search for the target language.
---

# Add Dependency Extractor with CocoSearch

A structured workflow for adding a dependency extractor to CocoSearch. Dependency extractors parse files to build a graph of what-depends-on-what, enabling `deps tree`, `deps impact`, `get_file_dependencies`/`get_file_impact` MCP tools, and `include_deps=True` in search results.

**Philosophy:** Extractors are autodiscovered and lightweight -- they parse one file at a time and emit edges. Module resolvers are optional and translate raw import strings into file paths. This skill guides you through both, with pre-checks that prevent wasted work.

**Reference:** The existing 8 extractors in `src/cocosearch/deps/extractors/` and 4 resolvers in `src/cocosearch/deps/resolver.py` serve as patterns.

## Step 1: Pre-checks

Before writing any code, verify the extractor is viable.

### 1a. Check If an Extractor Already Exists

```
search_code(
    query="dependency extractor LANGUAGES",
    symbol_type="class",
    use_hybrid_search=True,
    smart_context=True
)
```

Or check the registry directly:

```bash
uv run python -c "from cocosearch.deps.registry import get_all_extractor_language_ids; print(sorted(get_all_extractor_language_ids()))"
```

Currently registered: `cjs`, `cts`, `docker-compose`, `github-actions`, `go`, `helm-template`, `helm-values`, `js`, `jsx`, `mjs`, `mts`, `py`, `terraform`, `ts`, `tsx`.

**If the target language_id is already listed, stop.** The extractor exists. Inform the user.

### 1b. Determine the Language ID

The extractor's `LANGUAGES` set must match the `language_id` assigned during indexing:

| Source | language_id comes from | Example |
|---|---|---|
| Standard language | File extension without dot | `.py` -> `py`, `.go` -> `go` |
| Language handler | `handler.SEPARATOR_SPEC.language_name` | `hcl`, `dockerfile`, `bash` |
| Grammar handler | `handler.GRAMMAR_NAME` | `docker-compose`, `github-actions`, `terraform` |

Verify the language_id exists in the system:

```
search_code(
    query="LANGUAGE_EXTENSIONS EXTENSIONS language_name GRAMMAR_NAME",
    use_hybrid_search=True,
    smart_context=True
)
```

**If the language_id doesn't exist yet,** the user needs to add language/grammar support first. Suggest using `/cocosearch:cocosearch-add-language` or `/cocosearch:cocosearch-add-grammar`.

### 1c. Identify Import/Reference Patterns

Determine what dependency patterns the language has:

| Pattern Type | Edge Type | Examples |
|---|---|---|
| Import statements | `DepType.IMPORT` | Python `import`, JS `require()`, Go `import` |
| Symbol calls | `DepType.CALL` | Direct function calls across files |
| Reference patterns | `DepType.REFERENCE` | Docker Compose `image:`, GitHub Actions `uses:`, Terraform `source` |

**If the language has no recognizable import or reference patterns, stop.** Not all languages benefit from dependency extraction.

### 1d. Decide If a Module Resolver Is Needed

Resolvers translate raw import strings (e.g., `cocosearch.deps.models`) into file paths (e.g., `src/cocosearch/deps/models.py`). They run after extraction to resolve `target_file` from `metadata["module"]`.

| Language Type | Resolver Needed? | Why |
|---|---|---|
| Code with imports (Python, JS, Go) | Yes | Import strings need path resolution |
| Config with external refs (Docker Compose, GitHub Actions) | No | References point to external resources, not local files |
| IaC with local modules (Terraform) | Yes | Local `source = "./modules/..."` needs resolution |
| Templates with includes (Helm) | No | Template includes are path-relative |

Currently implemented resolvers: `PythonResolver`, `JavaScriptResolver`, `GoResolver`, `TerraformResolver`.

**Confirm with user:** "I'll add a dependency extractor for [language] (language_id: `[id]`) extracting [pattern types]. [Will/Won't] add a module resolver. Ready to proceed?"

## Step 2: Find the Best Analog Extractor

Choose based on the extraction technique:

| Extraction Technique | Analog Extractor | Key Pattern |
|---|---|---|
| Tree-sitter AST parsing | `go.py` | Parse with `get_parser()`, walk nodes |
| Regex on source code | `python.py` | Line-by-line regex matching |
| Multi-style imports (ES6 + CommonJS) | `javascript.py` | Multiple regex patterns + re-exports |
| YAML parsing with refs | `docker_compose.py` | `yaml.safe_load()`, walk dict structure |
| Regex + YAML hybrid | `helm.py` | Different parse strategy per language_id |
| HCL block parsing | `terraform.py` | Tree-sitter for `module` blocks |

Search for and read the analog:

```
search_code(
    query="<analog> dependency extractor extract LANGUAGES",
    symbol_type="class",
    use_hybrid_search=True,
    smart_context=True
)
```

Read the analog extractor fully before proceeding.

## Step 3: Create the Extractor

### 3a. Copy the Template

Copy `src/cocosearch/deps/extractors/_template.py` to `<language>.py`.

### 3b. Implement the Extractor Class

```python
from cocosearch.deps.models import DependencyEdge, DepType


class <Language>Extractor:
    """Extractor for <language> dependency edges."""

    LANGUAGES: set[str] = {"<language_id>"}

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        edges: list[DependencyEdge] = []
        # ... parse content, emit edges ...
        return edges
```

Key implementation rules:

1. **`LANGUAGES`** must contain the exact language_id(s) from Step 1b
2. **`file_path`** is the relative path within the project (use as `source_file`)
3. **`target_file`** should be `None` for unresolved imports (resolver fills it in later) or for external dependencies
4. **`metadata["module"]`** must contain the raw import string (resolvers use this)
5. **`metadata["line"]`** should contain the line number (1-indexed) for diagnostics
6. **Edge types:** Use `DepType.IMPORT` for code imports, `DepType.REFERENCE` for grammar-level refs (with `metadata["kind"]` for specifics like `"image"`, `"action"`, `"module_source"`)

### 3c. Parsing Approaches

**For tree-sitter languages** (preferred when available):

```python
from tree_sitter_language_pack import get_parser

parser = get_parser("<language>")
tree = parser.parse(content.encode())
# Walk tree.root_node to find import nodes
```

Explore the AST first:

```bash
uv run python -c "
from tree_sitter_language_pack import get_parser
parser = get_parser('<language>')
tree = parser.parse(b'''<sample-code-with-imports>''')
def show(node, indent=0):
    print(' ' * indent + f'{node.type} [{node.start_point[0]}:{node.start_point[1]}]')
    for child in node.children:
        show(child, indent + 2)
show(tree.root_node)
"
```

**For regex-based extraction** (simpler languages):

```python
import re

_IMPORT_RE = re.compile(r'^import\s+(.+)$', re.MULTILINE)

for match in _IMPORT_RE.finditer(content):
    line = content[:match.start()].count('\n') + 1
    edges.append(DependencyEdge(
        source_file=file_path,
        source_symbol=None,
        target_file=None,
        target_symbol=None,
        dep_type=DepType.IMPORT,
        metadata={"module": match.group(1), "line": line},
    ))
```

**For YAML-based grammars:**

```python
import yaml

try:
    data = yaml.safe_load(content)
except yaml.YAMLError:
    return []
# Walk data structure to find references
```

The extractor is **autodiscovered** at import time -- no registration code needed.

## Step 4: Add a Module Resolver (If Needed)

> **Skip this step** if pre-check 1d determined no resolver is needed.

### 4a. Read the Resolver Framework

```
search_code(
    query="ModuleResolver protocol build_index resolve",
    symbol_type="class",
    use_hybrid_search=True,
    smart_context=True
)
```

Read `src/cocosearch/deps/resolver.py` fully.

### 4b. Implement the Resolver

Add a new resolver class in `src/cocosearch/deps/resolver.py`:

```python
class <Language>Resolver:
    """Resolve <language> import paths to file paths."""

    def build_index(self, indexed_files: list[tuple[str, str]]) -> dict[str, str]:
        """Build module-name-to-file-path mapping."""
        index: dict[str, str] = {}
        for rel_path, lang_id in indexed_files:
            if lang_id not in self.LANGUAGES:
                continue
            # Map module identifier -> relative path
            # ...
        return index

    def resolve(self, edge: DependencyEdge, module_index: dict[str, str]) -> str | None:
        """Resolve an import to a file path."""
        module = edge.metadata.get("module", "")
        return module_index.get(module)
```

### 4c. Register the Resolver

Add the resolver to `_build_resolver_registry()` in `resolver.py`:

```python
<lang> = <Language>Resolver()
registry["<language_id>"] = <lang>
# If multiple language_ids share the same resolver:
# for lang_id in ("<id1>", "<id2>"):
#     registry[lang_id] = <lang>
```

## Step 5: Create Tests

### 5a. Extractor Tests

Create `tests/unit/deps/extractors/test_<language>.py`.

Follow the pattern from existing tests (e.g., `test_go.py`, `test_python.py`):

```python
from cocosearch.deps.extractors.<language> import <Language>Extractor
from cocosearch.deps.models import DepType


def _extract(code: str, file_path: str = "<default/path>"):
    """Helper to extract edges from <language> code."""
    extractor = <Language>Extractor()
    return extractor.extract(file_path, code)
```

Test categories:

| Category | What to Test |
|---|---|
| **Basic imports** | Single import, multiple imports, aliased imports |
| **Import variations** | Language-specific import styles (e.g., ES6 vs CommonJS, relative vs absolute) |
| **Edge metadata** | `module`, `line`, `alias`, `kind` fields are correct |
| **Edge types** | Correct `dep_type` (IMPORT, REFERENCE, CALL) |
| **Source file** | `source_file` matches the `file_path` argument |
| **Edge cases** | Empty file, no imports, comments containing imports, malformed imports |
| **LANGUAGES set** | `assert <Language>Extractor.LANGUAGES == {"<expected_ids>"}` |

### 5b. Resolver Tests (If Resolver Added)

Add tests to `tests/unit/deps/test_resolver.py`:

```python
class Test<Language>Resolver:
    def test_build_index_maps_files(self):
        resolver = <Language>Resolver()
        index = resolver.build_index([
            ("src/module.ext", "<lang_id>"),
            ("lib/other.ext", "<lang_id>"),
        ])
        assert "expected_key" in index

    def test_resolve_internal_import(self):
        resolver = <Language>Resolver()
        index = {"module_name": "src/module.ext"}
        edge = DependencyEdge(
            source_file="src/main.ext",
            source_symbol=None,
            target_file=None,
            target_symbol=None,
            dep_type=DepType.IMPORT,
            metadata={"module": "module_name"},
        )
        assert resolver.resolve(edge, index) == "src/module.ext"

    def test_resolve_external_returns_none(self):
        resolver = <Language>Resolver()
        edge = DependencyEdge(
            source_file="src/main.ext",
            source_symbol=None,
            target_file=None,
            target_symbol=None,
            dep_type=DepType.IMPORT,
            metadata={"module": "external_package"},
        )
        assert resolver.resolve(edge, {}) is None
```

**Checkpoint with user:** "Extractor and tests created. [N] test classes, [N] tests. Ready for documentation updates?"

## Step 6: Update Documentation

### 6a. CLAUDE.md

Update the `deps/` module description:

```
search_code(
    query="deps dependency extractor autodiscovery registry",
    use_hybrid_search=True,
    smart_context=True
)
```

Update:
- Extractor count (e.g., "8 extractors" -> "9 extractors")
- Language list in the `deps/` description
- Resolver count and list (if resolver added)
- Edge type documentation (if new edge types or metadata kinds)

### 6b. README.md

Update the languages and grammars tables -- the "Deps" column should show checkmark for the new language/grammar.

### 6c. docs/

If the extractor introduces a novel pattern, update `docs/architecture.md` or `docs/how-it-works.md`.

## Step 7: Verify

### 7a. Run Tests

```bash
# Extractor tests
uv run pytest tests/unit/deps/extractors/test_<language>.py -v

# Resolver tests (if added)
uv run pytest tests/unit/deps/test_resolver.py -v

# Registry smoke test (ensure autodiscovery works)
uv run python -c "from cocosearch.deps.registry import get_all_extractor_language_ids; print(sorted(get_all_extractor_language_ids()))"

# CLI shows Deps column correctly
uv run cocosearch languages --json | python -c "import json,sys; langs=json.load(sys.stdin); [print(f'{l[\"name\"]}: deps={l[\"deps\"]}') for l in langs if l['deps']]"
```

### 7b. Lint

```bash
uv run ruff check src/cocosearch/deps/ tests/unit/deps/
uv run ruff format --check src/cocosearch/deps/ tests/unit/deps/
```

### 7c. Present Summary

```
Dependency extractor added for [language]!

Extractor: src/cocosearch/deps/extractors/<language>.py
  - Language IDs: <ids>
  - Edge types: <import/reference/call>
  - Parsing: <tree-sitter/regex/yaml>
  - Resolver: <yes, in resolver.py / no, not needed>

Registration points:
  [x] Extractor file created (autodiscovered)
  [x] LANGUAGES matches language_id(s) from indexer
  [x] Module resolver added (if applicable)
  [x] Resolver registered in _build_resolver_registry() (if applicable)
  [x] Tests created
  [x] CLAUDE.md updated (extractor count, language list)
  [x] README.md Deps column updated

Tests: PASS
Lint: PASS

To try it out:
  uv run cocosearch index . --deps    # Index + extract dependencies
  uv run cocosearch deps show <file>  # Check dependencies for a file
  uv run cocosearch deps tree <file>  # Forward dependency tree
  uv run cocosearch deps impact <file> # Reverse impact tree
```

## Registration Checklist

Complete checklist of all registration points:

**Extractor:**
- [ ] `src/cocosearch/deps/extractors/<language>.py` created
- [ ] `LANGUAGES` set matches language_id(s) from handler/grammar/extension
- [ ] `extract()` returns edges with correct `dep_type` and `metadata`
- [ ] `tests/unit/deps/extractors/test_<language>.py` created

**Module Resolver (if needed):**
- [ ] Resolver class added to `src/cocosearch/deps/resolver.py`
- [ ] Resolver registered in `_build_resolver_registry()`
- [ ] Resolver tests added to `tests/unit/deps/test_resolver.py`

**Documentation:**
- [ ] `CLAUDE.md` -- extractor count, language list, resolver list updated
- [ ] `README.md` -- Deps column in languages/grammars table updated

For language handler support, use `/cocosearch:cocosearch-add-language`.
For grammar handler support, use `/cocosearch:cocosearch-add-grammar`.
