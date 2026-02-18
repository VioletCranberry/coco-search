# Search + AI Chat Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge the floating AI chat panel into the Search Code section as a pill-toggled mode, fix the non-functional Send button, and remove the floating panel.

**Architecture:** Single-file change to `index.html`. Add a segmented-control toggle (`[Search] [Ask AI]`) below the "Search Code" heading. Each mode shows/hides its content via `display` toggling to preserve state. Remove the floating chat panel (`.chat-toggle` button, `.chat-panel` sidebar) and its associated CSS/JS.

**Tech Stack:** HTML, CSS, vanilla JavaScript (no frameworks — matches existing codebase)

**File:** `src/cocosearch/dashboard/web/static/index.html` (all tasks modify this single file)

**Design doc:** `docs/plans/2026-02-18-search-chat-integration-design.md`

---

### Task 1: Add pill toggle CSS

**Files:**
- Modify: `src/cocosearch/dashboard/web/static/index.html:531-532` (after `.search-section h2` CSS block)

**Step 1: Add the segmented-control CSS**

Insert after the `.search-section h2` block (line 532) and before `.search-bar` (line 534):

```css
.search-mode-toggle {
    display: flex;
    gap: 0;
    margin-bottom: 14px;
}
.search-mode-toggle button {
    padding: 6px 16px;
    border: 1px solid var(--border-color);
    background: var(--bg-secondary);
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
}
.search-mode-toggle button:first-child {
    border-radius: 6px 0 0 6px;
}
.search-mode-toggle button:last-child {
    border-radius: 0 6px 6px 0;
    border-left: none;
}
.search-mode-toggle button.active {
    background: var(--accent-blue);
    color: white;
    border-color: var(--accent-blue);
}
.search-mode-toggle button.active + button {
    border-left: 1px solid var(--border-color);
}
.search-mode-toggle button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}
```

**Step 2: Verify visually**

Open the dashboard in a browser, confirm no CSS errors in DevTools. The toggle won't be visible yet (HTML added in Task 2).

---

### Task 2: Add pill toggle HTML and inline chat HTML

**Files:**
- Modify: `src/cocosearch/dashboard/web/static/index.html:1236-1281` (search-section HTML)

**Step 1: Add the toggle buttons and chat content area**

Replace the search-section block (lines 1236-1281) with:

```html
<div class="search-section">
    <h2>Search Code</h2>
    <div class="search-mode-toggle">
        <button id="modeSearchBtn" class="active" onclick="switchSearchMode('search')">Search</button>
        <button id="modeAskAIBtn" onclick="switchSearchMode('chat')" disabled title="Checking AI availability...">Ask AI</button>
    </div>

    <!-- Search mode content (existing) -->
    <div id="searchModeContent">
        <div class="search-bar">
            <input type="text" id="searchInput" placeholder="Search code with natural language..." autocomplete="off">
            <button class="action-btn" id="searchBtn" onclick="executeSearch()">Search</button>
            <button class="action-btn" id="clearSearchBtn" onclick="clearSearch()" style="display:none;">Clear</button>
        </div>
        <div class="search-filters">
            <label>Language:
                <select id="searchLanguage">
                    <option value="">All</option>
                </select>
            </label>
            <label>Symbol Type:
                <select id="searchSymbolType">
                    <option value="">All</option>
                    <option value="function">Function</option>
                    <option value="class">Class</option>
                    <option value="method">Method</option>
                    <option value="interface">Interface</option>
                </select>
            </label>
        </div>
        <details class="search-advanced">
            <summary>Advanced filters</summary>
            <div class="search-advanced-content">
                <label>Min score: <input type="range" id="searchMinScore" min="0" max="1" step="0.05" value="0.3"> <span id="minScoreValue">0.3</span></label>
                <label>Limit: <input type="number" id="searchLimit" min="1" max="50" value="10"></label>
                <label title="Combines semantic (vector) and keyword (tsvector) search via RRF fusion. Auto enables it only for code identifiers (camelCase, snake_case, PascalCase).">Hybrid search:
                    <select id="searchHybrid">
                        <option value="auto" selected>Auto</option>
                        <option value="on">On</option>
                        <option value="off">Off</option>
                    </select>
                    <span style="font-size: 11px; color: var(--text-secondary); font-style: italic;">Auto = on for code identifiers only</span>
                </label>
            </div>
        </details>
        <div class="search-results-area">
            <div class="search-loading" id="searchLoading">Searching...</div>
            <div class="search-empty" id="searchEmpty"></div>
            <div class="search-error" id="searchError"></div>
            <div id="searchResultsInfo" class="search-results-info" style="display: none;"></div>
            <div id="searchResults"></div>
        </div>
    </div>

    <!-- Ask AI mode content -->
    <div id="chatModeContent" style="display: none;">
        <div class="chat-inline-header">
            <button onclick="startNewChatSession()" title="New conversation" class="chat-new-btn">New conversation</button>
        </div>
        <div class="chat-inline-bar">
            <textarea id="chatInput" placeholder="Ask about your codebase..." rows="1"
                      onkeydown="handleChatKey(event)"></textarea>
            <button id="chatSend" onclick="sendChatMessage()">Send</button>
        </div>
        <div id="chatMessages" class="chat-messages"></div>
        <div id="chatTyping" class="chat-typing">Thinking</div>
    </div>
</div>
```

