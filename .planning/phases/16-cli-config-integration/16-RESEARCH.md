# Phase 16: CLI Config Integration - Research

**Researched:** 2026-01-31
**Domain:** CLI argument parsing with config file and environment variable precedence
**Confidence:** HIGH

## Summary

This phase implements CLI flags that override config file settings with a clear precedence chain: CLI > env var > config file > default. The existing codebase uses argparse with Rich for output formatting and Pydantic for config validation. The user decisions in CONTEXT.md specify: camelCase flag names with dot notation for nested values (e.g., `--indexing.chunkSize`), environment variables following `COCOSEARCH_SECTION_KEY` pattern, and a new `coco config` subcommand group for inspection.

The standard approach is to build on the existing argparse-based CLI while adding a custom precedence resolution layer. Rather than adopting a third-party library like ConfigArgParse (which would require refactoring the entire CLI), the recommended pattern is to: (1) use `os.environ.get()` for environment variable defaults, (2) apply `parser.set_defaults()` from loaded config, and (3) let CLI args naturally override through argparse's precedence. The `coco config show` command will use Rich Tables to display effective configuration with source attribution.

**Primary recommendation:** Extend the existing argparse CLI with a custom help formatter that shows config/env equivalents, and add a config resolution layer that applies precedence before command execution.

## Standard Stack

The established libraries/tools for this domain:

### Core (Already in Project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| argparse | stdlib | CLI argument parsing | Standard Python CLI library, already in use |
| pydantic | 2.12.5 | Config validation | Already used for CocoSearchConfig schema |
| pydantic-settings | 2.12.0 | Settings with env/CLI support | Already available via cocoindex dependency |
| rich | 13.0.0+ | Terminal formatting | Already used for console output |
| pyyaml | 6.0.2+ | YAML config loading | Already used for cocosearch.yaml |

### Supporting (No New Dependencies Needed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| os | stdlib | Environment variable access | `os.environ.get()` for env var resolution |
| difflib | stdlib | Fuzzy matching | Already used for typo suggestions |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual argparse extension | ConfigArgParse | Would require rewriting entire CLI; not worth it for existing codebase |
| Manual precedence | pydantic-settings CLI | Has native cli_parse_args but requires BaseSettings; our config is BaseModel |
| Custom help formatter | rich-argparse | Adds dependency; manual approach is simpler for our specific help format |

**Installation:**
No new dependencies required. All tools already available.

## Architecture Patterns

### Recommended Project Structure
```
src/cocosearch/
├── cli.py                    # Extend with config override logic
├── config/
│   ├── __init__.py
│   ├── schema.py            # CocoSearchConfig (existing)
│   ├── loader.py            # load_config (existing)
│   ├── errors.py            # ConfigError (existing)
│   ├── generator.py         # generate_config (existing)
│   └── resolver.py          # NEW: ConfigResolver for precedence
└── cli/
    └── config_cmd.py        # NEW: coco config show/path commands
```

### Pattern 1: Layered Configuration Resolution
**What:** Resolve config values through a clear precedence chain before command execution.
**When to use:** Any command that uses config values.
**Example:**
```python
# Source: Standard precedence pattern from Python CLI best practices
class ConfigResolver:
    """Resolve config values with CLI > env > config > default precedence."""

    def __init__(self, config: CocoSearchConfig):
        self.config = config
        self._sources: dict[str, str] = {}  # Track where each value came from

    def resolve(self,
                field_path: str,        # e.g., "indexing.chunkSize"
                cli_value: Any | None,  # From argparse
                env_var: str,           # e.g., "COCOSEARCH_INDEXING_CHUNK_SIZE"
                ) -> tuple[Any, str]:   # (value, source)
        """Return (resolved_value, source_description)."""

        # Priority 1: CLI flag
        if cli_value is not None:
            return cli_value, "CLI flag"

        # Priority 2: Environment variable
        env_value = os.environ.get(env_var)
        if env_value is not None:
            return self._parse_env_value(env_value, field_path), f"env:{env_var}"

        # Priority 3: Config file
        config_value = self._get_nested(field_path)
        if config_value is not None:
            return config_value, f"config:{self.config_path}"

        # Priority 4: Default
        return self._get_default(field_path), "default"
```

### Pattern 2: Custom Help Formatter for Config Info
**What:** Extend argparse's help to show config equivalents and env var names.
**When to use:** All arguments that have config file equivalents.
**Example:**
```python
# Source: argparse documentation + custom extension
class ConfigAwareHelpFormatter(argparse.HelpFormatter):
    """Help formatter that shows config file and env var equivalents."""

    def _get_help_string(self, action):
        help_text = action.help or ""

        # Add config key info if present
        if hasattr(action, 'config_key'):
            help_text += f" [config: {action.config_key}]"

        # Add env var info if present
        if hasattr(action, 'env_var'):
            help_text += f" [env: {action.env_var}]"

        # Add current effective value if available
        if hasattr(action, 'current_value') and hasattr(action, 'current_source'):
            help_text += f" [current: {action.current_value} from {action.current_source}]"

        return help_text
```

