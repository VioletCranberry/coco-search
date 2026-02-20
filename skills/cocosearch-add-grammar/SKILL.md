---
name: cocosearch-add-grammar
description: Use when adding a grammar handler for domain-specific file formats that share a base language extension (e.g., GitHub Actions within YAML). Guides through YamlGrammarBase inheritance, content validation, separator spec, metadata extraction, tests, and registration.
---

# Add Grammar Handler with CocoSearch

A structured workflow for adding a grammar handler to CocoSearch. Grammar handlers provide domain-specific chunking and metadata for files that share a base language extension but have distinct structure (e.g., GitHub Actions workflows are YAML files with a specific schema).

**Philosophy:** `YamlGrammarBase` handles the heavy lifting — `matches()`, `extract_metadata()`, comment stripping, and the fallback metadata chain are all inherited. Subclasses only implement `_has_content_markers(content)` for content validation and `_extract_grammar_metadata(stripped, text)` for grammar-specific metadata. Override `matches()` only for broad-pattern grammars that need mandatory content checks (like Kubernetes). This skill guides you through designing content validation and metadata extraction.

**Reference:** `docs/adding-languages.md` covers grammar handlers alongside language handlers. This skill is the dedicated deep-dive for grammars.

## Step 1: Identify the Grammar

Parse the user's request to determine what's being added.

**Extract from the request:**

- **Grammar name:** Lowercase hyphenated identifier (e.g., `github-actions`, `docker-compose`, `ansible-playbook`)
- **Base language:** The language this grammar extends (e.g., `yaml`, `json`, `toml`)
- **File path patterns:** Glob patterns matching file paths (e.g., `.github/workflows/*.yml`, `docker-compose*.yml`)
- **Content markers:** Strings that distinguish this grammar from other files with the same extension (e.g., `on:` + `jobs:` for GitHub Actions, `apiVersion:` + `kind:` for Kubernetes)

**Confirm with user:** "I'll add a grammar handler for [grammar] (base: [language]) matching [patterns]. Let me find the best analog."

## Step 2: Find the Best Analog

Choose the closest existing grammar handler based on the grammar type:

| Grammar Type | Analog | Why |
|---|---|---|
| CI/CD pipeline (YAML) | `github_actions.py` or `gitlab_ci.py` | Jobs/stages/steps structure |
| Container orchestration (YAML) | `docker_compose.py` or `kubernetes.py` | Services/resources structure |
| Template (YAML/gotmpl) | `helm_template.py` or `helm_values.py` | Template directives + values |
| Kubernetes manifest (YAML) | `kubernetes.py` | Content-heavy matching with exclusions |
| Config values (YAML) | `helm_values.py` | Comment-based section markers |

> **Non-YAML grammars:** The pattern applies equally to JSON, TOML, or XML base languages — adapt `PATH_PATTERNS` and content markers accordingly. All 7 existing grammars inherit from `YamlGrammarBase`, which provides shared comment stripping, regex patterns (`_TOP_KEY_RE`, `_ITEM_RE`, etc.), `matches()` with path + content delegation, and metadata orchestration with fallback chain. The handler structure is language-agnostic.

Search for and read the analog handler:

```
search_code(
    query="<analog-grammar> grammar handler GRAMMAR_NAME matches",
    symbol_type="class",
    use_hybrid_search=True,
    smart_context=True
)
```

Read the analog handler fully before proceeding.

## Step 3: Design Content Validation

Most grammars inherit `matches()` from `YamlGrammarBase` — it handles path matching via `fnmatch` with nested path support (`*/pattern`) and delegates content checks to your `_has_content_markers(content)`. You only override `matches()` for broad-pattern grammars that need mandatory content checks (rare — Kubernetes is the only current example).

Use the decision tree to determine what you need to implement:

```
Are your PATH_PATTERNS specific to this grammar?
(e.g., ".github/workflows/*.yml", ".gitlab-ci.yml", "docker-compose*.yml")

YES --> Implement _has_content_markers() only
  - Inherited matches() handles path matching and delegates to your method
  - _has_content_markers() confirms content when available (optional validation)
  - Returns True when path matches and content is None
  - Example: GitHubActionsHandler -- ".github/workflows/*.yml" is specific enough

NO --> Broad patterns that match many files
(e.g., "*.yaml", "*.yml")

  - Override matches() entirely (rare case)
  - Content check is MANDATORY -- return False when content is None
  - Must check for positive markers (e.g., "apiVersion:" + "kind:")
  - Must check for negative markers (exclude competing grammars)
  - Example: KubernetesHandler -- "*.yaml" matches everything, so content is required
```

### Path-specific grammars (most cases)

Inherited from `YamlGrammarBase` — shown for reference, **don't implement this**:

