"""Tests for config check command with connectivity checks."""

import json
import urllib.error

import pytest
import psycopg
from unittest.mock import patch, MagicMock

from cocosearch.cli import config_check_command, main


def _make_args():
    """Create a minimal args namespace for config_check_command."""
    import argparse

    return argparse.Namespace()


def _mock_tags_response(models=None):
    """Create a mock urlopen response for /api/tags."""
    if models is None:
        models = [{"name": "nomic-embed-text:latest"}]
    resp = MagicMock()
    resp.read.return_value = json.dumps({"models": models}).encode()
    return resp


class TestConfigCheckConnectivity:
    """Tests for connectivity checks in config_check_command."""

    def test_all_services_reachable_returns_zero(self, capsys):
        """Exit 0 and 'All checks passed' when all services are reachable."""
        mock_conn = MagicMock()
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect", return_value=mock_conn
        ):
            with patch(
                "cocosearch.indexer.preflight.urllib.request.urlopen",
                return_value=_mock_tags_response(),
            ):
                result = config_check_command(_make_args())

        assert result == 0
        output = capsys.readouterr().out
        assert "All checks passed" in output

    def test_postgres_unreachable_returns_one(self, capsys):
        """Exit 1 with remediation hint when PostgreSQL is unreachable."""
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect",
            side_effect=psycopg.OperationalError("connection refused"),
        ):
            with patch(
                "cocosearch.indexer.preflight.urllib.request.urlopen",
                return_value=_mock_tags_response(),
            ):
                result = config_check_command(_make_args())

        assert result == 1
        output = capsys.readouterr().out
        assert "unreachable" in output
        assert "docker compose up -d" in output

    def test_ollama_unreachable_skips_model_check(self, capsys, monkeypatch):
        """Exit 1, model check skipped when Ollama is unreachable."""
        monkeypatch.delenv("COCOSEARCH_EMBEDDING_PROVIDER", raising=False)
        monkeypatch.delenv("COCOSEARCH_EMBEDDING_API_KEY", raising=False)
        mock_conn = MagicMock()
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect", return_value=mock_conn
        ):
            with patch(
                "cocosearch.indexer.preflight.urllib.request.urlopen",
                side_effect=urllib.error.URLError("connection refused"),
            ):
                result = config_check_command(_make_args())

        assert result == 1
        output = capsys.readouterr().out
        assert "skipped" in output
        assert "--profile" in output

    def test_model_missing_returns_one(self, capsys, monkeypatch):
        """Exit 1 with 'ollama pull' hint when model is not found."""
        monkeypatch.delenv("COCOSEARCH_EMBEDDING_PROVIDER", raising=False)
        monkeypatch.delenv("COCOSEARCH_EMBEDDING_API_KEY", raising=False)
        mock_conn = MagicMock()
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect", return_value=mock_conn
        ):
            with patch(
                "cocosearch.indexer.preflight.urllib.request.urlopen",
                return_value=_mock_tags_response(models=[{"name": "llama3:latest"}]),
            ):
                result = config_check_command(_make_args())

        assert result == 1
        output = capsys.readouterr().out
        assert "not found" in output
        assert "ollama pull" in output

    def test_all_services_down_shows_all_failures(self, capsys, monkeypatch):
        """All failures shown (not just first) when everything is down."""
        monkeypatch.delenv("COCOSEARCH_EMBEDDING_PROVIDER", raising=False)
        monkeypatch.delenv("COCOSEARCH_EMBEDDING_API_KEY", raising=False)
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect",
            side_effect=psycopg.OperationalError("connection refused"),
        ):
            with patch(
                "cocosearch.indexer.preflight.urllib.request.urlopen",
                side_effect=urllib.error.URLError("connection refused"),
            ):
                result = config_check_command(_make_args())

        assert result == 1
        output = capsys.readouterr().out
        # Both PostgreSQL and Ollama failures should be shown
        assert output.count("✗ unreachable") == 2
        # Model should be skipped since Ollama is down
        assert "skipped" in output

    def test_custom_env_vars_used(self, capsys, monkeypatch):
        """Custom env vars are displayed and used for checks."""
        monkeypatch.setenv(
            "COCOSEARCH_DATABASE_URL", "postgresql://custom@myhost:9999/mydb"
        )
        monkeypatch.setenv("COCOSEARCH_OLLAMA_URL", "http://ollama-host:5555")
        monkeypatch.setenv("COCOSEARCH_EMBEDDING_MODEL", "custom-model")

        mock_conn = MagicMock()
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect", return_value=mock_conn
        ) as mock_pg:
            with patch(
                "cocosearch.indexer.preflight.urllib.request.urlopen",
                return_value=_mock_tags_response(
                    models=[{"name": "custom-model:latest"}]
                ),
            ):
                result = config_check_command(_make_args())

        assert result == 0
        output = capsys.readouterr().out
        assert "environment" in output
        # Verify the custom DB URL was used for the actual connection check
        mock_pg.assert_called_once_with(
            "postgresql://custom@myhost:9999/mydb", connect_timeout=3
        )

    def test_env_var_table_still_displayed(self, capsys):
        """Environment variable table is displayed alongside connectivity."""
        mock_conn = MagicMock()
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect", return_value=mock_conn
        ):
            with patch(
                "cocosearch.indexer.preflight.urllib.request.urlopen",
                return_value=_mock_tags_response(),
            ):
                config_check_command(_make_args())

        output = capsys.readouterr().out
        assert "Environment Variables" in output
        assert "Connectivity" in output


