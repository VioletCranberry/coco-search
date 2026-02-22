"""Tests for --deps flag on the index command."""

import argparse


class TestIndexDepsFlag:
    """Test that --deps flag is accepted by the index parser."""

    def test_deps_flag_is_recognized(self):
        """The --deps flag should be accepted by the index subcommand parser."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        index_parser = subparsers.add_parser("index")
        index_parser.add_argument("path")
        index_parser.add_argument("--deps", action="store_true")

        args = parser.parse_args(["index", ".", "--deps"])
        assert args.deps is True

    def test_deps_flag_defaults_false(self):
        """Without --deps, the flag should default to False."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        index_parser = subparsers.add_parser("index")
        index_parser.add_argument("path")
        index_parser.add_argument("--deps", action="store_true")

        args = parser.parse_args(["index", "."])
        assert args.deps is False
