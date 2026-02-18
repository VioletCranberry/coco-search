"""AI chat module for the CocoSearch web dashboard.

Provides a chat interface powered by the Claude Agent SDK that lets users
ask questions about their codebase directly from the browser. Requires
the optional ``claude-agent-sdk`` dependency (install with ``cocosearch[web-chat]``).
"""

from cocosearch.chat.session import (
    ChatSession,
    ChatSessionManager,
    get_session_manager,
    is_chat_available,
    check_cli_available,
)

__all__ = [
    "ChatSession",
    "ChatSessionManager",
    "get_session_manager",
    "is_chat_available",
    "check_cli_available",
]