class TestConfigCheckProvider:
    """Tests for provider-aware config check behavior."""

    def test_ollama_provider_shows_ollama_checks(self, capsys, monkeypatch):
        """Ollama provider shows Ollama connectivity checks."""
        monkeypatch.delenv("COCOSEARCH_EMBEDDING_PROVIDER", raising=False)
        monkeypatch.delenv("COCOSEARCH_EMBEDDING_API_KEY", raising=False)
        mock_conn = MagicMock()
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect", return_value=mock_conn
        ):
            with patch(
                "cocosearch.indexer.preflight.urllib.request.urlopen",
                return_value=_mock_tags_response(),
            ):
                result = config_check_command(_make_args())

        assert result == 0
        output = capsys.readouterr().out
        assert "Ollama" in output
        assert "COCOSEARCH_EMBEDDING_PROVIDER" in output

    def test_openai_provider_skips_ollama_checks(self, capsys, monkeypatch):
        """OpenAI provider skips Ollama checks and checks API key instead."""
        monkeypatch.setenv("COCOSEARCH_EMBEDDING_PROVIDER", "openai")
        monkeypatch.setenv("COCOSEARCH_EMBEDDING_API_KEY", "sk-test")

        mock_conn = MagicMock()
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect", return_value=mock_conn
        ):
            result = config_check_command(_make_args())

        assert result == 0
        output = capsys.readouterr().out
        assert "API Key" in output
        assert "✓ set" in output
        # Ollama URL should not appear in env vars table
        assert "COCOSEARCH_OLLAMA_URL" not in output

    def test_openai_provider_missing_key_fails(self, capsys, monkeypatch):
        """OpenAI provider without API key shows failure."""
        monkeypatch.setenv("COCOSEARCH_EMBEDDING_PROVIDER", "openai")
        monkeypatch.delenv("COCOSEARCH_EMBEDDING_API_KEY", raising=False)

        mock_conn = MagicMock()
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect", return_value=mock_conn
        ):
            result = config_check_command(_make_args())

        assert result == 1
        output = capsys.readouterr().out
        assert "✗ missing" in output
        assert "COCOSEARCH_EMBEDDING_API_KEY" in output

    def test_provider_displayed_in_env_table(self, capsys, monkeypatch):
        """Provider is displayed in the environment variables table."""
        monkeypatch.setenv("COCOSEARCH_EMBEDDING_PROVIDER", "openrouter")
        monkeypatch.setenv("COCOSEARCH_EMBEDDING_API_KEY", "sk-test")

        mock_conn = MagicMock()
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect", return_value=mock_conn
        ):
            config_check_command(_make_args())

        output = capsys.readouterr().out
        assert "openrouter" in output
        assert "COCOSEARCH_EMBEDDING_PROVIDER" in output


def _patch_all_services_ok():
    """Context manager that patches all services as reachable."""
    mock_conn = MagicMock()
    return (
        patch("cocosearch.indexer.preflight.psycopg.connect", return_value=mock_conn),
        patch(
            "cocosearch.indexer.preflight.urllib.request.urlopen",
            return_value=_mock_tags_response(),
        ),
    )


