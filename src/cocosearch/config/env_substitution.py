"""Environment variable substitution for config data structures."""

import os
import re
from typing import Any

# Pattern matches ${VAR} and ${VAR:-default}
ENV_VAR_PATTERN = re.compile(r"\$\{([^}^{]+)\}")


def substitute_env_vars(data: Any) -> tuple[Any, list[str]]:
    """Substitute environment variables in config data structure.

    Supports:
    - ${VAR} - Required env var, kept as-is if missing (added to missing list)
    - ${VAR:-default} - Env var with default value (never missing)

    Args:
        data: Parsed YAML data (dict, list, or scalar)

    Returns:
        Tuple of (substituted_data, list_of_missing_vars)

    Examples:
        >>> os.environ["MY_VAR"] = "hello"
        >>> substitute_env_vars("${MY_VAR}")
        ('hello', [])

        >>> substitute_env_vars("${UNDEFINED:-fallback}")
        ('fallback', [])
    """
    missing: list[str] = []

    def _substitute_in_string(value: str) -> str:
        """Replace ${VAR} patterns in a string."""

        def replacer(match: re.Match) -> str:
            expr = match.group(1)

            # Handle ${VAR:-default} syntax
            if ":-" in expr:
                var_name, default = expr.split(":-", 1)
                return os.environ.get(var_name, default)

            # Handle ${VAR} syntax - required variable
            var_name = expr
            env_value = os.environ.get(var_name)
            if env_value is None:
                missing.append(var_name)
                return match.group(0)  # Keep original placeholder
            return env_value

        return ENV_VAR_PATTERN.sub(replacer, value)

    def _recurse(data: Any) -> Any:
        """Recursively process data structure."""
        if isinstance(data, str):
            return _substitute_in_string(data)
        elif isinstance(data, dict):
            return {k: _recurse(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [_recurse(item) for item in data]
        return data

    result = _recurse(data)
    # Deduplicate missing vars while preserving order
    seen = set()
    unique_missing = []
    for var in missing:
        if var not in seen:
            seen.add(var)
            unique_missing.append(var)

    return result, unique_missing
