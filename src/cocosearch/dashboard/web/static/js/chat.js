import { state } from './state.js';

function renderMarkdown(text) {
    try {
        const html = marked.parse(text, { breaks: true, gfm: true });
        return DOMPurify.sanitize(html);
    } catch {
        return DOMPurify.sanitize(text);
    }
}

function scrollChatToBottom() {
    const area = document.getElementById('chatMessages');
    area.scrollTop = area.scrollHeight;
}

function addChatMessage(role, text) {
    const area = document.getElementById('chatMessages');
    const el = document.createElement('div');
    el.className = 'chat-msg ' + role;
    if (role === 'assistant' && text) {
        el.innerHTML = renderMarkdown(text);
        // Defer Prism highlighting
        requestAnimationFrame(() => Prism.highlightAllUnder(el));
    } else {
        el.textContent = text;
    }
    area.appendChild(el);
    scrollChatToBottom();
    return el;
}

function addToolUseElement(toolName) {
    const area = document.getElementById('chatMessages');
    const details = document.createElement('details');
    details.className = 'chat-tool-use';
    const summary = document.createElement('summary');
    summary.textContent = toolName;
    details.appendChild(summary);
    const inputDiv = document.createElement('div');
    inputDiv.className = 'tool-input';
    inputDiv.textContent = '...';
    details.appendChild(inputDiv);
    area.appendChild(details);
    scrollChatToBottom();
    return details;
}

function updateChatStats(stats) {
    const bar = document.getElementById('chatStatsBar');
    const parts = [];

    if (stats.num_turns != null) {
        parts.push('Turns: ' + stats.num_turns);
    }

    if (stats.usage) {
        const input = stats.usage.input_tokens || stats.usage.input || 0;
        const output = stats.usage.output_tokens || stats.usage.output || 0;
        const total = input + output;
        const display = total >= 1000 ? (total / 1000).toFixed(1) + 'k' : total;
        parts.push('Tokens: ' + display);
    }

    if (stats.cost_usd != null && typeof stats.cost_usd === 'number') {
        parts.push('$' + stats.cost_usd.toFixed(4));
    }

    bar.innerHTML = parts.join(' &middot; ');
    bar.classList.add('visible');
}

function finishChatSend() {
    state.chatSending = false;
    document.getElementById('chatSend').disabled = false;
    document.getElementById('chatTyping').classList.remove('active');
    scrollChatToBottom();
}

export async function createChatSession(indexName, projectPath) {
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
        if (res.ok && data.session_id) {
            state.chatSessionId = data.session_id;
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

export function sendChatMessage() {
    if (state.chatSending) return;
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;

    if (!state.chatSessionId) {
        addChatMessage('error', 'Chat session not started. Check that an index is selected.');
        return;
    }

    input.value = '';
    input.style.height = 'auto';
    addChatMessage('user', text);
    state.chatSending = true;
    document.getElementById('chatSend').disabled = true;
    document.getElementById('chatTyping').classList.add('active');

    const params = new URLSearchParams({session_id: state.chatSessionId, message: text});
    const es = new EventSource('/api/ai-chat/stream?' + params);
    let assistantEl = null;
    let fullText = '';
    let renderScheduled = false;
    // Track tool uses to attach input later
    const pendingTools = {};

    es.onmessage = (event) => {
        let item;
        try { item = JSON.parse(event.data); } catch { return; }

        if (item.type === 'token') {
            if (!assistantEl) {
                assistantEl = addChatMessage('assistant', '');
            }
            fullText += item.text;
            if (!renderScheduled) {
                renderScheduled = true;
                requestAnimationFrame(() => {
                    assistantEl.innerHTML = renderMarkdown(fullText);
                    scrollChatToBottom();
                    renderScheduled = false;
                });
            }
        } else if (item.type === 'tool_start') {
            const toolEl = addToolUseElement(item.name);
            if (item.tool_id) pendingTools[item.tool_id] = toolEl;
            // Reset assistantEl so next text goes into a new message bubble
            assistantEl = null;
            fullText = '';
        } else if (item.type === 'tool_input') {
            // Find the pending tool element by tool_id or fallback to name match
            let toolEl = item.tool_id ? pendingTools[item.tool_id] : null;
            if (!toolEl) {
                // Fallback: find by tool name in summary text
                toolEl = Object.values(pendingTools).find(
                    el => el.querySelector('summary')?.textContent === item.name
                ) || null;
            }
            if (toolEl) {
                const inputDiv = toolEl.querySelector('.tool-input');
                if (inputDiv) {
                    inputDiv.textContent = JSON.stringify(item.input, null, 2);
                }
            }
        } else if (item.type === 'stats') {
            updateChatStats(item);
        } else if (item.type === 'done') {
            // Final Prism highlight pass on the last assistant message
            if (assistantEl) {
                Prism.highlightAllUnder(assistantEl);
            }
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

export function switchSearchMode(mode) {
    if (mode === 'chat' && !state.chatAvailable) return;

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
        if (!state.chatSessionId) {
            const sel = document.getElementById('indexSelect');
            if (sel && sel.value) {
                const indexName = state.allIndexes[parseInt(sel.value)]?.name || sel.value;
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

export async function initChatPanel() {
    const chatBtn = document.getElementById('modeAskAIBtn');
    try {
        const res = await fetch('/api/ai-chat/status');
        const data = await res.json();
        state.chatAvailable = data.available === true;
        if (state.chatAvailable) {
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

export async function startNewChatSession() {
    if (state.chatSessionId) {
        try {
            await fetch('/api/ai-chat/session', {
                method: 'DELETE',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({session_id: state.chatSessionId})
            });
        } catch { /* best effort */ }
        state.chatSessionId = null;
    }
    document.getElementById('chatMessages').innerHTML = '';
    // Reset stats
    const statsBar = document.getElementById('chatStatsBar');
    statsBar.innerHTML = '';
    statsBar.classList.remove('visible');

    const sel = document.getElementById('indexSelect');
    if (sel && sel.value) {
        const indexName = state.allIndexes[parseInt(sel.value)]?.name || sel.value;
        fetch('/api/project').then(r => r.json()).then(proj => {
            createChatSession(indexName, proj.project_path || '.');
        }).catch(() => createChatSession(indexName, '.'));
    } else {
        addChatMessage('error', 'No index selected. Select an index above first.');
    }
}

export function handleChatKey(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendChatMessage();
    }
}
