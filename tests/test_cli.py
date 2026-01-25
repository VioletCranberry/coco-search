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
