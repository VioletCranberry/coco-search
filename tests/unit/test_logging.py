"""Tests for cocosearch.logging — structured domain logger (cs_log)."""

from __future__ import annotations

import logging

import pytest

from cocosearch.logging import CsLog, LogCategory, cs_log
from cocosearch.mcp.log_stream import LogBuffer

# ---------------------------------------------------------------------------
# LogCategory enum
# ---------------------------------------------------------------------------


class TestLogCategory:
    EXPECTED_CATEGORIES = {"search", "index", "mcp", "cache", "infra", "system", "deps"}

    def test_has_all_seven_categories(self) -> None:
        values = {c.value for c in LogCategory}
        assert values == self.EXPECTED_CATEGORIES

    def test_is_str_subclass(self) -> None:
        for cat in LogCategory:
            assert isinstance(cat, str)

    def test_category_values_match_names(self) -> None:
        for cat in LogCategory:
            assert cat.value == cat.name.lower()


# ---------------------------------------------------------------------------
# CsLog with explicit buffer
# ---------------------------------------------------------------------------


class TestCsLogWithBuffer:
    def test_search_creates_entry_with_correct_category_and_fields(self) -> None:
        buf = LogBuffer()
        log = CsLog(buffer=buf)
        log.search("query executed", query="hello", results=5)

        entries = buf.get_history()
        assert len(entries) == 1
        entry = entries[0]
        assert entry.category == "search"
        assert entry.message == "query executed"
        assert entry.level == "INFO"
        assert entry.fields == {"query": "hello", "results": 5}

    def test_mcp_creates_entry_with_correct_category(self) -> None:
        buf = LogBuffer()
        log = CsLog(buffer=buf)
        log.mcp("tool invoked", tool="search_code")

        entries = buf.get_history()
        assert len(entries) == 1
        entry = entries[0]
        assert entry.category == "mcp"
        assert entry.message == "tool invoked"
        assert entry.fields == {"tool": "search_code"}

    def test_custom_level_parameter(self) -> None:
        buf = LogBuffer()
        log = CsLog(buffer=buf)
        log.index("indexing failed", level="ERROR", reason="timeout")

        entries = buf.get_history()
        assert len(entries) == 1
        entry = entries[0]
        assert entry.level == "ERROR"
        assert entry.category == "index"
        assert entry.fields == {"reason": "timeout"}

    def test_all_seven_category_methods_exist_and_are_callable(self) -> None:
        buf = LogBuffer()
        log = CsLog(buffer=buf)

        methods = ["search", "index", "mcp", "cache", "infra", "system", "deps"]
        for method_name in methods:
            method = getattr(log, method_name)
            assert callable(method), f"{method_name} is not callable"
            method(f"test {method_name}")

        entries = buf.get_history()
        assert len(entries) == 7

        categories_seen = {e.category for e in entries}
        assert categories_seen == {c.value for c in LogCategory}

    def test_field_value_truncation(self) -> None:
        buf = LogBuffer()
        log = CsLog(buffer=buf)

        long_value = "x" * 600
        log.search("big field", data=long_value)

        entries = buf.get_history()
        assert len(entries) == 1
        truncated_value = entries[0].fields["data"]
        assert len(truncated_value) == 500
        assert truncated_value == "x" * 500

    def test_short_field_values_not_truncated(self) -> None:
        buf = LogBuffer()
        log = CsLog(buffer=buf)

        log.cache("hit", key="abc")

        entries = buf.get_history()
        assert entries[0].fields["key"] == "abc"

    def test_field_value_exactly_at_limit_not_truncated(self) -> None:
        buf = LogBuffer()
        log = CsLog(buffer=buf)

        exact_value = "a" * 500
        log.infra("check", val=exact_value)

        entries = buf.get_history()
        assert entries[0].fields["val"] == exact_value

    def test_non_string_field_value_truncation(self) -> None:
        """Non-string values whose str() exceeds 500 chars are truncated to a string."""
        buf = LogBuffer()
        log = CsLog(buffer=buf)

        long_list = list(range(200))  # str representation > 500 chars
        log.deps("big data", items=long_list)

        entries = buf.get_history()
        truncated = entries[0].fields["items"]
        assert isinstance(truncated, str)
        assert len(truncated) == 500

    def test_entry_has_timestamp(self) -> None:
        buf = LogBuffer()
        log = CsLog(buffer=buf)
        log.system("boot")

        entries = buf.get_history()
        assert entries[0].timestamp > 0


# ---------------------------------------------------------------------------
# CsLog fallback to Python logging (no buffer)
# ---------------------------------------------------------------------------


class TestCsLogFallback:
    @pytest.fixture(autouse=True)
    def _isolate_log_buffer(self):
        """Ensure get_log_buffer() returns None so the fallback path is exercised."""
        import cocosearch.mcp.log_stream as mod

        old_buf = mod._log_buffer
        mod._log_buffer = None
        yield
        mod._log_buffer = old_buf

    def test_fallback_to_python_logging_when_no_buffer(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        log = CsLog(buffer=None)

        with caplog.at_level(logging.INFO, logger="cocosearch"):
            log.search("fallback test", query="hello")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "[search]" in record.message
        assert "fallback test" in record.message
        assert "query=hello" in record.message

    def test_fallback_error_level(self, caplog: pytest.LogCaptureFixture) -> None:
        log = CsLog(buffer=None)

        with caplog.at_level(logging.DEBUG, logger="cocosearch"):
            log.infra("db down", level="ERROR", host="localhost")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == logging.ERROR
        assert "[infra]" in record.message
        assert "db down" in record.message
        assert "host=localhost" in record.message

    def test_fallback_no_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        log = CsLog(buffer=None)

        with caplog.at_level(logging.INFO, logger="cocosearch"):
            log.system("started")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.message == "[system] started"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------


class TestModuleSingleton:
    def test_cs_log_is_cslog_instance(self) -> None:
        assert isinstance(cs_log, CsLog)
