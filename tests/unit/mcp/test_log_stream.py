"""Tests for cocosearch.mcp.log_stream module."""

import asyncio
import io
import logging
import sys
import threading

import pytest

from cocosearch.mcp.log_stream import (
    BufferHandler,
    FileLogHandler,
    LogBuffer,
    LogEntry,
    RichLogHandler,
    StderrCapture,
    _QUEUE_MAXSIZE,
)


# ---------------------------------------------------------------------------
# LogEntry structure
# ---------------------------------------------------------------------------


class TestLogEntryStructure:
    def test_log_entry_has_category_and_fields(self):
        entry = LogEntry(
            timestamp=1.0,
            level="INFO",
            category="search",
            message="test",
            fields={"query": "hello"},
        )
        assert entry.category == "search"
        assert entry.fields == {"query": "hello"}

    def test_log_entry_default_fields(self):
        entry = LogEntry(
            timestamp=1.0, level="INFO", category="system", message="test", fields={}
        )
        assert entry.fields == {}


# ---------------------------------------------------------------------------
# LogBuffer
# ---------------------------------------------------------------------------


class TestLogBuffer:
    def test_append_and_history(self):
        buf = LogBuffer(maxlen=10)
        entry = LogEntry(
            timestamp=1.0, level="INFO", category="system", message="hello", fields={}
        )
        buf.append(entry)
        history = buf.get_history()
        assert len(history) == 1
        assert history[0] == entry

    def test_rolling_eviction(self):
        buf = LogBuffer(maxlen=3)
        for i in range(5):
            buf.append(
                LogEntry(
                    timestamp=float(i),
                    level="INFO",
                    category="system",
                    message=str(i),
                    fields={},
                )
            )
        history = buf.get_history()
        assert len(history) == 3
        assert [e.message for e in history] == ["2", "3", "4"]

    def test_subscribe_receives_entries(self):
        buf = LogBuffer()
        sub_id, q = buf.subscribe()
        entry = LogEntry(
            timestamp=1.0, level="INFO", category="system", message="live", fields={}
        )
        buf.append(entry)
        assert not q.empty()
        assert q.get_nowait() == entry
        buf.unsubscribe(sub_id)

    def test_unsubscribe_stops_delivery(self):
        buf = LogBuffer()
        sub_id, q = buf.subscribe()
        buf.unsubscribe(sub_id)
        buf.append(
            LogEntry(
                timestamp=1.0,
                level="INFO",
                category="system",
                message="after",
                fields={},
            )
        )
        assert q.empty()

    def test_full_queue_drops_subscriber(self):
        buf = LogBuffer()
        sub_id, q = buf.subscribe()
        # Fill the queue to capacity
        for i in range(_QUEUE_MAXSIZE):
            buf.append(
                LogEntry(
                    timestamp=float(i),
                    level="INFO",
                    category="system",
                    message=str(i),
                    fields={},
                )
            )
        # Next append should drop the subscriber
        buf.append(
            LogEntry(
                timestamp=999.0,
                level="INFO",
                category="system",
                message="overflow",
                fields={},
            )
        )
        # Subscriber should have been removed
        assert sub_id not in buf._subscribers

    def test_thread_safety(self):
        buf = LogBuffer(maxlen=100)
        errors = []

        def writer(start: int):
            try:
                for i in range(50):
                    buf.append(
                        LogEntry(
                            timestamp=float(start + i),
                            level="INFO",
                            category="system",
                            message=str(start + i),
                            fields={},
                        )
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i * 50,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # All entries should have been added (maxlen=100, 200 written -> last 100)
        history = buf.get_history()
        assert len(history) == 100

    def test_multiple_subscribers(self):
        buf = LogBuffer()
        id1, q1 = buf.subscribe()
        id2, q2 = buf.subscribe()
        entry = LogEntry(
            timestamp=1.0,
            level="INFO",
            category="system",
            message="fan-out",
            fields={},
        )
        buf.append(entry)
        assert q1.get_nowait() == entry
        assert q2.get_nowait() == entry
        buf.unsubscribe(id1)
        buf.unsubscribe(id2)

    def test_get_history_is_snapshot(self):
        buf = LogBuffer()
        buf.append(
            LogEntry(
                timestamp=1.0, level="INFO", category="system", message="a", fields={}
            )
        )
        snapshot = buf.get_history()
        buf.append(
            LogEntry(
                timestamp=2.0, level="INFO", category="system", message="b", fields={}
            )
        )
        assert len(snapshot) == 1  # snapshot unchanged

    @pytest.mark.asyncio
    async def test_subscribe_stores_event_loop(self):
        """subscribe() captures the running event loop for thread-safe delivery."""
        buf = LogBuffer()
        sub_id, q = buf.subscribe()
        loop, _ = buf._subscribers[sub_id]
        assert loop is asyncio.get_running_loop()
        buf.unsubscribe(sub_id)

    def test_subscribe_no_loop_in_sync_context(self):
        """subscribe() stores None for loop when no event loop is running."""
        buf = LogBuffer()
        sub_id, q = buf.subscribe()
        loop, _ = buf._subscribers[sub_id]
        assert loop is None
        buf.unsubscribe(sub_id)

    @pytest.mark.asyncio
    async def test_full_queue_in_async_context_drops_entries_silently(self):
        """QueueFull in async subscriber must not cascade via event loop callbacks."""
        buf = LogBuffer()
        sub_id, q = buf.subscribe()

        for i in range(_QUEUE_MAXSIZE):
            buf.append(
                LogEntry(
                    timestamp=float(i),
                    level="INFO",
                    category="system",
                    message=str(i),
                    fields={},
                )
            )

        # Queue is full; more appends should not raise or cascade
        for i in range(10):
            buf.append(
                LogEntry(
                    timestamp=1000.0 + i,
                    level="INFO",
                    category="system",
                    message=f"overflow-{i}",
                    fields={},
                )
            )

        await asyncio.sleep(0.05)  # Let scheduled callbacks execute

        assert sub_id in buf._subscribers  # NOT removed (entries silently dropped)
        assert q.qsize() == _QUEUE_MAXSIZE  # Queue still full, overflow dropped
        buf.unsubscribe(sub_id)


# ---------------------------------------------------------------------------
# BufferHandler
# ---------------------------------------------------------------------------


class TestBufferHandler:
    def test_captures_record(self):
        buf = LogBuffer()
        handler = BufferHandler(buf)
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="mylogger",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="test warning",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        history = buf.get_history()
        assert len(history) == 1
        assert history[0].level == "WARNING"
        assert history[0].category == "system"
        assert history[0].message == "test warning"

    def test_captures_correct_level(self):
        buf = LogBuffer()
        handler = BufferHandler(buf)
        handler.setFormatter(logging.Formatter("%(message)s"))

        for level in (logging.DEBUG, logging.INFO, logging.ERROR):
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="",
                lineno=0,
                msg=f"msg-{level}",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

        history = buf.get_history()
        assert len(history) == 3
        assert history[0].level == "DEBUG"
        assert history[1].level == "INFO"
        assert history[2].level == "ERROR"

    def test_captures_custom_category(self):
        buf = LogBuffer()
        handler = BufferHandler(buf)
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="search event",
            args=(),
            exc_info=None,
        )
        record.category = "search"  # type: ignore[attr-defined]
        record.fields = {"query": "hello"}  # type: ignore[attr-defined]
        handler.emit(record)

        history = buf.get_history()
        assert len(history) == 1
        assert history[0].category == "search"
        assert history[0].fields == {"query": "hello"}

    def test_defaults_to_system_category(self):
        buf = LogBuffer()
        handler = BufferHandler(buf)
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="third_party",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="some message",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        history = buf.get_history()
        assert len(history) == 1
        assert history[0].category == "system"
        assert history[0].fields == {}


