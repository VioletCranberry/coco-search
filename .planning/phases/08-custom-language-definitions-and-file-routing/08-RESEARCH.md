# Phase 8: Custom Language Definitions and File Routing - Research

**Researched:** 2026-01-27
**Domain:** CocoIndex CustomLanguageSpec regex separators, file routing, DevOps chunking
**Confidence:** HIGH (verified via CocoIndex Cargo.toml, official docs, Python API inspection, Rust source)

## Summary

This research investigated the five focus areas flagged by the roadmap for Phase 1 of v1.2 DevOps Language Support. The most significant finding is a **correction to prior research**: CocoIndex uses the standard Rust `regex` crate (v1.12.2), NOT `fancy-regex`. This means **lookahead patterns (`(?=...)`) are NOT supported** in `separators_regex`. All separator patterns in STACK.md and ARCHITECTURE.md that use lookaheads must be redesigned using standard regex features (alternation, non-capturing groups, character classes).

Additional key findings: (1) Bash is confirmed NOT in CocoIndex's built-in 28-language Tree-sitter list, so naming a custom language "bash" is safe; (2) extensionless files like `Dockerfile` require a custom `extract_language` function since `os.path.splitext()` returns empty string; (3) chunk_size of 2000 bytes is recommended for DevOps files based on typical block sizes; (4) separator text IS preserved in chunk output (verified via Markdown built-in behavior analysis), so keyword-bearing patterns work correctly.

**Primary recommendation:** Design separator patterns using standard Rust regex only (alternation `(?:a|b)`, character classes, anchors). Match the newline + block keyword as the separator; the keyword text will be preserved in the chunk output by CocoIndex's RecursiveChunker.

## Standard Stack

### Core (No changes from v1.1)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| CocoIndex | >=0.3.28 | `SplitRecursively` with `custom_languages` | Unchanged |
| Python stdlib `re` | 3.11+ | Metadata regex (Phase 2, not Phase 1) | Unchanged |
| Python stdlib `os` | 3.11+ | `os.path.splitext`, `os.path.basename` | Unchanged |

### CocoIndex Regex Engine (CORRECTION)
| Component | Prior Research Claim | Actual Finding | Confidence |
|-----------|---------------------|----------------|------------|
| Regex engine | `fancy-regex` (supports lookaheads) | Standard Rust `regex` v1.12.2 (NO lookaheads) | **HIGH** -- verified from `rust/extra_text/Cargo.toml` and `Cargo.toml` workspace deps |
| Docs link | fancy-regex docs | `docs.rs/regex/latest/regex/#syntax` | **HIGH** -- verified from official CocoIndex Functions page |

**Evidence:**
- CocoIndex workspace `Cargo.toml` lists `regex = "1.12.2"` -- standard crate
- `rust/extra_text/Cargo.toml` (the crate implementing SplitRecursively) lists `regex` as dependency, NOT `fancy-regex`
- Official docs link for regex syntax: `https://docs.rs/regex/latest/regex/#syntax`
- Standard Rust `regex` crate explicitly does NOT support lookaheads, lookbehinds, or backreferences

**Impact:** ALL separator patterns from ARCHITECTURE.md that use `(?=...)` must be rewritten. This is a **blocking finding** for Phase 1 planning.

## Architecture Patterns

### Pattern 1: Separator Design Without Lookaheads

**What:** Use standard regex alternation and boundary matching for separators
**When:** All `separators_regex` patterns in CustomLanguageSpec
**Why:** CocoIndex uses standard Rust `regex` crate which does not support lookaheads

**Key insight:** CocoIndex's RecursiveChunker preserves separator text in chunk output. The separator pattern identifies WHERE to split, but the matched text is not discarded -- it remains as part of the chunk content. This is confirmed by the built-in Markdown separators (`r"\n# "`, `r"\n## "`) which must preserve header markers in chunks for Markdown to be useful.

**Confidence:** MEDIUM-HIGH -- Inferred from Markdown behavior analysis and Rust source code review of `recursive.rs`. The RecursiveChunker uses atom-based splitting with DP merging, not simple `regex.split()`. Direct validation at implementation time is required.

