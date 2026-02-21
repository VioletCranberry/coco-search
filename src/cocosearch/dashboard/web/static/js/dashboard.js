import { state } from './state.js';
import { formatNumber, formatDate, escapeHtml } from './utils.js';
import { updateLanguageChart, updateSymbolChart, updateGrammarChart } from './charts.js';

export function updateTabStatus(status) {
    const colorMap = {
        indexing: { primary: '#FF9800', secondary: '#e07840' },
        indexed:  { primary: '#4CAF50', secondary: '#388E3C' },
        stale:    { primary: '#FFC107', secondary: '#FFA000' },
        error:    { primary: '#f44336', secondary: '#d32f2f' },
    };
    const defaultColors = { primary: '#f0a060', secondary: '#e07840' };
    const colors = colorMap[status] || defaultColors;

    const titleMap = {
        indexing: 'Indexing\u2026 \u00b7 Coco[-S]earch',
        indexed:  'Indexed \u00b7 Coco[-S]earch',
        stale:    'Stale \u00b7 Coco[-S]earch',
        error:    'Error \u00b7 Coco[-S]earch',
    };
    document.title = titleMap[status] || 'Coco[-S]earch';

    const svg = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>`
        + `<circle cx='24' cy='24' r='20' fill='none' stroke='${colors.primary}' stroke-width='5'/>`
        + `<line x1='38' y1='38' x2='58' y2='58' stroke='${colors.secondary}' stroke-width='6' stroke-linecap='round'/>`
        + `<text x='24' y='31' text-anchor='middle' font-family='Courier New,Courier,monospace' font-size='18' fill='${colors.primary}' font-weight='bold'>&lt;/&gt;</text>`
        + `</svg>`;
    const favicon = document.getElementById('favicon');
    if (favicon) {
        favicon.href = 'data:image/svg+xml,' + encodeURIComponent(svg);
    }
}

export function updateSummaryCards(stats) {
    document.getElementById('fileCount').textContent = formatNumber(stats.file_count);
    document.getElementById('chunkCount').textContent = formatNumber(stats.chunk_count);
    document.getElementById('storageSize').textContent = stats.storage_size_pretty;

    const updatedDate = formatDate(stats.updated_at);
    document.getElementById('lastUpdated').textContent = updatedDate;

    if (stats.staleness_days !== null && stats.staleness_days >= 0) {
        document.getElementById('stalenessLabel').textContent = `${stats.staleness_days} days old`;
    } else {
        document.getElementById('stalenessLabel').textContent = 'Index age';
    }

    // Source path
    const sourceEl = document.getElementById('sourcePath');
    if (stats.source_path) {
        sourceEl.textContent = stats.source_path;
    } else {
        sourceEl.textContent = '';
    }

    // Repo URL
    const repoUrlEl = document.getElementById('repoUrl');
    const repoUrlLink = document.getElementById('repoUrlLink');
    if (stats.repo_url) {
        repoUrlLink.href = stats.repo_url;
        repoUrlLink.textContent = stats.repo_url.replace(/^https?:\/\//, '');
        repoUrlEl.style.display = 'block';
    } else {
        repoUrlEl.style.display = 'none';
    }

    // Branch badge
    const branchBadge = document.getElementById('branchBadge');
    if (stats.branch) {
        branchBadge.querySelector('.branch-name').textContent = stats.branch + (stats.commit_hash ? ' (' + stats.commit_hash + ')' : '');
        const behindEl = branchBadge.querySelector('.branch-behind');
        if (stats.commits_behind !== null && stats.commits_behind !== undefined) {
            behindEl.textContent = stats.commits_behind === 0 ? 'up to date' : stats.commits_behind + ' commits behind';
            behindEl.style.display = '';
        } else {
            behindEl.style.display = 'none';
        }
        const countEl = branchBadge.querySelector('.branch-count');
        if (stats.branch_commit_count !== null && stats.branch_commit_count !== undefined) {
            countEl.textContent = stats.branch_commit_count.toLocaleString() + ' commits';
            countEl.style.display = '';
        } else {
            countEl.style.display = 'none';
        }
        branchBadge.style.display = 'flex';
    } else {
        branchBadge.style.display = 'none';
    }

    // Status
    const statusEl = document.getElementById('indexStatus');
    const statusLabelEl = document.getElementById('statusLabel');
    const status = stats.status || 'indexed';
    const isStaleState = status === 'indexed' &&
        (stats.is_stale || (stats.commits_behind !== null && stats.commits_behind > 0));
    if (status === 'indexing') {
        statusEl.textContent = 'Indexing...';
        statusEl.style.color = 'var(--accent-orange)';
        statusLabelEl.textContent = 'In progress';
    } else if (status === 'error') {
        statusEl.textContent = 'Error';
        statusEl.style.color = 'var(--accent-red, #ef4444)';
        statusLabelEl.textContent = 'Indexing failed';
    } else if (isStaleState) {
        statusEl.textContent = 'Stale';
        statusEl.style.color = '#FFC107';
        statusLabelEl.textContent = stats.commits_behind > 0 ? 'Behind HEAD' : 'Outdated index';
    } else {
        statusEl.textContent = 'Indexed';
        statusEl.style.color = 'var(--accent-green)';
        statusLabelEl.textContent = 'Ready to search';
    }
    updateTabStatus(isStaleState ? 'stale' : status);

    // Parse Health
    const parseHealthEl = document.getElementById('parseHealth');
    const parseHealthLabelEl = document.getElementById('parseHealthLabel');
    const parseStats = stats.parse_stats;
    if (parseStats && parseStats.total_files > 0) {
        const pct = parseStats.parse_health_pct;
        parseHealthEl.textContent = pct + '%';
        if (pct >= 95) {
            parseHealthEl.style.color = 'var(--accent-green)';
        } else if (pct >= 80) {
            parseHealthEl.style.color = 'var(--accent-orange)';
        } else {
            parseHealthEl.style.color = 'var(--accent-red)';
        }
        parseHealthLabelEl.textContent = `${parseStats.total_ok}/${parseStats.total_files} files clean`;
    } else {
        parseHealthEl.textContent = '-';
        parseHealthEl.style.color = 'var(--text-muted)';
        parseHealthLabelEl.textContent = 'No parse data';
    }
}

export function updateWarnings(warnings) {
    const banner = document.getElementById('warningBanner');
    const list = document.getElementById('warningList');

    if (warnings && warnings.length > 0) {
        list.innerHTML = warnings.map(w => `<li>${w}</li>`).join('');
        banner.classList.add('visible');
    } else {
        banner.classList.remove('visible');
    }
}

export function updateParseHealthTable(parseStats) {
    const section = document.getElementById('parseHealthSection');
    const tbody = document.getElementById('parseTableBody');

    if (!parseStats || !parseStats.by_language || Object.keys(parseStats.by_language).length === 0) {
        section.style.display = 'none';
        return;
    }

    const byLang = parseStats.by_language;
    const entries = Object.entries(byLang).sort((a, b) => b[1].files - a[1].files);

    // Sort: tracked languages first (by file count desc), then skipped languages
    const tracked = entries.filter(([, d]) => !d.skipped).sort((a, b) => b[1].files - a[1].files);
    const skipped = entries.filter(([, d]) => d.skipped).sort((a, b) => b[1].files - a[1].files);
    const sorted = [...tracked, ...skipped];

    let rowId = 0;
    tbody.innerHTML = sorted.map(([lang, data]) => {
        if (data.skipped) {
            return `<tr style="opacity: 0.5">
                <td style="font-weight: 500">${escapeHtml(lang)}</td>
                <td class="num">${data.files}</td>
                <td class="num" colspan="4" style="text-align: center; font-style: italic">text format — indexed as-is, no AST parsing</td>
            </tr>`;
        }

        const healthPct = data.files > 0 ? (data.ok / data.files * 100) : 100;
        let langColor = 'var(--accent-green)';
        if (healthPct < 80) langColor = 'var(--accent-red)';
        else if (healthPct < 95) langColor = 'var(--accent-orange)';

        const issues = (data.partial || 0) + (data.error || 0) + (data.no_grammar || 0);
        const id = 'lang-detail-' + (rowId++);
        const expandable = issues > 0 ? ` class="expandable-row" onclick="toggleLanguageDetails('${escapeHtml(lang)}', '${id}')"` : '';

        return `<tr${expandable}>
            <td style="font-weight: 500; color: ${langColor}">${escapeHtml(lang)}</td>
            <td class="num">${data.files}</td>
            <td class="num status-ok">${data.ok}</td>
            <td class="num status-partial">${data.partial || 0}</td>
            <td class="num status-error">${data.error || 0}</td>
            <td class="num status-no-grammar">${data.no_grammar || 0}</td>
        </tr>
        <tr class="detail-row" id="${id}"><td colspan="6"><div class="failure-list"></div></td></tr>`;
    }).join('');

    section.style.display = 'block';
}

export function toggleLanguageDetails(language, rowId) {
    const detailRow = document.getElementById(rowId);
    const parentRow = detailRow.previousElementSibling;
    const isExpanded = detailRow.classList.contains('visible');

    if (isExpanded) {
        detailRow.classList.remove('visible');
        parentRow.classList.remove('expanded');
        return;
    }

    parentRow.classList.add('expanded');
    detailRow.classList.add('visible');

    // Only populate once
    const listEl = detailRow.querySelector('.failure-list');
    if (listEl.innerHTML) return;

    const failures = state.parseFailuresData.filter(f => f.language === language);
    if (failures.length === 0) {
        listEl.innerHTML = '<p style="color: var(--text-muted); font-size: 13px; padding: 8px 0;">No failure details available</p>';
        return;
    }

    const statusOrder = { error: 0, partial: 1, no_grammar: 2 };
    const sorted = [...failures].sort((a, b) =>
        (statusOrder[a.parse_status] ?? 3) - (statusOrder[b.parse_status] ?? 3)
    );

    const statusClass = (s) => {
        if (s === 'error') return 'status-error';
        if (s === 'partial') return 'status-partial';
        return 'status-no-grammar';
    };

    listEl.innerHTML = `<table>
        <thead><tr>
            <th>File</th>
            <th>Status</th>
            <th>Error</th>
        </tr></thead>
        <tbody>${sorted.map(f => `<tr>
            <td class="file-path">${escapeHtml(f.file_path)}</td>
            <td class="${statusClass(f.parse_status)}">${escapeHtml(f.parse_status)}</td>
            <td class="error-msg" title="${escapeHtml(f.error_message || '')}">${escapeHtml(f.error_message || '-')}</td>
        </tr>`).join('')}</tbody>
    </table>`;
}

export function updateGrammarHealthTable(grammars) {
    const section = document.getElementById('grammarHealthSection');
    const tbody = document.getElementById('grammarHealthTableBody');

    if (!grammars || grammars.length === 0) {
        section.style.display = 'none';
        return;
    }

    let rowId = 0;
    tbody.innerHTML = grammars.map(g => {
        const pct = g.recognition_pct;
        let healthColor = 'var(--accent-green)';
        if (pct < 50) healthColor = 'var(--accent-red)';
        else if (pct < 80) healthColor = 'var(--accent-orange)';

        const id = 'grammar-detail-' + (rowId++);
        const expandable = g.unrecognized_chunks > 0 ? ` class="expandable-row" onclick="toggleGrammarDetails('${escapeHtml(g.grammar_name)}', '${id}')"` : '';

        return `<tr${expandable}>
            <td style="font-weight: 500">${escapeHtml(g.grammar_name)}</td>
            <td>${escapeHtml(g.base_language)}</td>
            <td class="num">${g.file_count}</td>
            <td class="num">${g.chunk_count}</td>
            <td class="num status-ok">${g.recognized_chunks}</td>
            <td class="num status-error">${g.unrecognized_chunks}</td>
            <td class="num" style="color: ${healthColor}; font-weight: 600">${pct}%</td>
        </tr>
        <tr class="detail-row" id="${id}"><td colspan="7"><div class="failure-list"></div></td></tr>`;
    }).join('');

    section.style.display = 'block';
}

export function toggleGrammarDetails(grammarName, rowId) {
    const detailRow = document.getElementById(rowId);
    const parentRow = detailRow.previousElementSibling;
    const isExpanded = detailRow.classList.contains('visible');

    if (isExpanded) {
        detailRow.classList.remove('visible');
        parentRow.classList.remove('expanded');
        return;
    }

    parentRow.classList.add('expanded');
    detailRow.classList.add('visible');

    // Only populate once
    const listEl = detailRow.querySelector('.failure-list');
    if (listEl.innerHTML) return;

    const failures = state.grammarFailuresData.filter(f => f.grammar_name === grammarName);
    if (failures.length === 0) {
        listEl.innerHTML = '<p style="color: var(--text-muted); font-size: 13px; padding: 8px 0;">No failure details available</p>';
        return;
    }

    listEl.innerHTML = `<table>
        <thead><tr>
            <th>File</th>
            <th>Total Chunks</th>
            <th>Unrecognized</th>
        </tr></thead>
        <tbody>${failures.map(f => `<tr>
            <td class="file-path">${escapeHtml(f.file_path)}</td>
            <td class="num">${f.total_chunks}</td>
            <td class="num status-error">${f.unrecognized_chunks}</td>
        </tr>`).join('')}</tbody>
    </table>`;
}

export function populateLanguageFilter(languages) {
    const select = document.getElementById('searchLanguage');
    const current = select.value;
    const options = ['<option value="">All</option>'];
    if (languages && languages.length > 0) {
        const langs = [...languages].sort((a, b) => b.chunk_count - a.chunk_count);
        for (const l of langs) {
            options.push(`<option value="${escapeHtml(l.language)}">${escapeHtml(l.language)}</option>`);
        }
    }
    select.innerHTML = options.join('');
    // Preserve previous selection
    if (current) {
        select.value = current;
    }
}

export function updateDashboard(stats) {
    state.parseFailuresData = stats.parse_failures || [];
    state.grammarFailuresData = stats.grammar_failures || [];
    updateSummaryCards(stats);
    updateWarnings(stats.warnings);
    updateLanguageChart(stats.languages || []);
    updateSymbolChart(stats.symbols || {});
    updateGrammarChart(stats.grammars || []);
    updateGrammarHealthTable(stats.grammars || []);
    updateParseHealthTable(stats.parse_stats);
    populateLanguageFilter(stats.languages || []);
}
