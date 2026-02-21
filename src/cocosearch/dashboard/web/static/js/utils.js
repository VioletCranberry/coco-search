import { state } from './state.js';

export function formatNumber(num) {
    return num.toLocaleString();
}

export function formatDate(dateStr) {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
    const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    if (diffDays === 0) return 'Today ' + time;
    if (diffDays === 1) return 'Yesterday ' + time;
    if (diffDays < 7) return `${diffDays} days ago`;

    if (date.getFullYear() === now.getFullYear()) {
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ', ' + time;
    }
    return date.toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' }) + ', ' + time;
}

export function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

export function isDarkMode() {
    return true; // Always dark for terminal theme
}

export function copyToClipboard(text) {
    navigator.clipboard.writeText(text).catch(() => {
        // Fallback for older browsers
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
    });
}

export function showToast(message, duration = 3000, type = 'error') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.style.background = type === 'success' ? 'var(--accent-green)' : 'var(--accent-red)';
    toast.classList.add('visible');
    if (state.toastTimer) clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(() => toast.classList.remove('visible'), duration);
}

export function copyPathWithFeedback(el, path) {
    copyToClipboard(path);
    // Flash green + show toast
    el.classList.add('copied');
    showToast('Copied!', 1500, 'success');
    setTimeout(() => el.classList.remove('copied'), 1200);
}

export function resolveFilePath(filePath) {
    if (filePath.startsWith('/')) return filePath;
    // Get source path from current index stats or project context
    const select = document.getElementById('indexSelect');
    const idx = parseInt(select.value);
    const stats = state.allIndexes[idx];
    const basePath = (stats && stats.source_path)
        || (state.projectContext && state.projectContext.project_path)
        || '';
    if (basePath) {
        return basePath.replace(/\/$/, '') + '/' + filePath;
    }
    return filePath;
}
