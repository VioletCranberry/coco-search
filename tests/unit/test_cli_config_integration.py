"""Tests for CLI config integration and precedence."""

import os
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cocosearch.cli import config_path_command, config_show_command, main


class TestConfigCommands:
    """Test config subcommands."""

    def test_config_show_displays_table(self, capsys):
        """Test that config show command displays a table."""
        # Mock args
        args = MagicMock()

        # Run command
        exit_code = config_show_command(args)

        # Verify success
        assert exit_code == 0

        # Capture output
        captured = capsys.readouterr()

        # Verify table headers present
        assert "KEY" in captured.out
        assert "VALUE" in captured.out
        assert "SOURCE" in captured.out

        # Verify some config keys present
        assert "indexName" in captured.out
        assert "search.resultLimit" in captured.out

    def test_config_show_with_config_file(self, tmp_path, capsys):
        """Test config show with a config file loaded."""
        # Create test config
        config_file = tmp_path / "cocosearch.yaml"
        config_file.write_text("""
indexName: test-index
search:
  resultLimit: 25
""")

        # Mock find_config_file to return our test config
        with patch("cocosearch.cli.find_config_file", return_value=config_file):
            args = MagicMock()
            exit_code = config_show_command(args)

        assert exit_code == 0
        captured = capsys.readouterr()

        # Verify config values are shown
        assert "test-index" in captured.out
        assert "25" in captured.out

    def test_config_show_with_env_vars(self, capsys, monkeypatch):
        """Test config show with environment variables."""
        # Set env vars
        monkeypatch.setenv("COCOSEARCH_INDEX_NAME", "from-env")
        monkeypatch.setenv("COCOSEARCH_SEARCH_RESULT_LIMIT", "50")

        args = MagicMock()
        exit_code = config_show_command(args)

        assert exit_code == 0
        captured = capsys.readouterr()

        # Verify env values shown with source
        assert "from-env" in captured.out
        assert "50" in captured.out
        # Env var names may be truncated in table display
        assert "env:COCOSEARCH_INDEX_N" in captured.out
        assert "env:COCOSEARCH_SEARCH_" in captured.out

    def test_config_path_with_config(self, tmp_path, capsys):
        """Test config path command when config exists."""
        config_file = tmp_path / "cocosearch.yaml"
        config_file.write_text("indexName: test")

        with patch("cocosearch.cli.find_config_file", return_value=config_file):
            args = MagicMock()
            exit_code = config_path_command(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        # Path should be in output (may have ANSI codes or line breaks)
        output_cleaned = captured.out.replace("\n", "").replace("\r", "")
        assert "cocosearch.yaml" in output_cleaned

    def test_config_path_without_config(self, capsys):
        """Test config path command when no config found."""
        with patch("cocosearch.cli.find_config_file", return_value=None):
            args = MagicMock()
            exit_code = config_path_command(args)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "No config file found" in captured.out

    def test_config_show_with_validation_error(self, tmp_path, capsys):
        """Test config show with invalid config file."""
        config_file = tmp_path / "cocosearch.yaml"
        config_file.write_text("invalid: {yaml structure")

        with patch("cocosearch.cli.find_config_file", return_value=config_file):
            args = MagicMock()
            exit_code = config_show_command(args)

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Configuration error" in captured.out


class TestHelpText:
    """Test help text includes config metadata."""

    def test_index_help_shows_config_metadata(self):
        """Test that index command help shows config keys and env vars."""
        with patch.object(sys, "argv", ["cocosearch", "index", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        # Help causes exit 0
        assert exc_info.value.code == 0

    def test_index_help_contains_config_keys(self, capsys):
        """Test index help contains [config: X] annotations."""
        with patch.object(sys, "argv", ["cocosearch", "index", "--help"]):
            try:
                main()
            except SystemExit:
                pass

        captured = capsys.readouterr()
        # Help text may wrap, so check for key components
        output = captured.out.replace("\n", " ")  # Remove line breaks for easier matching
        assert "[config: indexName]" in output
        assert "COCOSEARCH_INDEX_NAME" in output
        assert "[config: indexing.includePatterns]" in output
        assert "COCOSEARCH_INDEXING_INCLUDE_PATTERNS" in output

    def test_search_help_contains_config_keys(self, capsys):
        """Test search help contains [config: X] annotations."""
        with patch.object(sys, "argv", ["cocosearch", "search", "--help"]):
            try:
                main()
            except SystemExit:
                pass

        captured = capsys.readouterr()
        # Help text may wrap across lines
        output = captured.out
        # Check that config annotations appear (may be split across lines)
        assert "config:" in output and "indexName" in output
        assert "COCOSEARCH_INDEX_NAME" in output
        assert "config:" in output and "search.resultLimit" in output
        assert "COCOSEARCH_SEARCH_RESULT_LIMIT" in output
        assert "config:" in output and "search.minScore" in output
        assert "COCOSEARCH_SEARCH_MIN_SCORE" in output


class TestPrecedenceIntegration:
    """Test precedence chain in index and search commands."""

    @patch("cocosearch.cli.run_index")
    @patch("cocosearch.cli.IndexingProgress")
    def test_index_cli_overrides_env(self, mock_progress, mock_run_index, tmp_path, monkeypatch):
        """Test that CLI flag overrides environment variable."""
        # Set env var
        monkeypatch.setenv("COCOSEARCH_INDEX_NAME", "from-env")

        # Create test directory
        test_dir = tmp_path / "test_repo"
        test_dir.mkdir()

        # Mock run_index return value
        mock_run_index.return_value = MagicMock(stats={})

        with patch.object(sys, "argv", ["cocosearch", "index", str(test_dir), "--name", "from-cli"]):
            with patch("cocosearch.cli.find_config_file", return_value=None):
                try:
                    main()
                except SystemExit:
                    pass

        # Verify run_index was called with CLI value
        mock_run_index.assert_called_once()
        assert mock_run_index.call_args[1]["index_name"] == "from-cli"

    @patch("cocosearch.cli.run_index")
    @patch("cocosearch.cli.IndexingProgress")
    def test_index_env_overrides_config(self, mock_progress, mock_run_index, tmp_path, monkeypatch):
        """Test that environment variable overrides config file."""
        # Set env var
        monkeypatch.setenv("COCOSEARCH_INDEX_NAME", "from-env")

        # Create test config
        config_file = tmp_path / "cocosearch.yaml"
        config_file.write_text("indexName: from-config")

        # Create test directory
        test_dir = tmp_path / "test_repo"
        test_dir.mkdir()

        # Mock run_index return value
        mock_run_index.return_value = MagicMock(stats={})

        with patch.object(sys, "argv", ["cocosearch", "index", str(test_dir)]):
            with patch("cocosearch.cli.find_config_file", return_value=config_file):
                try:
                    main()
                except SystemExit:
                    pass

        # Verify run_index was called with env value
        mock_run_index.assert_called_once()
        assert mock_run_index.call_args[1]["index_name"] == "from-env"

    @patch("cocosearch.cli.run_index")
    @patch("cocosearch.cli.IndexingProgress")
    def test_index_config_overrides_default(self, mock_progress, mock_run_index, tmp_path):
        """Test that config file overrides default."""
        # Create test config
        config_file = tmp_path / "cocosearch.yaml"
        config_file.write_text("indexName: from-config")

        # Create test directory
        test_dir = tmp_path / "test_repo"
        test_dir.mkdir()

        # Mock run_index return value
        mock_run_index.return_value = MagicMock(stats={})

        with patch.object(sys, "argv", ["cocosearch", "index", str(test_dir)]):
            with patch("cocosearch.cli.find_config_file", return_value=config_file):
                try:
                    main()
                except SystemExit:
                    pass

        # Verify run_index was called with config value
        mock_run_index.assert_called_once()
        assert mock_run_index.call_args[1]["index_name"] == "from-config"

    @patch("cocoindex.init")
    @patch("cocosearch.cli.search")
    def test_search_limit_precedence(self, mock_search, mock_cocoindex_init, tmp_path, monkeypatch):
        """Test search limit precedence chain."""
        # Set env var
        monkeypatch.setenv("COCOSEARCH_SEARCH_RESULT_LIMIT", "30")

        # Create test config
        config_file = tmp_path / "cocosearch.yaml"
        config_file.write_text("""
search:
  resultLimit: 20
""")

        # Mock search return
        mock_search.return_value = []

        # Test CLI override
        with patch.object(sys, "argv", ["cocosearch", "search", "--limit", "40", "test query"]):
            with patch("cocosearch.cli.find_config_file", return_value=config_file):
                try:
                    main()
                except SystemExit:
                    pass

        # Verify search was called with CLI value (40)
        mock_search.assert_called_once()
        assert mock_search.call_args[1]["limit"] == 40

        # Reset mock
        mock_search.reset_mock()

        # Test env overrides config (no CLI flag)
        with patch.object(sys, "argv", ["cocosearch", "search", "test query"]):
            with patch("cocosearch.cli.find_config_file", return_value=config_file):
                try:
                    main()
                except SystemExit:
                    pass

        # Verify search was called with env value (30)
        mock_search.assert_called_once()
        assert mock_search.call_args[1]["limit"] == 30

    @patch("cocoindex.init")
    @patch("cocosearch.cli.search")
    def test_search_min_score_precedence(self, mock_search, mock_cocoindex_init, tmp_path, monkeypatch):
        """Test search min_score precedence chain."""
        # Set env var
        monkeypatch.setenv("COCOSEARCH_SEARCH_MIN_SCORE", "0.6")

        # Mock search return
        mock_search.return_value = []

        # Test env value used
        with patch.object(sys, "argv", ["cocosearch", "search", "test query"]):
            with patch("cocosearch.cli.find_config_file", return_value=None):
                try:
                    main()
                except SystemExit:
                    pass

        # Verify search was called with env value
        mock_search.assert_called_once()
        assert mock_search.call_args[1]["min_score"] == 0.6


class TestConfigRouting:
    """Test config command routing."""

    def test_config_show_routing(self, capsys):
        """Test that 'coco config show' routes correctly."""
        with patch.object(sys, "argv", ["cocosearch", "config", "show"]):
            try:
                main()
            except SystemExit as e:
                assert e.code == 0

        captured = capsys.readouterr()
        assert "KEY" in captured.out

    def test_config_path_routing(self, capsys):
        """Test that 'coco config path' routes correctly."""
        with patch.object(sys, "argv", ["cocosearch", "config", "path"]):
            with patch("cocosearch.cli.find_config_file", return_value=None):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0

        captured = capsys.readouterr()
        assert "No config file found" in captured.out