```python
# This is in YamlGrammarBase — you get it for free
def matches(self, filepath: str, content: str | None = None) -> bool:
    for pattern in self.PATH_PATTERNS:
        if fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(
            filepath, f"*/{pattern}"
        ):
            if content is not None:
                return self._has_content_markers(content)
            return True
    return False
```

**What you implement** — `_has_content_markers()` for content validation:

```python
def _has_content_markers(self, content: str) -> bool:
    # Return True if content has grammar-specific markers
    return "marker_a:" in content and "marker_b:" in content
```

### Broad pattern matching — rare case, override `matches()`

Only when PATH_PATTERNS are too broad (e.g., `*.yaml`) and mandatory content checks are needed. Kubernetes is the only current example:

```python
def matches(self, filepath: str, content: str | None = None) -> bool:
    basename = filepath.rsplit("/", 1)[-1] if "/" in filepath else filepath
    for pattern in self.PATH_PATTERNS:
        if fnmatch.fnmatch(basename, pattern):
            if content is None:
                return False  # Can't distinguish without content
            # Positive markers
            if "required_key:" not in content:
                return False
            # Negative markers (exclude competing grammars)
            if any(marker in content for marker in _COMPETING_MARKERS):
                return False
            return True
    return False
```

### Conflict avoidance

When multiple grammars share broad patterns (`*.yaml`, `*.yml`), check for markers from competing grammars:

- **Kubernetes** excludes Helm markers via `_HELM_MARKERS` import from `helm_template.py`
- **Docker Compose** uses path-specific patterns (`docker-compose*.yml`) to avoid overlap
- **GitLab CI** uses an exact filename (`.gitlab-ci.yml`) to avoid overlap

Search for potential conflicts:

```
search_code(
    query="PATH_PATTERNS matches grammar handler yaml yml",
    use_hybrid_search=True,
    smart_context=True
)
```

Review all existing grammar `PATH_PATTERNS` and `matches()` logic to ensure your new grammar won't claim files that belong to another grammar.

## Step 4: Create the Handler File

1. **Copy** `src/cocosearch/handlers/grammars/_template.py` to `<grammar>.py`
2. **Rename** the class to `<Grammar>Handler` (e.g., `AnsiblePlaybookHandler`)
3. **Inherit** from `YamlGrammarBase` (imported from `cocosearch.handlers.grammars._base`)
4. **Set** `GRAMMAR_NAME` -- unique lowercase hyphenated identifier (e.g., `ansible-playbook`)
5. **Set** `PATH_PATTERNS` -- glob patterns matching file paths
6. **Override** `matches()` only for broad patterns (rare — see Step 3 decision tree)
7. **Define** `SEPARATOR_SPEC` with `CustomLanguageSpec` -- hierarchical regex separators from coarsest to finest
8. **Implement** `_has_content_markers(content)` -- return True if content has grammar-specific markers
9. **Implement** `_extract_grammar_metadata(stripped, text)` -- return metadata dict or `None` for fallback chain

**Separator constraints:** Use standard regex only -- no lookaheads/lookbehinds (CocoIndex uses Rust regex).

**Autodiscovery:** The grammar is autodiscovered at import time. Any `handlers/grammars/*.py` file (not prefixed with `_`) implementing the grammar handler protocol is auto-registered. No registration code needed.

### Metadata extraction tips

- Comment stripping is handled by inherited `_strip_comments()` — called automatically before `_extract_grammar_metadata()`
- Use `self._make_result(block_type, hierarchy)` for result construction (sets `language_id` to `GRAMMAR_NAME`)
- Return `None` from `_extract_grammar_metadata()` to trigger the fallback chain (document → value → empty)
- Inherited regex patterns available for YAML parsing: `_TOP_KEY_RE`, `_ITEM_RE`, `_NESTED_KEY_RE`, `_LIST_ITEM_KEY_RE`
- Identify the most meaningful block types (e.g., "job", "step", "service", "resource")
- Build `hierarchy` as a structured path (e.g., `"job:build"`, `"service:web"`, `"kind:Deployment"`)

## Step 5: Create Tests

Create `tests/unit/handlers/grammars/test_<grammar>.py` following the 4-class test pattern from existing grammars:

### TestMatching

- **Path matching (positive):** Files matching PATH_PATTERNS are detected
- **Path matching (negative):** Non-matching paths are rejected
- **Nested paths:** Patterns work when nested under parent directories (e.g., `project/.github/workflows/ci.yml`)
- **Content matching (positive):** Content with correct markers is detected
- **Content matching (negative):** Content without markers is rejected
- **`content=None` behavior:** Returns True for path-specific grammars, False for broad-pattern grammars

### TestSeparatorSpec

- `language_name` matches `GRAMMAR_NAME`
- `separators_regex` is non-empty
- No lookaheads/lookbehinds in regex patterns (assert `(?=`, `(?!`, `(?<=`, `(?<!` not in separators)