### Pattern 3: Config Subcommand Group
**What:** Add `coco config show` and `coco config path` for configuration inspection.
**When to use:** Debugging "why is this value what it is?" scenarios.
**Example:**
```python
# Source: Rich Tables documentation
from rich.table import Table

def show_command(args: argparse.Namespace) -> int:
    """Display effective configuration with sources."""
    console = Console()
    resolver = load_resolved_config()

    table = Table(title="Effective Configuration")
    table.add_column("KEY", style="cyan", no_wrap=True)
    table.add_column("VALUE", style="magenta")
    table.add_column("SOURCE", style="green")

    for key, (value, source) in resolver.all_values():
        table.add_row(key, str(value), source)

    console.print(table)
    return 0
```

### Anti-Patterns to Avoid
- **Mixing precedence in commands:** Don't have different commands with different precedence rules. All commands should use the same ConfigResolver.
- **Hardcoding env var names:** Define env var patterns from config keys systematically (`COCOSEARCH_` + section + `_` + key in UPPER_SNAKE_CASE).
- **Silent fallback:** Always track and report where values come from for debuggability.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Env var parsing for types | Custom type coercion | Pydantic field validators | Handle int, float, bool, list consistently |
| Help text formatting | String concatenation | argparse formatter_class | Consistent formatting, proper wrapping |
| Table output | Manual print() | Rich Table | Handles terminal width, alignment, styling |
| Config path display | os.path manipulation | pathlib.Path | Cross-platform, cleaner API |
| Nested field access | Manual dict drilling | getattr chain or operator.attrgetter | Handles missing keys gracefully |

**Key insight:** The existing codebase already uses Rich and Pydantic. Leverage their capabilities rather than building parallel solutions.

## Common Pitfalls

### Pitfall 1: Environment Variable Type Coercion
**What goes wrong:** Env vars are always strings. `COCOSEARCH_INDEXING_CHUNK_SIZE=1000` needs to become `int(1000)`.
**Why it happens:** Forgetting that env vars don't carry type information.
**How to avoid:** Parse env var values through the same Pydantic validators used for config files. Use field type hints to determine coercion.
**Warning signs:** TypeError when passing env var values to functions expecting ints/floats.

### Pitfall 2: List/Array Values in Environment Variables
**What goes wrong:** `COCOSEARCH_INDEXING_INCLUDE_PATTERNS="*.py,*.js"` - how to parse this?
**Why it happens:** No standard format for list values in env vars.
**How to avoid:** Per CONTEXT.md "Claude's Discretion" - recommend JSON format for complex types: `'["*.py", "*.js"]'` or comma-separated for simple cases.
**Warning signs:** Users expecting `a,b,c` to work but getting a single string.

### Pitfall 3: Partial Config Override
**What goes wrong:** User sets `--indexing.chunkSize=500` but expects other indexing fields to still come from config.
**Why it happens:** Confusion between "override one field" vs "replace entire section".
**How to avoid:** Per CONTEXT.md decision: "Complete replacement: CLI flag replaces config entirely (no merging for lists)". Each field is resolved independently.
**Warning signs:** Users complaining that other fields "reset to defaults".

### Pitfall 4: Help Text Clutter
**What goes wrong:** Help becomes unreadable with too much metadata per argument.
**Why it happens:** Adding [config:...] [env:...] [current:...] to every argument.
**How to avoid:** Keep inline notes concise. Use `coco config show` for detailed inspection. Only show current value for flags that have non-default values.
**Warning signs:** Help output exceeds one screen for simple command.

### Pitfall 5: Config Path Resolution in Help
**What goes wrong:** Help shows "current: X from ./cocosearch.yaml" but config was actually in git root.
**Why it happens:** Not using `find_config_file()` consistently.
**How to avoid:** Always use the same config discovery logic. Store resolved path once.
**Warning signs:** Inconsistent path reporting between commands.

## Code Examples

Verified patterns from official sources and project codebase:

### Environment Variable Name Generation
```python
# Source: CONTEXT.md decision on env var naming
def config_key_to_env_var(config_key: str) -> str:
    """Convert config key to environment variable name.

    Examples:
        "indexName" -> "COCOSEARCH_INDEX_NAME"
        "indexing.chunkSize" -> "COCOSEARCH_INDEXING_CHUNK_SIZE"
    """
    # Split on dots for nested keys
    parts = config_key.split(".")

    # Convert camelCase to UPPER_SNAKE_CASE
    def camel_to_snake(s: str) -> str:
        import re
        return re.sub(r'(?<!^)(?=[A-Z])', '_', s).upper()

    env_parts = [camel_to_snake(p) for p in parts]
    return "COCOSEARCH_" + "_".join(env_parts)
```

### Argument with Config Metadata
```python
# Source: argparse documentation + custom extension
def add_config_argument(
    parser: argparse.ArgumentParser,
    *flags: str,
    config_key: str,
    help: str,
    **kwargs
) -> None:
    """Add argument with config and env var metadata for help text."""
    env_var = config_key_to_env_var(config_key)

    # Build help string with metadata
    full_help = f"{help} [config: {config_key}] [env: {env_var}]"

    action = parser.add_argument(*flags, help=full_help, **kwargs)
    # Store metadata for later use
    action.config_key = config_key
    action.env_var = env_var
```

