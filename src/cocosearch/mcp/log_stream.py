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
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class LogEntry(NamedTuple):
    timestamp: float
    level: str
    name: str
    message: str


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

    # -- buffer ops --

    def append(self, entry: LogEntry) -> None:
        with self._lock:
            self._buf.append(entry)
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
                name=record.name,
                message=self.format(record),
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
                            name="stderr",
                            message=line,
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
# Singleton lifecycle
# ---------------------------------------------------------------------------

_log_buffer: LogBuffer | None = None
_setup_done = False


def setup_log_capture() -> LogBuffer:
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

    _setup_done = True
    return _log_buffer


def get_log_buffer() -> LogBuffer | None:
    """Return the singleton LogBuffer, or None if not yet initialized."""
    return _log_buffer