**Step 2: Verify in browser**

Open dashboard. The toggle should be visible. "Search" pill should be active (blue). "Ask AI" should be disabled/grayed out. Search mode content should display normally.

---

### Task 3: Add inline chat CSS (replace floating panel CSS)

**Files:**
- Modify: `src/cocosearch/dashboard/web/static/index.html:928-1093` (replace all `.chat-toggle` and `.chat-panel` CSS)

**Step 1: Replace the floating chat CSS block**

Replace the entire `/* AI Chat Panel */` CSS section (lines 928-1093) with inline chat styles:

```css
/* Inline AI Chat (inside search section) */
.chat-inline-header {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 8px;
}
.chat-new-btn {
    background: none;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 12px;
    padding: 4px 10px;
}
.chat-new-btn:hover {
    background: var(--bg-secondary);
    color: var(--text-primary);
}

.chat-inline-bar {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
}
.chat-inline-bar textarea {
    flex: 1;
    resize: none;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 14px;
    font-family: inherit;
    background: var(--bg-secondary);
    color: var(--text-primary);
    outline: none;
    min-height: 40px;
    max-height: 120px;
    transition: border-color 0.2s;
}
.chat-inline-bar textarea:focus {
    border-color: var(--accent-blue);
}
.chat-inline-bar textarea::placeholder {
    color: var(--text-muted);
}
.chat-inline-bar button {
    align-self: flex-end;
    padding: 10px 16px;
    background: var(--accent-blue);
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: opacity 0.15s;
}
.chat-inline-bar button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}
.chat-inline-bar button:hover:not(:disabled) {
    opacity: 0.9;
}

.chat-messages {
    max-height: 500px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 4px 0;
}

.chat-msg {
    max-width: 88%;
    padding: 10px 14px;
    border-radius: 12px;
    font-size: 13px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
}
.chat-msg.user {
    align-self: flex-end;
    background: var(--accent-blue);
    color: white;
    border-bottom-right-radius: 4px;
}
.chat-msg.assistant {
    align-self: flex-start;
    background: var(--bg-secondary);
    color: var(--text-primary);
    border-bottom-left-radius: 4px;
}
.chat-msg.error {
    align-self: center;
    background: var(--accent-red);
    color: white;
    font-size: 12px;
    opacity: 0.9;
}

.chat-typing {
    display: none;
    align-self: flex-start;
    padding: 10px 14px;
    background: var(--bg-secondary);
    border-radius: 12px;
    font-size: 13px;
    color: var(--text-muted);
}
.chat-typing.active { display: block; }
.chat-typing::after {
    content: '';
    animation: typingDots 1.2s infinite;
}
@keyframes typingDots {
    0%, 20% { content: '.'; }
    40% { content: '..'; }
    60%, 100% { content: '...'; }
}
```

**Step 2: Verify in browser**

Open dashboard. Search mode should look exactly like before. No visual regressions.

---

### Task 4: Remove floating chat HTML

**Files:**
- Modify: `src/cocosearch/dashboard/web/static/index.html:1400-1417` (floating chat HTML)

**Step 1: Delete the floating chat HTML**

Remove these lines entirely (the `<!-- AI Chat -->` block):

