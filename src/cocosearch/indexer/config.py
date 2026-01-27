"""Configuration module for cocosearch indexer."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class IndexingConfig(BaseModel):
    """Configuration for code indexing."""

    # See also https://cocoindex.io/docs/ops/functions#supported-languages
    include_patterns: list[str] = [
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
        "*.sol",
        "*.sql",
        "*.swift",
        "*.toml",
        "*.tsx",
        "*.ts",
        "*.xml",
        "*.yaml",
        "*.yml",
        # DevOps files (HCL/Terraform)
        "*.tf",
        "*.hcl",
        "*.tfvars",
        # DevOps files (Dockerfile)
        "Dockerfile",
        "Dockerfile.*",
        "Containerfile",
        # DevOps files (Bash/Shell)
        "*.sh",
        "*.bash",
    ]
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
