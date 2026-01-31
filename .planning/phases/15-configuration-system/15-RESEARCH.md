# Phase 15: Configuration System - Research

**Researched:** 2026-01-31
**Domain:** Python YAML configuration with Pydantic validation
**Confidence:** HIGH

## Summary

This phase implements a YAML-based configuration system for CocoSearch using the existing PyYAML and Pydantic libraries already in the project. The research confirmed that the standard approach is to parse YAML with `yaml.safe_load()` and validate using Pydantic BaseModel with `extra='forbid'` for strict unknown field rejection.

The existing codebase already has a rudimentary config implementation in `src/cocosearch/indexer/config.py` using Pydantic's BaseModel. This phase extends that foundation with the full config schema, proper validation, error handling with typo suggestions, and an `init` command for config generation.

**Primary recommendation:** Extend the existing `IndexingConfig` model into a comprehensive `CocoSearchConfig` model with nested sections, add `extra='forbid'` and `strict=True` for validation, use Python's built-in `difflib.get_close_matches()` for typo suggestions, and handle all YAML errors with user-friendly messages.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyYAML | 6.0.2 | YAML parsing | Already in project; mature, stable library |
| Pydantic | (via cocoindex) | Schema validation | Already in project via cocoindex dependency |
| difflib | stdlib | Typo suggestions | Built-in Python module, no dependencies |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib | stdlib | File path handling | Finding config files, git root detection |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyYAML | ruamel.yaml | Preserves comments better, but adds dependency |
| difflib | rapidfuzz | Faster fuzzy matching, but unnecessary for small field sets |
| Pydantic | dataclasses | Lighter weight, but loses validation features |

**Installation:**
```bash
# No new dependencies needed - PyYAML and Pydantic already available
```

## Architecture Patterns

### Recommended Project Structure
```
src/cocosearch/
├── config/              # NEW: Configuration module
│   ├── __init__.py      # Exports: CocoSearchConfig, load_config, ConfigError
│   ├── schema.py        # Pydantic models for config schema
│   ├── loader.py        # Config file discovery and loading
│   ├── errors.py        # Custom error types and formatting
│   └── generator.py     # Config template generation for `init` command
├── cli.py               # Extended with `init` command
└── indexer/
    └── config.py        # DEPRECATED: Migrate to config module
```

### Pattern 1: Nested Pydantic Models with Strict Validation
**What:** Config schema using nested Pydantic models with `extra='forbid'` and `strict=True`
**When to use:** When config has logical groupings and strict validation is required
**Example:**
```python
# Source: https://docs.pydantic.dev/latest/concepts/models/
from pydantic import BaseModel, ConfigDict, Field

class IndexingSection(BaseModel):
    """Configuration for indexing behavior."""
    model_config = ConfigDict(extra='forbid', strict=True)

    includePatterns: list[str] = Field(default_factory=list)
    excludePatterns: list[str] = Field(default_factory=list)
    chunkSize: int = Field(default=1000, gt=0)
    chunkOverlap: int = Field(default=300, ge=0)

class SearchSection(BaseModel):
    """Configuration for search behavior."""
    model_config = ConfigDict(extra='forbid', strict=True)

    resultLimit: int = Field(default=10, gt=0)
    minScore: float = Field(default=0.3, ge=0.0, le=1.0)

class EmbeddingSection(BaseModel):
    """Configuration for embedding model."""
    model_config = ConfigDict(extra='forbid', strict=True)

    model: str = Field(default="nomic-embed-text")

class CocoSearchConfig(BaseModel):
    """Root configuration model."""
    model_config = ConfigDict(extra='forbid', strict=True)

    indexName: str | None = None
    indexing: IndexingSection = Field(default_factory=IndexingSection)
    search: SearchSection = Field(default_factory=SearchSection)
    embedding: EmbeddingSection = Field(default_factory=EmbeddingSection)
```

