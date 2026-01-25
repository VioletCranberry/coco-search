"""Tests for cocosearch CLI."""
import argparse
import json
import pytest
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
                args = argparse.Namespace(
                    path=str(tmp_codebase),
                    name="testindex",
                    include=None,
                    exclude=None,
                    no_gitignore=False,
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
                pretty=False,
                interactive=False,
            )
            result = search_command(args)
        assert result == 1
        captured = capsys.readouterr()
        assert "Query required" in captured.out

    def test_json_output_is_valid(self, capsys, make_search_result):
        """Search returns parseable JSON."""
        # Create mock search results
        mock_results = [
            make_search_result(filename="/test/file.py", start_byte=0, end_byte=100, score=0.9),
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
                    pretty=False,
                    interactive=False,
                )
                result = search_command(args)

        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert isinstance(output, list)


class TestListCommand:
    """Tests for list_command."""

    def test_json_output(self, capsys, mock_db_pool):
        """Returns JSON list of indexes."""
        pool, cursor = mock_db_pool(results=[
            ("codeindex_myproject__myproject_chunks",),
        ])

        with patch("cocoindex.init"):
            with patch("cocosearch.management.discovery.get_connection_pool", return_value=pool):
                args = argparse.Namespace(pretty=False)
                result = list_command(args)

        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert isinstance(output, list)
