"""Tests for cocosearch.indexer.config module."""

import pytest
import yaml

from cocosearch.indexer.config import IndexingConfig, load_config


class TestIndexingConfig:
    """Tests for IndexingConfig defaults."""

    def test_default_include_patterns_contains_python(self):
        """Default include_patterns should contain *.py."""
        config = IndexingConfig()
        assert "*.py" in config.include_patterns

    def test_default_include_patterns_contains_common_languages(self):
        """Default include_patterns should contain common language patterns."""
        config = IndexingConfig()
        expected = ["*.py", "*.js", "*.ts", "*.go", "*.rs"]
        for pattern in expected:
            assert pattern in config.include_patterns

    def test_default_chunk_size(self):
        """Default chunk_size should be 1000."""
        config = IndexingConfig()
        assert config.chunk_size == 1000

    def test_default_chunk_overlap(self):
        """Default chunk_overlap should be 300."""
        config = IndexingConfig()
        assert config.chunk_overlap == 300

    def test_default_exclude_patterns_empty(self):
        """Default exclude_patterns should be empty list."""
        config = IndexingConfig()
        assert config.exclude_patterns == []


class TestLoadConfig:
    """Tests for load_config function."""

    def test_returns_defaults_when_no_config(self, tmp_path):
        """Returns IndexingConfig with defaults when .cocosearch.yaml missing."""
        config = load_config(str(tmp_path))

        assert isinstance(config, IndexingConfig)
        assert "*.py" in config.include_patterns
        assert config.chunk_size == 1000

    def test_loads_from_yaml(self, tmp_path):
        """Loads settings from .cocosearch.yaml file."""
        config_content = {
            "indexing": {
                "include_patterns": ["*.py", "*.js"],
                "chunk_size": 500,
            }
        }
        (tmp_path / ".cocosearch.yaml").write_text(yaml.dump(config_content))

        config = load_config(str(tmp_path))

        assert config.include_patterns == ["*.py", "*.js"]
        assert config.chunk_size == 500

    def test_returns_defaults_on_malformed_yaml(self, tmp_path):
        """Returns defaults when YAML is malformed."""
        # Write invalid YAML (duplicate key at same level causes issues)
        (tmp_path / ".cocosearch.yaml").write_text(": invalid yaml content :")

        config = load_config(str(tmp_path))

        assert isinstance(config, IndexingConfig)
        assert "*.py" in config.include_patterns

    def test_merges_partial_config(self, tmp_path):
        """Partial YAML config merges with defaults."""
        # Only specify chunk_size, leave include_patterns to default
        config_content = {
            "indexing": {
                "chunk_size": 2000,
            }
        }
        (tmp_path / ".cocosearch.yaml").write_text(yaml.dump(config_content))

        config = load_config(str(tmp_path))

        # chunk_size from file
        assert config.chunk_size == 2000
        # include_patterns from defaults
        assert "*.py" in config.include_patterns

    def test_handles_empty_yaml(self, tmp_path):
        """Returns defaults when YAML file is empty."""
        (tmp_path / ".cocosearch.yaml").write_text("")

        config = load_config(str(tmp_path))

        assert isinstance(config, IndexingConfig)
        assert config.chunk_size == 1000

    def test_handles_non_dict_indexing_value(self, tmp_path):
        """Returns defaults when indexing key is not a dict."""
        config_content = {"indexing": "not a dict"}
        (tmp_path / ".cocosearch.yaml").write_text(yaml.dump(config_content))

        config = load_config(str(tmp_path))

        assert isinstance(config, IndexingConfig)
        assert config.chunk_size == 1000
