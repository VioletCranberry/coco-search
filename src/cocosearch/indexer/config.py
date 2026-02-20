"""Configuration module for cocosearch indexer."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# CocoIndex built-in language patterns
# See https://cocoindex.io/docs/ops/functions#supported-languages
_BASE_INCLUDE_PATTERNS = [
    "*.c",
    "*.cpp",
    "*.cc",
    "*.cxx",
    "*.h",
    "*.hpp",
    "*.cs",
    "*.css",
    "*.scss",
    "*.dtd",
    "*.f",
    "*.f90",
    "*.f95",
    "*.f03",
    "*.go",
    "*.html",
    "*.htm",
    "*.java",
    "*.js",
    "*.json",
    "*.kt",
    "*.kts",
    "*.md",
    "*.mdx",
    "*.pas",
    "*.dpr",
    "*.php",
    "*.py",
    "*.r",
    "*.rb",
    "*.rs",
    "*.scala",
    "*.groovy",
    "*.gradle",
    "*.sol",
    "*.sql",
    "*.swift",
    "*.toml",
    "*.tsx",
    "*.ts",
    "*.xml",
    "*.yaml",
    "*.yml",
]


def _default_include_patterns() -> list[str]:
    """Build include patterns by merging base patterns with handler-derived patterns.

    Collects patterns from:
    - Language handlers: EXTENSIONS converted to globs (e.g., ".hcl" -> "*.hcl")
                         plus INCLUDE_PATTERNS if defined (e.g., Dockerfile patterns)
    - Grammar handlers: file extensions extracted from PATH_PATTERNS (e.g., "**/*.tf" -> "*.tf")
    """
    from cocosearch.handlers import get_registered_handlers, get_registered_grammars

    patterns = set(_BASE_INCLUDE_PATTERNS)

    # Collect from language handlers
    for handler in get_registered_handlers():
        for ext in handler.EXTENSIONS:
            patterns.add(f"*{ext}")
        # Support INCLUDE_PATTERNS for non-extension patterns (e.g., Dockerfile)
        if hasattr(handler, "INCLUDE_PATTERNS"):
            patterns.update(handler.INCLUDE_PATTERNS)

    # Collect from grammar handlers (extract file extensions from PATH_PATTERNS)
    for handler in get_registered_grammars():
        for pattern in handler.PATH_PATTERNS:
            basename = os.path.basename(pattern)
            _, ext = os.path.splitext(basename)
            if ext:
                patterns.add(f"*{ext}")

    return sorted(patterns)


class IndexingConfig(BaseModel):
    """Configuration for code indexing."""

    include_patterns: list[str] = Field(default_factory=_default_include_patterns)
    exclude_patterns: list[str] = []
    chunk_size: int = 1000  # bytes
    chunk_overlap: int = 300  # bytes


def load_config(codebase_path: str) -> IndexingConfig:
    """Load indexing configuration from .cocosearch.yaml if present.

    Args:
        codebase_path: Path to the codebase root directory.

    Returns:
        IndexingConfig with values from config file or defaults.
    """
    config_path = Path(codebase_path) / ".cocosearch.yaml"

    if not config_path.exists():
        return IndexingConfig()

    try:
        with open(config_path, "r") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}

        indexing_data = data.get("indexing", {})
        if not isinstance(indexing_data, dict):
            return IndexingConfig()

        return IndexingConfig(**indexing_data)
    except (yaml.YAMLError, TypeError, ValueError):
        # Malformed config, return defaults
        return IndexingConfig()
