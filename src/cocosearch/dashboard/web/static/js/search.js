import { state } from './state.js';
import { escapeHtml, copyToClipboard, showToast, resolveFilePath } from './utils.js';

export async function executeSearch() {
    const query = document.getElementById('searchInput').value.trim();
    if (!query) return;

    const select = document.getElementById('indexSelect');
    const indexIndex = parseInt(select.value);
    const stats = state.allIndexes[indexIndex];
    if (!stats) return;

    const language = document.getElementById('searchLanguage').value || undefined;
    const symbolType = document.getElementById('searchSymbolType').value || undefined;
    const minScore = parseFloat(document.getElementById('searchMinScore').value);
    const limit = parseInt(document.getElementById('searchLimit').value) || 10;
    const hybridVal = document.getElementById('searchHybrid').value;
    const useHybrid = hybridVal === 'on' ? true : hybridVal === 'off' ? false : undefined;

    // Show loading
    document.getElementById('searchLoading').style.display = 'block';
    document.getElementById('searchEmpty').style.display = 'none';
    document.getElementById('searchError').style.display = 'none';
    document.getElementById('searchResultsInfo').style.display = 'none';
    document.getElementById('searchResults').innerHTML = '';
    document.getElementById('searchBtn').disabled = true;

    try {
        const body = {
            query: query,
            index_name: stats.name,
            limit: limit,
            min_score: minScore,
        };
        if (language) body.language = language;
        if (symbolType) body.symbol_type = symbolType;
        if (useHybrid !== undefined) body.use_hybrid = useHybrid;

        const resp = await fetch('/api/search', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        });
        const data = await resp.json();

        document.getElementById('searchLoading').style.display = 'none';
        document.getElementById('searchBtn').disabled = false;

        if (!resp.ok) {
            document.getElementById('searchError').textContent = data.error || 'Search failed';
            document.getElementById('searchError').style.display = 'block';
            document.getElementById('clearSearchBtn').style.display = '';
            return;
        }

        displaySearchResults(data);
        document.getElementById('clearSearchBtn').style.display = '';
    } catch (err) {
        document.getElementById('searchLoading').style.display = 'none';
        document.getElementById('searchBtn').disabled = false;
        document.getElementById('searchError').textContent = 'Search failed: ' + err.message;
        document.getElementById('searchError').style.display = 'block';
        document.getElementById('clearSearchBtn').style.display = '';
    }
}

export function clearSearch() {
    document.getElementById('searchInput').value = '';
    document.getElementById('searchResults').innerHTML = '';
    document.getElementById('searchResultsInfo').style.display = 'none';
    document.getElementById('searchEmpty').style.display = 'none';
    document.getElementById('searchError').style.display = 'none';
    document.getElementById('searchLoading').style.display = 'none';
    document.getElementById('clearSearchBtn').style.display = 'none';
}

