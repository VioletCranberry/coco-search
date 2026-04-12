"""Unit tests for cocosearch.watch — foreground incremental-reindex loop."""

import threading
from unittest.mock import patch

from cocosearch.watch import run_watch


class TestRunWatch:
    """The watch loop calls run_reindex_sync and respects the stop event."""

    def test_runs_then_stops_on_event(self, tmp_path):
        """Loop exits cleanly after the injected stop event trips."""
        stop_event = threading.Event()
        calls: list[dict] = []

        def _capture(index_name, project_path, *, fresh=False, include_deps=True):
            calls.append({"include_deps": include_deps})
            # Trip the stop event after the first tick so the loop exits.
            stop_event.set()
            return {
                "success": True,
                "deps_extracted": include_deps,
                "error": None,
            }

        with (
            patch("cocosearch.watch.run_reindex_sync", side_effect=_capture),
            patch("cocosearch.watch.signal.signal"),
            patch("cocosearch.watch.time.sleep"),
        ):
            exit_code = run_watch(
                tmp_path,
                "my_index",
                interval_seconds=1,
                include_deps=True,
                stop_event=stop_event,
            )

        assert exit_code == 0
        assert len(calls) == 1
        assert calls[0]["include_deps"] is True

    def test_no_deps_passes_include_deps_false(self, tmp_path):
        """include_deps=False should flow through to run_reindex_sync."""
        stop_event = threading.Event()
        calls: list[dict] = []

        def _capture(index_name, project_path, *, fresh=False, include_deps=True):
            calls.append({"include_deps": include_deps})
            stop_event.set()
            return {"success": True, "deps_extracted": False, "error": None}

        with (
            patch("cocosearch.watch.run_reindex_sync", side_effect=_capture),
            patch("cocosearch.watch.signal.signal"),
            patch("cocosearch.watch.time.sleep"),
        ):
            exit_code = run_watch(
                tmp_path,
                "my_index",
                interval_seconds=1,
                include_deps=False,
                stop_event=stop_event,
            )

        assert exit_code == 0
        assert calls == [{"include_deps": False}]

    def test_exception_in_tick_does_not_crash_loop(self, tmp_path, capsys):
        """A transient error in one tick must not bring down the loop."""
        stop_event = threading.Event()
        call_count = {"n": 0}

        def _sometimes_fail(*a, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("transient db hiccup")
            stop_event.set()
            return {"success": True, "deps_extracted": False, "error": None}

        with (
            patch("cocosearch.watch.run_reindex_sync", side_effect=_sometimes_fail),
            patch("cocosearch.watch.signal.signal"),
            patch("cocosearch.watch.time.sleep"),
        ):
            exit_code = run_watch(
                tmp_path,
                "my_index",
                interval_seconds=1,
                include_deps=False,
                stop_event=stop_event,
            )

        assert exit_code == 0
        # First call raised; second succeeded and set the stop event.
        assert call_count["n"] == 2

    def test_already_set_stop_event_no_ops(self, tmp_path):
        """If stop is set before the first tick, the loop exits without calling run_reindex_sync."""
        stop_event = threading.Event()
        stop_event.set()

        with (
            patch("cocosearch.watch.run_reindex_sync") as mock_run,
            patch("cocosearch.watch.signal.signal"),
            patch("cocosearch.watch.time.sleep"),
        ):
            exit_code = run_watch(
                tmp_path,
                "my_index",
                interval_seconds=1,
                include_deps=False,
                stop_event=stop_event,
            )

        assert exit_code == 0
        mock_run.assert_not_called()