```html
<!-- AI Chat -->
<button id="chatToggle" class="chat-toggle" onclick="toggleChatPanel()" title="Ask AI about your codebase">&#128172;</button>
<div id="chatPanel" class="chat-panel">
    <div class="chat-header">
        <h3>AI Chat</h3>
        <div class="chat-header-actions">
            <button onclick="startNewChatSession()" title="New conversation">New</button>
            <button onclick="toggleChatPanel()" title="Close">&times;</button>
        </div>
    </div>
    <div id="chatMessages" class="chat-messages"></div>
    <div id="chatTyping" class="chat-typing">Thinking</div>
    <div class="chat-input-area">
        <textarea id="chatInput" placeholder="Ask about your codebase..." rows="1"
                  onkeydown="handleChatKey(event)"></textarea>
        <button id="chatSend" onclick="sendChatMessage()">Send</button>
    </div>
</div>
```

These elements now live inside `#chatModeContent` in the search section (added in Task 2).

**Step 2: Verify no console errors**

Open dashboard. Confirm no JS errors about missing `chatToggle` or `chatPanel` elements. The page should load cleanly.

---

### Task 5: Rewrite JavaScript — mode switching and chat initialization

**Files:**
- Modify: `src/cocosearch/dashboard/web/static/index.html:2649-2804` (AI Chat Panel JS section)

**Step 1: Replace the entire AI Chat Panel JS section**

Replace the block from `// ---- AI Chat Panel ----` (line 2649) through the `initChatPanel()` call (line 2804) with:

```javascript
// ---- Search Mode Toggle + AI Chat ----
let chatSessionId = null;
let chatAvailable = false;
let chatSending = false;
let currentSearchMode = 'search';

function switchSearchMode(mode) {
    if (mode === 'chat' && !chatAvailable) return;
    currentSearchMode = mode;

    const searchContent = document.getElementById('searchModeContent');
    const chatContent = document.getElementById('chatModeContent');
    const searchBtn = document.getElementById('modeSearchBtn');
    const chatBtn = document.getElementById('modeAskAIBtn');

    if (mode === 'search') {
        searchContent.style.display = '';
        chatContent.style.display = 'none';
        searchBtn.classList.add('active');
        chatBtn.classList.remove('active');
    } else {
        searchContent.style.display = 'none';
        chatContent.style.display = '';
        searchBtn.classList.remove('active');
        chatBtn.classList.add('active');

        // Auto-create session on first switch to chat
        if (!chatSessionId) {
            const sel = document.getElementById('indexSelector');
            if (sel && sel.value) {
                const indexName = sel.value;
                fetch('/api/project').then(r => r.json()).then(proj => {
                    createChatSession(indexName, proj.project_path || '.');
                }).catch(() => createChatSession(indexName, '.'));
            } else {
                addChatMessage('error', 'No index selected. Select an index above first.');
            }
        }
        // Focus the input
        document.getElementById('chatInput').focus();
    }
}

async function initChatPanel() {
    const chatBtn = document.getElementById('modeAskAIBtn');
    try {
        const res = await fetch('/api/ai-chat/status');
        const data = await res.json();
        chatAvailable = data.available === true;
        if (chatAvailable) {
            chatBtn.disabled = false;
            chatBtn.title = 'Ask AI about your codebase';
        } else {
            chatBtn.disabled = true;
            chatBtn.title = data.reason || 'Requires cocosearch[web-chat] and claude CLI';
        }
    } catch {
        chatBtn.disabled = true;
        chatBtn.title = 'AI chat unavailable — server error';
    }
}

async function createChatSession(indexName, projectPath) {
    const sendBtn = document.getElementById('chatSend');
    sendBtn.disabled = true;
    sendBtn.textContent = 'Connecting...';
    try {
        const res = await fetch('/api/ai-chat/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({index_name: indexName, project_path: projectPath})
        });
        const data = await res.json();
        if (data.session_id) {
            chatSessionId = data.session_id;
            addChatMessage('assistant', 'Session started. Ask me anything about your codebase.');
        } else {
            addChatMessage('error', data.error || 'Failed to start session');
        }
    } catch (e) {
        addChatMessage('error', 'Failed to connect: ' + e.message);
    } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send';
    }
}

function sendChatMessage() {
    if (chatSending) return;
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;

    if (!chatSessionId) {
        addChatMessage('error', 'Chat session not started. Check that an index is selected.');
        return;
    }

    input.value = '';
    input.style.height = 'auto';
    addChatMessage('user', text);
    chatSending = true;
    document.getElementById('chatSend').disabled = true;
    document.getElementById('chatTyping').classList.add('active');

    const params = new URLSearchParams({session_id: chatSessionId, message: text});
    const es = new EventSource('/api/ai-chat/stream?' + params);
    let assistantEl = null;
    let fullText = '';

    es.onmessage = (event) => {
        let item;
        try { item = JSON.parse(event.data); } catch { return; }

        if (item.type === 'token') {
            if (!assistantEl) {
                assistantEl = addChatMessage('assistant', '');
            }
            fullText += item.text;
            assistantEl.textContent = fullText;
            scrollChatToBottom();
        } else if (item.type === 'done') {
            es.close();
            finishChatSend();
        } else if (item.type === 'error') {
            es.close();
            addChatMessage('error', item.error || 'Unknown error');
            finishChatSend();
        }
    };

    es.onerror = () => {
        es.close();
        if (!fullText) addChatMessage('error', 'Connection lost');
        finishChatSend();
    };
}

function finishChatSend() {
    chatSending = false;
    document.getElementById('chatSend').disabled = false;
    document.getElementById('chatTyping').classList.remove('active');
    scrollChatToBottom();
}

function addChatMessage(role, text) {
    const area = document.getElementById('chatMessages');
    const el = document.createElement('div');
    el.className = 'chat-msg ' + role;
    el.textContent = text;
    area.appendChild(el);
    scrollChatToBottom();
    return el;
}

function scrollChatToBottom() {
    const area = document.getElementById('chatMessages');
    area.scrollTop = area.scrollHeight;
}

async function startNewChatSession() {
    if (chatSessionId) {
        try {
            await fetch('/api/ai-chat/session', {
                method: 'DELETE',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({session_id: chatSessionId})
            });
        } catch { /* best effort */ }
        chatSessionId = null;
    }
    document.getElementById('chatMessages').innerHTML = '';

    const sel = document.getElementById('indexSelector');
    if (sel && sel.value) {
        const indexName = sel.value;
        fetch('/api/project').then(r => r.json()).then(proj => {
            createChatSession(indexName, proj.project_path || '.');
        }).catch(() => createChatSession(indexName, '.'));
    } else {
        addChatMessage('error', 'No index selected. Select an index above first.');
    }
}

function handleChatKey(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendChatMessage();
    }
}

// Auto-resize chat textarea
document.getElementById('chatInput').addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});

initChatPanel();
```