### TestExtractMetadata

- Each block type returns correct `block_type` and `hierarchy`
- Comments are stripped before analysis (`_strip_comments()` inherited from `YamlGrammarBase`)
- Unrecognized content falls through to inherited fallback chain (document → value → empty)
- `language_id` always equals `GRAMMAR_NAME` (set by inherited `_make_result()`)

### TestProtocol

- `GRAMMAR_NAME` is set and non-empty
- `BASE_LANGUAGE` is set and non-empty
- `PATH_PATTERNS` is a non-empty list

Find the analog's test file for the exact pattern:

```
search_code(
    query="test <analog-grammar> grammar matching separator metadata",
    symbol_type="class",
    use_hybrid_search=True,
    smart_context=True
)
```

**Checkpoint with user:** "Grammar handler created at `src/cocosearch/handlers/grammars/<grammar>.py` with [path-specific/broad] matching. Tests pass. Ready for count assertions and documentation?"

## Step 6: Update Count Assertions

> **This is the most commonly missed step.** Do not skip.

### 6a. Grammar Count

```
search_code(
    query="test grammar registry count _GRAMMAR_REGISTRY",
    use_hybrid_search=True,
    smart_context=True
)
```

Update in `tests/unit/handlers/test_grammar_registry.py`:
- `len(_GRAMMAR_REGISTRY) == N` -- increment by 1
- Grammar name in the expected names set -- add the new grammar name
- `len(grammars) == N` from `get_registered_grammars()` -- increment by 1

### 6b. Combined Spec Count

```
search_code(
    query="test_returns_twelve_specs get_all_custom_language_specs",
    use_hybrid_search=True,
    smart_context=True
)
```

Update in `tests/unit/handlers/test_registry.py`:
- `len(specs) == N` from `get_all_custom_language_specs()` -- increment by 1 (this is the combined total of all language handler specs + grammar handler specs)

## Step 7: Update Documentation

### 7a. CLAUDE.md

Update module descriptions and counts:
- Handler count in Architecture section (e.g., "Total custom language specs: N")
- Grammar handler list in the `handlers/` module description
- Any handler/grammar counts mentioned

### 7b. README.md

```
search_code(
    query="Supported Grammars grammar table badges",
    use_hybrid_search=True,
    smart_context=True
)
```

Update:
- Grammar badge row in the badge section
- Grammar table with new entry (grammar name, file format, path patterns)
- Grammar count in prose (if mentioned)

### 7c. docs/adding-languages.md

If the new grammar introduces a novel matching pattern (e.g., first non-YAML grammar, first content-only match without path patterns), add it as a worked example.

## Step 8: Verify

### 8a. Run Tests

```bash
# Grammar tests
uv run pytest tests/unit/handlers/grammars/test_<grammar>.py -v

# Registry count assertions
uv run pytest tests/unit/handlers/test_registry.py -v
uv run pytest tests/unit/handlers/test_grammar_registry.py -v

# Full handler test suite
uv run pytest tests/unit/handlers/ -v
```

### 8b. Lint

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

### 8c. Present Summary

```
Grammar handler added for [grammar]!

Handler: src/cocosearch/handlers/grammars/<grammar>.py
  - Grammar name: <grammar-name>
  - Base language: <base-language>
  - Path patterns: <patterns>
  - Matching strategy: <path-specific/broad with content validation>
  - Separator levels: <N>

Registration points:
  [x] Grammar handler file created (autodiscovered)
  [x] Tests created (tests/unit/handlers/grammars/test_<grammar>.py)
  [x] test_grammar_registry.py counts updated
  [x] test_registry.py combined spec count updated
  [x] CLAUDE.md updated
  [x] README.md updated

Tests: PASS
Lint: PASS

To try it out:
  uv run cocosearch grammars          # Verify grammar appears
  uv run cocosearch index .           # Reindex to pick up grammar-matched files
  uv run cocosearch search "query" --language <grammar-name>
```

## Registration Checklist

Complete checklist of all registration points. Check off each one as you complete it:

- [ ] `src/cocosearch/handlers/grammars/<grammar>.py` created
- [ ] `tests/unit/handlers/grammars/test_<grammar>.py` created
- [ ] `tests/unit/handlers/test_grammar_registry.py` -- grammar count and name set updated
- [ ] `tests/unit/handlers/test_registry.py` -- combined spec count updated
- [ ] `CLAUDE.md` -- grammar handler list and counts updated
- [ ] `README.md` -- grammar table and badges updated

For common search tips (hybrid search, smart_context, symbol filtering), see `skills/README.md`.

For the full language support workflow (handlers, symbols, context expansion), use `/cocosearch:cocosearch-add-language`.
