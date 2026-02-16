"""Environment variable validation for CocoSearch.

Provides fail-fast validation of required environment variables with
helpful error messages.
"""

import os
from typing import NamedTuple
from urllib.parse import urlparse, urlunparse


DEFAULT_DATABASE_URL = "postgresql://cocosearch:cocosearch@localhost:5432/cocosearch"


class EnvVarError(NamedTuple):
    """Environment variable validation error."""

    var_name: str
    hint: str


def get_database_url() -> str:
    """Get database URL from environment or return default.

    Returns COCOSEARCH_DATABASE_URL if set, otherwise the default
    (postgresql://cocosearch:cocosearch@localhost:5432/cocosearch).

    Side effect: Sets COCOINDEX_DATABASE_URL in os.environ if not already
    set, bridging to the CocoIndex SDK which reads that variable.
    """
    url = os.getenv("COCOSEARCH_DATABASE_URL", DEFAULT_DATABASE_URL)
    # Bridge: CocoIndex SDK reads COCOINDEX_DATABASE_URL, not COCOSEARCH_*
    if not os.getenv("COCOINDEX_DATABASE_URL"):
        os.environ["COCOINDEX_DATABASE_URL"] = url
    return url


def validate_required_env_vars() -> list[EnvVarError]:
    """Validate required environment variables.

    Checks that all required environment variables are set and returns
    a list of errors for any that are missing.

    Returns:
        List of EnvVarError for missing variables (empty if all valid).
    """
    errors: list[EnvVarError] = []

    # DATABASE_URL now has a default, no longer required from environment
    # COCOSEARCH_OLLAMA_URL is optional (has default), so don't validate it

    return errors


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
