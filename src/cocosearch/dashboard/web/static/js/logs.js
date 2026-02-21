import { state } from './state.js';

const LOG_MAX_LINES = 1000;
const LOG_MAX_RETRIES = 5;

function _connectLogStream() {
    if (state.logEventSource) {
        state.logEventSource.close();
        state.logEventSource = null;
    }
    const es = new EventSource('/api/logs');
    state.logEventSource = es;

    es.onmessage = function(event) {
        state.logRetries = 0;
        try {
            const entry = JSON.parse(event.data);
            appendLogLine(entry);
        } catch(e) { /* ignore malformed */ }
    };

    es.addEventListener('history_done', function() {
        scrollLogsToBottom();
    });

    es.onerror = function() {
        es.close();
        state.logEventSource = null;
        state.logRetries++;
        if (state.logRetries <= LOG_MAX_RETRIES) {
            setTimeout(_connectLogStream, Math.min(1000 * Math.pow(2, state.logRetries - 1), 16000));
        }
    };

    es.onopen = function() { state.logRetries = 0; };
}

export function startLogStream() {
    if (state.logEventSource) return;
    state.logRetries = 0;
    _connectLogStream();
}

export function appendLogLine(entry) {
    const body = document.getElementById('logPanelBody');
    const div = document.createElement('div');
    div.className = 'log-line';

    // Format timestamp as HH:MM:SS
    const d = new Date(entry.ts * 1000);
    const ts = d.toTimeString().slice(0, 8);

    const tsSpan = document.createElement('span');
    tsSpan.className = 'log-ts';
    tsSpan.textContent = ts + ' ';

    const lvlSpan = document.createElement('span');
    lvlSpan.className = 'log-level-' + (entry.level || 'INFO');
    lvlSpan.textContent = (entry.level || 'INFO').padEnd(8);

    const msgSpan = document.createElement('span');
    msgSpan.textContent = entry.msg || '';

    div.appendChild(tsSpan);
    div.appendChild(lvlSpan);
    div.appendChild(msgSpan);
    body.appendChild(div);

    // Enforce max lines
    state.logLineCount++;
    while (body.children.length > LOG_MAX_LINES) {
        body.removeChild(body.firstChild);
        state.logLineCount = body.children.length;
    }

    // Update line count
    document.getElementById('logLineCount').textContent = state.logLineCount + ' lines';

    // Auto-scroll or show badge
    if (state.logAutoScroll) {
        body.scrollTop = body.scrollHeight;
    } else {
        const indicator = document.getElementById('logScrollIndicator');
        indicator.classList.add('visible');
    }

    // Unread badge if panel closed
    const panel = document.getElementById('logPanel');
    if (!panel.classList.contains('open')) {
        state.logUnreadCount++;
        document.getElementById('logBadge').classList.add('active');
    }
}

export function toggleLogPanel() {
    const panel = document.getElementById('logPanel');
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) {
        state.logUnreadCount = 0;
        document.getElementById('logBadge').classList.remove('active');
        if (!state.logEventSource) startLogStream();
        // Scroll to bottom on open
        const body = document.getElementById('logPanelBody');
        body.scrollTop = body.scrollHeight;
        state.logAutoScroll = true;
        document.getElementById('logScrollIndicator').classList.remove('visible');
    }
}

export function scrollLogsToBottom() {
    const body = document.getElementById('logPanelBody');
    body.scrollTop = body.scrollHeight;
    state.logAutoScroll = true;
    document.getElementById('logScrollIndicator').classList.remove('visible');
}

export function clearLogPanel() {
    const body = document.getElementById('logPanelBody');
    body.innerHTML = '';
    state.logLineCount = 0;
    document.getElementById('logLineCount').textContent = '0 lines';
}
