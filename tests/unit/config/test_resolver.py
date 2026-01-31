"""Unit tests for config resolver precedence logic."""

import os
from pathlib import Path

import pytest

from cocosearch.config import CocoSearchConfig
from cocosearch.config.resolver import (
    ConfigResolver,
    config_key_to_env_var,
    parse_env_value,
)


class TestConfigKeyToEnvVar:
    """Test environment variable name generation."""

    def test_simple_field(self):
        """Test simple root-level field conversion."""
        assert config_key_to_env_var("indexName") == "COCOSEARCH_INDEX_NAME"

    def test_nested_field(self):
        """Test nested field with dot notation."""
        assert config_key_to_env_var("indexing.chunkSize") == "COCOSEARCH_INDEXING_CHUNK_SIZE"

    def test_deeply_nested_field(self):
        """Test deeply nested field conversion."""
        assert config_key_to_env_var("search.resultLimit") == "COCOSEARCH_SEARCH_RESULT_LIMIT"

    def test_camel_case_conversion(self):
        """Test camelCase to UPPER_SNAKE_CASE conversion."""
        assert config_key_to_env_var("includePatterns") == "COCOSEARCH_INCLUDE_PATTERNS"
        assert config_key_to_env_var("indexing.excludePatterns") == "COCOSEARCH_INDEXING_EXCLUDE_PATTERNS"


class TestParseEnvValue:
    """Test environment variable value parsing."""

    def test_parse_int(self):
        """Test integer parsing."""
        assert parse_env_value("100", int) == 100
        assert parse_env_value("0", int) == 0
        assert parse_env_value("-50", int) == -50

    def test_parse_float(self):
        """Test float parsing."""
        assert parse_env_value("0.5", float) == 0.5
        assert parse_env_value("1.0", float) == 1.0
        assert parse_env_value("-0.3", float) == -0.3

    def test_parse_bool_true(self):
        """Test boolean true parsing."""
        assert parse_env_value("true", bool) is True
        assert parse_env_value("True", bool) is True
        assert parse_env_value("1", bool) is True
        assert parse_env_value("yes", bool) is True
        assert parse_env_value("YES", bool) is True

    def test_parse_bool_false(self):
        """Test boolean false parsing."""
        assert parse_env_value("false", bool) is False
        assert parse_env_value("False", bool) is False
        assert parse_env_value("0", bool) is False
        assert parse_env_value("no", bool) is False
        assert parse_env_value("NO", bool) is False

    def test_parse_list_json(self):
        """Test list parsing from JSON."""
        assert parse_env_value('["*.py", "*.js"]', list[str]) == ["*.py", "*.js"]
        assert parse_env_value('["rust", "python"]', list[str]) == ["rust", "python"]

    def test_parse_list_comma_fallback(self):
        """Test list parsing with comma fallback."""
        assert parse_env_value("*.py,*.js", list[str]) == ["*.py", "*.js"]
        assert parse_env_value("rust,python,go", list[str]) == ["rust", "python", "go"]

    def test_parse_string(self):
        """Test string parsing (pass-through)."""
        assert parse_env_value("hello", str) == "hello"
        assert parse_env_value("nomic-embed-text", str) == "nomic-embed-text"

    def test_parse_none_indicators(self):
        """Test None value indicators."""
        assert parse_env_value("", str) is None
        assert parse_env_value("null", str) is None
        assert parse_env_value("none", str) is None
        assert parse_env_value("None", str) is None


