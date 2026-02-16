"""Configuration module for CocoSearch."""

from .env_validation import (
    DEFAULT_DATABASE_URL,
    get_database_url,
    mask_password,
    validate_required_env_vars,
)
from .errors import format_validation_errors, suggest_field_name
from .generator import CONFIG_TEMPLATE, generate_config
from .loader import find_config_file, load_config
from .resolver import ConfigResolver, config_key_to_env_var, parse_env_value
from .schema import (
    CocoSearchConfig,
    ConfigError,
    EmbeddingSection,
    IndexingSection,
    SearchSection,
)

__all__ = [
    "CocoSearchConfig",
    "ConfigError",
    "EmbeddingSection",
    "IndexingSection",
    "SearchSection",
    "find_config_file",
    "load_config",
    "format_validation_errors",
    "suggest_field_name",
    "generate_config",
    "CONFIG_TEMPLATE",
    "ConfigResolver",
    "config_key_to_env_var",
    "parse_env_value",
    "validate_required_env_vars",
    "mask_password",
    "DEFAULT_DATABASE_URL",
    "get_database_url",
]
