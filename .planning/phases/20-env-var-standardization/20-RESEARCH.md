# Phase 20: Env Var Standardization - Research

**Researched:** 2026-02-01
**Domain:** Python environment variable management and validation
**Confidence:** HIGH

## Summary

This phase standardizes CocoSearch environment variables to use consistent `COCOSEARCH_*` prefix, replacing the current inconsistent naming (`COCOINDEX_DATABASE_URL`, `OLLAMA_HOST`). The research covers Python best practices for environment variable validation, CLI integration patterns, error messaging, and migration documentation.

**Current state:** The codebase uses two environment variables inconsistently:
- `COCOINDEX_DATABASE_URL` - PostgreSQL connection string (legacy naming from CocoIndex dependency)
- `OLLAMA_HOST` - Ollama API endpoint (generic naming, no prefix)

**Target state:** All environment variables use `COCOSEARCH_*` prefix:
- `COCOSEARCH_DATABASE_URL` - Replaces `COCOINDEX_DATABASE_URL`
- `COCOSEARCH_OLLAMA_URL` - Replaces `OLLAMA_HOST` (also standardizes naming from HOST to URL)

The codebase already has sophisticated config resolution infrastructure (Phase 19) with `ConfigResolver` supporting CLI > env > config > default precedence. This phase adds startup validation and a `config check` command.

**Primary recommendation:** Use Python's built-in capabilities (os.getenv with validation) for required environment variable checking at startup, add a lightweight `config check` subcommand to the existing CLI structure, and document the migration with a complete mapping table in a new CHANGELOG.md file.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| os.getenv | stdlib | Read environment variables | Built-in Python, universally supported, no dependencies |
| argparse | stdlib | CLI argument parsing | Already used throughout cocosearch.cli, standard library |
| pydantic | 2.x | Type validation and settings | Already a dependency, provides BaseSettings for env var validation |
| rich | >=13.0.0 | Terminal output formatting | Already used for CLI output, consistent with existing UX |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-settings | 2.x (included with pydantic) | Environment variable validation with type safety | Optional - for more complex validation scenarios (not needed for this phase) |
| python-dotenv | Latest | Load .env files | NOT NEEDED - CocoSearch doesn't auto-load .env, users manage their own environment |

### Current Stack Analysis
CocoSearch already uses:
- `os.getenv()` and `os.environ.get()` for reading env vars (5+ locations)
- `argparse` for CLI commands (comprehensive subcommand structure)
- `pydantic` BaseModel for config validation (CocoSearchConfig schema)
- `ConfigResolver` for precedence resolution (CLI > env > config > default)
- `rich.Console` for formatted output

**Installation:** No new dependencies required - all needed libraries already installed.

## Architecture Patterns

### Recommended Validation Structure
```
src/cocosearch/
├── config/
│   ├── env_validation.py    # New: Startup env var validation
│   ├── resolver.py           # Existing: Precedence resolution
│   └── schema.py             # Existing: Pydantic config schema
└── cli.py                    # Modified: Add config check command
```

### Pattern 1: Fail-Fast Startup Validation
**What:** Validate all required environment variables before any work begins, collecting all errors and presenting them together.

**When to use:** At application startup (before calling `cocoindex.init()`, before database connections).

**Example:**
```python
# Source: Python environment variable best practices 2026
import os
from typing import NamedTuple

class EnvVarError(NamedTuple):
    var_name: str
    hint: str

def validate_required_env_vars() -> list[EnvVarError]:
    """Validate required environment variables.

    Returns:
        List of missing variables with hints (empty if all present).
    """
    errors = []

    # Check DATABASE_URL
    if not os.getenv("COCOSEARCH_DATABASE_URL"):
        errors.append(EnvVarError(
            var_name="COCOSEARCH_DATABASE_URL",
            hint="Missing COCOSEARCH_DATABASE_URL. See .env.example for format."
        ))

    # OLLAMA_URL is optional (has default), no validation needed

    return errors

def check_env_or_exit(console) -> None:
    """Validate environment and exit with error message if invalid."""
    errors = validate_required_env_vars()
    if errors:
        console.print("[bold red]Environment configuration errors:[/bold red]")
        for error in errors:
            console.print(f"  - {error.hint}")
        console.print("\n[dim]Run 'cocosearch config check' to validate configuration.[/dim]")
        sys.exit(1)
```

