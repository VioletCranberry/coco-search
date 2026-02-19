---
name: cocosearch-add-grammar
description: Use when adding a grammar handler for domain-specific file formats that share a base language extension (e.g., GitHub Actions within YAML). Guides through matches() design, separator spec, metadata extraction, tests, and registration.
---

# Add Grammar Handler with CocoSearch

A structured workflow for adding a grammar handler to CocoSearch. Grammar handlers provide domain-specific chunking and metadata for files that share a base language extension but have distinct structure (e.g., GitHub Actions workflows are YAML files with a specific schema).

**Philosophy:** The hardest part of a grammar handler is the `matches()` method — getting path/content detection right so it claims the right files without conflicting with other grammars. This skill provides a decision tree to get it right the first time.

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

> **Non-YAML grammars:** The pattern applies equally to JSON, TOML, or XML base languages — adapt `PATH_PATTERNS` and content markers accordingly. All 6 existing grammars use YAML/gotmpl, but the handler structure is language-agnostic.

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

## Step 3: Design the `matches()` Method

This is the critical step. Use the decision tree to determine the right matching strategy:

```
Are your PATH_PATTERNS specific to this grammar?
(e.g., ".github/workflows/*.yml", ".gitlab-ci.yml", "docker-compose*.yml")

YES --> Path-specific matching
  - fnmatch against PATH_PATTERNS (with nested path support via */pattern)
  - Content check is OPTIONAL (confirmatory, improves accuracy)
  - Return True when path matches and content is None
  - Example: GitHubActionsHandler -- ".github/workflows/*.yml" is specific enough

NO --> Broad patterns that match many files
(e.g., "*.yaml", "*.yml")

  - Content check is MANDATORY
  - Return False when content is None (can't distinguish without content)
  - Must check for positive markers (e.g., "apiVersion:" + "kind:")
  - Must check for negative markers (exclude other grammars' files)
  - Example: KubernetesHandler -- "*.yaml" matches everything, so content is required
```

### Path-specific matching pattern

```python
def matches(self, filepath: str, content: str | None = None) -> bool:
    for pattern in self.PATH_PATTERNS:
        if fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(
            filepath, f"*/{pattern}"
        ):
            if content is not None:
                # Optional: confirm with content markers
                return "marker_a:" in content and "marker_b:" in content
            return True  # Path is specific enough
    return False
```

### Broad pattern matching (content required)

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
3. **Set** `GRAMMAR_NAME` -- unique lowercase hyphenated identifier (e.g., `ansible-playbook`)
4. **Set** `BASE_LANGUAGE` -- the base language (e.g., `"yaml"`)
5. **Set** `PATH_PATTERNS` -- glob patterns matching file paths
6. **Implement** `matches(filepath, content)` -- per decision tree in Step 3
7. **Define** `SEPARATOR_SPEC` with `CustomLanguageSpec` -- hierarchical regex separators from coarsest to finest
8. **Implement** `extract_metadata(text)` returning `block_type`, `hierarchy`, and `language_id`

**Separator constraints:** Use standard regex only -- no lookaheads/lookbehinds (CocoIndex uses Rust regex).

**Autodiscovery:** The grammar is autodiscovered at import time. Any `handlers/grammars/*.py` file (not prefixed with `_`) implementing the grammar handler protocol is auto-registered. No registration code needed.

### Metadata extraction tips

- Strip leading comments before analysis (use `strip_leading_comments` from `cocosearch.handlers.utils`)
- Identify the most meaningful block types (e.g., "job", "step", "service", "resource")
- Build `hierarchy` as a structured path (e.g., `"job:build"`, `"service:web"`, `"kind:Deployment"`)
- Always set `language_id` to `self.GRAMMAR_NAME`
- Return empty strings for unrecognized content (not `None`)

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
- Comments are stripped before analysis
- Unrecognized content returns empty strings as fallback
- `language_id` always equals `GRAMMAR_NAME`

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