class TestConfigCheckLinkedIndexes:
    """Tests for linked indexes section in config check command."""

    def _make_config(self, linked=None):
        """Create a mock CocoSearchConfig with linkedIndexes."""
        config = MagicMock()
        config.linkedIndexes = linked or []
        config.embedding = MagicMock()
        config.embedding.provider = None
        config.embedding.model = None
        config.embedding.baseUrl = None
        config.logging = MagicMock()
        config.logging.file = False
        return config

    def test_linked_indexes_shown_when_configured(self, capsys):
        """Linked Indexes table appears when linkedIndexes is configured."""
        pg_patch, ollama_patch = _patch_all_services_ok()
        config = self._make_config(linked=["other_repo"])

        with pg_patch, ollama_patch:
            with patch(
                "cocosearch.cli.find_config_file",
                return_value="/fake/cocosearch.yaml",
            ):
                with patch(
                    "cocosearch.cli.load_project_config",
                    return_value=config,
                ):
                    with patch(
                        "cocosearch.management.discovery.list_indexes",
                        return_value=[],
                    ):
                        result = config_check_command(_make_args())

        assert result == 0
        output = capsys.readouterr().out
        assert "Linked Indexes" in output

    def test_missing_linked_index_shows_not_indexed(self, capsys):
        """Missing linked index shows 'not indexed' status."""
        pg_patch, ollama_patch = _patch_all_services_ok()
        config = self._make_config(linked=["missing_repo"])

        with pg_patch, ollama_patch:
            with patch(
                "cocosearch.cli.find_config_file",
                return_value="/fake/cocosearch.yaml",
            ):
                with patch(
                    "cocosearch.cli.load_project_config",
                    return_value=config,
                ):
                    with patch(
                        "cocosearch.management.discovery.list_indexes",
                        return_value=[],
                    ):
                        result = config_check_command(_make_args())

        assert result == 0
        output = capsys.readouterr().out
        assert "not indexed" in output

    def test_healthy_linked_index_shows_healthy(self, capsys):
        """Healthy linked index shows 'healthy' status."""
        pg_patch, ollama_patch = _patch_all_services_ok()
        config = self._make_config(linked=["healthy_repo"])

        with pg_patch, ollama_patch:
            with patch(
                "cocosearch.cli.find_config_file",
                return_value="/fake/cocosearch.yaml",
            ):
                with patch(
                    "cocosearch.cli.load_project_config",
                    return_value=config,
                ):
                    with patch(
                        "cocosearch.management.discovery.list_indexes",
                        return_value=[{"name": "healthy_repo"}],
                    ):
                        with patch(
                            "cocosearch.management.stats.check_staleness",
                            return_value=(False, 1),
                        ):
                            with patch(
                                "cocosearch.management.stats.check_branch_staleness",
                                return_value={},
                            ):
                                with patch(
                                    "cocosearch.management.stats.check_deps_staleness",
                                    return_value=[],
                                ):
                                    result = config_check_command(_make_args())

        assert result == 0
        output = capsys.readouterr().out
        assert "healthy" in output

    def test_linked_indexes_do_not_affect_exit_code(self, capsys):
        """Missing/stale linked indexes still return exit 0."""
        pg_patch, ollama_patch = _patch_all_services_ok()
        config = self._make_config(linked=["missing_repo"])

        with pg_patch, ollama_patch:
            with patch(
                "cocosearch.cli.find_config_file",
                return_value="/fake/cocosearch.yaml",
            ):
                with patch(
                    "cocosearch.cli.load_project_config",
                    return_value=config,
                ):
                    with patch(
                        "cocosearch.management.discovery.list_indexes",
                        return_value=[],
                    ):
                        result = config_check_command(_make_args())

        assert result == 0

    def test_no_linked_indexes_no_table(self, capsys):
        """No linkedIndexes config means no Linked Indexes table."""
        pg_patch, ollama_patch = _patch_all_services_ok()
        config = self._make_config(linked=[])

        with pg_patch, ollama_patch:
            with patch(
                "cocosearch.cli.find_config_file",
                return_value="/fake/cocosearch.yaml",
            ):
                with patch(
                    "cocosearch.cli.load_project_config",
                    return_value=config,
                ):
                    result = config_check_command(_make_args())

        assert result == 0
        output = capsys.readouterr().out
        assert "Linked Indexes" not in output


class TestConfigSubcommandHelp:
    """Tests that 'cocosearch config' with no sub-subcommand shows config help."""

    def test_config_no_subcommand_shows_config_help(self, capsys):
        """Running 'config' alone should show config-specific help, not top-level."""
        with patch("sys.argv", ["cocosearch", "config"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

        output = capsys.readouterr().out
        # Config-specific description and subcommands should appear
        assert "Inspect and manage CocoSearch configuration" in output
        assert "show" in output
        assert "path" in output
        assert "check" in output