# ---------------------------------------------------------------------------
# StderrCapture
# ---------------------------------------------------------------------------


class TestStderrCapture:
    def test_tees_to_original(self):
        original = io.StringIO()
        buf = LogBuffer()
        capture = StderrCapture(original, buf)

        capture.write("hello world\n")
        assert original.getvalue() == "hello world\n"

    def test_captures_complete_lines(self):
        original = io.StringIO()
        buf = LogBuffer()
        capture = StderrCapture(original, buf)

        capture.write("line one\nline two\n")
        history = buf.get_history()
        assert len(history) == 2
        assert history[0].message == "line one"
        assert history[0].level == "STDERR"
        assert history[0].category == "system"
        assert history[0].fields == {}
        assert history[1].message == "line two"

    def test_buffers_partial_lines(self):
        original = io.StringIO()
        buf = LogBuffer()
        capture = StderrCapture(original, buf)

        capture.write("partial")
        assert len(buf.get_history()) == 0  # no newline yet

        capture.write(" complete\n")
        history = buf.get_history()
        assert len(history) == 1
        assert history[0].message == "partial complete"

    def test_delegates_fileno(self):
        """fileno() should delegate to original stderr."""
        buf = LogBuffer()
        capture = StderrCapture(sys.stderr, buf)
        # Should not raise -- delegates to real stderr
        assert capture.fileno() == sys.stderr.fileno()

    def test_delegates_flush(self):
        original = io.StringIO()
        buf = LogBuffer()
        capture = StderrCapture(original, buf)
        # Should not raise
        capture.flush()

    def test_encoding_property(self):
        buf = LogBuffer()
        capture = StderrCapture(sys.stderr, buf)
        assert isinstance(capture.encoding, str)

    def test_writable_readable(self):
        original = io.StringIO()
        buf = LogBuffer()
        capture = StderrCapture(original, buf)
        assert capture.writable() is True
        assert capture.readable() is False

    def test_empty_lines_skipped(self):
        """Empty lines between newlines should not produce entries."""
        original = io.StringIO()
        buf = LogBuffer()
        capture = StderrCapture(original, buf)

        capture.write("\n\nhello\n\n")
        history = buf.get_history()
        # Only "hello" should be captured -- empty strings are skipped
        assert len(history) == 1
        assert history[0].message == "hello"