**Key changes from original:**
1. `switchSearchMode()` — new function to toggle between search and chat modes
2. `sendChatMessage()` — no longer silently returns on null session; shows error message instead
3. `createChatSession()` — disables Send button and shows "Connecting..." during session creation
4. `initChatPanel()` — enables/disables the "Ask AI" pill toggle instead of showing/hiding a floating button
5. `toggleChatPanel()` — removed (no longer needed)
6. Removed `chatToggle` display logic

**Step 2: Verify full functionality**

1. Open dashboard in browser
2. Confirm "Search" pill is active, search works as before
3. If AI is available: "Ask AI" pill should be clickable
4. Click "Ask AI" — chat area appears, session auto-creates
5. Type a message and click Send or press Enter — message sends
6. Click "New conversation" — clears and starts fresh
7. Switch back to "Search" — search results preserved
8. Switch to "Ask AI" — chat history preserved

---

### Task 6: Commit

**Step 1: Run lint check**

```bash
# No Python changes, but verify HTML is well-formed by opening in browser
```

**Step 2: Commit all changes**

```bash
git add src/cocosearch/dashboard/web/static/index.html docs/plans/
git commit -m "feat(dashboard): integrate AI chat into search section with pill toggle

Replace the floating AI chat sidebar with an inline pill-toggled mode
inside the Search Code section. [Search] and [Ask AI] pills switch
between code search and AI chat within the same area.

Fixes: Send button and Enter key now show error feedback instead of
silently failing when chat session is not established.

Removes: floating chat bubble button and slide-in panel."
```

---

## Summary of Changes

| What | Before | After |
|------|--------|-------|
| AI chat location | Floating sidebar, bottom-right bubble | Inline in Search Code section via pill toggle |
| Mode switching | Open/close panel | `[Search] [Ask AI]` segmented control |
| Send with no session | Silent no-op | Error message: "Chat session not started..." |
| Session creation | No loading state | "Connecting..." button state |
| AI unavailable | Toggle button hidden | "Ask AI" pill grayed out with tooltip |
| State preservation | Panel open/close | Both modes preserved via display toggling |