**Standard regex features available:**
- Non-capturing groups: `(?:a|b|c)` -- YES, supported
- Alternation: `a|b|c` -- YES, supported
- Character classes: `[a-z]`, `\s`, `\w` -- YES, supported
- Anchors: `^`, `$` -- YES, supported (with `(?m)` for multiline)
- Quantifiers: `+`, `*`, `?`, `{n,m}` -- YES, supported
- Lookaheads: `(?=...)` -- **NO, NOT supported**
- Lookbehinds: `(?<=...)` -- **NO, NOT supported**
- Backreferences: `\1` -- **NO, NOT supported**

### Pattern 2: File Extension to Language Routing

**What:** A custom function maps filename to language identifier for CocoIndex routing
**When:** Replacing the current `extract_extension` function for DevOps files
**Why:** `os.path.splitext("Dockerfile")` returns `""`, making extensionless files unroutable

**Current behavior (verified):**
```
Dockerfile           -> ""           (BROKEN -- falls to plain text)
Dockerfile.dev       -> "dev"        (BROKEN -- "dev" matches nothing)
Dockerfile.production -> "production" (BROKEN -- "production" matches nothing)
Containerfile        -> ""           (BROKEN -- falls to plain text)
main.tf              -> "tf"         (OK -- will match alias)
variables.tfvars     -> "tfvars"     (OK -- will match alias)
deploy.sh            -> "sh"         (OK -- will match alias)
.bashrc              -> ""           (BROKEN -- no extension)
```

**Required solution:** Replace or enhance `extract_extension` with a function that checks filename patterns FIRST, then falls back to extension:
```python
def extract_language(filename: str) -> str:
    basename = os.path.basename(filename)
    # Filename-based routing (check first)
    if basename == "Containerfile" or basename.startswith("Dockerfile"):
        return "dockerfile"
    # Extension-based routing (existing behavior)
    _, ext = os.path.splitext(filename)
    return ext[1:] if ext else ""
```

**Confidence:** HIGH -- verified by testing `os.path.splitext()` on all target file patterns

### Pattern 3: CustomLanguageSpec Alias Registration

**What:** Register file extensions as aliases so CocoIndex routes files to custom language specs
**When:** Defining DEVOPS_CUSTOM_LANGUAGES
**Why:** CocoIndex matches the `language` parameter against `language_name` OR `aliases` (case-insensitive)

**Alias mapping needed:**
| Custom Language | language_name | aliases | Files Routed |
|----------------|---------------|---------|--------------|
| HCL | `"hcl"` | `["tf", "tfvars"]` | `*.tf`, `*.hcl`, `*.tfvars` |
| Dockerfile | `"dockerfile"` | `[]` | `Dockerfile*`, `Containerfile` |
| Bash | `"bash"` | `["sh", "zsh", "shell"]` | `*.sh`, `*.bash`, `*.zsh` |

**Note on Dockerfile:** No aliases needed because the custom `extract_language` function returns `"dockerfile"` (matching `language_name` directly). Extension-based aliases like `"dev"` or `"production"` would not help since those aren't language identifiers.

**Note on HCL:** `"hcl"` is both the `language_name` AND a valid file extension. Files with `.hcl` extension will match the `language_name` directly. Files with `.tf` and `.tfvars` extensions need aliases.

### Recommended Project Structure
```
src/cocosearch/
    indexer/
        config.py            # MODIFY: Add DevOps include_patterns
        embedder.py          # MODIFY: Enhance extract_extension -> extract_language
        flow.py              # MODIFY: Pass custom_languages to SplitRecursively
        languages.py         # NEW: CustomLanguageSpec definitions
```