# ---------------------------------------------------------------------------
# setup_log_capture -- idempotency & stdout safety
# ---------------------------------------------------------------------------


class TestSetupLogCapture:
    def test_idempotent(self):
        """Calling setup_log_capture twice returns the same buffer."""
        import cocosearch.mcp.log_stream as mod

        # Reset module state for clean test
        old_buf = mod._log_buffer
        old_done = mod._setup_done
        mod._log_buffer = None
        mod._setup_done = False

        original_stderr = sys.stderr

        try:
            buf1 = mod.setup_log_capture()
            buf2 = mod.setup_log_capture()
            assert buf1 is buf2
        finally:
            # Restore original state
            sys.stderr = original_stderr
            mod._log_buffer = old_buf
            mod._setup_done = old_done
            # Remove any handlers we added
            root = logging.getLogger()
            root.handlers = [
                h for h in root.handlers if not isinstance(h, BufferHandler)
            ]

    def test_does_not_touch_stdout(self):
        """setup_log_capture must never modify sys.stdout."""
        import cocosearch.mcp.log_stream as mod

        old_buf = mod._log_buffer
        old_done = mod._setup_done
        mod._log_buffer = None
        mod._setup_done = False

        original_stdout = sys.stdout
        original_stderr = sys.stderr

        try:
            mod.setup_log_capture()
            assert sys.stdout is original_stdout
        finally:
            sys.stderr = original_stderr
            mod._log_buffer = old_buf
            mod._setup_done = old_done
            root = logging.getLogger()
            root.handlers = [
                h for h in root.handlers if not isinstance(h, BufferHandler)
            ]

    def test_get_log_buffer_returns_none_before_setup(self):
        import cocosearch.mcp.log_stream as mod

        old_buf = mod._log_buffer
        mod._log_buffer = None
        try:
            assert mod.get_log_buffer() is None
        finally:
            mod._log_buffer = old_buf


