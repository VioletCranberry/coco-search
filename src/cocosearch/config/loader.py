"""Configuration file loading for CocoSearch."""

import subprocess
from pathlib import Path

import yaml
from pydantic import ValidationError

from .env_substitution import substitute_env_vars
from .errors import format_validation_errors
from .schema import CocoSearchConfig, ConfigError


def find_config_file() -> Path | None:
    """Find cocosearch.yaml in current directory or git root.

    Returns:
        Path to config file, or None if not found.
    """
    # Check current working directory first
    cwd_config = Path.cwd() / "cocosearch.yaml"
    if cwd_config.exists():
        return cwd_config

    # Try git root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_root = Path(result.stdout.strip())
        git_config = git_root / "cocosearch.yaml"
        if git_config.exists():
            return git_config
    except subprocess.CalledProcessError:
        # Not in a git repository, that's fine
        pass

    return None


def load_config(path: Path | None = None) -> CocoSearchConfig:
    """Load configuration from YAML file.

    Supports environment variable substitution in config values:
    - ${VAR} - Required env var, raises ConfigError if not set
    - ${VAR:-default} - Env var with default value if not set

    Args:
        path: Optional path to config file. If None, searches for cocosearch.yaml.

    Returns:
        CocoSearchConfig instance with loaded or default values.

    Raises:
        ConfigError: If YAML is invalid, validation fails, or required env vars missing.
    """
    if path is None:
        path = find_config_file()

    # No config file found, return defaults
    if path is None:
        return CocoSearchConfig()

    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        # Handle empty file
        if data is None:
            return CocoSearchConfig()

        # Substitute environment variables
        data, missing_vars = substitute_env_vars(data)
        if missing_vars:
            raise ConfigError(
                f"Missing required environment variables in {path}: "
                f"{', '.join(sorted(missing_vars))}"
            )

        # Validate with Pydantic
        try:
            return CocoSearchConfig.model_validate(data)
        except ValidationError as e:
            # Format validation errors with typo suggestions
            formatted_message = format_validation_errors(e, path)
            raise ConfigError(formatted_message) from e

    except yaml.YAMLError as e:
        # Extract line and column information if available
        if hasattr(e, "problem_mark"):
            mark = e.problem_mark
            raise ConfigError(
                f"Invalid YAML syntax in {path} at line {mark.line + 1}, "
                f"column {mark.column + 1}: {e.problem}"
            ) from e
        else:
            raise ConfigError(f"Invalid YAML syntax in {path}: {e}") from e
    except OSError as e:
        raise ConfigError(f"Failed to read config file {path}: {e}") from e
