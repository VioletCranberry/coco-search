"""Unit tests for cocosearch.chat.session module."""

import queue
import threading
import time
from unittest.mock import patch

import pytest


class TestIsAvailable:
    """Tests for SDK availability detection."""

    def test_is_chat_available_returns_bool(self):
        from cocosearch.chat.session import is_chat_available

        result = is_chat_available()
        assert isinstance(result, bool)

    def test_check_cli_available_with_claude_on_path(self):
        with patch(
            "cocosearch.chat.session.shutil.which",
            side_effect=lambda cmd: "/usr/bin/claude" if cmd == "claude" else None,
        ):
            from cocosearch.chat.session import check_cli_available

            assert check_cli_available() is True

    def test_check_cli_available_with_claude_code_on_path(self):
        with patch(
            "cocosearch.chat.session.shutil.which",
            side_effect=lambda cmd: (
                "/usr/bin/claude-code" if cmd == "claude-code" else None
            ),
        ):
            from cocosearch.chat.session import check_cli_available

            assert check_cli_available() is True

    def test_check_cli_available_without_claude(self):
        with patch("cocosearch.chat.session.shutil.which", return_value=None):
            from cocosearch.chat.session import check_cli_available

            assert check_cli_available() is False


class TestChatSessionManager:
    """Tests for session manager capacity, lookup, and cleanup."""

    def _make_manager(self):
        from cocosearch.chat.session import ChatSessionManager

        return ChatSessionManager()

    @patch("cocosearch.chat.session._SDK_AVAILABLE", True)
    @patch("cocosearch.chat.session.ChatSession.start")
    def test_create_session_returns_session(self, mock_start):
        mgr = self._make_manager()
        session = mgr.create_session("test_index", "/tmp/project")
        assert session is not None
        assert session.index_name == "test_index"
        assert session.project_path == "/tmp/project"
        mock_start.assert_called_once()

    @patch("cocosearch.chat.session._SDK_AVAILABLE", True)
    @patch("cocosearch.chat.session.ChatSession.start")
    def test_get_session_found(self, mock_start):
        mgr = self._make_manager()
        session = mgr.create_session("idx", "/tmp")
        found = mgr.get_session(session.session_id)
        assert found is session

    @patch("cocosearch.chat.session._SDK_AVAILABLE", True)
    @patch("cocosearch.chat.session.ChatSession.start")
    def test_get_session_not_found(self, mock_start):
        mgr = self._make_manager()
        assert mgr.get_session("nonexistent") is None

    @patch("cocosearch.chat.session._SDK_AVAILABLE", True)
    @patch("cocosearch.chat.session.ChatSession.start")
    def test_close_session(self, mock_start):
        mgr = self._make_manager()
        session = mgr.create_session("idx", "/tmp")
        with patch.object(session, "close") as mock_close:
            result = mgr.close_session(session.session_id)
            assert result is True
            mock_close.assert_called_once()
        assert mgr.active_count == 0

    def test_close_session_not_found(self):
        mgr = self._make_manager()
        assert mgr.close_session("nonexistent") is False

    @patch("cocosearch.chat.session._MAX_SESSIONS", 2)
    @patch("cocosearch.chat.session._SDK_AVAILABLE", True)
    @patch("cocosearch.chat.session.ChatSession.start")
    def test_capacity_limit(self, mock_start):
        mgr = self._make_manager()
        s1 = mgr.create_session("idx", "/tmp")
        s2 = mgr.create_session("idx", "/tmp")
        s3 = mgr.create_session("idx", "/tmp")
        assert s1 is not None
        assert s2 is not None
        assert s3 is None
        assert mgr.active_count == 2

    @patch("cocosearch.chat.session._SESSION_TIMEOUT_SECS", 0)
    @patch("cocosearch.chat.session._SDK_AVAILABLE", True)
    @patch("cocosearch.chat.session.ChatSession.start")
    def test_evict_expired(self, mock_start):
        mgr = self._make_manager()
        session = mgr.create_session("idx", "/tmp")
        # Simulate old activity
        session.last_activity = time.monotonic() - 100
        with patch.object(session, "close"):
            mgr._evict_expired()
        assert mgr.active_count == 0

    @patch("cocosearch.chat.session._SDK_AVAILABLE", True)
    @patch("cocosearch.chat.session.ChatSession.start")
    def test_active_count(self, mock_start):
        mgr = self._make_manager()
        assert mgr.active_count == 0
        mgr.create_session("idx", "/tmp")
        assert mgr.active_count == 1


class TestChatSession:
    """Tests for individual chat session behavior."""

    def _make_session(self):
        from cocosearch.chat.session import ChatSession

        return ChatSession("test-id", "test_index", "/tmp/project")

    @patch("cocosearch.chat.session._SDK_AVAILABLE", False)
    def test_start_raises_without_sdk(self):
        session = self._make_session()
        with pytest.raises(RuntimeError, match="claude-agent-sdk is not installed"):
            session.start()

    def test_send_message_before_start(self):
        session = self._make_session()
        q = queue.Queue()
        session.send_message("hello", q)
        msg = q.get(timeout=1)
        assert msg["type"] == "error"
        assert "not active" in msg["error"]

    def test_send_message_after_close(self):
        session = self._make_session()
        session._started = True
        session._closed = True
        q = queue.Queue()
        session.send_message("hello", q)
        msg = q.get(timeout=1)
        assert msg["type"] == "error"

    def test_close_idempotent(self):
        session = self._make_session()
        session.close()
        session.close()  # Should not raise
        assert session._closed is True

    def test_initial_state(self):
        session = self._make_session()
        assert session._started is False
        assert session._closed is False
        assert session._client is None


class TestGetSessionManager:
    """Tests for the module-level singleton."""

    def test_returns_same_instance(self):
        import cocosearch.chat.session as mod

        # Reset singleton for test isolation
        with patch.object(mod, "_manager", None):
            with patch.object(mod, "_manager_lock", threading.Lock()):
                m1 = mod.get_session_manager()
                m2 = mod.get_session_manager()
                assert m1 is m2
