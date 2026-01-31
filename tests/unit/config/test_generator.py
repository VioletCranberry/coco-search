"""Tests for config generator module."""

import pytest
import yaml

from cocosearch.config import CONFIG_TEMPLATE, ConfigError, generate_config


def test_generate_config_creates_file(tmp_path):
    """Test that generate_config creates a file with the template."""
    config_path = tmp_path / "cocosearch.yaml"

    generate_config(config_path)

    assert config_path.exists()
    assert config_path.read_text() == CONFIG_TEMPLATE


def test_generate_config_fails_if_exists(tmp_path):
    """Test that generate_config raises ConfigError if file exists."""
    config_path = tmp_path / "cocosearch.yaml"
    config_path.write_text("existing content")

    with pytest.raises(ConfigError) as exc_info:
        generate_config(config_path)

    assert "already exists" in str(exc_info.value)


def test_config_template_is_valid_yaml():
    """Test that CONFIG_TEMPLATE parses as valid YAML."""
    # Parse the template (comments are preserved but ignored by YAML parser)
    data = yaml.safe_load(CONFIG_TEMPLATE)

    # Template has all fields commented, so parsed data should be minimal
    # (only non-commented sections like empty indexing/search/embedding)
    assert data is not None
    assert "indexing" in data
    assert "search" in data
    assert "embedding" in data
