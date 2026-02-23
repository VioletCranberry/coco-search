import { state } from './state.js';
import { escapeHtml, copyToClipboard, showToast, resolveFilePath } from './utils.js';
import { fetchDepsGraph } from './api.js';

let _abortController = null;

export async function executeSearch() {
    // If a search is in flight, cancel it instead
    if (_abortController) {
        cancelSearch();
        return;
    }

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
    const includeDeps = document.getElementById('searchIncludeDeps').checked;

    // Show loading, swap button to Cancel
    const searchBtn = document.getElementById('searchBtn');
    document.getElementById('searchLoading').style.display = 'block';
    document.getElementById('searchEmpty').style.display = 'none';
    document.getElementById('searchError').style.display = 'none';
    document.getElementById('searchResultsInfo').style.display = 'none';
    document.getElementById('searchResults').innerHTML = '';
    searchBtn.textContent = 'Cancel';
    searchBtn.classList.add('cancel-mode');

    _abortController = new AbortController();

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
        if (includeDeps) body.include_deps = true;

        const resp = await fetch('/api/search', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body),
            signal: _abortController.signal
        });
        const data = await resp.json();

        if (!resp.ok) {
            document.getElementById('searchError').textContent = data.error || 'Search failed';
            document.getElementById('searchError').style.display = 'block';
            document.getElementById('clearSearchBtn').style.display = '';
            return;
        }

        displaySearchResults(data);
        document.getElementById('clearSearchBtn').style.display = '';
    } catch (err) {
        if (err.name === 'AbortError') {
            document.getElementById('searchEmpty').textContent = 'Search cancelled.';
            document.getElementById('searchEmpty').style.display = 'block';
        } else {
            document.getElementById('searchError').textContent = 'Search failed: ' + err.message;
            document.getElementById('searchError').style.display = 'block';
        }
        document.getElementById('clearSearchBtn').style.display = '';
    } finally {
        _abortController = null;
        document.getElementById('searchLoading').style.display = 'none';
        const btn = document.getElementById('searchBtn');
        btn.textContent = 'Search';
        btn.classList.remove('cancel-mode');
    }
}

export function cancelSearch() {
    if (_abortController) {
        _abortController.abort();
    }
}

export function clearSearch() {
    cancelSearch();
    document.getElementById('searchInput').value = '';
    document.getElementById('searchResults').innerHTML = '';
    document.getElementById('searchResultsInfo').style.display = 'none';
    document.getElementById('searchEmpty').style.display = 'none';
    document.getElementById('searchError').style.display = 'none';
    document.getElementById('searchLoading').style.display = 'none';
    document.getElementById('clearSearchBtn').style.display = 'none';
}

