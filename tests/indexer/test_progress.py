"""Tests for cocosearch.indexer.progress module."""

import io
import pytest
from rich.console import Console

from cocosearch.indexer.progress import IndexingProgress, print_summary


class TestIndexingProgress:
    """Tests for IndexingProgress context manager."""

    def test_context_manager_works(self):
        """Can use as `with IndexingProgress() as progress`."""
        output = io.StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        with IndexingProgress(console=console) as progress:
            assert progress is not None

        # No exception = success

    def test_start_indexing_displays(self):
        """start_indexing(path) shows progress indicator."""
        output = io.StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        with IndexingProgress(console=console) as progress:
            progress.start_indexing("/test/path")
            # Progress bar is transient, so we just verify no exception

    def test_update_status_works(self):
        """update_status changes progress description."""
        output = io.StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        with IndexingProgress(console=console) as progress:
            progress.start_indexing("/test/path")
            progress.update_status("Processing files...")
            # Verify no exception

    def test_complete_displays_stats(self):
        """complete(stats_dict) shows summary panel."""
        output = io.StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        stats = {
            "files_added": 10,
            "files_removed": 2,
            "files_updated": 5,
        }

        with IndexingProgress(console=console) as progress:
            progress.start_indexing("/test/path")
            progress.complete(stats)

        result = output.getvalue()
        # Verify key stats appear in output
        assert "10" in result
        assert "2" in result
        assert "5" in result

    def test_accepts_custom_console(self):
        """Accepts custom Rich console for output."""
        custom_output = io.StringIO()
        custom_console = Console(file=custom_output, force_terminal=True, width=80)

        with IndexingProgress(console=custom_console) as progress:
            progress.start_indexing("/test")
            progress.complete({"files_added": 1, "files_removed": 0, "files_updated": 0})

        # Output should go to custom console
        assert custom_output.getvalue()  # Not empty


class TestPrintSummary:
    """Tests for print_summary function."""

    def test_summary_shows_stats(self):
        """Summary displays all provided stats."""
        output = io.StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        stats = {
            "files_added": 10,
            "files_removed": 2,
            "files_updated": 5,
        }
        print_summary(stats, console=console)

        result = output.getvalue()
        assert "10" in result
        assert "2" in result
        assert "5" in result

    def test_summary_shows_optional_chunks(self):
        """Summary includes chunks_created when provided."""
        output = io.StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        stats = {
            "files_added": 5,
            "files_removed": 0,
            "files_updated": 0,
            "chunks_created": 42,
        }
        print_summary(stats, console=console)

        result = output.getvalue()
        assert "42" in result

    def test_summary_shows_duration(self):
        """Summary includes duration when provided."""
        output = io.StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        stats = {
            "files_added": 5,
            "files_removed": 0,
            "files_updated": 0,
            "duration": "2.5s",
        }
        print_summary(stats, console=console)

        result = output.getvalue()
        assert "2.5s" in result

    def test_summary_handles_empty_stats(self):
        """Summary handles stats with all zeros."""
        output = io.StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        stats = {
            "files_added": 0,
            "files_removed": 0,
            "files_updated": 0,
        }
        print_summary(stats, console=console)

        result = output.getvalue()
        # Should still display the summary panel
        assert "Indexing Summary" in result

    def test_summary_defaults_missing_keys(self):
        """Summary defaults missing keys to 0."""
        output = io.StringIO()
        console = Console(file=output, force_terminal=True, width=80)

        # Empty stats dict
        stats = {}
        print_summary(stats, console=console)

        result = output.getvalue()
        # Should display with default 0 values
        assert "Indexing Summary" in result

    def test_creates_default_console_if_none(self):
        """Creates new Console if none provided."""
        stats = {"files_added": 1, "files_removed": 0, "files_updated": 0}

        # This should not raise - it creates its own console
        # We can't easily capture stdout here, so just verify no exception
        import sys
        from io import StringIO

        # Redirect stdout temporarily
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            print_summary(stats, console=None)
        finally:
            sys.stdout = old_stdout
