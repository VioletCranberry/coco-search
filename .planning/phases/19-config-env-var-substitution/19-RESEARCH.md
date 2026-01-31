# Phase 19: Config Env Var Substitution - Research

**Researched:** 2026-01-31
**Domain:** Python YAML configuration with environment variable substitution
**Confidence:** HIGH

## Summary

This phase implements environment variable substitution in the existing cocosearch.yaml config file. The project already uses PyYAML for YAML parsing and Pydantic for schema validation. The standard approach is to process the YAML data after loading (post-parse substitution) to replace `${VAR}` patterns with environment variable values before passing to Pydantic validation.

Two approaches exist: adding a library (pyaml-env, envyaml) or hand-rolling with Python's `re` module and `os.environ`. Given the project already has PyYAML and the feature scope is narrow (string substitution only, not YAML structure changes), hand-rolling is the better choice. It avoids a new dependency, keeps the implementation transparent, and aligns with the project's "zero new dependencies" pattern established in DevOps chunking.

The recommended pattern uses recursive string replacement on the parsed YAML dict, supporting: `${VAR}` syntax for required env vars, `${VAR:-default}` syntax for optional env vars with defaults, and clear error messages when required env vars are missing.

**Primary recommendation:** Hand-roll env var substitution in loader.py using regex pattern `\$\{([^}^{]+)\}`, process recursively after yaml.safe_load(), before Pydantic validation.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyYAML | 6.0.2+ | YAML parsing | Already in project, safe_load is secure |
| re (stdlib) | N/A | Regex pattern matching | Standard library, no dependency |
| os (stdlib) | N/A | Environment variable access | os.environ.get() for safe access |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pyaml-env | 1.2.2 | YAML with env var substitution | If needing advanced features (multiple defaults, custom tags) |
| pyyaml-env-tag | 1.1 | YAML tag-based env vars | If wanting `!ENV` tag syntax |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-roll regex | pyaml-env library | Library adds dependency, more features but more complexity |
| Post-load substitution | Custom YAML loader | Loader approach ties into YAML parsing internals, harder to test |
| `${VAR:-default}` syntax | `${VAR\|default}` (envyaml) | Bash-compatible syntax more familiar to users |

**Installation:**
No new packages needed - use existing PyYAML + stdlib.

## Architecture Patterns

### Recommended Integration Point

Substitution should happen in `loader.py` between YAML parse and Pydantic validation:

```
cocosearch.yaml → yaml.safe_load() → substitute_env_vars() → model_validate() → CocoSearchConfig
```

### Pattern 1: Post-Parse Recursive Substitution
**What:** Parse YAML to dict, then recursively walk the dict substituting env vars in string values.
**When to use:** For string-value substitution without changing YAML structure.
**Example:**
```python
# Source: Community pattern verified across multiple implementations
import re
import os
from typing import Any

ENV_VAR_PATTERN = re.compile(r'\$\{([^}^{]+)\}')

def substitute_env_vars(data: Any) -> Any:
    """Recursively substitute ${VAR} and ${VAR:-default} in data structure."""
    if isinstance(data, str):
        return _substitute_string(data)
    elif isinstance(data, dict):
        return {k: substitute_env_vars(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [substitute_env_vars(item) for item in data]
    return data

def _substitute_string(value: str) -> str:
    """Replace all ${VAR} and ${VAR:-default} patterns in a string."""
    def replacer(match: re.Match) -> str:
        expr = match.group(1)
        # Handle ${VAR:-default} syntax
        if ':-' in expr:
            var_name, default = expr.split(':-', 1)
            return os.environ.get(var_name, default)
        # Handle ${VAR} syntax (required)
        return os.environ.get(expr, match.group(0))  # Keep original if not found

    return ENV_VAR_PATTERN.sub(replacer, value)
```

### Pattern 2: Strict Mode with Missing Var Errors
**What:** Collect all missing env vars and raise clear error listing them all.
**When to use:** When strict validation is needed (production configs).
**Example:**
```python
class MissingEnvVarError(ConfigError):
    """Raised when required environment variables are not set."""
    pass

def substitute_env_vars_strict(data: Any) -> tuple[Any, list[str]]:
    """Substitute with tracking of missing required vars."""
    missing = []

    def _substitute_string(value: str) -> str:
        def replacer(match: re.Match) -> str:
            expr = match.group(1)
            if ':-' in expr:
                var_name, default = expr.split(':-', 1)
                return os.environ.get(var_name, default)
            var_name = expr
            env_value = os.environ.get(var_name)
            if env_value is None:
                missing.append(var_name)
                return match.group(0)  # Keep placeholder
            return env_value
        return ENV_VAR_PATTERN.sub(replacer, value)

    # ... recursive walk calling _substitute_string
    result = _recursive_substitute(data, _substitute_string)
    return result, missing
```