function buildDepsHtml(r, i) {
    const dedup = (arr, keyFn) => {
        const seen = new Set();
        return arr.filter(d => { const k = keyFn(d); if (seen.has(k)) return false; seen.add(k); return true; });
    };
    const uniqueDeps = dedup(r.dependencies || [], d => d.target_file || d.module || 'external');
    const uniqueDepnts = dedup(r.dependents || [], d => d.source_file || '');
    const depsCount = uniqueDeps.length;
    const depntsCount = uniqueDepnts.length;
    const escapedPath = escapeHtml(r.file_path).replace(/'/g, "\\'");

    const depsZero = depsCount === 0 ? ' dep-badge-zero' : '';
    const depntsZero = depntsCount === 0 ? ' dep-badge-zero' : '';
    const depsClick = depsCount > 0 || depntsCount > 0 ? `onclick="toggleDepsPanel(${i})"` : '';
    const depntsClick = depsClick;

    const badgesHtml = `<span class="dep-badges">` +
        `<span class="dep-badge dep-badge-imports${depsZero}" ${depsClick} title="${depsCount} imports">&rarr; ${depsCount}</span>` +
        `<span class="dep-badge dep-badge-dependents${depntsZero}" ${depntsClick} title="${depntsCount} dependents">&larr; ${depntsCount}</span>` +
        `</span>`;

    if (depsCount === 0 && depntsCount === 0) {
        return { badgesHtml, panelHtml: '' };
    }

    const maxShow = 10;
    const renderDepItem = (d) => {
        const name = d.target_file || d.module || 'external';
        return `<li title="${escapeHtml(name)}"><span class="dep-type-tag">${escapeHtml(d.dep_type || 'import')}</span>${escapeHtml(name)}</li>`;
    };
    const renderDepntItem = (d) => {
        const name = d.source_file || '';
        return `<li title="${escapeHtml(name)}"><span class="dep-type-tag">${escapeHtml(d.dep_type || 'import')}</span>${escapeHtml(name)}</li>`;
    };

    const depsVisible = uniqueDeps.slice(0, maxShow).map(renderDepItem).join('');
    const depsOverflow = uniqueDeps.length > maxShow
        ? `<span class="deps-overflow" id="deps-overflow-${i}-imports">${uniqueDeps.slice(maxShow).map(renderDepItem).join('')}</span>` +
          `<li class="deps-show-more" onclick="toggleDepsOverflow(${i}, 'imports')">+ ${uniqueDeps.length - maxShow} more</li>`
        : '';

    const depntsVisible = uniqueDepnts.slice(0, maxShow).map(renderDepntItem).join('');
    const depntsOverflow = uniqueDepnts.length > maxShow
        ? `<span class="deps-overflow" id="deps-overflow-${i}-dependents">${uniqueDepnts.slice(maxShow).map(renderDepntItem).join('')}</span>` +
          `<li class="deps-show-more" onclick="toggleDepsOverflow(${i}, 'dependents')">+ ${uniqueDepnts.length - maxShow} more</li>`
        : '';

    const panelHtml = `<div class="search-result-deps" id="deps-panel-${i}">
        <div class="deps-columns">
            <div>
                <div class="deps-section-title">This file imports (${depsCount})</div>
                <ul class="deps-file-list">${depsVisible}${depsOverflow}</ul>
            </div>
            <div>
                <div class="deps-section-title">Imported by (${depntsCount})</div>
                <ul class="deps-file-list">${depntsVisible}${depntsOverflow}</ul>
            </div>
        </div>
        <div class="deps-actions">
            <button onclick="openDepsGraph('${escapedPath}')">View Graph</button>
        </div>
    </div>`;

    return { badgesHtml, panelHtml };
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

        const hasDeps = r.dependencies !== undefined;
        const { badgesHtml, panelHtml } = hasDeps ? buildDepsHtml(r, i) : { badgesHtml: '', panelHtml: '' };

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
                    ${badgesHtml}
                </div>
            </div>
            ${symbolHtml}
            <div class="search-result-code">
                <pre id="code-preview-${i}">${previewText}</pre>
                ${hasMore ? `<button class="expand-btn" onclick="toggleCodeExpand(${i}, this)" data-full="${fullText.replace(/"/g, '&quot;')}" data-preview="${previewText.replace(/"/g, '&quot;')}">Show all ${lines.length} lines</button>` : ''}
            </div>
            ${panelHtml}
            <div class="search-result-actions">
                <button onclick="copyToClipboard('${escapedPath}')">Copy Path</button>
                <button onclick="copyToClipboard(document.getElementById('code-preview-${i}').textContent)">Copy Code</button>
                <button onclick="openInEditor('${escapedPath}', ${r.start_line || 1})">Open</button>
                <button onclick="viewFile('${escapedPath}', ${r.start_line || 1}, ${r.end_line || r.start_line || 1})">View File</button>
            </div>
        </div>`;
    }).join('');
}

export function toggleDepsPanel(index) {
    const panel = document.getElementById(`deps-panel-${index}`);
    if (panel) panel.classList.toggle('visible');
}

export function toggleDepsOverflow(index, type) {
    const overflow = document.getElementById(`deps-overflow-${index}-${type}`);
    if (!overflow) return;
    const isVisible = overflow.classList.toggle('visible');
    const toggle = overflow.nextElementSibling;
    if (toggle && toggle.classList.contains('deps-show-more')) {
        toggle.textContent = isVisible ? 'Show less' : `+ ${overflow.children.length} more`;
    }
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

// --- Dependency Graph Modal ---

let _currentGraphFile = null;

export async function openDepsGraph(filePath) {
    _currentGraphFile = filePath;
    const backdrop = document.getElementById('depsGraphBackdrop');
    const loading = document.getElementById('depsGraphLoading');
    const svgEl = document.getElementById('depsGraphSvg');
    const titleEl = document.getElementById('depsGraphTitle');
    const depthEl = document.getElementById('depsGraphDepth');

    titleEl.textContent = filePath.split('/').pop();
    loading.style.display = 'block';
    svgEl.innerHTML = '';
    backdrop.classList.add('visible');

    const select = document.getElementById('indexSelect');
    const idx = parseInt(select.value);
    const stats = state.allIndexes[idx];
    if (!stats) {
        loading.textContent = 'No index selected';
        return;
    }

    const depth = parseInt(depthEl.value) || 3;

    try {
        const data = await fetchDepsGraph(filePath, stats.name, depth);
        loading.style.display = 'none';
        renderDepsGraph(data, svgEl, filePath);
    } catch (err) {
        loading.style.display = 'none';
        svgEl.innerHTML = `<text x="50%" y="50%" text-anchor="middle" fill="#806040" font-size="14">${escapeHtml(err.message)}</text>`;
    }
}

export function closeDepsGraph() {
    document.getElementById('depsGraphBackdrop').classList.remove('visible');
    if (state.depsGraphSimulation) {
        state.depsGraphSimulation.stop();
        state.depsGraphSimulation = null;
    }
    _currentGraphFile = null;
}

export async function onDepsDepthChange() {
    if (_currentGraphFile) {
        await openDepsGraph(_currentGraphFile);
    }
}

function renderDepsGraph(data, svgEl, rootFile) {
    if (typeof d3 === 'undefined') {
        svgEl.innerHTML = '<text x="50%" y="50%" text-anchor="middle" fill="#806040" font-size="14">D3.js not loaded</text>';
        return;
    }

    const nodes = data.nodes || [];
    const edges = data.edges || [];

    if (nodes.length === 0) {
        svgEl.innerHTML = '<text x="50%" y="50%" text-anchor="middle" fill="#806040" font-size="14">No dependencies found</text>';
        return;
    }

    // Clean previous
    if (state.depsGraphSimulation) {
        state.depsGraphSimulation.stop();
    }

    const svg = d3.select(svgEl);
    svg.selectAll('*').remove();

    const rect = svgEl.getBoundingClientRect();
    const width = rect.width || 800;
    const height = rect.height || 600;

    // Arrow markers
    const defs = svg.append('defs');
    defs.append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', 'rgba(240,160,96,0.4)');
    defs.append('marker')
        .attr('id', 'arrowhead-reverse')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', 'rgba(100,160,220,0.5)');

    const g = svg.append('g');

    // Zoom
    svg.call(d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => g.attr('transform', event.transform))
    );

    // Force simulation
    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(edges).id(d => d.id).distance(120))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collide', d3.forceCollide(40));

    state.depsGraphSimulation = simulation;

    // Edges
    const link = g.selectAll('.link')
        .data(edges)
        .enter().append('line')
        .attr('class', d => d.direction === 'reverse' ? 'link reverse' : 'link')
        .attr('marker-end', d => d.direction === 'reverse' ? 'url(#arrowhead-reverse)' : 'url(#arrowhead)');

    // Edge labels
    const linkLabel = g.selectAll('.link-label')
        .data(edges)
        .enter().append('text')
        .attr('class', 'link-label')
        .attr('text-anchor', 'middle')
        .text(d => d.dep_type || '');

    // Nodes
    const node = g.selectAll('.node')
        .data(nodes)
        .enter().append('g')
        .attr('class', d => {
            if (d.id === rootFile) return 'node root';
            if (d.is_external) return 'node external';
            return 'node';
        })
        .call(d3.drag()
            .on('start', (event, d) => {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            })
            .on('drag', (event, d) => {
                d.fx = event.x;
                d.fy = event.y;
            })
            .on('end', (event, d) => {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            })
        );

    node.append('circle')
        .attr('r', d => {
            if (d.id === rootFile) return 10;
            if (d.is_external) return 4;
            return 7;
        })
        .attr('stroke-dasharray', d => d.is_external ? '2,2' : null)
        .style('opacity', d => d.is_external ? 0.5 : 1);

    node.append('text')
        .attr('dx', 14)
        .attr('dy', 4)
        .style('font-style', d => d.is_external ? 'italic' : null)
        .style('opacity', d => d.is_external ? 0.6 : 1)
        .text(d => {
            const label = d.label || d.id.split('/').pop();
            return d.is_external ? `${label} (ext)` : label;
        });

    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

        linkLabel
            .attr('x', d => (d.source.x + d.target.x) / 2)
            .attr('y', d => (d.source.y + d.target.y) / 2 - 4);

        node.attr('transform', d => `translate(${d.x},${d.y})`);
    });
}
