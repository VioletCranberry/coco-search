# Language Handlers

This package provides language-aware chunking for code indexing.

## Architecture

- Each language has a dedicated handler module (e.g., `hcl.py`, `dockerfile.py`, `bash.py`)
- Handlers implement the `LanguageHandler` protocol
- Registry autodiscovers handlers at import time
- Unknown extensions fall back to TextHandler

## Adding a New Language

1. Copy `_template.py` to `<language>.py`
2. Update EXTENSIONS list with file extensions (with dots, e.g., `['.ext']`)
3. Define SEPARATOR_SPEC with CustomLanguageSpec:
   - `language_name`: Canonical language identifier
   - `separators_regex`: List of regex patterns (highest to lowest priority)
   - `aliases`: List of alternative language names
4. Implement `extract_metadata()` returning dict with:
   - `block_type`: Type of code block (e.g., "resource", "function")
   - `hierarchy`: Dot-separated or colon-separated path
   - `language_id`: Canonical language identifier
5. Create `tests/unit/handlers/test_<language>.py`:
   - Test EXTENSIONS contains expected extensions
   - Test SEPARATOR_SPEC.language_name and aliases
   - Test separators don't contain lookaheads/lookbehinds
   - Test extract_metadata for various block types
6. Run tests: `uv run pytest tests/unit/handlers/test_<language>.py -v`

## Handler Interface

Handlers implement the LanguageHandler protocol:

```python
class LanguageHandler(Protocol):
    EXTENSIONS: ClassVar[list[str]]
    """File extensions this handler claims (e.g., ['.tf', '.hcl'])."""

    SEPARATOR_SPEC: ClassVar[CustomLanguageSpec | None]
    """CocoIndex CustomLanguageSpec for chunking, or None for default."""

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from chunk text.

        Returns:
            Dict with at least: block_type, hierarchy, language_id
        """
```

## Separator Design

Separators define chunking boundaries from highest to lowest priority:

- **Level 1**: Major structural boundaries (e.g., functions, resources, FROM statements)
- **Level 2+**: Progressively finer-grained splits (blank lines, comments, newlines)
- **Last level**: Whitespace (fallback)

**Important**: Separators must use standard regex only. Do NOT use:
- Lookaheads: `(?=...)`
- Lookbehinds: `(?<=...)`
- Negative lookaheads: `(?!...)`
- Negative lookbehinds: `(?<!...)`

CocoIndex uses Rust regex which has different support than Python regex.

## Testing

Each handler must have a corresponding test file. Run all handler tests:

```bash
uv run pytest tests/unit/handlers/ -v
```

Test individual handler:

```bash
uv run pytest tests/unit/handlers/test_<language>.py -v
```

## Existing Handlers

| Handler | Extensions | Language | SEPARATOR_SPEC |
|---------|------------|----------|----------------|
| HclHandler | .tf, .hcl, .tfvars | HCL/Terraform | Yes |
| DockerfileHandler | .dockerfile | Dockerfile | Yes |
| BashHandler | .sh, .bash, .zsh | Bash/Shell | Yes |
| TextHandler | (fallback) | Plain text | No (default text splitting) |

## Registry Autodiscovery

Handlers are discovered automatically at module import time by scanning `handlers/*.py` files:

1. Files starting with `_` are excluded (e.g., `_template.py`)
2. Classes implementing LanguageHandler protocol are instantiated
3. Extensions are registered in `_HANDLER_REGISTRY`
4. Extension conflicts raise `ValueError` immediately

## Public API

```python
from cocosearch.handlers import get_handler, get_custom_languages, extract_devops_metadata

# Get handler for file extension
handler = get_handler('.tf')  # Returns HclHandler
handler = get_handler('.unknown')  # Returns TextHandler (fallback)

# Get all CustomLanguageSpec for CocoIndex
specs = get_custom_languages()  # Returns [HCL_SPEC, DOCKERFILE_SPEC, BASH_SPEC]

# Extract metadata from chunk (CocoIndex transform)
metadata = extract_devops_metadata(text="resource \"aws_s3_bucket\" \"data\" {", language_id="tf")
# Returns: {"block_type": "resource", "hierarchy": "resource.aws_s3_bucket.data", "language_id": "hcl"}
```

## Implementation Notes

### HCL Handler

- Matches 12 top-level HCL block keywords: resource, data, variable, output, locals, module, provider, terraform, import, moved, removed, check
- Extracts up to 2 quoted labels for hierarchy
- Comment-aware (strips `#`, `//`, and `/* */` comments)

### Dockerfile Handler

- FROM separator has higher priority than other instructions
- FROM with AS clause produces `stage:name` hierarchy
- FROM without AS produces `image:ref` hierarchy
- Other instructions produce empty hierarchy

### Bash Handler

- Supports 3 function syntaxes: POSIX `name() {`, ksh `function name {`, hybrid `function name() {`
- Function definitions produce `function:name` hierarchy
- Comment-aware (strips `#` comments)

### Text Handler

- Used as fallback for unknown extensions
- Returns empty metadata
- No SEPARATOR_SPEC (uses CocoIndex default text splitting)