### Anti-Patterns to Avoid
- **Custom YAML Loader/Constructor:** Ties into YAML parsing internals, harder to understand and test. Post-parse substitution is cleaner.
- **Substitution after Pydantic validation:** Values would already be typed (int, float), losing the string patterns.
- **Global regex replacement on raw YAML text:** Can corrupt YAML structure if ${} appears in comments or multiline strings.
- **Silent failure on missing vars:** Leads to hard-to-debug empty string values.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing | Custom parser | yaml.safe_load() | Security, edge cases, Unicode |
| Schema validation | Manual type checking | Pydantic model_validate() | Error messages, type coercion |
| Complex template syntax | Full template engine | Just ${VAR} pattern | Keep scope narrow |

**Key insight:** The substitution itself IS the hand-roll part - it's simple enough. YAML parsing and validation already have good solutions.

## Common Pitfalls

### Pitfall 1: Substituting in Comments
**What goes wrong:** Regex replaces ${VAR} inside YAML comments, leading to confusing behavior.
**Why it happens:** Operating on raw YAML text instead of parsed data.
**How to avoid:** Always substitute AFTER yaml.safe_load(), which strips comments.
**Warning signs:** Users report env vars "not working" in commented-out config.

### Pitfall 2: Type Coercion Issues
**What goes wrong:** `${PORT}` substitutes to string "5432" but Pydantic expects int.
**Why it happens:** All env vars are strings, but config schema has typed fields.
**How to avoid:** Pydantic's strict=False mode coerces "5432" to int 5432. Current schema uses strict=True.
**Warning signs:** ValidationError on integer fields after env var substitution.

**Resolution:** Either relax Pydantic strict mode for substituted values, or document that only string fields support substitution. Given CONFIG-03 requires "all config sections", relaxing strict mode is recommended for fields likely to use env vars (like model name, index name).

### Pitfall 3: Empty String vs Missing
**What goes wrong:** User sets `export VAR=""` but code treats it as missing.
**Why it happens:** `os.environ.get(var)` returns "" for set-but-empty, which is falsy.
**How to avoid:** Check `if var in os.environ` for existence, then get value.
**Warning signs:** User explicitly sets empty string, but default is used instead.

### Pitfall 4: Partial Substitution in Strings
**What goes wrong:** `"https://${HOST}:${PORT}/api"` only partially substitutes.
**Why it happens:** re.sub with single match instead of global replacement.
**How to avoid:** Use re.sub() which replaces ALL occurrences, or re.finditer() for custom logic.
**Warning signs:** URLs or paths with multiple variables break.

### Pitfall 5: Escaping ${} Literals
**What goes wrong:** User wants literal `${not_a_var}` in config value.
**Why it happens:** No escape syntax defined.
**How to avoid:** Document that $${VAR} escapes to literal ${VAR}, or ${{VAR}} syntax.
**Warning signs:** Users can't use literal dollar-brace strings.

**Recommendation:** For v1.5 scope, defer escaping support. Document that ${} is always substituted. Add escape syntax later if requested.

## Code Examples

Verified patterns from research:

### Basic Substitution Function
```python
# Adapted from pyaml-env and community patterns
import re
import os
from typing import Any

# Pattern matches ${VAR} and ${VAR:-default}
ENV_VAR_PATTERN = re.compile(r'\$\{([^}^{]+)\}')

def substitute_env_vars(data: Any) -> Any:
    """Recursively substitute environment variables in config data.

    Supports:
    - ${VAR} - Required env var, kept as-is if missing
    - ${VAR:-default} - Env var with default value

    Args:
        data: Parsed YAML data (dict, list, or scalar)

    Returns:
        Data with env vars substituted
    """
    if isinstance(data, str):
        return _substitute_in_string(data)
    elif isinstance(data, dict):
        return {k: substitute_env_vars(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [substitute_env_vars(item) for item in data]
    return data

def _substitute_in_string(value: str) -> str:
    """Replace ${VAR} patterns in a string."""
    def replacer(match: re.Match) -> str:
        expr = match.group(1)

        # Handle ${VAR:-default} syntax
        if ':-' in expr:
            var_name, default = expr.split(':-', 1)
            return os.environ.get(var_name, default)

        # Handle ${VAR} syntax - required variable
        var_name = expr
        return os.environ.get(var_name, match.group(0))  # Keep if missing

    return ENV_VAR_PATTERN.sub(replacer, value)
```