### Pattern 2: Config File Discovery
**What:** Search for config file in project root, then git root
**When to use:** CLI needs to auto-discover config without explicit path
**Example:**
```python
# Source: Existing pattern in src/cocosearch/management/git.py
from pathlib import Path
import subprocess

def find_config_file() -> Path | None:
    """Find cocosearch.yaml in project root or git root.

    Search order:
    1. Current working directory
    2. Git repository root (if in a git repo)

    Returns:
        Path to config file if found, None otherwise.
    """
    config_name = "cocosearch.yaml"

    # Check current directory first
    cwd_config = Path.cwd() / config_name
    if cwd_config.exists():
        return cwd_config

    # Check git root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True
        )
        git_root = Path(result.stdout.strip())
        git_config = git_root / config_name
        if git_config.exists():
            return git_config
    except subprocess.CalledProcessError:
        pass  # Not in a git repo

    return None
```

### Pattern 3: Typo Suggestions with difflib
**What:** Use `difflib.get_close_matches()` to suggest corrections for unknown fields
**When to use:** When validating config fields to provide helpful error messages
**Example:**
```python
# Source: https://docs.python.org/3/library/difflib.html
from difflib import get_close_matches

def suggest_field_name(unknown: str, valid_fields: list[str]) -> str | None:
    """Suggest a valid field name for a typo.

    Args:
        unknown: The unrecognized field name.
        valid_fields: List of valid field names.

    Returns:
        Suggested field name if close match found, None otherwise.
    """
    matches = get_close_matches(unknown, valid_fields, n=1, cutoff=0.6)
    return matches[0] if matches else None

# Usage in error formatting:
# "Unknown field 'indxName'. Did you mean 'indexName'?"
```

### Pattern 4: All-at-Once Error Collection
**What:** Collect all validation errors before reporting
**When to use:** When user wants to see all config problems at once
**Example:**
```python
# Source: https://docs.pydantic.dev/latest/errors/validation_errors/
from pydantic import ValidationError

def format_validation_errors(exc: ValidationError) -> str:
    """Format all validation errors into a single message.

    Args:
        exc: Pydantic ValidationError with all validation failures.

    Returns:
        Human-readable error message with all issues listed.
    """
    lines = ["Configuration errors:"]
    for error in exc.errors():
        loc = ".".join(str(l) for l in error["loc"])
        msg = error["msg"]
        lines.append(f"  - {loc}: {msg}")
    return "\n".join(lines)
```

### Pattern 5: YAML Error Handling
**What:** Catch and format PyYAML parsing errors with line numbers
**When to use:** When loading config file to provide helpful syntax error messages
**Example:**
```python
# Source: https://zread.ai/yaml/pyyaml/4-basic-yaml-loading-and-dumping
import yaml

def load_yaml_file(path: Path) -> dict:
    """Load YAML file with helpful error messages.

    Args:
        path: Path to YAML file.

    Returns:
        Parsed YAML as dictionary.

    Raises:
        ConfigError: If YAML is invalid with line/column info.
    """
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        return data if data is not None else {}
    except yaml.YAMLError as e:
        if hasattr(e, 'problem_mark'):
            mark = e.problem_mark
            raise ConfigError(
                f"Invalid YAML syntax at line {mark.line + 1}, "
                f"column {mark.column + 1}: {e.problem}"
            )
        raise ConfigError(f"Invalid YAML: {e}")
```

### Anti-Patterns to Avoid
- **Silent field ignoring:** Don't use `extra='ignore'` - strict mode catches typos
- **Type coercion:** Don't allow `"10"` where `10` is expected - use strict mode
- **Single error reporting:** Don't stop at first error - collect all and report
- **Missing default mention:** Always tell user when using defaults (no config found)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy string matching | Custom Levenshtein | `difflib.get_close_matches()` | Handles cutoff, n-best, edge cases |
| YAML parsing | Custom parser | `yaml.safe_load()` | Security, YAML spec compliance |
| Schema validation | Manual dict checking | Pydantic BaseModel | Type coercion, nested validation |
| Field type validation | isinstance checks | Pydantic Field() | Constraints, error messages |
| Config merging | dict.update() | Pydantic model defaults | Proper nested merging |

