"""Unit tests for CLI client mode dispatch.

Tests the early-exit dispatch in cli.main() that forwards commands to a remote
CocoSearch server when COCOSEARCH_SERVER_URL is set, and the local-only command
rejection in client.run_client_command().
"""

import argparse
from unittest.mock import patch

import pytest

from cocosearch.client import _LOCAL_ONLY_COMMANDS, run_client_command


# ---------------------------------------------------------------------------
# TestClientModeDispatch — tests for main() client mode branching
# ---------------------------------------------------------------------------


class TestClientModeDispatch:
    """Tests for the client mode dispatch path in cli.main()."""

    def test_server_url_set_dispatches_to_client(self, monkeypatch):
        """When COCOSEARCH_SERVER_URL is set and a command is given, run_client_command is called."""
        monkeypatch.setenv("COCOSEARCH_SERVER_URL", "http://localhost:3000")
        monkeypatch.setattr("sys.argv", ["cocosearch", "search", "test query"])

        with patch("cocosearch.client.run_client_command", return_value=0) as mock_client:
            with pytest.raises(SystemExit) as exc_info:
                from cocosearch.cli import main

                main()

            mock_client.assert_called_once()
            call_args = mock_client.call_args
            args_namespace = call_args[0][0]
            server_url = call_args[0][1]

            assert args_namespace.command == "search"
            assert args_namespace.query == "test query"
            assert server_url == "http://localhost:3000"
            assert exc_info.value.code == 0

    def test_server_url_unset_runs_locally(self, monkeypatch):
        """When COCOSEARCH_SERVER_URL is not set, the normal local execution path is taken."""
        monkeypatch.delenv("COCOSEARCH_SERVER_URL", raising=False)
        monkeypatch.setattr("sys.argv", ["cocosearch", "search", "test query"])

        with (
            patch("cocosearch.client.run_client_command") as mock_client,
            patch("cocosearch.config.env_validation.get_database_url"),
            patch("cocosearch.cli.search_command", return_value=0) as mock_search,
        ):
            with pytest.raises(SystemExit) as exc_info:
                from cocosearch.cli import main

                main()

            # Client mode should NOT be invoked
            mock_client.assert_not_called()
            # Local command handler should be invoked instead
            mock_search.assert_called_once()
            assert exc_info.value.code == 0

    def test_server_url_set_no_command_shows_help(self, monkeypatch):
        """When env var set but no command (just 'cocosearch'), should show help and exit."""
        monkeypatch.setenv("COCOSEARCH_SERVER_URL", "http://localhost:3000")
        # No subcommand given — parser.parse_args() will set args.command to None
        monkeypatch.setattr("sys.argv", ["cocosearch"])

        with patch("cocosearch.client.run_client_command") as mock_client:
            with pytest.raises(SystemExit) as exc_info:
                from cocosearch.cli import main

                main()

            # Client mode should NOT be invoked because args.command is None
            mock_client.assert_not_called()
            # Should exit with code 1 (help/no-command path)
            assert exc_info.value.code == 1

    def test_server_url_set_exit_code_forwarded(self, monkeypatch):
        """Exit code from run_client_command is forwarded through sys.exit."""
        monkeypatch.setenv("COCOSEARCH_SERVER_URL", "http://localhost:3000")
        monkeypatch.setattr("sys.argv", ["cocosearch", "stats"])

        with patch("cocosearch.client.run_client_command", return_value=1) as mock_client:
            with pytest.raises(SystemExit) as exc_info:
                from cocosearch.cli import main

                main()

            mock_client.assert_called_once()
            assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# TestLocalOnlyCommands — tests for _LOCAL_ONLY_COMMANDS rejection
# ---------------------------------------------------------------------------


class TestLocalOnlyCommands:
    """Tests that local-only commands are rejected in client mode."""

    def test_local_only_commands_set_is_correct(self):
        """Verify the _LOCAL_ONLY_COMMANDS set contains expected commands."""
        assert _LOCAL_ONLY_COMMANDS == {"mcp", "dashboard", "init", "config"}

    def test_mcp_command_rejected_in_client_mode(self, capsys):
        """mcp command returns 1 with helpful message in client mode."""
        args = argparse.Namespace(command="mcp")
        result = run_client_command(args, "http://localhost:3000")

        assert result == 1
        captured = capsys.readouterr()
        assert "'mcp' runs locally only" in captured.out
        assert "cannot be forwarded" in captured.out

    def test_dashboard_command_rejected_in_client_mode(self, capsys):
        """dashboard command returns 1 with helpful message in client mode."""
        args = argparse.Namespace(command="dashboard")
        result = run_client_command(args, "http://localhost:3000")

        assert result == 1
        captured = capsys.readouterr()
        assert "'dashboard' runs locally only" in captured.out

    def test_init_command_rejected_in_client_mode(self, capsys):
        """init command returns 1 with helpful message in client mode."""
        args = argparse.Namespace(command="init")
        result = run_client_command(args, "http://localhost:3000")

        assert result == 1
        captured = capsys.readouterr()
        assert "'init' runs locally only" in captured.out

    def test_config_command_rejected_in_client_mode(self, capsys):
        """config command returns 1 with helpful message in client mode."""
        args = argparse.Namespace(command="config")
        result = run_client_command(args, "http://localhost:3000")

        assert result == 1
        captured = capsys.readouterr()
        assert "'config' runs locally only" in captured.out