### Config Show Table
```python
# Source: Rich Tables documentation
from rich.console import Console
from rich.table import Table

def display_config(resolver: ConfigResolver) -> None:
    """Display resolved configuration as table."""
    console = Console()

    table = Table(title="Effective Configuration")
    table.add_column("KEY", justify="left", style="cyan", no_wrap=True)
    table.add_column("VALUE", style="magenta")
    table.add_column("SOURCE", justify="right", style="dim")

    # Iterate all config fields
    for field_path in resolver.all_field_paths():
        value, source = resolver.get_resolved(field_path)
        table.add_row(
            field_path,
            _format_value(value),
            source
        )

    console.print(table)

def _format_value(value: Any) -> str:
    """Format value for display."""
    if isinstance(value, list):
        if not value:
            return "[]"
        return ", ".join(str(v) for v in value)
    return str(value) if value is not None else "(not set)"
```

### Parsing Environment Variable Values
```python
# Source: Pydantic validators + standard type coercion
import json
from typing import Any, get_origin, get_args

def parse_env_value(raw: str, field_type: type) -> Any:
    """Parse environment variable string to appropriate type."""
    origin = get_origin(field_type)

    # Handle None/Optional
    if raw.lower() in ("", "null", "none"):
        return None

    # Handle list types
    if origin is list:
        try:
            # Try JSON array first
            return json.loads(raw)
        except json.JSONDecodeError:
            # Fall back to comma-separated
            return [s.strip() for s in raw.split(",")]

    # Handle basic types
    if field_type is bool:
        return raw.lower() in ("true", "1", "yes")
    if field_type is int:
        return int(raw)
    if field_type is float:
        return float(raw)

    return raw
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| argparse only | argparse + config file | Phase 15 | Users can set defaults in config |
| Manual env handling | Pydantic-settings | pydantic-settings 2.0+ | Native CLI parsing available |
| ConfigArgParse | pydantic-settings | 2023-2024 | Type-safe config with validation |

**Deprecated/outdated:**
- ConfigArgParse: Still works but pydantic-settings offers better type safety
- fromfile_prefix_chars: Argparse's built-in file loading is limited compared to YAML config

**Note on pydantic-settings:** While pydantic-settings 2.12.0 has native `cli_parse_args` support, the existing CocoSearchConfig uses `BaseModel` not `BaseSettings`. Migrating would require restructuring the config module. The recommended approach for this phase is to keep `BaseModel` and build a lightweight precedence resolver on top, avoiding a major refactor.

## Open Questions

Things that couldn't be fully resolved:

1. **Exact env var format for lists**
   - What we know: JSON arrays work (`'["*.py", "*.js"]'`), comma-separated is ambiguous
   - What's unclear: Should we support both formats? What about escaped commas?
   - Recommendation: Support JSON format only for lists. Document this clearly. Keep it simple.

2. **Help text verbosity balance**
   - What we know: User wants "information-dense but scannable" help
   - What's unclear: Exact format for `[current: value from source]` - always show? Only for non-defaults?
   - Recommendation: Show current value only when it differs from default, and only in verbose mode (`--verbose`)

3. **Error handling when CLI overrides bad config**
   - What we know: Per CONTEXT.md "CLI rescues config errors: if CLI provides valid override, ignore bad config value"
   - What's unclear: What if config has error in field A but user overrides field B?
   - Recommendation: Load config with best-effort parsing. Only fail on errors in fields not overridden by CLI.

## Sources

### Primary (HIGH confidence)
- Python argparse documentation - HelpFormatter customization, format specifiers
- Rich Tables documentation - Table API, styling, columns
- Existing codebase: `/Users/fedorzhdanov/GIT/personal/coco-s/src/cocosearch/cli.py` - current CLI structure
- Existing codebase: `/Users/fedorzhdanov/GIT/personal/coco-s/src/cocosearch/config/` - current config schema

### Secondary (MEDIUM confidence)
- [ConfigArgParse GitHub](https://github.com/bw2/ConfigArgParse) - precedence pattern: CLI > env > config > defaults
- [rich-argparse GitHub](https://github.com/hamdanal/rich-argparse) - help formatter customization patterns
- [Pydantic Settings docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) - CLI parsing, source priority
- [LabEx argparse defaults](https://labex.io/tutorials/python-how-to-set-argparse-default-values-451017) - set_defaults patterns

### Tertiary (LOW confidence)
- Web search results for "Python CLI config precedence" - general patterns confirmed by multiple sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - using only existing dependencies, patterns verified in codebase
- Architecture: HIGH - patterns directly based on argparse/Rich docs and existing CLI structure
- Pitfalls: MEDIUM - based on common CLI issues, some from web search

**Research date:** 2026-01-31
**Valid until:** 60 days (stable domain, argparse/Rich are mature)