**Key insight:** Pydantic already provides the full validation pipeline. The custom work is only in error message formatting and config file discovery.

## Common Pitfalls

### Pitfall 1: Silent Type Coercion
**What goes wrong:** User writes `chunkSize: "1000"` (string) but gets no error, causing subtle bugs
**Why it happens:** Pydantic defaults to coercing compatible types
**How to avoid:** Use `strict=True` in model_config or `ConfigDict(strict=True)`
**Warning signs:** Unexpected type behavior, "it worked in testing but failed in production"

### Pitfall 2: Partial Config Overwriting Defaults
**What goes wrong:** User specifies only `languages: [python]` but loses all default include patterns
**Why it happens:** Treating user list as replacement instead of understanding intent
**How to avoid:** Document behavior clearly ("lists replace entirely, not merge")
**Warning signs:** User complaints about "missing defaults" after partial config

### Pitfall 3: Forgetting extra='forbid'
**What goes wrong:** User makes typo `indexNme` and it's silently ignored
**Why it happens:** Pydantic defaults to `extra='ignore'`
**How to avoid:** Always set `extra='forbid'` on all config models
**Warning signs:** Config seems to have no effect, user confusion

### Pitfall 4: Poor YAML Error Messages
**What goes wrong:** User gets "YAMLError" with no context on what's wrong or where
**Why it happens:** Not handling `yaml.YAMLError` with `problem_mark` extraction
**How to avoid:** Always check for `problem_mark` attribute and extract line/column
**Warning signs:** User can't figure out what's wrong with their config

### Pitfall 5: Missing Config Not Reported
**What goes wrong:** CLI silently uses defaults, user thinks config is loaded
**Why it happens:** Not implementing the "first run" message
**How to avoid:** Print "[dim]No cocosearch.yaml found, using defaults[/dim]" when config missing
**Warning signs:** User frustrated that config changes have no effect (wrong file location)

## Code Examples

Verified patterns from official sources:

### Loading Config with Full Error Handling
```python
# Combined from PyYAML and Pydantic documentation
from pathlib import Path
from typing import Any
import yaml
from pydantic import ValidationError

class ConfigError(Exception):
    """Configuration loading or validation error."""
    pass

def load_config(path: Path | None = None) -> CocoSearchConfig:
    """Load and validate configuration.

    Args:
        path: Explicit path to config file. If None, auto-discover.

    Returns:
        Validated configuration object.

    Raises:
        ConfigError: If config is invalid.
    """
    # Find config file
    if path is None:
        path = find_config_file()

    if path is None:
        # No config file - use defaults
        return CocoSearchConfig()

    # Load YAML
    try:
        with open(path) as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        if hasattr(e, 'problem_mark'):
            mark = e.problem_mark
            raise ConfigError(
                f"Invalid YAML syntax in {path} at line {mark.line + 1}, "
                f"column {mark.column + 1}: {e.problem}"
            ) from e
        raise ConfigError(f"Invalid YAML in {path}: {e}") from e

    if raw_data is None:
        raw_data = {}

    # Validate with Pydantic
    try:
        return CocoSearchConfig.model_validate(raw_data)
    except ValidationError as e:
        # Format all errors with suggestions
        raise ConfigError(format_errors_with_suggestions(e, path)) from e
```

