"""Tests for interactive REPL."""

from unittest.mock import MagicMock, patch

from cocosearch.search.repl import SearchREPL, _parse_query_filters


class TestParseQueryFilters:
    def test_no_filter(self):
        query, lang = _parse_query_filters("hello world")
        assert query == "hello world"
        assert lang is None

    def test_lang_filter(self):
        query, lang = _parse_query_filters("hello lang:python world")
        assert query == "hello  world"
        assert lang == "python"


class TestSearchREPL:
    def test_init_single_index(self):
        repl = SearchREPL("test_index")
        assert repl.index_name == "test_index"
        assert repl.index_names is None

    def test_init_multi_index(self):
        repl = SearchREPL("idx_a", index_names=["idx_a", "idx_b"])
        assert repl.index_name == "idx_a"
        assert repl.index_names == ["idx_a", "idx_b"]

    @patch("cocosearch.search.repl.search")
    @patch("cocosearch.search.repl.format_pretty")
    def test_single_index_search(self, mock_fmt, mock_search):
        mock_search.return_value = []
        repl = SearchREPL("test_index")
        repl.default("test query")
        mock_search.assert_called_once()
        assert mock_search.call_args.kwargs["index_name"] == "test_index"

    @patch("cocosearch.search.multi.multi_search")
    @patch("cocosearch.search.repl.format_pretty")
    def test_multi_index_search(self, mock_fmt, mock_multi):
        mock_multi.return_value = []
        repl = SearchREPL("idx_a", index_names=["idx_a", "idx_b"])
        repl.default("test query")
        mock_multi.assert_called_once()
        assert mock_multi.call_args.kwargs["index_names"] == ["idx_a", "idx_b"]

    def test_indexes_command_sets_multi(self):
        repl = SearchREPL("test_index")
        repl.handle_setting(":indexes repo_a,repo_b")
        assert repl.index_names == ["repo_a", "repo_b"]
        assert repl.index_name == "repo_a"

    def test_indexes_command_requires_two(self):
        repl = SearchREPL("test_index")
        repl.handle_setting(":indexes single")
        assert repl.index_names is None  # Not changed

    def test_index_command_clears_multi(self):
        repl = SearchREPL("idx_a", index_names=["idx_a", "idx_b"])
        repl.handle_setting(":index new_idx")
        assert repl.index_name == "new_idx"
        assert repl.index_names is None

    @patch("cocosearch.config.find_config_file")
    @patch("cocosearch.config.load_config")
    @patch("cocosearch.management.discovery.list_indexes")
    def test_searchall_toggle_on(self, mock_list, mock_load, mock_find):
        mock_find.return_value = "/fake/cocosearch.yaml"
        mock_cfg = MagicMock()
        mock_cfg.linkedIndexes = ["linked_a", "linked_b"]
        mock_load.return_value = mock_cfg
        mock_list.return_value = [
            {"name": "test_index"},
            {"name": "linked_a"},
            {"name": "linked_b"},
        ]

        repl = SearchREPL("test_index")
        repl.handle_setting(":searchall")
        assert repl.index_names == ["test_index", "linked_a", "linked_b"]

    def test_searchall_toggle_off(self):
        repl = SearchREPL("idx_a", index_names=["idx_a", "idx_b"])
        repl.handle_setting(":searchall")
        assert repl.index_names is None