### Pattern 2: Config Check Command
**What:** Lightweight CLI command that validates environment variables and shows their current values/sources without connecting to infrastructure.

**When to use:** User troubleshooting, CI/CD validation, pre-flight checks.

**Example:**
```python
# Source: Python CLI validation pattern 2026
def config_check_command(args: argparse.Namespace) -> int:
    """Validate environment and configuration without connecting to services.

    Returns:
        Exit code (0 for valid, 1 for errors).
    """
    from rich.table import Table

    console = Console()

    # Validate without connecting to database/Ollama
    errors = validate_required_env_vars()

    if errors:
        console.print("[bold red]Environment configuration errors:[/bold red]")
        for error in errors:
            console.print(f"  - {error.hint}")
        return 1

    # Show current configuration
    console.print("[green]✓ All required environment variables are set[/green]\n")

    table = Table(title="Environment Variables")
    table.add_column("Variable", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Source", style="dim")

    # Check DATABASE_URL
    db_url = os.getenv("COCOSEARCH_DATABASE_URL")
    if db_url:
        # Mask password in display
        masked = mask_password(db_url)
        table.add_row("COCOSEARCH_DATABASE_URL", masked, "environment")

    # Check OLLAMA_URL
    ollama_url = os.getenv("COCOSEARCH_OLLAMA_URL", "http://localhost:11434")
    source = "environment" if "COCOSEARCH_OLLAMA_URL" in os.environ else "default"
    table.add_row("COCOSEARCH_OLLAMA_URL", ollama_url, source)

    console.print(table)
    return 0
```

### Pattern 3: Default Value Handling
**What:** Provide sensible defaults for optional environment variables, document required vs optional clearly.

**When to use:** For variables that can have reasonable defaults (Ollama URL, not database URL).

**Example:**
```python
# Source: Existing cocosearch pattern (embedder.py)
def get_ollama_url() -> str:
    """Get Ollama URL with default fallback.

    Returns:
        Ollama URL from environment or default localhost:11434.
    """
    return os.getenv("COCOSEARCH_OLLAMA_URL", "http://localhost:11434")

def get_database_url() -> str:
    """Get database URL, raising error if not set.

    Returns:
        Database URL from environment.

    Raises:
        ValueError: If COCOSEARCH_DATABASE_URL not set.
    """
    url = os.getenv("COCOSEARCH_DATABASE_URL")
    if not url:
        raise ValueError(
            "Missing COCOSEARCH_DATABASE_URL. "
            "Set this environment variable to your PostgreSQL connection string. "
            "See .env.example for format."
        )
    return url
```

### Anti-Patterns to Avoid
- **Silent defaults for required variables:** Never silently default `DATABASE_URL` to localhost - require explicit configuration
- **Fail-on-first-error:** Show ALL missing variables together, not one at a time (frustrating UX)
- **Validation during connection:** Validate early at startup, not when first connecting to database/Ollama
- **Auto-loading .env files:** CocoSearch follows 12-factor app principles - users manage their environment explicitly

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password masking in URLs | Custom regex for postgresql:// parsing | `urllib.parse.urlparse()` + replace password component | Handles edge cases (special chars, IPv6, ports) |
| Environment variable type conversion | Custom string parsing for booleans/ints | Existing `ConfigResolver.parse_env_value()` | Already handles bool/int/float/list with proper error handling |
| Configuration precedence | New precedence system | Existing `ConfigResolver` class | Phase 19 already implements CLI > env > config > default |
| CLI subcommand structure | New argparse patterns | Existing cli.py subcommand pattern | Consistent with `config show`, `config path` structure |

**Key insight:** The codebase already has excellent infrastructure from Phase 19. This phase is primarily search-and-replace for variable names plus adding validation and documentation, not building new systems.

## Common Pitfalls

### Pitfall 1: Breaking Existing Users Without Migration Guide
**What goes wrong:** Users upgrade, application fails with "COCOSEARCH_DATABASE_URL not set" with no explanation of why their existing `COCOINDEX_DATABASE_URL` stopped working.

**Why it happens:** Breaking changes without prominent documentation and migration path.

**How to avoid:**
- Create CHANGELOG.md file with complete old → new mapping table
- Error messages include hint about checking .env.example
- Document in README Environment Variables section
- Update all MCP configuration examples in README