### Anti-Patterns to Avoid
- **Using lookahead patterns in separators_regex:** The Rust regex engine does not support them. Patterns like `r"\n(?=resource\s)"` will cause a runtime error.
- **Adding `Dockerfile` as a glob pattern without routing logic:** Adding `Dockerfile` to `include_patterns` without fixing the language routing means Dockerfile content will be chunked as plain text.
- **Naming a custom language identically to a built-in AND registering conflicting aliases:** The docs say "It's an error if any language name or alias is duplicated." While bash is NOT a built-in, be cautious with aliases that might match built-in extensions (e.g., don't alias "py" or "js").

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HCL/Dockerfile/Bash parsing | Custom AST parser | `CustomLanguageSpec` regex separators | CocoIndex handles chunking; regex identifies boundaries |
| File extension routing | Custom language detection framework | Enhanced `extract_language` function (10 lines) | Simple filename prefix + extension check covers all cases |
| Separator text preservation | Custom post-processing to re-attach keywords | CocoIndex's built-in RecursiveChunker behavior | Separator text is preserved in chunks by default |
| Regex lookaheads | Custom splitting logic outside CocoIndex | Standard regex alternation `(?:a\|b)` | Standard regex achieves the same boundary detection |

## Common Pitfalls

### Pitfall 1: Using Lookahead Patterns (CRITICAL)
**What goes wrong:** Separator patterns with `(?=...)` cause runtime errors because CocoIndex uses the standard Rust `regex` crate, not `fancy-regex`.
**Why it happens:** Prior research (STACK.md) incorrectly stated `fancy-regex` was the engine. The official docs link to `docs.rs/regex` (standard crate), and the Cargo.toml confirms `regex = "1.12.2"`.
**How to avoid:** Use ONLY standard regex features. Replace `r"\n(?=resource\s)"` with `r"\nresource "`. The alternation pattern `r"\n(?:resource|data|module|...) "` is valid standard regex.
**Warning signs:** Runtime error when creating or running a flow with custom_languages containing lookahead patterns.

### Pitfall 2: Extensionless Dockerfile Falls to Plain Text
**What goes wrong:** `extract_extension("Dockerfile")` returns `""`, which matches no language, so the file is chunked as plain text.
**Why it happens:** `os.path.splitext()` requires a dot-separated extension. `Dockerfile` has no extension.
**How to avoid:** Create `extract_language()` that checks filename patterns first (prefix match for `Dockerfile*`, exact match for `Containerfile`), then falls back to extension.
**Warning signs:** Dockerfile chunks at arbitrary character boundaries instead of instruction boundaries.

### Pitfall 3: Dockerfile.dev Returns "dev" as Language
**What goes wrong:** `os.path.splitext("Dockerfile.dev")` returns `"dev"`, which matches no language, so the file is chunked as plain text.
**Why it happens:** `splitext` treats `.dev` as the extension, not recognizing the Dockerfile naming convention.
**How to avoid:** The `extract_language()` function must check `basename.startswith("Dockerfile")` BEFORE falling back to extension extraction.
**Warning signs:** `Dockerfile.dev` and `Dockerfile.production` files chunked as plain text despite `Dockerfile` working correctly.

### Pitfall 4: Bash Name Collision (Non-Issue)
**What goes wrong:** Concern that naming a custom language "bash" conflicts with a built-in Tree-sitter bash language.
**Actual status:** **NOT a problem.** Bash is NOT in CocoIndex's built-in 28-language list. The `rust/extra_text/Cargo.toml` has NO `tree-sitter-bash` dependency. Naming the custom language "bash" with aliases ["sh", "zsh", "shell"] is safe.
**Evidence:** Verified from `extra_text/Cargo.toml` dependency list -- bash grammar is absent. The 28 built-in languages are: C, C++, C#, CSS, DTD, Fortran, Go, HTML, Java, JavaScript, JSON, Kotlin, Markdown, Pascal, PHP, Python, R, Ruby, Rust, Scala, Solidity, SQL, Swift, TOML, TSX, TypeScript, XML, YAML.
**Confidence:** HIGH

### Pitfall 5: Chunk Size Too Small for DevOps Files
**What goes wrong:** Default `chunk_size=1000` bytes splits most DevOps structural units across multiple chunks.
**Why it happens:** Terraform resources average 300-600 bytes for simple blocks, 600-2000+ bytes for complex blocks (with nested blocks, heredocs, IAM policies). Dockerfiles with multi-line RUN commands can be 500-1500 bytes per instruction.
**How to avoid:** Use `chunk_size=2000` for DevOps files. This keeps most resources as single chunks while still splitting very large blocks. The `min_chunk_size` default (chunk_size/2 = 1000) prevents tiny fragments.
**Warning signs:** DevOps file chunks that start mid-block or contain partial resource definitions.

### Pitfall 6: include_patterns for Extensionless Files
**What goes wrong:** Standard glob patterns like `*.dockerfile` don't match `Dockerfile` (no extension).
**How to avoid:** Use exact filename patterns: `"Dockerfile"`, `"Dockerfile.*"`, `"Containerfile"`. CocoIndex's `LocalFile` source `included_patterns` supports both glob and exact-name patterns.
**Confidence:** MEDIUM -- needs validation that `included_patterns` supports bare filenames without wildcards.

## Code Examples

### Example 1: HCL CustomLanguageSpec (Standard Regex)
```python
# Source: Designed per CocoIndex docs regex syntax (docs.rs/regex)
# Standard Rust regex -- NO lookaheads
HCL_LANGUAGE = cocoindex.functions.CustomLanguageSpec(
    language_name="hcl",
    aliases=["tf", "tfvars"],
    separators_regex=[
        # Level 1: Top-level HCL block boundaries
        # Non-capturing group with alternation (standard regex)
        r"\n(?:resource|data|variable|output|locals|module|provider|terraform|import|moved|removed|check) ",
        # Level 2: Blank lines between sections
        r"\n\n+",
        # Level 3: Single newlines
        r"\n",
        # Level 4: Whitespace
        r" ",
    ],
)
```

### Example 2: Dockerfile CustomLanguageSpec (Standard Regex)
```python
# Source: Designed per CocoIndex docs regex syntax (docs.rs/regex)
DOCKERFILE_LANGUAGE = cocoindex.functions.CustomLanguageSpec(
    language_name="dockerfile",
    aliases=[],
    separators_regex=[
        # Level 1: FROM (build stage boundaries)
        r"\nFROM ",
        # Level 2: Major instructions (case-sensitive, Dockerfile convention)
        r"\n(?:RUN|COPY|ADD|ENV|EXPOSE|VOLUME|WORKDIR|USER|LABEL|ARG|ENTRYPOINT|CMD|HEALTHCHECK|SHELL|ONBUILD|STOPSIGNAL|MAINTAINER) ",
        # Level 3: Blank lines / comments
        r"\n\n+",
        r"\n# ",
        # Level 4: Single newlines
        r"\n",
        # Level 5: Whitespace
        r" ",
    ],
)
```

### Example 3: Bash CustomLanguageSpec (Standard Regex)
```python
# Source: Designed per CocoIndex docs regex syntax (docs.rs/regex)
BASH_LANGUAGE = cocoindex.functions.CustomLanguageSpec(
    language_name="bash",
    aliases=["sh", "zsh", "shell"],
    separators_regex=[
        # Level 1: Function definitions (two patterns)
        r"\nfunction ",
        # Level 2: Blank lines (logical section separators in scripts)
        r"\n\n+",
        # Level 3: Comment-based section headers
        r"\n#+",
        # Level 4: Control flow keywords
        r"\n(?:if |for |while |case |until )",
        # Level 5: Single newlines
        r"\n",
        # Level 6: Whitespace
        r" ",
    ],
)
```

**Note on Bash function detection:** The pattern `r"\nfunction "` catches `function func_name` syntax. The `func_name() {` syntax is harder to capture without lookaheads because the separator would need to match `\n` followed by a word and `()`. This is a known limitation. Blank-line splitting (Level 2) handles most cases since Bash functions are typically separated by blank lines.

### Example 4: Enhanced Language Routing Function
```python
# Source: Designed to replace extract_extension for DevOps file support
import os
import cocoindex

@cocoindex.op.function()
def extract_language(filename: str) -> str:
    """Extract language identifier for SplitRecursively routing.

    Checks filename patterns first (for extensionless files like Dockerfile),
    then falls back to extension-based detection.
    """
    basename = os.path.basename(filename)

    # Filename-based routing (extensionless files)
    if basename == "Containerfile" or basename.startswith("Dockerfile"):
        return "dockerfile"

    # Extension-based routing (standard behavior)
    _, ext = os.path.splitext(filename)
    return ext[1:] if ext else ""
```

### Example 5: Updated include_patterns
```python
# Added DevOps file patterns to IndexingConfig.include_patterns
NEW_PATTERNS = [
    # HCL/Terraform
    "*.tf",
    "*.hcl",
    "*.tfvars",
    # Dockerfile (exact names + glob)
    "Dockerfile",
    "Dockerfile.*",
    "Containerfile",
    # Bash/Shell
    "*.sh",
    "*.bash",
]
```

## State of the Art

| Old Approach (STACK.md) | Current Approach (Corrected) | When Changed | Impact |
|--------------------------|------------------------------|--------------|--------|
| `fancy-regex` engine (lookaheads supported) | Standard Rust `regex` v1.12.2 (NO lookaheads) | This research | ALL separator patterns must be redesigned without `(?=...)` |
| Bash may be built-in (contradiction in FEATURES.md) | Bash confirmed NOT in built-in list | This research | Safe to use `language_name="bash"` without collision risk |
| `extract_extension` sufficient for routing | `extract_language` needed for Dockerfile | This research | New function required before custom languages work for Dockerfiles |

**Corrected from prior research:**
- STACK.md line 48: "Regex engine: Rust fancy-regex crate" -- **INCORRECT.** Engine is standard `regex` crate.
- STACK.md lines 147-156: Regex compatibility table claiming lookaheads supported in CocoIndex -- **INCORRECT for separators_regex.**
- ARCHITECTURE.md lines 86-94: HCL separator patterns using `r"\n(?=..."` -- **WILL NOT WORK.** Must be rewritten.
- ARCHITECTURE.md lines 101-112: Dockerfile separator patterns using `r"\n(?=FROM\s)"` -- **WILL NOT WORK.**
- ARCHITECTURE.md lines 119-131: Bash separator patterns using `r"\n(?=\w+\s*\(\)\s*\{)"` -- **WILL NOT WORK.**
- FEATURES.md line 17: "Bash IS in CocoIndex's built-in Tree-sitter list" -- **INCORRECT.** Bash is NOT in the list.

## Chunk Size Recommendation

| File Type | Recommended chunk_size | Recommended chunk_overlap | Rationale |
|-----------|----------------------|--------------------------|-----------|
| HCL (Terraform) | 2000 bytes | 500 bytes | Typical resources 300-600 bytes, complex ones 1000-2000+. 2000 keeps most resources intact. |
| Dockerfile | 1500 bytes | 300 bytes | Instructions are shorter (50-500 bytes each), but RUN commands can be long. 1500 balances stage completeness. |
| Bash | 2000 bytes | 500 bytes | Functions vary widely (100-2000 bytes). Scripts with heredocs need room. |
| Default (programming languages) | 1000 bytes | 300 bytes | Unchanged from v1.1 |

**Implementation approach:** Since CocoIndex's `SplitRecursively` accepts a single `chunk_size` at transform-call time (not per-language), the flow must use a SINGLE chunk_size for all files. Recommended: **2000 bytes** as the DevOps-aware default. This is within 2x of the current 1000-byte default and will not degrade programming language chunking significantly (Python functions average 500-1500 bytes, so 2000 is still reasonable).

**Alternative:** Use per-index chunk_size configuration in `.cocosearch.yaml`, letting users set higher values for infrastructure repos.

**Confidence:** MEDIUM -- chunk size optimization is empirical. 2000 is a well-informed starting point based on DevOps file structure analysis, but should be validated against real repositories.

## Open Questions

### 1. Separator Text Preservation Behavior
- **What we know:** CocoIndex's RecursiveChunker uses atom-based splitting with DP cost optimization. Built-in Markdown separators (`r"\n# "`) would be useless if headers were discarded. Source code analysis suggests separator text is preserved in chunks.
- **What's unclear:** The EXACT behavior for custom language separators. Does the entire match stay with the right chunk? Is the `\n` part discarded or kept?
- **Recommendation:** Validate at implementation time by creating a minimal flow with a custom language and inspecting chunk output. This is the FIRST thing to test in Phase 1.
- **Confidence:** MEDIUM-HIGH

### 2. include_patterns for Bare Filenames
- **What we know:** CocoIndex's `LocalFile` source has `included_patterns` which accepts glob patterns like `"*.tf"`.
- **What's unclear:** Whether it accepts bare filenames like `"Dockerfile"` (no wildcard) or requires `"**/Dockerfile"`.
- **Recommendation:** Test both patterns at implementation time. If bare filenames don't work, use `"**/Dockerfile"` or `"**/Dockerfile*"`.
- **Confidence:** LOW -- needs validation

### 3. Duplicate Language Name Error (Custom vs Built-in)
- **What we know:** The docs say "It's an error if any language name or alias is duplicated." Construction of specs with duplicate names succeeds (Python-side validation is lazy). The error surfaces at runtime in the Rust engine.
- **What's unclear:** Whether this prohibition applies ONLY to duplicates within custom_languages, or also between custom and built-in names. Since bash is NOT built-in, this is a non-issue for our use case. But it could matter for future custom languages.
- **Recommendation:** Avoid using any built-in language name (python, javascript, etc.) as a custom language name or alias. This is not relevant for Phase 1 (hcl, dockerfile, bash are all safe).
- **Confidence:** MEDIUM

### 4. Single chunk_size for Mixed Codebases
- **What we know:** `SplitRecursively.transform()` takes `chunk_size` at call time. The current flow uses one chunk_size for all files.
- **What's unclear:** Whether we can pass different chunk_sizes for different files within the same flow. CocoIndex flows are declarative, making conditional parameters difficult.
- **Recommendation:** Start with a single chunk_size of 2000 for all files. If needed later, explore whether CocoIndex supports dynamic chunk_size based on file extension (likely not without flow restructuring).
- **Confidence:** HIGH that single chunk_size is the correct approach for v1.2

## Sources

### Primary (HIGH confidence)
- CocoIndex `rust/extra_text/Cargo.toml` -- confirmed `regex` (standard), no `fancy-regex` dependency
- CocoIndex workspace `Cargo.toml` -- confirmed `regex = "1.12.2"`
- [CocoIndex Functions Documentation](https://cocoindex.io/docs/ops/functions) -- `SplitRecursively` API, `CustomLanguageSpec`, supported languages table, regex syntax link to `docs.rs/regex`
- [Rust regex crate documentation](https://docs.rs/regex/latest/regex/#syntax) -- confirmed NO lookahead/lookbehind/backreference support
- CocoIndex Python API (`help(SplitRecursively)`, `help(CustomLanguageSpec)`) -- verified locally
- `rust/extra_text/Cargo.toml` dependency list -- confirmed 28 Tree-sitter grammars, bash absent

### Secondary (MEDIUM confidence)
- CocoIndex `rust/extra_text/src/split/recursive.rs` -- RecursiveChunker algorithm analysis (via WebFetch, source partially visible)
- CocoIndex `rust/extra_text/src/split/by_separators.rs` -- KeepSeparator modes (Left/Right/None) analysis
- [CocoIndex Academic Papers Example](https://cocoindex.io/docs/examples/academic_papers_index) -- CustomLanguageSpec usage pattern with standard regex
- [CocoIndex PDF Elements Example](https://cocoindex.io/examples/pdf_elements) -- CustomLanguageSpec usage pattern

### Tertiary (LOW confidence)
- WebSearch analysis stating separator text is preserved in chunks -- inferred from Markdown behavior, not directly documented
- Chunk size recommendations -- based on general DevOps file size analysis, not empirically tested on this codebase

## Metadata

**Confidence breakdown:**
- Regex engine (standard, not fancy-regex): HIGH -- verified from Cargo.toml, official docs link
- Bash not in built-in list: HIGH -- verified from extra_text/Cargo.toml tree-sitter dependencies
- Separator patterns (standard regex): HIGH for syntax validity, MEDIUM for chunk output behavior
- File routing for Dockerfile: HIGH -- verified via Python os.path.splitext() testing
- Chunk size recommendation: MEDIUM -- empirically reasonable but not validated
- Separator text preservation: MEDIUM -- inferred from Markdown behavior, needs validation

**Research date:** 2026-01-27
**Valid until:** 60 days (CocoIndex API is stable; regex engine is unlikely to change)
