"""Configuration module for CocoSearch."""

from .env_validation import (
    DEFAULT_DATABASE_URL,
    get_database_url,
    mask_password,
    validate_required_env_vars,
)
from .errors import format_validation_errors, suggest_field_name
from .generator import (
    CLAUDE_MD_DUPLICATE_MARKER,
    CLAUDE_MD_ROUTING_SECTION,
    COCOSEARCH_MCP_TOOL_PERMISSIONS,
    CONFIG_TEMPLATE,
    check_claude_plugin_installed,
    generate_agents_md_routing,
    generate_claude_md_routing,
    generate_claude_settings,
    generate_config,
    generate_opencode_mcp_config,
    generate_opencode_skills,
    install_claude_plugin,
)
from .loader import find_config_file, load_config
from .resolver import ConfigResolver, config_key_to_env_var, parse_env_value
from .schema import (
    CocoSearchConfig,
    ConfigError,
    EmbeddingSection,
    IndexingSection,
    LoggingSection,
    SearchSection,
    VALID_EMBEDDING_PROVIDERS,
    default_model_for_provider,
)

__all__ = [
    "CocoSearchConfig",
    "ConfigError",
    "EmbeddingSection",
    "IndexingSection",
    "LoggingSection",
    "SearchSection",
    "find_config_file",
    "load_config",
    "format_validation_errors",
    "suggest_field_name",
    "generate_config",
    "generate_claude_md_routing",
    "generate_agents_md_routing",
    "generate_claude_settings",
    "generate_opencode_mcp_config",
    "generate_opencode_skills",
    "check_claude_plugin_installed",
    "install_claude_plugin",
    "CONFIG_TEMPLATE",
    "CLAUDE_MD_ROUTING_SECTION",
    "CLAUDE_MD_DUPLICATE_MARKER",
    "COCOSEARCH_MCP_TOOL_PERMISSIONS",
    "ConfigResolver",
    "config_key_to_env_var",
    "parse_env_value",
    "validate_required_env_vars",
    "mask_password",
    "DEFAULT_DATABASE_URL",
    "get_database_url",
    "VALID_EMBEDDING_PROVIDERS",
    "default_model_for_provider",
]