**Warning signs:**
- No CHANGELOG.md file exists yet
- README examples show old variable names
- docker-compose.yml uses old variable names
- MCP configs in README use old variable names

### Pitfall 2: Validation Too Late in Startup Sequence
**What goes wrong:** Application validates `DATABASE_URL` only when first connecting to database, after doing other work (loading config, parsing args, etc.). Error message appears mid-execution.

**Why it happens:** Lazy validation - checking variables when used rather than at startup.

**How to avoid:**
- Call `check_env_or_exit()` early in each command function (index, search, list, etc.)
- Before `cocoindex.init()` which reads COCOSEARCH_DATABASE_URL
- Before any database operations
- Show all missing variables together in one error message

**Warning signs:**
- Different commands fail at different points
- Error messages appear after progress output starts
- Users see partial execution before failure

### Pitfall 3: Hardcoded Default Database URL
**What goes wrong:** Setting a default like `postgresql://localhost:5432/cocosearch` makes it unclear whether database is actually configured or just using default.

**Why it happens:** Trying to make application "just work" without configuration.

**How to avoid:**
- DATABASE_URL is REQUIRED - no default value
- .env.example shows the default value users should copy
- Error message explicitly tells users to set the variable
- Documentation makes clear distinction: required vs optional with defaults

**Warning signs:**
- Application connects to localhost database without user configuring it
- Unclear whether user set DATABASE_URL or it's using default
- Different behavior between documented default and actual default

### Pitfall 4: Inconsistent Naming Conventions
**What goes wrong:** Using `COCOSEARCH_OLLAMA_HOST` instead of `COCOSEARCH_OLLAMA_URL` creates inconsistency with `DATABASE_URL`.

**Why it happens:** Preserving old naming patterns (OLLAMA_HOST) rather than standardizing.

**How to avoid:**
- Use `*_URL` suffix for all endpoint/connection variables
- `COCOSEARCH_DATABASE_URL` - PostgreSQL connection
- `COCOSEARCH_OLLAMA_URL` - Ollama API endpoint
- Both follow same pattern: [PREFIX]_[SERVICE]_URL

**Warning signs:**
- Mix of `*_HOST` and `*_URL` suffixes
- Inconsistent variable name patterns
- Documentation uses different naming than code

## Code Examples

Verified patterns from the codebase and research:

### Environment Variable Access Pattern
```python
# Source: cocosearch/search/db.py (current pattern, needs updating)
import os

def get_database_url() -> str:
    """Get database URL from environment.

    Returns:
        PostgreSQL connection URL.

    Raises:
        ValueError: If COCOSEARCH_DATABASE_URL is not set.
    """
    conninfo = os.getenv("COCOSEARCH_DATABASE_URL")
    if not conninfo:
        raise ValueError(
            "Missing COCOSEARCH_DATABASE_URL. "
            "Set this environment variable to your PostgreSQL connection string. "
            "See .env.example for format."
        )
    return conninfo

def get_ollama_url() -> str:
    """Get Ollama URL from environment or use default.

    Returns:
        Ollama API URL (defaults to localhost:11434).
    """
    return os.getenv("COCOSEARCH_OLLAMA_URL", "http://localhost:11434")
```

### Password Masking for Display
```python
# Source: Python best practices - URL parsing
from urllib.parse import urlparse, urlunparse

def mask_password(url: str) -> str:
    """Mask password in database URL for display.

    Args:
        url: Full URL potentially containing password.

    Returns:
        URL with password replaced by '***'.

    Examples:
        >>> mask_password("postgresql://user:pass123@host:5432/db")
        'postgresql://user:***@host:5432/db'
    """
    parsed = urlparse(url)
    if parsed.password:
        # Replace password component with ***
        netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
        return urlunparse(parsed._replace(netloc=netloc))
    return url
```

### Startup Validation Integration
```python
# Source: Python CLI startup pattern 2026
def index_command(args: argparse.Namespace) -> int:
    """Execute the index command."""
    console = Console()

    # Validate environment BEFORE any work
    check_env_or_exit(console)

    # ... rest of command implementation
    cocoindex.init()  # Now safe - DATABASE_URL validated above
    # ...
```

