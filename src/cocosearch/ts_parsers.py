"""Thread-local tree-sitter parser provider.

tree-sitter ``Parser`` objects are *unsendable* in the pyo3 bindings: each
parser records the thread that created it and panics
(``pyo3_runtime.PanicException: _native::Parser is unsendable, but sent to
another thread``) the moment it is used from any other thread.

CocoSearch does its indexing and dependency extraction in background worker
threads — most visibly the dashboard "reindex" button, which spawns a *fresh*
thread per click (``mcp.server._run``). A parser cached in a process-global
variable and reused across those threads therefore crashes the worker: the
panic is a ``BaseException`` (not caught by ``except Exception``), so the thread
dies mid-index, the git ref/metadata never update, and the staleness warning
never clears.

This module is the single, safe way to obtain a parser. Parsers are cached
*per thread* via :class:`threading.local`, so each thread reuses its own
instances (preserving the perf win of caching) while never sharing a parser
across threads.
"""

import threading

from tree_sitter import Parser
from tree_sitter_language_pack import get_parser as _pack_get_parser

_local = threading.local()


def get_parser(language: str) -> Parser:
    """Return a tree-sitter parser for ``language``, cached per thread.

    Args:
        language: Tree-sitter language name (e.g. ``"python"``, ``"go"``,
            ``"javascript"``, ``"markdown"``).

    Returns:
        A :class:`tree_sitter.Parser` owned by the calling thread. Repeated
        calls on the same thread return the same instance; different threads
        always get their own instances.
    """
    cache = getattr(_local, "parsers", None)
    if cache is None:
        cache = {}
        _local.parsers = cache

    parser = cache.get(language)
    if parser is None:
        parser = _pack_get_parser(language)
        cache[language] = parser
    return parser


__all__ = ["get_parser"]
