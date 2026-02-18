"""Chat session management for the AI chat feature.

Wraps the Claude Agent SDK to provide multi-turn conversations about
the user's codebase. Each ChatSession owns a private asyncio event loop
in a daemon thread, bridging the sync HTTP handlers and async SDK client.
"""

import asyncio
import logging
import queue
import shutil
import threading
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# Guarded SDK import — feature is unavailable when not installed
try:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        ResultMessage,
        ToolUseBlock,
        create_sdk_mcp_server,
        tool,
    )
    from claude_agent_sdk.types import StreamEvent

    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False

_MAX_SESSIONS = 10
_SESSION_TIMEOUT_SECS = 30 * 60  # 30 minutes
_CLEANUP_INTERVAL_SECS = 5 * 60  # 5 minutes


def is_chat_available() -> bool:
    """Return True if the Claude Agent SDK is installed."""
    return _SDK_AVAILABLE


def check_cli_available() -> bool:
    """Return True if the Claude Code CLI binary is on PATH.

    Checks both ``claude`` (npm/brew/direct install) and ``claude-code``
    since the binary name varies by installation method.
    """
    return shutil.which("claude") is not None or shutil.which("claude-code") is not None


def _build_search_tool() -> Any:
    """Create the search_codebase SDK MCP tool wrapping cocosearch.search.search()."""
    if not _SDK_AVAILABLE:
        return None

    @tool(
        "search_codebase",
        "Search the indexed codebase using natural language. "
        "Returns code chunks ranked by semantic similarity.",
        {"query": str, "limit": int},
    )
    async def search_codebase(args: dict[str, Any]) -> dict[str, Any]:
        from cocosearch.search import byte_to_line, read_chunk_content, search

        query_text = args.get("query", "")
        limit = args.get("limit", 10)

        # index_name is injected by the closure at session creation time
        try:
            results = search(
                query=query_text,
                index_name=search_codebase._index_name,
                limit=limit,
                use_hybrid=True,
            )
        except Exception as exc:
            return {
                "content": [{"type": "text", "text": f"Search error: {exc}"}],
                "is_error": True,
            }

        if not results:
            return {
                "content": [
                    {"type": "text", "text": "No results found for that query."}
                ]
            }

        lines: list[str] = []
        for r in results:
            start_line = byte_to_line(r.filename, r.start_byte)
            end_line = byte_to_line(r.filename, r.end_byte)
            content = read_chunk_content(r.filename, r.start_byte, r.end_byte)
            header = f"## {r.filename}:{start_line}-{end_line}"
            if r.symbol_name:
                header += f" ({r.symbol_type}: {r.symbol_name})"
            lines.append(header)
            lines.append(f"Score: {r.score:.3f}")
            lines.append("```")
            lines.append(content)
            lines.append("```")
            lines.append("")

        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    return search_codebase