### Config Check Command
```python
# Source: CLI pattern from cli.py (existing config subcommands)
def config_check_command(args: argparse.Namespace) -> int:
    """Execute the config check command.

    Validates environment variables without connecting to services.
    Lightweight check for troubleshooting and CI/CD validation.

    Returns:
        Exit code (0 for valid, 1 for errors).
    """
    console = Console()

    # Validate required variables
    errors = validate_required_env_vars()

    if errors:
        console.print("[bold red]Environment configuration errors:[/bold red]")
        for error in errors:
            console.print(f"  - {error.hint}")
        console.print("\n[dim]See .env.example for configuration format.[/dim]")
        return 1

    # Show success + current values
    console.print("[green]✓ All required environment variables are set[/green]\n")

    # Display current environment variables
    from rich.table import Table

    table = Table(title="Environment Variables")
    table.add_column("Variable", style="cyan")
    table.add_column("Value", style="white")
    table.add_column("Source", style="dim")

    # DATABASE_URL (required)
    db_url = os.getenv("COCOSEARCH_DATABASE_URL")
    table.add_row(
        "COCOSEARCH_DATABASE_URL",
        mask_password(db_url),
        "environment"
    )

    # OLLAMA_URL (optional with default)
    ollama_url = os.getenv("COCOSEARCH_OLLAMA_URL")
    if ollama_url:
        table.add_row("COCOSEARCH_OLLAMA_URL", ollama_url, "environment")
    else:
        table.add_row(
            "COCOSEARCH_OLLAMA_URL",
            "http://localhost:11434",
            "default"
        )

    console.print(table)
    console.print("\n[dim]Configuration is valid and ready to use.[/dim]")
    return 0
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Allow environment variable access from workflow code | Block by default with allowlist | n8n 2.0 (Dec 2025) | Security-first: explicit allowlist instead of exposing all env vars |
| Expose all env vars to webpack bundle | Allowlist with prefix filter | Shakapacker 9.5.0 (Jan 2026) | Only `SHAKAPACKER_PUBLIC_*` exposed by default, preventing secret leaks |
| Fail-on-first validation error | Collect and show all errors | Python best practice 2026 | Better UX - users fix all issues at once |
| Auto-load .env files | Explicit environment management | 12-factor app principles | Clear separation of config from code |

**Deprecated/outdated:**
- **pydantic-settings for simple env vars:** For CocoSearch's simple case (2 env vars, both strings), pydantic-settings adds unnecessary complexity. Use `os.getenv()` with validation.
- **python-dotenv auto-loading:** Modern Python apps follow 12-factor principles - users manage environment explicitly (docker-compose, systemd, shell rc files).

## Open Questions

No significant open questions - this is a well-understood domain with clear patterns.

The phase is straightforward:
1. Search-and-replace variable names in code
2. Add startup validation
3. Add `config check` command
4. Update documentation and examples
5. Create CHANGELOG with migration table

## Sources

### Primary (HIGH confidence)
- [Settings Management - Pydantic](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) - Official Pydantic settings documentation
- [argparse — Python stdlib](https://docs.python.org/3/library/argparse.html) - Official argparse documentation
- [PEP 8 – Style Guide for Python Code](https://peps.python.org/pep-0008/) - Official Python naming conventions
- Existing cocosearch codebase patterns (config/resolver.py, cli.py, search/db.py)

### Secondary (MEDIUM confidence)
- [Best Practices for Python Env Variables - Dagster](https://dagster.io/blog/python-environment-variables) - Environment variable validation best practices
- [Python Environment Variables - Codecademy](https://www.codecademy.com/article/python-environment-variables) - Standard patterns
- [CLI Design Patterns](https://cli-guide.readthedocs.io/en/latest/design/patterns.html) - Command-line interface patterns
- [n8n 2.0 breaking changes](https://docs.n8n.io/2-0-breaking-changes/) - Real-world example of env var migration (Dec 2025)
- [Shakapacker 9.5.0 security fix](https://github.com/brave-intl/publishers/pull/5151) - Environment variable allowlist pattern (Jan 2026)

### Tertiary (LOW confidence)
- None - all findings verified with official sources or existing code patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using stdlib (os, argparse) and existing dependencies (pydantic, rich)
- Architecture: HIGH - Based on existing codebase patterns and Python stdlib patterns
- Pitfalls: HIGH - Verified with recent real-world migrations (n8n, Shakapacker) and existing code

**Research date:** 2026-02-01
**Valid until:** 2026-03-01 (30 days - stable domain, Python stdlib doesn't change rapidly)