### Strict Mode with Error Collection
```python
def substitute_env_vars_strict(data: Any) -> tuple[Any, list[str]]:
    """Substitute env vars, tracking missing required variables.

    Returns:
        Tuple of (substituted_data, list_of_missing_vars)
    """
    missing: list[str] = []

    def _substitute_in_string(value: str) -> str:
        def replacer(match: re.Match) -> str:
            expr = match.group(1)

            if ':-' in expr:
                var_name, default = expr.split(':-', 1)
                return os.environ.get(var_name, default)

            var_name = expr
            env_value = os.environ.get(var_name)
            if env_value is None:
                missing.append(var_name)
                return match.group(0)
            return env_value

        return ENV_VAR_PATTERN.sub(replacer, value)

    def _recurse(data: Any) -> Any:
        if isinstance(data, str):
            return _substitute_in_string(data)
        elif isinstance(data, dict):
            return {k: _recurse(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [_recurse(item) for item in data]
        return data

    result = _recurse(data)
    return result, list(set(missing))  # Dedupe missing vars
```

### Integration in loader.py
```python
def load_config(path: Path | None = None) -> CocoSearchConfig:
    """Load configuration from YAML file with env var substitution."""
    if path is None:
        path = find_config_file()

    if path is None:
        return CocoSearchConfig()

    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        if data is None:
            return CocoSearchConfig()

        # NEW: Substitute environment variables
        data, missing_vars = substitute_env_vars_strict(data)
        if missing_vars:
            raise ConfigError(
                f"Missing required environment variables in {path}: "
                f"{', '.join(sorted(missing_vars))}"
            )

        # Validate with Pydantic
        return CocoSearchConfig.model_validate(data)

    except yaml.YAMLError as e:
        # ... existing YAML error handling
```

### Example Config Usage
```yaml
# cocosearch.yaml with env var substitution
indexName: ${PROJECT_NAME:-my-project}

embedding:
  model: ${OLLAMA_MODEL:-nomic-embed-text}

# Typical use case: database URL in env
# database:
#   url: ${COCOSEARCH_DATABASE_URL}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| !ENV tag required | Implicit ${} syntax | 2022+ | Users don't need special YAML tags |
| Error on any missing | Default value support ${:-} | 2023+ | More flexible configs |
| Full template engines | Simple regex substitution | Always | YAML configs don't need Jinja2 complexity |

**Deprecated/outdated:**
- Using `yaml.Loader` instead of `yaml.SafeLoader`: Security vulnerability
- Modifying yaml.Loader class globally: Side effects across application
- Env var substitution before YAML parse: Can corrupt YAML structure

## Open Questions

Things that couldn't be fully resolved:

1. **Type Coercion for Substituted Values**
   - What we know: Pydantic strict=True rejects "5432" for int field
   - What's unclear: Should we relax strict mode, or only support string fields?
   - Recommendation: Keep strict mode, document that substitution works best with string fields. Future phases can add type coercion if needed. Given current schema (model name, index name, patterns), all likely substitution targets are strings.

2. **Escape Syntax for Literal ${**
   - What we know: Users may want literal ${VAR} in config values
   - What's unclear: Best escape syntax ($${}, $$, \${?)
   - Recommendation: Defer to future phase. Document that ${} is always substituted. This is a rare edge case.

3. **Nested Variable References**
   - What we know: ${${INNER}} or ${OUTER_${SUFFIX}} is possible
   - What's unclear: Whether to support this complexity
   - Recommendation: Don't support. Single-level ${VAR} covers all practical use cases.

## Sources

### Primary (HIGH confidence)
- [pyaml-env GitHub](https://github.com/mkaranasou/pyaml_env) - Pattern for default value syntax, strict mode
- [pyyaml-env-tag GitHub](https://github.com/waylan/pyyaml-env-tag) - Clean implementation reference
- [Python YAML configuration with environment variables parsing - DEV Community](https://dev.to/mkaranasou/python-yaml-configuration-with-environment-variables-parsing-2ha6) - Original pattern article
- [Python Load a yaml configuration file and resolve any environment variables - GitHub Gist](https://gist.github.com/mkaranasou/ba83e25c835a8f7629e34dd7ede01931) - Code reference

### Secondary (MEDIUM confidence)
- [envyaml PyPI](https://pypi.org/project/envyaml/) - Alternative library, pipe syntax for defaults
- [Variable Substitution in YAML Config pyyaml](https://ahmedzbyr.gitlab.io/python/var-sub-yaml-python/) - Implementation tutorial

### Tertiary (LOW confidence)
- Stack Overflow discussions on env var substitution patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - PyYAML + stdlib regex is well-established
- Architecture: HIGH - Post-parse substitution is canonical pattern
- Pitfalls: HIGH - Verified against multiple library implementations

**Research date:** 2026-01-31
**Valid until:** 90 days (stable domain, patterns don't change frequently)
