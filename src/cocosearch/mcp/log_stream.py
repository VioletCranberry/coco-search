"""Real-time log streaming for the web dashboard.

Captures Python logging output and raw stderr writes into a thread-safe ring
buffer, then fans out to SSE subscriber queues for the ``/api/logs`` endpoint.

Components:
- LogEntry — structured log record
- LogBuffer — ring buffer with pub/sub for SSE clients
- BufferHandler — logging.Handler that feeds the buffer
- StderrCapture — tee wrapper that also feeds the buffer (for CocoIndex output)
- setup_log_capture() / get_log_buffer() — singleton lifecycle
"""

from __future__ import annotations

import asyncio
import collections
import io
import logging
import sys
import threading
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler as _RotatingFileHandler
from pathlib import Path
from typing import Any, NamedTuple

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class LogEntry(NamedTuple):
    timestamp: float
    level: str
    category: str
    message: str
    fields: dict[str, Any]


# ---------------------------------------------------------------------------
# Ring buffer with pub/sub
# ---------------------------------------------------------------------------

_BUFFER_MAXLEN = 1000
_QUEUE_MAXSIZE = 500


class LogBuffer:
    """Thread-safe ring buffer with async subscriber fan-out."""

    def __init__(self, maxlen: int = _BUFFER_MAXLEN) -> None:
        self._buf: collections.deque[LogEntry] = collections.deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._subscribers: dict[int, asyncio.Queue[LogEntry]] = {}
        self._next_id = 0
        self._handlers: list = []

    def add_handler(self, handler) -> None:
        self._handlers.append(handler)

    # -- buffer ops --

    def append(self, entry: LogEntry) -> None:
        with self._lock:
            self._buf.append(entry)
            # Fan out to handlers (terminal, file)
            for h in self._handlers:
                try:
                    h.handle(entry)
                except Exception:
                    pass
            # Fan out to SSE subscribers
            dead: list[int] = []
            for sub_id, q in self._subscribers.items():
                try:
                    q.put_nowait(entry)
                except asyncio.QueueFull:
                    dead.append(sub_id)
            for sub_id in dead:
                self._subscribers.pop(sub_id, None)

    def get_history(self) -> list[LogEntry]:
        with self._lock:
            return list(self._buf)

    # -- subscriber management --

    def subscribe(self) -> tuple[int, asyncio.Queue[LogEntry]]:
        q: asyncio.Queue[LogEntry] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        with self._lock:
            sub_id = self._next_id
            self._next_id += 1
            self._subscribers[sub_id] = q
        return sub_id, q

    def unsubscribe(self, sub_id: int) -> None:
        with self._lock:
            self._subscribers.pop(sub_id, None)


# ---------------------------------------------------------------------------
# logging.Handler → buffer
# ---------------------------------------------------------------------------


class BufferHandler(logging.Handler):
    """Logging handler that appends formatted records to a LogBuffer."""

    def __init__(self, buffer: LogBuffer) -> None:
        super().__init__()
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = LogEntry(
                timestamp=record.created,
                level=record.levelname,
                category=getattr(record, "category", "system"),
                message=self.format(record),
                fields=getattr(record, "fields", {}),
            )
            self._buffer.append(entry)
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
# stderr tee → buffer
# ---------------------------------------------------------------------------