class TestConfigResolver:
    """Test ConfigResolver precedence logic."""

    def test_cli_value_takes_precedence(self, monkeypatch):
        """Test CLI flag value overrides all other sources."""
        # Set up config with indexName
        config = CocoSearchConfig(indexName="config-value")
        resolver = ConfigResolver(config, config_path=Path("/path/to/config.yaml"))

        # Set environment variable
        monkeypatch.setenv("COCOSEARCH_INDEX_NAME", "env-value")

        # CLI value should win
        value, source = resolver.resolve(
            "indexName",
            cli_value="cli-value",
            env_var="COCOSEARCH_INDEX_NAME"
        )

        assert value == "cli-value"
        assert source == "CLI flag"

    def test_env_value_over_config(self, monkeypatch):
        """Test env var overrides config file."""
        config = CocoSearchConfig(indexName="config-value")
        resolver = ConfigResolver(config, config_path=Path("/path/to/config.yaml"))

        monkeypatch.setenv("COCOSEARCH_INDEX_NAME", "env-value")

        value, source = resolver.resolve(
            "indexName",
            cli_value=None,
            env_var="COCOSEARCH_INDEX_NAME"
        )

        assert value == "env-value"
        assert source == "env:COCOSEARCH_INDEX_NAME"

    def test_config_value_over_default(self):
        """Test config file value overrides default."""
        config = CocoSearchConfig(indexName="config-value")
        resolver = ConfigResolver(config, config_path=Path("/path/to/config.yaml"))

        value, source = resolver.resolve(
            "indexName",
            cli_value=None,
            env_var="COCOSEARCH_INDEX_NAME"
        )

        assert value == "config-value"
        assert source == "config:/path/to/config.yaml"

    def test_default_value_fallback(self):
        """Test default value when no other source provides value."""
        config = CocoSearchConfig()  # No indexName set
        resolver = ConfigResolver(config)

        value, source = resolver.resolve(
            "indexName",
            cli_value=None,
            env_var="COCOSEARCH_INDEX_NAME"
        )

        assert value is None  # Default for optional field
        assert source == "default"

    def test_nested_field_resolution(self, monkeypatch):
        """Test resolution of nested config fields."""
        config = CocoSearchConfig()
        resolver = ConfigResolver(config)

        # Test CLI override for nested field
        value, source = resolver.resolve(
            "indexing.chunkSize",
            cli_value=2000,
            env_var="COCOSEARCH_INDEXING_CHUNK_SIZE"
        )

        assert value == 2000
        assert source == "CLI flag"

    def test_nested_field_env_parsing(self, monkeypatch):
        """Test env var parsing for nested integer field."""
        config = CocoSearchConfig()
        resolver = ConfigResolver(config)

        monkeypatch.setenv("COCOSEARCH_INDEXING_CHUNK_SIZE", "2500")

        value, source = resolver.resolve(
            "indexing.chunkSize",
            cli_value=None,
            env_var="COCOSEARCH_INDEXING_CHUNK_SIZE"
        )

        assert value == 2500
        assert isinstance(value, int)
        assert source == "env:COCOSEARCH_INDEXING_CHUNK_SIZE"

    def test_nested_field_config_value(self):
        """Test config value for nested field."""
        config = CocoSearchConfig()
        config.indexing.chunkSize = 1500
        resolver = ConfigResolver(config, config_path=Path("/path/to/config.yaml"))

        value, source = resolver.resolve(
            "indexing.chunkSize",
            cli_value=None,
            env_var="COCOSEARCH_INDEXING_CHUNK_SIZE"
        )

        assert value == 1500
        assert source == "config:/path/to/config.yaml"

    def test_nested_field_default(self):
        """Test default value for nested field."""
        config = CocoSearchConfig()
        resolver = ConfigResolver(config)

        value, source = resolver.resolve(
            "indexing.chunkSize",
            cli_value=None,
            env_var="COCOSEARCH_INDEXING_CHUNK_SIZE"
        )

        assert value == 1000  # Default from schema
        assert source == "default"

    def test_list_field_from_env(self, monkeypatch):
        """Test list field parsing from environment."""
        config = CocoSearchConfig()
        resolver = ConfigResolver(config)

        monkeypatch.setenv("COCOSEARCH_INDEXING_LANGUAGES", '["rust", "python"]')

        value, source = resolver.resolve(
            "indexing.languages",
            cli_value=None,
            env_var="COCOSEARCH_INDEXING_LANGUAGES"
        )

        assert value == ["rust", "python"]
        assert source == "env:COCOSEARCH_INDEXING_LANGUAGES"

    def test_float_field_from_env(self, monkeypatch):
        """Test float field parsing from environment."""
        config = CocoSearchConfig()
        resolver = ConfigResolver(config)

        monkeypatch.setenv("COCOSEARCH_SEARCH_MIN_SCORE", "0.7")

        value, source = resolver.resolve(
            "search.minScore",
            cli_value=None,
            env_var="COCOSEARCH_SEARCH_MIN_SCORE"
        )

        assert value == 0.7
        assert isinstance(value, float)
        assert source == "env:COCOSEARCH_SEARCH_MIN_SCORE"

    def test_config_path_in_source_when_provided(self):
        """Test that config path appears in source when provided."""
        config = CocoSearchConfig(indexName="test")
        resolver = ConfigResolver(config, config_path=Path("/custom/path/coco.yaml"))

        value, source = resolver.resolve(
            "indexName",
            cli_value=None,
            env_var="COCOSEARCH_INDEX_NAME"
        )

        assert source == "config:/custom/path/coco.yaml"

    def test_config_source_without_path(self):
        """Test config source when no path provided."""
        config = CocoSearchConfig(indexName="test")
        resolver = ConfigResolver(config)

        value, source = resolver.resolve(
            "indexName",
            cli_value=None,
            env_var="COCOSEARCH_INDEX_NAME"
        )

        assert source == "config"

    def test_all_field_paths(self):
        """Test listing all resolvable field paths."""
        config = CocoSearchConfig()
        resolver = ConfigResolver(config)

        paths = resolver.all_field_paths()

        # Check that key paths are present
        assert "indexName" in paths
        assert "indexing.chunkSize" in paths
        assert "indexing.chunkOverlap" in paths
        assert "indexing.includePatterns" in paths
        assert "indexing.excludePatterns" in paths
        assert "indexing.languages" in paths
        assert "search.resultLimit" in paths
        assert "search.minScore" in paths
        assert "embedding.model" in paths

        # Should have at least these 9 fields
        assert len(paths) >= 9
