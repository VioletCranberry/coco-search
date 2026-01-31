"""Unit tests for config file loading."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from cocosearch.config import ConfigError, CocoSearchConfig, load_config
from cocosearch.config.loader import find_config_file


class TestFindConfigFile:
    """Test config file discovery."""

    def test_returns_none_when_no_config_exists(self, tmp_path, monkeypatch):
        """Test that find_config_file returns None when no config exists."""
        # Change to temp directory with no config
        monkeypatch.chdir(tmp_path)

        # Mock git to fail (not in a git repo)
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git")
            result = find_config_file()

        assert result is None

    def test_finds_config_in_cwd(self, tmp_path, monkeypatch):
        """Test that find_config_file finds config in current directory."""
        monkeypatch.chdir(tmp_path)

        # Create config in cwd
        config_file = tmp_path / "cocosearch.yaml"
        config_file.write_text("indexName: test")

        result = find_config_file()
        assert result == config_file

    def test_finds_config_in_git_root(self, tmp_path, monkeypatch):
        """Test that find_config_file finds config in git root."""
        # Set up directory structure:
        # git_root/
        #   cocosearch.yaml
        #   subdir/  <-- we'll be here
        git_root = tmp_path / "git_root"
        git_root.mkdir()
        subdir = git_root / "subdir"
        subdir.mkdir()

        monkeypatch.chdir(subdir)

        # Create config in git root (not in cwd)
        config_file = git_root / "cocosearch.yaml"
        config_file.write_text("indexName: test")

        # Mock git to return git_root
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = str(git_root) + "\n"
            mock_run.return_value = mock_result
            result = find_config_file()

        assert result == config_file

    def test_prefers_cwd_over_git_root(self, tmp_path, monkeypatch):
        """Test that cwd config takes precedence over git root config."""
        git_root = tmp_path / "git_root"
        git_root.mkdir()
        subdir = git_root / "subdir"
        subdir.mkdir()

        monkeypatch.chdir(subdir)

        # Create config in both locations
        git_config = git_root / "cocosearch.yaml"
        git_config.write_text("indexName: git-root")
        cwd_config = subdir / "cocosearch.yaml"
        cwd_config.write_text("indexName: cwd")

        # Should return cwd config without even calling git
        result = find_config_file()
        assert result == cwd_config

    def test_handles_git_error_gracefully(self, tmp_path, monkeypatch):
        """Test that git errors are handled gracefully (not in git repo)."""
        monkeypatch.chdir(tmp_path)

        # Mock git to raise CalledProcessError
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                128, "git", stderr="fatal: not a git repository"
            )
            result = find_config_file()

        assert result is None


class TestLoadConfig:
    """Test config loading and validation."""

    def test_returns_defaults_when_no_config_file(self, tmp_path, monkeypatch):
        """Test that load_config returns defaults when no config file exists."""
        monkeypatch.chdir(tmp_path)

        # Mock git to fail
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git")
            config = load_config()

        # Should return defaults
        assert isinstance(config, CocoSearchConfig)
        assert config.indexName is None
        assert config.indexing.chunkSize == 1000
        assert config.search.resultLimit == 10

    def test_parses_valid_yaml(self, tmp_path):
        """Test that load_config parses valid YAML correctly."""
        config_file = tmp_path / "cocosearch.yaml"
        config_file.write_text("""
indexName: my-index
indexing:
  chunkSize: 2000
  chunkOverlap: 500
search:
  resultLimit: 25
  minScore: 0.6
embedding:
  model: custom-model
""")

        config = load_config(config_file)
        assert config.indexName == "my-index"
        assert config.indexing.chunkSize == 2000
        assert config.indexing.chunkOverlap == 500
        assert config.search.resultLimit == 25
        assert config.search.minScore == 0.6
        assert config.embedding.model == "custom-model"

    def test_handles_empty_yaml_file(self, tmp_path):
        """Test that load_config handles empty YAML file."""
        config_file = tmp_path / "cocosearch.yaml"
        config_file.write_text("")

        config = load_config(config_file)
        # Should return defaults
        assert isinstance(config, CocoSearchConfig)
        assert config.indexName is None

    def test_handles_yaml_with_only_comments(self, tmp_path):
        """Test that load_config handles YAML with only comments."""
        config_file = tmp_path / "cocosearch.yaml"
        config_file.write_text("""
# This is a comment
# indexName: test
""")

        config = load_config(config_file)
        # Should return defaults
        assert isinstance(config, CocoSearchConfig)

    def test_raises_config_error_on_invalid_yaml_syntax(self, tmp_path):
        """Test that load_config raises ConfigError on invalid YAML syntax."""
        config_file = tmp_path / "cocosearch.yaml"
        config_file.write_text("""
indexName: test
  invalid indentation:
    this is broken
""")

        with pytest.raises(ConfigError) as exc_info:
            load_config(config_file)

        error_msg = str(exc_info.value)
        assert "Invalid YAML syntax" in error_msg
        assert str(config_file) in error_msg
        # Should include line/column information
        assert "line" in error_msg
        assert "column" in error_msg

    def test_raises_config_error_on_validation_error(self, tmp_path):
        """Test that load_config raises ConfigError on validation errors."""
        config_file = tmp_path / "cocosearch.yaml"
        # Invalid: chunkSize must be > 0
        config_file.write_text("""
indexing:
  chunkSize: 0
""")

        with pytest.raises(ConfigError) as exc_info:
            load_config(config_file)

        error_msg = str(exc_info.value)
        assert "Configuration validation failed" in error_msg

    def test_raises_config_error_on_unknown_field(self, tmp_path):
        """Test that load_config raises ConfigError on unknown field."""
        config_file = tmp_path / "cocosearch.yaml"
        config_file.write_text("""
unknownField: value
""")

        with pytest.raises(ConfigError) as exc_info:
            load_config(config_file)

        error_msg = str(exc_info.value)
        assert "Configuration validation failed" in error_msg

    def test_raises_config_error_on_type_mismatch(self, tmp_path):
        """Test that load_config raises ConfigError on type mismatch."""
        config_file = tmp_path / "cocosearch.yaml"
        # Invalid: chunkSize should be int, not string
        config_file.write_text("""
indexing:
  chunkSize: "not a number"
""")

        with pytest.raises(ConfigError) as exc_info:
            load_config(config_file)

        error_msg = str(exc_info.value)
        assert "Configuration validation failed" in error_msg

    def test_loads_partial_config(self, tmp_path):
        """Test that load_config works with partial configuration."""
        config_file = tmp_path / "cocosearch.yaml"
        config_file.write_text("""
indexName: partial-config
search:
  resultLimit: 30
""")

        config = load_config(config_file)
        assert config.indexName == "partial-config"
        assert config.search.resultLimit == 30
        # Other fields use defaults
        assert config.indexing.chunkSize == 1000
        assert config.embedding.model == "nomic-embed-text"

    def test_accepts_explicit_path(self, tmp_path):
        """Test that load_config accepts explicit path parameter."""
        # Create config in non-standard location
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        config_file = custom_dir / "my-config.yaml"
        config_file.write_text("""
indexName: custom-location
""")

        config = load_config(config_file)
        assert config.indexName == "custom-location"

    def test_raises_config_error_on_file_read_error(self, tmp_path):
        """Test that load_config raises ConfigError on file read errors."""
        # Try to load a file that doesn't exist
        config_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(ConfigError) as exc_info:
            load_config(config_file)

        error_msg = str(exc_info.value)
        assert "Failed to read config file" in error_msg