class StderrCapture(io.TextIOBase):
    """Tee wrapper around stderr that also feeds complete lines to the buffer.

    Always writes to the original stderr first so nothing is swallowed.
    Never touches sys.stdout (critical for stdio JSON-RPC).
    """

    def __init__(self, original: io.TextIOBase, buffer: LogBuffer) -> None:
        self._original = original
        self._buffer = buffer
        self._partial = ""
        self._lock = threading.Lock()

    # -- io.TextIOBase interface --

    def write(self, s: str) -> int:
        # Tee to original stderr first
        self._original.write(s)

        # Buffer partial lines until newline
        with self._lock:
            self._partial += s
            while "\n" in self._partial:
                line, self._partial = self._partial.split("\n", 1)
                line = line.rstrip("\r")
                if line:
                    self._buffer.append(
                        LogEntry(
                            timestamp=time.time(),
                            level="STDERR",
                            category="system",
                            message=line,
                            fields={},
                        )
                    )
        return len(s)

    def flush(self) -> None:
        self._original.flush()

    def fileno(self) -> int:
        return self._original.fileno()

    @property
    def encoding(self) -> str:
        return getattr(self._original, "encoding", "utf-8")

    def isatty(self) -> bool:
        return self._original.isatty()

    def writable(self) -> bool:
        return True

    def readable(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# Rich terminal handler
# ---------------------------------------------------------------------------

_CATEGORY_COLORS = {
    "search": "cyan",
    "index": "green",
    "mcp": "magenta",
    "cache": "yellow",
    "infra": "blue",
    "system": "white",
    "deps": "bright_cyan",
}

_LEVEL_COLORS = {
    "DEBUG": "dim",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "red bold",
    "STDERR": "dim italic",
}


class RichLogHandler:
    """Prints structured LogEntry records to stderr using Rich markup."""

    def __init__(self) -> None:
        from rich.console import Console
        self._console = Console(stderr=True)

    def handle(self, entry: LogEntry) -> None:
        ts = datetime.fromtimestamp(entry.timestamp).strftime("%H:%M:%S")
        cat_color = _CATEGORY_COLORS.get(entry.category, "white")
        lvl_color = _LEVEL_COLORS.get(entry.level, "white")

        fields_str = ""
        if entry.fields:
            fields_str = "  " + " ".join(f"{k}={v}" for k, v in entry.fields.items())

        self._console.print(
            f"[dim]{ts}[/dim] [{cat_color}][{entry.category}][/{cat_color}] "
            f"[{lvl_color}]{entry.level:<8}[/{lvl_color}] {entry.message}"
            f"[dim]{fields_str}[/dim]",
            highlight=False,
        )


# ---------------------------------------------------------------------------
# File log handler
# ---------------------------------------------------------------------------


class FileLogHandler:
    """Writes structured LogEntry records to a rotating log file."""

    _DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
    _DEFAULT_BACKUP_COUNT = 3

    def __init__(
        self,
        filepath: str,
        max_bytes: int = _DEFAULT_MAX_BYTES,
        backup_count: int = _DEFAULT_BACKUP_COUNT,
    ) -> None:
        self._max_bytes = max_bytes
        self._backup_count = backup_count
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        self._handler = _RotatingFileHandler(
            filepath, maxBytes=max_bytes, backupCount=backup_count
        )

    def handle(self, entry: LogEntry) -> None:
        ts = datetime.fromtimestamp(entry.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        fields_str = ""
        if entry.fields:
            fields_str = "  " + " ".join(f"{k}={v}" for k, v in entry.fields.items())
        line = f"{ts} [{entry.category}] {entry.level:<8} {entry.message}{fields_str}"
        record = logging.LogRecord(
            name="cocosearch",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=line,
            args=(),
            exc_info=None,
        )
        self._handler.emit(record)

    def close(self) -> None:
        self._handler.close()


# ---------------------------------------------------------------------------
# Singleton lifecycle
# ---------------------------------------------------------------------------

_log_buffer: LogBuffer | None = None
_setup_done = False


def setup_log_capture(*, enable_rich: bool = True, log_file: bool = False) -> LogBuffer:
    """Idempotent setup: attach handler to root logger, wrap stderr.

    Returns the singleton LogBuffer.
    """
    global _log_buffer, _setup_done

    if _setup_done and _log_buffer is not None:
        return _log_buffer

    _log_buffer = LogBuffer()

    # Attach handler to root logger (captures all Python loggers)
    handler = BufferHandler(_log_buffer)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logging.getLogger().addHandler(handler)

    # Wrap stderr to capture CocoIndex framework output
    if not isinstance(sys.stderr, StderrCapture):
        sys.stderr = StderrCapture(sys.stderr, _log_buffer)  # type: ignore[assignment]

    # Rich terminal handler
    if enable_rich:
        _log_buffer.add_handler(RichLogHandler())

    # Rotating file handler
    if log_file:
        import os

        log_path = os.path.expanduser("~/.cocosearch/logs/cocosearch.log")
        _log_buffer.add_handler(FileLogHandler(log_path))

    _setup_done = True
    return _log_buffer


def get_log_buffer() -> LogBuffer | None:
    """Return the singleton LogBuffer, or None if not yet initialized."""
    return _log_buffer