function displaySearchResults(data) {
    const results = data.results || [];
    const container = document.getElementById('searchResults');
    const infoEl = document.getElementById('searchResultsInfo');
    const emptyEl = document.getElementById('searchEmpty');

    if (results.length === 0) {
        emptyEl.textContent = 'No results found. Try a different query or broader filters.';
        emptyEl.style.display = 'block';
        return;
    }

    infoEl.textContent = `${data.total} result${data.total !== 1 ? 's' : ''} in ${data.query_time_ms}ms`;
    infoEl.style.display = 'block';

    container.innerHTML = results.map((r, i) => {
        const scoreClass = r.score >= 0.7 ? 'badge-score-high' : r.score >= 0.4 ? 'badge-score-mid' : 'badge-score-low';
        const matchBadge = r.match_type ? `<span class="search-result-badge badge-match">${escapeHtml(r.match_type)}</span>` : '';
        const langBadge = r.language_id ? `<span class="search-result-badge badge-lang">${escapeHtml(r.language_id)}</span>` : '';
        const lineRange = r.start_line && r.end_line ? `Lines ${r.start_line}-${r.end_line}` : '';
        const escapedPath = escapeHtml(r.file_path).replace(/'/g, "\\'");

        let symbolHtml = '';
        if (r.symbol_type || r.symbol_name) {
            const parts = [];
            if (r.symbol_type) parts.push(`[${escapeHtml(r.symbol_type)}]`);
            if (r.symbol_name) parts.push(escapeHtml(r.symbol_name));
            symbolHtml = `<div class="search-result-symbol">${parts.join(' ')}</div>`;
        }

        const lines = (r.content || '').split('\n');
        const previewLines = lines.slice(0, 8);
        const hasMore = lines.length > 8;
        const previewText = escapeHtml(previewLines.join('\n'));
        const fullText = escapeHtml(r.content || '');

        return `<div class="search-result-card">
            <div class="search-result-header">
                <span class="search-result-path clickable" onclick="copyPathWithFeedback(this, '${escapedPath}')" title="Click to copy path">${escapeHtml(r.file_path)}</span>
                <div class="search-result-meta">
                    <span style="font-size: 12px; color: var(--text-muted);">${escapeHtml(lineRange)}</span>
                    <span class="search-result-badge ${scoreClass}">${r.score.toFixed(2)}</span>
                    ${matchBadge}
                    ${langBadge}
                </div>
            </div>
            ${symbolHtml}
            <div class="search-result-code">
                <pre id="code-preview-${i}">${previewText}</pre>
                ${hasMore ? `<button class="expand-btn" onclick="toggleCodeExpand(${i}, this)" data-full="${fullText.replace(/"/g, '&quot;')}" data-preview="${previewText.replace(/"/g, '&quot;')}">Show all ${lines.length} lines</button>` : ''}
            </div>
            <div class="search-result-actions">
                <button onclick="copyToClipboard('${escapedPath}')">Copy Path</button>
                <button onclick="copyToClipboard(document.getElementById('code-preview-${i}').textContent)">Copy Code</button>
                <button onclick="openInEditor('${escapedPath}', ${r.start_line || 1})">Open</button>
                <button onclick="viewFile('${escapedPath}', ${r.start_line || 1}, ${r.end_line || r.start_line || 1})">View File</button>
            </div>
        </div>`;
    }).join('');
}

export function toggleCodeExpand(index, btn) {
    const pre = document.getElementById('code-preview-' + index);
    const isExpanded = btn.dataset.expanded === 'true';
    if (isExpanded) {
        pre.textContent = btn.dataset.preview;
        btn.textContent = 'Show all lines';
        btn.dataset.expanded = 'false';
    } else {
        pre.textContent = btn.dataset.full;
        btn.textContent = 'Show less';
        btn.dataset.expanded = 'true';
    }
}

export async function openInEditor(filePath, line) {
    filePath = resolveFilePath(filePath);
    try {
        const resp = await fetch('/api/open-in-editor', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ file_path: filePath, line: line })
        });
        const data = await resp.json();
        if (!resp.ok) {
            showToast(data.error || 'Failed to open editor');
        }
    } catch (err) {
        showToast('Failed to open editor: ' + err.message);
    }
}

export async function viewFile(filePath, startLine, endLine) {
    filePath = resolveFilePath(filePath);
    const backdrop = document.getElementById('fileModalBackdrop');
    const pathEl = document.getElementById('fileModalPath');
    const linesEl = document.getElementById('fileModalLines');
    const codeEl = document.getElementById('fileModalCode');
    const bodyEl = document.getElementById('fileModalBody');

    // Show modal with loading state
    pathEl.textContent = filePath;
    linesEl.textContent = '';
    codeEl.textContent = 'Loading...';
    codeEl.className = '';
    backdrop.classList.add('visible');

    try {
        const resp = await fetch('/api/file-content?path=' + encodeURIComponent(filePath));
        const data = await resp.json();
        if (!resp.ok) {
            codeEl.textContent = 'Error: ' + (data.error || 'Failed to load file');
            return;
        }

        linesEl.textContent = data.lines + ' lines' + (data.truncated ? ' (truncated)' : '');
        const langClass = data.language && data.language !== 'plain' ? 'language-' + data.language : '';
        codeEl.className = langClass;
        codeEl.textContent = data.content;

        // Re-run Prism highlighting
        if (typeof Prism !== 'undefined') {
            Prism.highlightElement(codeEl);
        }

        // Scroll to matched line range and highlight
        if (startLine && startLine > 0) {
            setTimeout(() => {
                highlightAndScrollToLine(bodyEl, startLine, endLine);
            }, 100);
        }
    } catch (err) {
        codeEl.textContent = 'Error: ' + err.message;
    }
}

function highlightAndScrollToLine(container, startLine, endLine) {
    // Find line number elements from Prism line-numbers plugin
    const lineRows = container.querySelectorAll('.line-numbers-rows > span');
    if (lineRows.length > 0 && startLine <= lineRows.length) {
        // Highlight the range by adding background
        const start = Math.max(0, startLine - 1);
        const end = Math.min(lineRows.length - 1, (endLine || startLine) - 1);
        for (let i = start; i <= end; i++) {
            lineRows[i].style.background = 'rgba(255, 200, 50, 0.15)';
        }
        // Scroll the start line into view
        lineRows[start].scrollIntoView({ block: 'center', behavior: 'smooth' });
    } else {
        // Fallback: estimate line height and scroll
        const pre = container.querySelector('pre');
        if (pre) {
            const lineHeight = parseFloat(getComputedStyle(pre).lineHeight) || 20;
            container.scrollTop = (startLine - 1) * lineHeight - container.clientHeight / 3;
        }
    }
}

export function closeFileModal() {
    document.getElementById('fileModalBackdrop').classList.remove('visible');
}
