# Search + AI Chat Integration Design

## Problem

1. **Send button bug**: The AI chat's Send button and Enter key are non-functional when `chatSessionId` is null (silent failure — no user feedback).
2. **Discoverability**: AI chat is hidden behind a floating bubble button, separate from the main search UI.
3. **Confusion**: Users can't tell whether "Search Code" involves AI or not.

## Decision

Merge AI chat into the Search Code section using a **pill/segmented-control toggle** (`[Search] [Ask AI]`). Remove the floating chat panel entirely.

## Design

### Toggle Control

A segmented control sits between the section header and the input bar:

```
Search Code
[Search] [Ask AI]
┌─────────────────────────────────┐
│ Input bar here...               │
└─────────────────────────────────┘
```

- Active pill: `var(--accent-blue)` background, white text
- Inactive pill: `var(--bg-secondary)` background, `var(--text-secondary)` text
- Default: Search mode (always available)
- When AI unavailable: "Ask AI" pill is grayed out (`opacity: 0.4`, `cursor: not-allowed`) with tooltip: "Requires cocosearch[web-chat] and claude CLI"

### Search Mode

Unchanged from current behavior: search input, language/symbol filters, advanced filters `<details>`, results area.

### Ask AI Mode

- **Input**: `<textarea>` (auto-resizing, max 120px) with Send button. Placeholder: "Ask about your codebase..."
- **Chat messages**: Fixed 500px `max-height` scrollable area below input. User messages right-aligned (blue), assistant messages left-aligned (secondary bg). Same styling as current panel.
- **Typing indicator**: "Thinking..." with dot animation below messages
- **Session management**: "New conversation" button top-right of chat area. Session auto-creates on first switch to Ask AI mode.
- **Filters**: Hidden (not relevant to chat)

### Send Button Bug Fix

- If `chatSessionId` is null when user tries to send, show inline error: "Chat session not started. Check that an index is selected."
- Disable Send button + show "Connecting..." during session creation
- On session creation failure, show the error in chat messages area

### State Preservation

Switching modes uses `display: none` toggling — both search results and chat history are preserved across switches.

### Removed

- Floating chat toggle button (`.chat-toggle`)
- Slide-in chat panel (`.chat-panel`, `.chat-panel.open`)
- All associated CSS and positioning logic

### Files Changed

- `src/cocosearch/dashboard/web/static/index.html` — HTML structure, CSS, JavaScript
- No backend changes needed (API endpoints remain the same)
