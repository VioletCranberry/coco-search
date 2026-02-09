"""Tests for cocosearch CLI."""

import argparse
import json
from unittest.mock import patch, MagicMock

from cocosearch.cli import (
    derive_index_name,
    parse_query_filters,
    index_command,
    search_command,
    list_command,
    stats_command,
    clear_command,
)


class TestDeriveIndexName:
    """Tests for derive_index_name function."""

    def test_simple_directory(self):
        """Extracts and sanitizes directory name."""
        assert derive_index_name("/home/user/MyProject") == "myproject"

    def test_directory_with_hyphens(self):
        """Converts hyphens to underscores."""
        assert derive_index_name("/tmp/test-repo") == "test_repo"

    def test_trailing_slash(self):
        """Handles trailing slash."""
        assert derive_index_name("/home/user/project/") == "project"

    def test_collapses_multiple_underscores(self):
        """Collapses multiple consecutive underscores."""
        assert derive_index_name("/path/my--project") == "my_project"

    def test_empty_result_returns_index(self):
        """Returns 'root' when name would be empty."""
        # Root path returns "root"
        assert derive_index_name("/") == "root"


class TestParseQueryFilters:
    """Tests for parse_query_filters function."""

    def test_no_filters(self):
        """Returns original query when no filters."""
        query, lang = parse_query_filters("find auth code")
        assert query == "find auth code"
        assert lang is None

    def test_lang_filter(self):
        """Extracts lang:xxx pattern."""
        query, lang = parse_query_filters("find auth code lang:python")
        assert query == "find auth code"
        assert lang == "python"

    def test_lang_filter_middle(self):
        """Handles lang filter in middle of query."""
        query, lang = parse_query_filters("find lang:typescript auth code")
        assert query == "find  auth code"  # Note double space from removal
        assert lang == "typescript"


