"""Configuration resolver with CLI > env > config > default precedence."""

import json
import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .schema import CocoSearchConfig


def config_key_to_env_var(config_key: str) -> str:
    """Convert config key to environment variable name.

    Args:
        config_key: Config key in dot.notation.camelCase format

    Returns:
        Environment variable name in COCOSEARCH_UPPER_SNAKE_CASE format

    Examples:
        >>> config_key_to_env_var("indexName")
        'COCOSEARCH_INDEX_NAME'
        >>> config_key_to_env_var("indexing.chunkSize")
        'COCOSEARCH_INDEXING_CHUNK_SIZE'
    """
    # Split on dots for nested keys
    parts = config_key.split(".")

    # Convert each part from camelCase to snake_case
    snake_parts = []
    for part in parts:
        # Insert underscore before uppercase letters
        snake = re.sub(r'(?<!^)(?=[A-Z])', '_', part)
        snake_parts.append(snake.upper())

    # Join with underscores and add prefix
    return "COCOSEARCH_" + "_".join(snake_parts)


def parse_env_value(raw: str, field_type: type) -> Any:
    """Parse environment variable value to target type.

    Args:
        raw: Raw string value from environment
        field_type: Target type to parse to

    Returns:
        Parsed value in target type, or None for null indicators

    Examples:
        >>> parse_env_value("100", int)
        100
        >>> parse_env_value("true", bool)
        True
        >>> parse_env_value('["*.py"]', list[str])
        ['*.py']
    """
    # Handle None indicators
    if raw.lower() in ("", "null", "none"):
        return None

    # Get the origin type for generic types like list[str]
    origin = getattr(field_type, '__origin__', field_type)

    # Handle bool specially (before int, since bool is subclass of int)
    if field_type is bool:
        return raw.lower() in ("true", "1", "yes")

    # Handle int
    if field_type is int:
        return int(raw)

    # Handle float
    if field_type is float:
        return float(raw)

    # Handle list
    if origin is list:
        # Try JSON parse first
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback to comma-separated
        return [item.strip() for item in raw.split(",")]

    # Default: return as string
    return raw


class ConfigResolver:
    """Resolves config values with CLI > env > config > default precedence.

    This class implements the precedence resolution logic for configuration
    values from multiple sources.

    Precedence order (highest to lowest):
    1. CLI flag value
    2. Environment variable
    3. Config file value
    4. Default value from schema

    Each resolution includes source tracking for debugging and transparency.
    """

    def __init__(self, config: CocoSearchConfig, config_path: Path | None = None):
        """Initialize resolver with config and optional path.

        Args:
            config: Loaded configuration object
            config_path: Path to config file (for source tracking)
        """
        self.config = config
        self.config_path = config_path

    def resolve(
        self,
        field_path: str,
        cli_value: Any | None,
        env_var: str
    ) -> tuple[Any, str]:
        """Resolve config value through precedence chain.

        Args:
            field_path: Dot-notation path to field (e.g., "indexing.chunkSize")
            cli_value: Value from CLI flag (None if not provided)
            env_var: Environment variable name to check

        Returns:
            Tuple of (resolved_value, source_description)

        Examples:
            >>> resolver.resolve("indexName", "cli-val", "COCOSEARCH_INDEX_NAME")
            ('cli-val', 'CLI flag')
        """
        # Priority 1: CLI flag
        if cli_value is not None:
            return cli_value, "CLI flag"

        # Priority 2: Environment variable
        env_value = os.environ.get(env_var)
        if env_value is not None:
            field_type = self._get_field_type(field_path)
            parsed_value = parse_env_value(env_value, field_type)
            return parsed_value, f"env:{env_var}"

        # Priority 3: Config file
        config_value = self._get_config_value(field_path)
        default_value = self._get_default_value(field_path)

        # Check if config value differs from default (meaning it was explicitly set)
        if config_value != default_value:
            source = f"config:{self.config_path}" if self.config_path else "config"
            return config_value, source

        # Priority 4: Default
        return default_value, "default"

    def _get_config_value(self, field_path: str) -> Any:
        """Get value from config object using dot notation.

        Args:
            field_path: Dot-notation path to field

        Returns:
            Value from config, or None if not found
        """
        parts = field_path.split(".")
        current = self.config

        for part in parts:
            if not hasattr(current, part):
                return None
            current = getattr(current, part)

        return current

    def _get_field_type(self, field_path: str) -> type:
        """Get type hint for field from Pydantic model.

        Args:
            field_path: Dot-notation path to field

        Returns:
            Type of the field
        """
        parts = field_path.split(".")
        current_model = CocoSearchConfig

        # Navigate through nested models
        for i, part in enumerate(parts):
            field_info = current_model.model_fields.get(part)
            if not field_info:
                return str  # Default to str if field not found

            # If not the last part, get the nested model type
            if i < len(parts) - 1:
                current_model = field_info.annotation
            else:
                # Last part - return the field type
                return field_info.annotation

        return str

    def _get_default_value(self, field_path: str) -> Any:
        """Get default value from Pydantic model.

        Args:
            field_path: Dot-notation path to field

        Returns:
            Default value for the field
        """
        parts = field_path.split(".")
        current_model = CocoSearchConfig

        # Navigate through nested models
        for i, part in enumerate(parts):
            field_info = current_model.model_fields.get(part)
            if not field_info:
                return None

            # If not the last part, get the nested model and its default
            if i < len(parts) - 1:
                nested_model = field_info.annotation
                # Get the default factory or default value
                if field_info.default_factory:
                    nested_default = field_info.default_factory()
                elif field_info.default is not None:
                    nested_default = field_info.default
                else:
                    nested_default = nested_model()

                current_model = field_info.annotation

                # For next iteration, we need to look at the nested model's fields
                # But we also need to return the actual default value from the instance
                if i == len(parts) - 2:
                    # Next is last, so get the field from nested default
                    final_part = parts[-1]
                    return getattr(nested_default, final_part)
            else:
                # Last part - return the default
                if field_info.default_factory:
                    return field_info.default_factory()
                return field_info.default

        return None

    def all_field_paths(self) -> list[str]:
        """Get list of all resolvable field paths.

        Returns:
            List of dot-notation field paths

        Examples:
            >>> resolver.all_field_paths()
            ['indexName', 'indexing.chunkSize', 'indexing.chunkOverlap', ...]
        """
        paths = []

        # Add root-level fields
        for field_name, field_info in CocoSearchConfig.model_fields.items():
            # Check if this is a nested model
            if isinstance(field_info.annotation, type) and issubclass(field_info.annotation, BaseModel):
                # Add nested fields
                nested_model = field_info.annotation
                for nested_field_name in nested_model.model_fields.keys():
                    paths.append(f"{field_name}.{nested_field_name}")
            else:
                # Add simple field
                paths.append(field_name)

        return sorted(paths)