### Config Template Generation
```python
# For `cocosearch init` command
CONFIG_TEMPLATE = '''\
# CocoSearch Configuration
# See: https://github.com/VioletCranberry/cocosearch

# Index name (optional - defaults to directory name)
# indexName: my-project

indexing:
  # File patterns to include (glob patterns)
  # includePatterns:
  #   - "*.py"
  #   - "*.js"
  #   - "*.ts"

  # File patterns to exclude (glob patterns)
  # excludePatterns:
  #   - "*_test.py"
  #   - "*.min.js"

  # Languages to index (empty = all supported languages)
  # languages:
  #   - python
  #   - typescript

  # Chunk settings
  # chunkSize: 1000
  # chunkOverlap: 300

search:
  # Maximum results returned
  # resultLimit: 10

  # Minimum similarity score (0.0 - 1.0)
  # minScore: 0.3

embedding:
  # Ollama model for embeddings
  # model: nomic-embed-text
'''

def generate_config(path: Path) -> None:
    """Generate starter configuration file.

    Args:
        path: Path where to write config file.

    Raises:
        ConfigError: If file already exists.
    """
    if path.exists():
        raise ConfigError(f"Config file already exists: {path}")

    with open(path, 'w') as f:
        f.write(CONFIG_TEMPLATE)
```

### CLI Init Command
```python
# Addition to cli.py
def init_command(args: argparse.Namespace) -> int:
    """Execute the init command to create config file."""
    console = Console()

    config_path = Path.cwd() / "cocosearch.yaml"

    try:
        generate_config(config_path)
        console.print(f"[green]Created {config_path}[/green]")
        console.print("[dim]Edit this file to customize CocoSearch behavior.[/dim]")
        return 0
    except ConfigError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return 1
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual dict validation | Pydantic v2 | 2023 | 5-10x faster validation, better errors |
| `extra='ignore'` default | `extra='forbid'` recommended | Pydantic v2 | Catches typos, stricter validation |
| yaml.load() | yaml.safe_load() | PyYAML 5.1 (2019) | Security: prevents code execution |

**Deprecated/outdated:**
- `yaml.load()` without Loader: Security vulnerability, always use `safe_load()`
- Pydantic v1 Config class: Replaced by `model_config = ConfigDict(...)` in v2

## Open Questions

Things that couldn't be fully resolved:

1. **Section grouping specifics**
   - What we know: User decided on "grouped sections" with camelCase
   - What's unclear: Exact section names (indexing/search/embedding vs index/query/model)
   - Recommendation: Use `indexing`, `search`, `embedding` to match CLI subcommands

2. **Comment preservation on config update**
   - What we know: User wants comments preserved
   - What's unclear: Whether we need to update existing configs (Phase 15 scope?)
   - Recommendation: This phase creates configs; updating is future feature. ruamel.yaml would be needed for true comment preservation.

3. **Languages list default behavior**
   - What we know: Empty list = all languages, specified list = only those
   - What's unclear: Default value in schema (empty list vs list of common languages)
   - Recommendation: Default to empty list (meaning "all") for maximum convenience

## Sources

### Primary (HIGH confidence)
- Pydantic v2 documentation - BaseModel, ConfigDict, ValidationError handling
  - URL: https://docs.pydantic.dev/latest/concepts/models/
  - URL: https://docs.pydantic.dev/latest/errors/validation_errors/
- Python difflib documentation - get_close_matches() for typo suggestions
  - URL: https://docs.python.org/3/library/difflib.html
- PyYAML documentation - safe_load(), error handling with problem_mark
  - URL: https://zread.ai/yaml/pyyaml/4-basic-yaml-loading-and-dumping

### Secondary (MEDIUM confidence)
- Existing codebase patterns - config.py, git.py, cli.py
  - Path: src/cocosearch/indexer/config.py
  - Path: src/cocosearch/management/git.py

### Tertiary (LOW confidence)
- None - all findings verified with official documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in project, well documented
- Architecture: HIGH - Follows existing codebase patterns
- Pitfalls: HIGH - Documented in official Pydantic/PyYAML docs

**Research date:** 2026-01-31
**Valid until:** 2026-03-01 (stable domain, 30-day validity)
