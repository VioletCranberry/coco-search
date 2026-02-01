"""Environment variable validation for CocoSearch.

Provides fail-fast validation of required environment variables with
helpful error messages.
"""

import os
import sys
from typing import NamedTuple
from urllib.parse import urlparse, urlunparse

from rich.console import Console


class EnvVarError(NamedTuple):
    """Environment variable validation error."""

    var_name: str
    hint: str


def validate_required_env_vars() -> list[EnvVarError]:
    """Validate required environment variables.

    Checks that all required environment variables are set and returns
    a list of errors for any that are missing.

    Returns:
        List of EnvVarError for missing variables (empty if all valid).
    """
    errors: list[EnvVarError] = []

    # Check COCOSEARCH_DATABASE_URL (required)
    if not os.getenv("COCOSEARCH_DATABASE_URL"):
        errors.append(
            EnvVarError(
                var_name="COCOSEARCH_DATABASE_URL",
                hint="Missing COCOSEARCH_DATABASE_URL. See .env.example for format.",
            )
        )

    # COCOSEARCH_OLLAMA_URL is optional (has default), so don't validate it

    return errors


def check_env_or_exit(console: Console) -> None:
    """Check required environment variables and exit if any are missing.

    Args:
        console: Rich console for formatted output.
    """
    errors = validate_required_env_vars()
    if errors:
        console.print("[bold red]Environment configuration errors:[/bold red]")
        for error in errors:
            console.print(f"  - {error.hint}")
        console.print("[dim]Run 'cocosearch config check' for details.[/dim]")
        sys.exit(1)


def mask_password(url: str) -> str:
    """Mask password in URL for safe display.

    Args:
        url: URL string (e.g., postgresql://user:pass@host:5432/db).

    Returns:
        URL with password replaced by *** (e.g., postgresql://user:***@host:5432/db).
        Returns unchanged if URL has no password or is invalid.
    """
    try:
        parsed = urlparse(url)
        if parsed.password:
            # Replace password in netloc
            netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
            # Reconstruct URL with masked password
            masked = parsed._replace(netloc=netloc)
            return urlunparse(masked)
        return url
    except Exception:
        # If parsing fails, return unchanged (better to show something than crash)
        return url