# ---------------------------------------------------------------------------
# TestClientModeCommandRouting — tests for forwarding specific commands
# ---------------------------------------------------------------------------


class TestClientModeCommandRouting:
    """Tests that specific commands are routed to the correct client methods."""

    def test_search_command_forwarded(self, monkeypatch):
        """When COCOSEARCH_SERVER_URL set and 'search' command used, client search is called."""
        monkeypatch.setenv("COCOSEARCH_INDEX_NAME", "testindex")

        args = argparse.Namespace(
            command="search",
            query="test query",
            index="testindex",
            limit=10,
            min_score=0.3,
            lang=None,
            interactive=False,
            pretty=False,
            hybrid=None,
            symbol_type=None,
            symbol_name=None,
            no_cache=False,
            before_context=None,
            after_context=None,
            context=None,
            no_smart=False,
        )

        mock_search_result = {"results": [], "total": 0}

        with patch(
            "cocosearch.client.CocoSearchClient.search",
            return_value=mock_search_result,
        ) as mock_search:
            result = run_client_command(args, "http://localhost:3000")

        assert result == 0
        mock_search.assert_called_once()
        call_kwargs = mock_search.call_args
        assert call_kwargs[1]["query"] == "test query"
        assert call_kwargs[1]["index_name"] == "testindex"

    def test_stats_command_forwarded(self):
        """When COCOSEARCH_SERVER_URL set and 'stats' command used, client stats is called."""
        args = argparse.Namespace(
            command="stats",
            index="testindex",
            all=False,
            pretty=False,
            json=True,
        )

        mock_stats_result = {"name": "testindex", "file_count": 10, "chunk_count": 50}

        with patch(
            "cocosearch.client.CocoSearchClient.stats",
            return_value=mock_stats_result,
        ) as mock_stats:
            result = run_client_command(args, "http://localhost:3000")

        assert result == 0
        mock_stats.assert_called_once_with("testindex")

    def test_list_command_forwarded(self):
        """When COCOSEARCH_SERVER_URL set and 'list' command used, client list_indexes is called."""
        args = argparse.Namespace(
            command="list",
            pretty=False,
        )

        mock_list_result = [{"name": "idx1"}, {"name": "idx2"}]

        with patch(
            "cocosearch.client.CocoSearchClient.list_indexes",
            return_value=mock_list_result,
        ) as mock_list:
            result = run_client_command(args, "http://localhost:3000")

        assert result == 0
        mock_list.assert_called_once()

    def test_unknown_command_returns_error(self, capsys):
        """Unknown command in client mode returns 1."""
        args = argparse.Namespace(command="nonexistent")
        result = run_client_command(args, "http://localhost:3000")

        assert result == 1
        captured = capsys.readouterr()
        assert "Unknown command" in captured.out

    def test_connection_error_returns_1(self, capsys):
        """Connection error to remote server returns exit code 1."""
        from cocosearch.client import CocoSearchConnectionError

        args = argparse.Namespace(
            command="stats",
            index="testindex",
            all=False,
            pretty=False,
            json=True,
        )

        with patch(
            "cocosearch.client.CocoSearchClient.stats",
            side_effect=CocoSearchConnectionError("Connection refused"),
        ):
            result = run_client_command(args, "http://localhost:3000")

        assert result == 1
        captured = capsys.readouterr()
        assert "Connection error" in captured.out

    def test_client_error_returns_1(self, capsys):
        """Server error response returns exit code 1."""
        from cocosearch.client import CocoSearchClientError

        args = argparse.Namespace(
            command="stats",
            index="testindex",
            all=False,
            pretty=False,
            json=True,
        )

        with patch(
            "cocosearch.client.CocoSearchClient.stats",
            side_effect=CocoSearchClientError("Index not found"),
        ):
            result = run_client_command(args, "http://localhost:3000")

        assert result == 1
        captured = capsys.readouterr()
        assert "Server error" in captured.out
