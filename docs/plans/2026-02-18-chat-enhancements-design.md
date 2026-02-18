# Chat Enhancements Design: Markdown, Tools, Usage Stats

## Features

### 1. Markdown Rendering

Add `marked.js` (CDN) + `DOMPurify` (CDN) for safe markdown rendering of assistant messages. User messages stay plain text. After rendering, call `Prism.highlightAllUnder(el)` to highlight code blocks (Prism.js already loaded on the page).

During streaming: accumulate `fullText`, re-render markdown on each token via `marked.parse()` + DOMPurify sanitization + `innerHTML`. Final Prism highlight pass on `done`.

### 2. Tool Use Display (collapsible)

Parse two event sources in `_stream_response()`:
- `StreamEvent`: `content_block_start` events where `content_block.type === "tool_use"` — extract tool name
- `AssistantMessage.content`: `ToolUseBlock` objects — extract `name` and `input`

New SSE events:
```json
{"type": "tool_start", "name": "search_codebase", "tool_id": "..."}
{"type": "tool_input", "name": "search_codebase", "input": {"query": "...", "limit": 10}}
```

Frontend: collapsible `<details>` elements in chat flow showing tool name, expandable to see input params.

### 3. Session Stats Bar

Persistent stats line below chat input:
- Turns: `3/20` (ResultMessage.num_turns / max_turns=20)
- Tokens: `12.4k` (ResultMessage.usage)
- Cost: `$0.03` (ResultMessage.total_cost_usd)
- Time left: `28m left` (30min timeout, client-side countdown, reset on each response)

New SSE event at end of each turn:
```json
{"type": "stats", "num_turns": 3, "max_turns": 20, "usage": {...}, "cost_usd": 0.03}
```

### Files Changed

- `src/cocosearch/chat/session.py` — Extend `_stream_response()` for tool_use events and ResultMessage stats
- `src/cocosearch/dashboard/web/static/index.html` — CDN libs, markdown rendering, tool use display, stats bar

### Not Doing

- Tool result display (too verbose)
- Per-message token breakdown (only cumulative)
- Persistent usage history across sessions
