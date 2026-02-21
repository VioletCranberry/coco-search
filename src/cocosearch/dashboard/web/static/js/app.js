import { state } from './state.js';
import { copyToClipboard, copyPathWithFeedback } from './utils.js';
import { updateTabStatus } from './dashboard.js';
import { toggleLanguageDetails, toggleGrammarDetails } from './dashboard.js';
import {
    loadIndexList, onIndexSelectChange,
    reindex, stopIndexing, deleteIndex, indexCurrentProject,
} from './index-mgmt.js';
import { executeSearch, clearSearch, toggleCodeExpand, openInEditor, viewFile, closeFileModal } from './search.js';
import { startLogStream, toggleLogPanel, clearLogPanel, scrollLogsToBottom } from './logs.js';

// --- Expose functions needed by dynamically generated onclick handlers ---
window.toggleLanguageDetails = toggleLanguageDetails;
window.toggleGrammarDetails = toggleGrammarDetails;
window.toggleCodeExpand = toggleCodeExpand;
window.copyPathWithFeedback = copyPathWithFeedback;
window.copyToClipboard = copyToClipboard;
window.openInEditor = openInEditor;
window.viewFile = viewFile;

// --- Wire up static DOM event listeners ---

// Index selector
document.getElementById('indexSelect').addEventListener('change', onIndexSelectChange);

// Index management buttons
document.getElementById('reindexBtn').addEventListener('click', () => reindex(false));
document.getElementById('freshIndexBtn').addEventListener('click', () => reindex(true));
document.getElementById('stopIndexBtn').addEventListener('click', stopIndexing);
document.getElementById('deleteIndexBtn').addEventListener('click', deleteIndex);

// Search
document.getElementById('searchInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') executeSearch();
});
document.getElementById('searchBtn').addEventListener('click', executeSearch);
document.getElementById('clearSearchBtn').addEventListener('click', clearSearch);

// Search min score slider
document.getElementById('searchMinScore').addEventListener('input', (e) => {
    document.getElementById('minScoreValue').textContent = e.target.value;
});

// Index now button
document.getElementById('indexNowBtn').addEventListener('click', indexCurrentProject);

// Log panel
document.querySelector('.logs-btn').addEventListener('click', toggleLogPanel);
document.querySelector('.log-panel .log-header-btns button:first-child').addEventListener('click', clearLogPanel);
document.querySelector('.log-panel .log-header-btns button:last-child').addEventListener('click', toggleLogPanel);
document.getElementById('logScrollIndicator').addEventListener('click', scrollLogsToBottom);

// Log auto-scroll detection
document.getElementById('logPanelBody').addEventListener('scroll', function() {
    const body = this;
    const atBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 30;
    state.logAutoScroll = atBottom;
    if (atBottom) {
        document.getElementById('logScrollIndicator').classList.remove('visible');
    }
});

// File modal
document.getElementById('fileModalBackdrop').addEventListener('click', function(event) {
    if (event.target === this) closeFileModal();
});
document.querySelector('.file-modal-close').addEventListener('click', closeFileModal);
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeFileModal();
});

// --- Server heartbeat (auto-close on disconnect) ---
window.addEventListener('beforeunload', () => { state.isUnloading = true; });

function startHeartbeat() {
    const es = new EventSource('/api/heartbeat');
    let retries = 0;
    const maxRetries = 3;

    es.onerror = () => {
        es.close();
        if (state.isUnloading) return;
        if (retries < maxRetries) {
            retries++;
            setTimeout(startHeartbeat, 1000 * retries);
            return;
        }
        updateTabStatus(null);
        document.getElementById('disconnectOverlay').style.display = 'flex';
        window.close();
    };

    es.onopen = () => { retries = 0; };
}

// --- Uptime Clock ---
function updateUptime() {
    const uptime = document.getElementById('uptime');
    if (!uptime) return;

    const now = Date.now();
    const start = window.performance.timing.navigationStart;
    const diff = now - start;

    const hours = Math.floor(diff / 3600000).toString().padStart(2, '0');
    const mins = Math.floor((diff % 3600000) / 60000).toString().padStart(2, '0');
    const secs = Math.floor((diff % 60000) / 1000).toString().padStart(2, '0');

    uptime.textContent = `UPTIME: ${hours}:${mins}:${secs}`;
}

// --- Initialize ---
startHeartbeat();
loadIndexList();
setInterval(updateUptime, 1000);
updateUptime();
startLogStream();
