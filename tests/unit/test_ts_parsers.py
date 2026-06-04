"""Tests for the centralized thread-local tree-sitter parser provider.

tree-sitter ``Parser`` objects are *unsendable* in the pyo3 bindings: each
parser panics (``pyo3_runtime.PanicException``) if it is touched from any thread
other than the one that created it. CocoSearch indexes in background worker
threads (e.g. the dashboard "reindex" button spawns a fresh thread per click),
so a parser cached process-globally and reused across threads crashes the
worker. These tests pin the invariant that prevents that crash: parsers are
cached *per thread*, never shared between threads.
"""

import threading

from cocosearch.ts_parsers import get_parser


def test_same_thread_returns_cached_instance():
    """Within one thread, repeated calls return the same cached parser."""
    first = get_parser("python")
    second = get_parser("python")
    assert first is second


def test_distinct_threads_get_distinct_parsers():
    """A parser cached by one thread is never handed to another thread.

    This is the regression guard for the ``_native::Parser is unsendable, but
    sent to another thread`` panic seen on dashboard reindex.
    """
    results: dict[str, object] = {}
    barrier = threading.Event()

    def worker(key: str):
        results[key] = get_parser("python")
        barrier.set()

    # Thread A creates and caches a parser, then dies.
    t_a = threading.Thread(target=worker, args=("a",))
    t_a.start()
    t_a.join()

    # Thread B (a *new* thread, mimicking the next reindex worker) must get its
    # own parser, not the one cached by the now-dead thread A.
    t_b = threading.Thread(target=worker, args=("b",))
    t_b.start()
    t_b.join()

    assert results["a"] is not results["b"]


def test_different_languages_cached_independently():
    """Different languages get different parser instances within a thread."""
    py = get_parser("python")
    go = get_parser("go")
    assert py is not go
    assert get_parser("python") is py