class TestIndexCommand:
    """Tests for index_command."""

    def test_invalid_path_returns_error(self, capsys):
        """Returns 1 for nonexistent path."""
        args = argparse.Namespace(
            path="/nonexistent/path",
            name=None,
            include=None,
            exclude=None,
            no_gitignore=False,
            fresh=False,
        )
        result = index_command(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out
        assert "does not exist" in captured.out

    def test_valid_path_runs_indexing(self, capsys, tmp_codebase):
        """Returns 0 for valid path with mocked indexing."""
        with patch("cocosearch.cli.run_index") as mock_run:
            mock_run.return_value = MagicMock(stats={"files": {"num_insertions": 1}})
            with patch("cocosearch.cli.IndexingProgress"):
                with patch("cocosearch.cli.register_index_path"):
                    args = argparse.Namespace(
                        path=str(tmp_codebase),
                        name="testindex",
                        include=None,
                        exclude=None,
                        no_gitignore=False,
                        fresh=False,
                    )
                    result = index_command(args)
        assert result == 0


class TestSearchCommand:
    """Tests for search_command."""

    def test_requires_query_without_interactive(self, capsys):
        """Returns 1 when no query and not interactive."""
        with patch("cocoindex.init"):
            args = argparse.Namespace(
                query=None,
                index="testindex",
                limit=10,
                lang=None,
                min_score=0.3,
                context=5,
                before_context=None,
                after_context=None,
                no_smart=False,
                pretty=False,
                interactive=False,
                hybrid=None,
                symbol_type=None,
                symbol_name=None,
                no_cache=False,
            )
            result = search_command(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "Query required" in captured.out

    def test_json_output_is_valid(self, capsys, make_search_result):
        """Search returns parseable JSON."""
        # Create mock search results
        mock_results = [
            make_search_result(
                filename="/test/file.py", start_byte=0, end_byte=100, score=0.9
            ),
        ]

        with patch("cocoindex.init"):
            with patch("cocosearch.cli.search", return_value=mock_results):
                args = argparse.Namespace(
                    query="test query",
                    index="testindex",
                    limit=10,
                    lang=None,
                    min_score=0.3,
                    context=5,
                    before_context=None,
                    after_context=None,
                    no_smart=False,
                    pretty=False,
                    interactive=False,
                    hybrid=None,
                    symbol_type=None,
                    symbol_name=None,
                    no_cache=False,
                )
                result = search_command(args)

        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert isinstance(output, list)


class TestListCommand:
    """Tests for list_command."""

    def test_json_output(self, capsys):
        """Returns JSON list of indexes."""
        mock_indexes = [
            {
                "name": "myproject",
                "table_name": "codeindex_myproject__myproject_chunks",
            },
        ]

        with patch("cocoindex.init"):
            with patch("cocosearch.cli.list_indexes", return_value=mock_indexes):
                args = argparse.Namespace(pretty=False)
                result = list_command(args)

        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert isinstance(output, list)
        assert len(output) == 1
        assert output[0]["name"] == "myproject"


class TestStatsCommand:
    """Tests for stats_command."""

    def test_specific_index_json(self, capsys):
        """Returns stats for specific index."""
        from cocosearch.management.stats import IndexStats

        mock_stats = IndexStats(
            name="testindex",
            file_count=10,
            chunk_count=50,
            storage_size=1024 * 1024,
            storage_size_pretty="1.0 MB",
            created_at=None,
            updated_at=None,
            is_stale=False,
            staleness_days=-1,
            languages=[],
            symbols={},
            warnings=[],
            parse_stats={},
            source_path=None,
            status=None,
            repo_url=None,
        )

        with patch("cocoindex.init"):
            with patch(
                "cocosearch.cli.get_comprehensive_stats", return_value=mock_stats
            ):
                args = argparse.Namespace(
                    index="testindex",
                    pretty=False,
                    verbose=False,
                    json=True,
                    all=False,
                    staleness_threshold=7,
                    live=False,
                    watch=False,
                    refresh_interval=1.0,
                    show_failures=False,
                )
                result = stats_command(args)

        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "file_count" in output
        assert output["file_count"] == 10

    def test_nonexistent_index_error(self, capsys):
        """Returns error for nonexistent index."""
        with patch("cocoindex.init"):
            with patch(
                "cocosearch.cli.get_comprehensive_stats",
                side_effect=ValueError("Index not found"),
            ):
                args = argparse.Namespace(
                    index="missing",
                    pretty=False,
                    verbose=False,
                    json=True,
                    all=False,
                    staleness_threshold=7,
                    live=False,
                    watch=False,
                    refresh_interval=1.0,
                )
                result = stats_command(args)

        assert result == 1
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "error" in output


class TestClearCommand:
    """Tests for clear_command."""

    def test_force_deletes_without_prompt(self, capsys):
        """--force skips confirmation."""
        mock_stats = {
            "file_count": 5,
            "chunk_count": 25,
            "storage_size_bytes": 512,
            "storage_size_pretty": "512 B",
        }
        mock_result = {"success": True, "index": "testindex"}

        with patch("cocoindex.init"):
            with patch("cocosearch.cli.get_stats", return_value=mock_stats):
                with patch("cocosearch.cli.clear_index", return_value=mock_result):
                    args = argparse.Namespace(
                        index="testindex", force=True, pretty=False
                    )
                    result = clear_command(args)

        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True

    def test_nonexistent_index_error(self, capsys):
        """Returns error for nonexistent index."""
        with patch("cocoindex.init"):
            with patch(
                "cocosearch.cli.get_stats", side_effect=ValueError("Index not found")
            ):
                args = argparse.Namespace(index="missing", force=True, pretty=False)
                result = clear_command(args)

        assert result == 1
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "error" in output


class TestErrorHandling:
    """Tests for CLI error handling."""

    def test_search_error_returns_json_error(self, capsys):
        """Search errors return JSON error object."""
        with patch("cocoindex.init"):
            with patch("cocosearch.cli.search", side_effect=ValueError("DB error")):
                args = argparse.Namespace(
                    query="test",
                    index="testindex",
                    limit=10,
                    lang=None,
                    min_score=0.3,
                    context=5,
                    before_context=None,
                    after_context=None,
                    no_smart=False,
                    pretty=False,
                    interactive=False,
                    hybrid=None,
                    symbol_type=None,
                    symbol_name=None,
                    no_cache=False,
                )
                result = search_command(args)

        assert result == 1
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "error" in output
        assert "DB error" in output["error"]


class TestSymbolFilterArguments:
    """Tests for search command symbol filter argument parsing."""

    def test_symbol_type_single(self):
        """Single --symbol-type flag parses correctly."""

        # Test by inspecting search_parser behavior via argparse directly
        parser = argparse.ArgumentParser()
        parser.add_argument("query", nargs="?")
        parser.add_argument(
            "--symbol-type",
            action="append",
            dest="symbol_type",
        )

        args = parser.parse_args(["query", "--symbol-type", "function"])
        assert args.symbol_type == ["function"]

    def test_symbol_type_multiple(self):
        """Multiple --symbol-type flags create list."""
        parser = argparse.ArgumentParser()
        parser.add_argument("query", nargs="?")
        parser.add_argument(
            "--symbol-type",
            action="append",
            dest="symbol_type",
        )

        args = parser.parse_args(
            ["query", "--symbol-type", "function", "--symbol-type", "method"]
        )
        assert args.symbol_type == ["function", "method"]

    def test_symbol_name_pattern(self):
        """--symbol-name accepts glob pattern."""
        parser = argparse.ArgumentParser()
        parser.add_argument("query", nargs="?")
        parser.add_argument("--symbol-name")

        args = parser.parse_args(["query", "--symbol-name", "get*"])
        assert args.symbol_name == "get*"

    def test_symbol_filters_with_other_flags(self):
        """Symbol filters work with --lang and --hybrid."""
        parser = argparse.ArgumentParser()
        parser.add_argument("query", nargs="?")
        parser.add_argument("--symbol-type", action="append", dest="symbol_type")
        parser.add_argument("--symbol-name")
        parser.add_argument("--lang")
        parser.add_argument("--hybrid", action="store_true", default=None)

        args = parser.parse_args(
            [
                "query",
                "--symbol-type",
                "function",
                "--symbol-name",
                "fetch*",
                "--lang",
                "python",
                "--hybrid",
            ]
        )
        assert args.symbol_type == ["function"]
        assert args.symbol_name == "fetch*"
        assert args.lang == "python"
        assert args.hybrid is True

    def test_symbol_type_all_four(self):
        """All four symbol types can be specified."""
        parser = argparse.ArgumentParser()
        parser.add_argument("query", nargs="?")
        parser.add_argument("--symbol-type", action="append", dest="symbol_type")

        args = parser.parse_args(
            [
                "query",
                "--symbol-type",
                "function",
                "--symbol-type",
                "class",
                "--symbol-type",
                "method",
                "--symbol-type",
                "interface",
            ]
        )
        assert args.symbol_type == ["function", "class", "method", "interface"]

    def test_symbol_name_complex_patterns(self):
        """--symbol-name handles complex glob patterns."""
        parser = argparse.ArgumentParser()
        parser.add_argument("query", nargs="?")
        parser.add_argument("--symbol-name")

        # Pattern with asterisk on both ends
        args = parser.parse_args(["query", "--symbol-name", "*Handler*"])
        assert args.symbol_name == "*Handler*"

        # Pattern with question mark
        args = parser.parse_args(["query", "--symbol-name", "get?User"])
        assert args.symbol_name == "get?User"

        # Pattern like ClassName.method
        args = parser.parse_args(["query", "--symbol-name", "User*.get*"])
        assert args.symbol_name == "User*.get*"

    def test_symbol_filters_none_by_default(self):
        """Symbol filters are None when not specified."""
        parser = argparse.ArgumentParser()
        parser.add_argument("query", nargs="?")
        parser.add_argument("--symbol-type", action="append", dest="symbol_type")
        parser.add_argument("--symbol-name")

        args = parser.parse_args(["query"])
        assert args.symbol_type is None
        assert args.symbol_name is None


class TestMCPCommand:
    """Tests for mcp_command transport handling."""

    def test_default_transport_is_stdio(self, monkeypatch):
        """Default transport is stdio when no flag or env."""
        monkeypatch.delenv("MCP_TRANSPORT", raising=False)
        monkeypatch.delenv("COCOSEARCH_MCP_PORT", raising=False)
        with patch("cocosearch.mcp.run_server") as mock_run:
            from cocosearch.cli import mcp_command

            args = argparse.Namespace(
                transport=None,
                port=None,
                project_from_cwd=False,
            )
            mcp_command(args)
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["transport"] == "stdio"

    def test_transport_flag_overrides_env(self, monkeypatch):
        """CLI --transport overrides MCP_TRANSPORT env var."""
        monkeypatch.setenv("MCP_TRANSPORT", "stdio")
        monkeypatch.delenv("COCOSEARCH_MCP_PORT", raising=False)
        with patch("cocosearch.mcp.run_server") as mock_run:
            from cocosearch.cli import mcp_command

            args = argparse.Namespace(
                transport="sse",
                port=None,
                project_from_cwd=False,
            )
            mcp_command(args)
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["transport"] == "sse"

    def test_env_transport_used_when_no_flag(self, monkeypatch):
        """MCP_TRANSPORT env var used when no --transport flag."""
        monkeypatch.setenv("MCP_TRANSPORT", "http")
        monkeypatch.delenv("COCOSEARCH_MCP_PORT", raising=False)
        with patch("cocosearch.mcp.run_server") as mock_run:
            from cocosearch.cli import mcp_command

            args = argparse.Namespace(
                transport=None,
                port=None,
                project_from_cwd=False,
            )
            mcp_command(args)
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["transport"] == "http"

    def test_invalid_transport_returns_error(self, monkeypatch, capsys):
        """Invalid transport value returns exit code 1."""
        monkeypatch.setenv("MCP_TRANSPORT", "invalid")
        monkeypatch.delenv("COCOSEARCH_MCP_PORT", raising=False)
        from cocosearch.cli import mcp_command

        args = argparse.Namespace(
            transport=None,
            port=None,
            project_from_cwd=False,
        )
        result = mcp_command(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "Invalid transport" in captured.err

    def test_invalid_transport_cli_returns_error(self, monkeypatch, capsys):
        """Invalid transport via CLI flag returns exit code 1."""
        monkeypatch.delenv("MCP_TRANSPORT", raising=False)
        monkeypatch.delenv("COCOSEARCH_MCP_PORT", raising=False)
        from cocosearch.cli import mcp_command

        args = argparse.Namespace(
            transport="websocket",
            port=None,
            project_from_cwd=False,
        )
        result = mcp_command(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "Invalid transport" in captured.err

    def test_port_flag_sets_port(self, monkeypatch):
        """--port flag sets server port."""
        monkeypatch.delenv("MCP_TRANSPORT", raising=False)
        monkeypatch.delenv("COCOSEARCH_MCP_PORT", raising=False)
        with patch("cocosearch.mcp.run_server") as mock_run:
            from cocosearch.cli import mcp_command

            args = argparse.Namespace(
                transport="sse",
                port=8080,
                project_from_cwd=False,
            )
            mcp_command(args)
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["port"] == 8080

    def test_port_env_used_when_no_flag(self, monkeypatch):
        """COCOSEARCH_MCP_PORT env var used when no --port flag."""
        monkeypatch.delenv("MCP_TRANSPORT", raising=False)
        monkeypatch.setenv("COCOSEARCH_MCP_PORT", "9000")
        with patch("cocosearch.mcp.run_server") as mock_run:
            from cocosearch.cli import mcp_command

            args = argparse.Namespace(
                transport="sse",
                port=None,
                project_from_cwd=False,
            )
            mcp_command(args)
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["port"] == 9000

    def test_port_flag_overrides_env(self, monkeypatch):
        """CLI --port overrides COCOSEARCH_MCP_PORT env var."""
        monkeypatch.delenv("MCP_TRANSPORT", raising=False)
        monkeypatch.setenv("COCOSEARCH_MCP_PORT", "9000")
        with patch("cocosearch.mcp.run_server") as mock_run:
            from cocosearch.cli import mcp_command

            args = argparse.Namespace(
                transport="sse",
                port=8080,
                project_from_cwd=False,
            )
            mcp_command(args)
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["port"] == 8080

    def test_invalid_port_env_returns_error(self, monkeypatch, capsys):
        """Invalid COCOSEARCH_MCP_PORT returns exit code 1."""
        monkeypatch.delenv("MCP_TRANSPORT", raising=False)
        monkeypatch.setenv("COCOSEARCH_MCP_PORT", "not-a-number")
        from cocosearch.cli import mcp_command

        args = argparse.Namespace(
            transport="sse",
            port=None,
            project_from_cwd=False,
        )
        result = mcp_command(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "Invalid port" in captured.err

    def test_default_port_is_3000(self, monkeypatch):
        """Default port is 3000 when no CLI flag or env var."""
        monkeypatch.delenv("MCP_TRANSPORT", raising=False)
        monkeypatch.delenv("COCOSEARCH_MCP_PORT", raising=False)
        with patch("cocosearch.mcp.run_server") as mock_run:
            from cocosearch.cli import mcp_command

            args = argparse.Namespace(
                transport="sse",
                port=None,
                project_from_cwd=False,
            )
            mcp_command(args)
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["port"] == 3000