class ChatSession:
    """A single AI chat session backed by ClaudeSDKClient.

    Owns a private asyncio event loop running in a daemon thread.
    """

    def __init__(self, session_id: str, index_name: str, project_path: str):
        self.session_id = session_id
        self.index_name = index_name
        self.project_path = project_path
        self.last_activity = time.monotonic()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._client: Any = None  # ClaudeSDKClient when available
        self._started = False
        self._closed = False

    def start(self) -> None:
        """Start the background event loop and connect the SDK client."""
        if not _SDK_AVAILABLE:
            raise RuntimeError("claude-agent-sdk is not installed")

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name=f"chat-{self.session_id[:8]}"
        )
        self._thread.start()

        # Connect client inside the loop
        future = asyncio.run_coroutine_threadsafe(self._connect(), self._loop)
        future.result(timeout=30)
        self._started = True

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _connect(self) -> None:
        search_tool = _build_search_tool()
        # Inject the index name so the tool closure can access it
        search_tool._index_name = self.index_name

        search_server = create_sdk_mcp_server(
            name="coco",
            version="1.0.0",
            tools=[search_tool],
        )

        options = ClaudeAgentOptions(
            mcp_servers={"coco": search_server},
            allowed_tools=[
                "Read",
                "Grep",
                "Glob",
                "mcp__coco__search_codebase",
            ],
            permission_mode="bypassPermissions",
            cwd=self.project_path,
            system_prompt=(
                f"You are a code assistant for the project at {self.project_path}. "
                "ALWAYS start with the search_codebase tool for any code question — "
                "it provides semantic search over the indexed codebase and is your "
                "primary tool. Only fall back to Read, Grep, or Glob when you need "
                "to read a specific file path or do an exact string match. "
                "Always cite file paths and line numbers in your answers."
            ),
            include_partial_messages=True,
            max_turns=20,
        )
        self._client = ClaudeSDKClient(options)
        await self._client.connect()

    def send_message(self, text: str, response_queue: queue.Queue) -> None:
        """Send a message and stream response tokens onto *response_queue*.

        Puts dicts ``{"type": "token", "text": ...}`` for each text delta,
        ``{"type": "done"}`` when finished, or ``{"type": "error", ...}`` on failure.
        The caller reads from the queue until it sees ``done`` or ``error``.
        """
        if self._closed or not self._started:
            response_queue.put({"type": "error", "error": "Session not active"})
            return

        self.last_activity = time.monotonic()

        future = asyncio.run_coroutine_threadsafe(
            self._stream_response(text, response_queue), self._loop
        )
        # Don't block — the coroutine pushes to the queue asynchronously
        future.add_done_callback(lambda f: self._handle_future_error(f, response_queue))

    def _handle_future_error(
        self, future: asyncio.Future, response_queue: queue.Queue
    ) -> None:
        exc = future.exception()
        if exc is not None:
            logger.error("Chat stream error: %s", exc)
            try:
                response_queue.put({"type": "error", "error": str(exc)})
            except Exception:
                pass

    async def _stream_response(self, text: str, response_queue: queue.Queue) -> None:
        try:
            await self._client.query(text)

            async for message in self._client.receive_response():
                if isinstance(message, StreamEvent):
                    # Extract text deltas and tool use from raw Anthropic stream events
                    event = message.event
                    if isinstance(event, dict):
                        event_type = event.get("type", "")
                        if event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                token_text = delta.get("text", "")
                                if token_text:
                                    response_queue.put(
                                        {"type": "token", "text": token_text}
                                    )
                        elif event_type == "content_block_start":
                            cb = event.get("content_block", {})
                            if cb.get("type") == "tool_use":
                                response_queue.put(
                                    {
                                        "type": "tool_start",
                                        "name": cb.get("name", ""),
                                        "tool_id": cb.get("id", ""),
                                    }
                                )
                elif isinstance(message, AssistantMessage):
                    # TextBlocks already emitted via StreamEvent deltas — only
                    # extract tool use blocks here.
                    for block in message.content:
                        if isinstance(block, ToolUseBlock):
                            response_queue.put(
                                {
                                    "type": "tool_input",
                                    "name": block.name,
                                    "tool_id": block.id,
                                    "input": block.input,
                                }
                            )
                elif isinstance(message, ResultMessage):
                    # Emit session stats from the completed turn
                    stats: dict[str, Any] = {
                        "type": "stats",
                        "num_turns": message.num_turns,
                        "max_turns": 20,
                        "cost_usd": message.total_cost_usd,
                        "duration_ms": message.duration_ms,
                    }
                    if message.usage:
                        stats["usage"] = message.usage
                    response_queue.put(stats)

            response_queue.put({"type": "done"})
        except Exception as exc:
            logger.error("Error streaming chat response: %s", exc)
            response_queue.put({"type": "error", "error": str(exc)})

    def close(self) -> None:
        """Disconnect the client and stop the event loop."""
        if self._closed:
            return
        self._closed = True

        if self._client and self._loop and self._loop.is_running():
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._client.disconnect(), self._loop
                )
                future.result(timeout=5)
            except Exception:
                pass

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)


class ChatSessionManager:
    """Manages active chat sessions with capacity limits and idle timeouts."""

    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._lock = threading.Lock()
        self._cleanup_thread: threading.Thread | None = None

    def _start_cleanup(self) -> None:
        if self._cleanup_thread is not None:
            return
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop, daemon=True, name="chat-cleanup"
        )
        self._cleanup_thread.start()

    def _cleanup_loop(self) -> None:
        while True:
            time.sleep(_CLEANUP_INTERVAL_SECS)
            self._evict_expired()

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired: list[str] = []
        with self._lock:
            for sid, session in self._sessions.items():
                if now - session.last_activity > _SESSION_TIMEOUT_SECS:
                    expired.append(sid)

        for sid in expired:
            self.close_session(sid)

    def create_session(self, index_name: str, project_path: str) -> ChatSession | None:
        """Create a new chat session. Returns None if at capacity."""
        self._start_cleanup()

        with self._lock:
            if len(self._sessions) >= _MAX_SESSIONS:
                return None
            session_id = str(uuid.uuid4())
            session = ChatSession(session_id, index_name, project_path)
            self._sessions[session_id] = session

        session.start()
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is not None:
            session.last_activity = time.monotonic()
        return session

    def close_session(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        session.close()
        return True

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._sessions)


# Module-level singleton
_manager: ChatSessionManager | None = None
_manager_lock = threading.Lock()


def get_session_manager() -> ChatSessionManager:
    """Return the global ChatSessionManager singleton."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = ChatSessionManager()
    return _manager
