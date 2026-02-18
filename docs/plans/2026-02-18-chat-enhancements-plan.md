# Chat Enhancements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add markdown rendering, tool use display, and session stats to the AI chat in the dashboard.

**Architecture:** Backend changes to `session.py` to emit new SSE event types (tool_start, tool_input, stats). Frontend changes to `index.html` to render markdown, display tool use, and show stats bar.

**Tech Stack:** Python (session.py), HTML/CSS/JS (index.html), marked.js + DOMPurify (CDN)

---

### Task 1: Backend — Extend _stream_response() for tool use + stats

**Files:**
- Modify: `src/cocosearch/chat/session.py`

**Changes:**

1. Add `ToolUseBlock` to SDK imports (line 21-29)
2. Extend `_stream_response()` to:
   - Parse `content_block_start` events for tool_use blocks → emit `{"type": "tool_start", "name": ..., "tool_id": ...}`
   - Parse `AssistantMessage.content` for `ToolUseBlock` objects → emit `{"type": "tool_input", "name": ..., "input": ...}`
   - Parse `ResultMessage` → emit `{"type": "stats", "num_turns": ..., "max_turns": 20, "usage": ..., "cost_usd": ...}`

### Task 2: Frontend — CDN libs, markdown rendering, tool display, stats bar

**Files:**
- Modify: `src/cocosearch/dashboard/web/static/index.html`

**Changes:**

1. Add marked.js + DOMPurify CDN scripts in `<head>`
2. Add stats bar HTML below chat input bar in `#chatModeContent`
3. Add CSS for `.chat-stats-bar`, `.chat-tool-use` elements
4. Update `addChatMessage()` to render markdown for assistant messages
5. Update `sendChatMessage()` SSE handler to process `tool_start`, `tool_input`, `stats` events
6. Add idle timeout countdown timer (client-side `setInterval`)
7. Update `startNewChatSession()` to reset stats

### Task 3: Commit