# ---------------------------------------------------------------------------
# RichLogHandler
# ---------------------------------------------------------------------------


class TestRichLogHandler:
    def test_formats_entry(self, capsys):
        handler = RichLogHandler()
        entry = LogEntry(
            timestamp=1740000000.0,
            level="INFO",
            category="search",
            message="Query received",
            fields={"query": "hello", "results": 5},
        )
        handler.handle(entry)
        captured = capsys.readouterr()
        assert "search" in captured.err or "Query received" in captured.err

    def test_formats_fields_inline(self, capsys):
        handler = RichLogHandler()
        entry = LogEntry(
            timestamp=1740000000.0,
            level="WARNING",
            category="infra",
            message="Connection failed",
            fields={"error": "timeout"},
        )
        handler.handle(entry)
        captured = capsys.readouterr()
        assert "timeout" in captured.err or "error" in captured.err

    def test_custom_file_bypasses_stderr(self):
        """RichLogHandler(file=...) writes to the given file, not stderr."""
        import io

        buf = io.StringIO()
        handler = RichLogHandler(file=buf)
        entry = LogEntry(
            timestamp=1740000000.0,
            level="INFO",
            category="search",
            message="Custom output",
            fields={},
        )
        handler.handle(entry)
        output = buf.getvalue()
        assert "Custom output" in output
        assert "INFO" in output

    def test_category_visible_in_rich_output(self):
        """Category badge like [search] must appear as visible text."""
        buf = io.StringIO()
        handler = RichLogHandler(file=buf)
        entry = LogEntry(
            timestamp=1740000000.0,
            level="INFO",
            category="search",
            message="test",
            fields={},
        )
        handler.handle(entry)
        output = buf.getvalue()
        assert "[search]" in output


# ---------------------------------------------------------------------------
# FileLogHandler
# ---------------------------------------------------------------------------


class TestFileLogHandler:
    def test_writes_to_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        handler = FileLogHandler(str(log_file))
        entry = LogEntry(
            timestamp=1740000000.0,
            level="INFO",
            category="search",
            message="Test log",
            fields={"key": "value"},
        )
        handler.handle(entry)
        handler.close()
        content = log_file.read_text()
        assert "Test log" in content
        assert "search" in content
        assert "key=value" in content

    def test_rotation_config(self, tmp_path):
        log_file = tmp_path / "test.log"
        handler = FileLogHandler(str(log_file), max_bytes=1024, backup_count=2)
        assert handler._max_bytes == 1024
        assert handler._backup_count == 2
        handler.close()


# ---------------------------------------------------------------------------
# LogBuffer handler integration
# ---------------------------------------------------------------------------


class TestLogBufferHandlers:
    def test_add_handler_called_on_append(self):
        buf = LogBuffer()
        calls = []

        class MockHandler:
            def handle(self, entry):
                calls.append(entry)

        buf.add_handler(MockHandler())
        entry = LogEntry(
            timestamp=1.0, level="INFO", category="search", message="test", fields={}
        )
        buf.append(entry)
        assert len(calls) == 1
        assert calls[0] == entry

    def test_handler_exception_does_not_break_append(self):
        buf = LogBuffer()

        class BadHandler:
            def handle(self, entry):
                raise RuntimeError("broken")

        buf.add_handler(BadHandler())
        entry = LogEntry(
            timestamp=1.0, level="INFO", category="system", message="test", fields={}
        )
        buf.append(entry)  # Should not raise
        assert len(buf.get_history()) == 1
