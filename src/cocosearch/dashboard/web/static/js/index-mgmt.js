import { state } from './state.js';
import { loadProjectContext, fetchStats, fetchProjects, fetchInfra } from './api.js';
import { updateDashboard, updateSummaryCards, updateWarnings } from './dashboard.js';

export function setButtonsDisabled(disabled) {
    document.getElementById('reindexBtn').disabled = disabled;
    document.getElementById('freshIndexBtn').disabled = disabled;
    document.getElementById('extractDepsBtn').disabled = disabled;
    document.getElementById('deleteIndexBtn').disabled = disabled;
    document.getElementById('stopIndexBtn').style.display = disabled ? 'inline-block' : 'none';
}

export function showStatusBanner(message, type) {
    const banner = document.getElementById('statusBanner');
    banner.textContent = message;
    banner.className = 'status-banner visible ' + type;
}

export function hideStatusBanner() {
    document.getElementById('statusBanner').className = 'status-banner';
}

function showError(message) {
    document.getElementById('loadingMessage').style.display = 'none';
    document.getElementById('dashboardContent').style.display = 'none';
    const errorEl = document.getElementById('errorMessage');
    errorEl.textContent = message;
    errorEl.style.display = 'block';
}

export function stopPolling() {
    if (state.pollInterval) {
        clearInterval(state.pollInterval);
        state.pollInterval = null;
    }
}

export function stopStalenessPolling() {
    if (state.stalenessInterval) {
        clearInterval(state.stalenessInterval);
        state.stalenessInterval = null;
    }
}

export function startStalenessPolling() {
    stopStalenessPolling();
    state.stalenessInterval = setInterval(async () => {
        if (state.pollInterval) return; // fast poll is active, skip
        try {
            const data = await fetchStats(null, false);
            state.allIndexes = Array.isArray(data) ? data : [data];

            const select = document.getElementById('indexSelect');
            const indexIndex = parseInt(select.value);
            const stats = state.allIndexes[indexIndex];
            if (!stats) return;

            updateWarnings(stats.warnings);
            updateSummaryCards(stats);

            // Auto-detect externally-started indexing
            if (stats.status === 'indexing') {
                stopStalenessPolling();
                setButtonsDisabled(true);
                showStatusBanner('Indexing in progress...', 'info');
                startPolling();
            }
        } catch {
            // Silently swallow errors — background poll
        }
    }, 30000);
}

export function startPolling(reloadListOnComplete = false) {
    stopPolling();
    stopStalenessPolling();
    state.pollInterval = setInterval(async () => {
        try {
            const data = await fetchStats();
            state.allIndexes = Array.isArray(data) ? data : [data];

            const select = document.getElementById('indexSelect');

            // If we're polling after initial indexing, look for the new index
            if (reloadListOnComplete && state.projectContext) {
                const matchIdx = state.allIndexes.findIndex(
                    idx => idx.name === state.projectContext.index_name
                );
                if (matchIdx >= 0) {
                    // Rebuild dropdown and select the new index
                    const linkedSet = new Set(state.linkedIndexes);
                    select.innerHTML = state.allIndexes.map((idx, i) => {
                        const prefix = linkedSet.has(idx.name) ? '[linked] ' : '';
                        return `<option value="${i}">${prefix}${idx.name}</option>`;
                    }).join('');
                    select.value = String(matchIdx);
                    // Ensure dashboard is visible (may already be from indexCurrentProject)
                    document.getElementById('loadingMessage').style.display = 'none';
                    document.getElementById('dashboardContent').style.display = 'block';
                    updateDashboard(state.allIndexes[matchIdx]);

                    const status = state.allIndexes[matchIdx].status || 'indexed';
                    if (status !== 'indexing') {
                        stopPolling();
                        startStalenessPolling();
                        setButtonsDisabled(false);
                        showStatusBanner('Indexing complete', 'success');
                        setTimeout(hideStatusBanner, 5000);
                    }
                    return;
                }
            }

            const indexIndex = parseInt(select.value);
            if (state.allIndexes[indexIndex]) {
                updateDashboard(state.allIndexes[indexIndex]);

                const status = state.allIndexes[indexIndex].status || 'indexed';
                if (status !== 'indexing') {
                    stopPolling();
                    startStalenessPolling();
                    setButtonsDisabled(false);
                    showStatusBanner('Indexing complete', 'success');
                    setTimeout(hideStatusBanner, 5000);
                }
            }
        } catch (err) {
            // Keep polling on transient errors
        }
    }, 3000);
}

export async function loadDashboard(indexIndex) {
    const stats = state.allIndexes[indexIndex];

    document.getElementById('loadingMessage').style.display = 'none';
    document.getElementById('errorMessage').style.display = 'none';
    document.getElementById('dashboardContent').style.display = 'block';

    updateDashboard(stats);
}

function showInfraBanner(infra) {
    const banner = document.getElementById('infraBanner');
    const details = document.getElementById('infraDetails');
    if (!banner || !details) return;
    const issues = [];
    if (!infra.database.ok) {
        issues.push('Database: ' + (infra.database.error || 'unavailable'));
    }
    if (!infra.embedding.ok) {
        issues.push('Embedding (' + infra.embedding.provider + '): ' + (infra.embedding.error || 'unavailable'));
    }
    details.textContent = issues.join(' | ');
    banner.style.display = 'block';
}

export async function loadIndexList() {
    try {
        // Load project context, stats, infra health, and discovered projects in parallel
        const [ctx, data, projects, infra] = await Promise.all([
            loadProjectContext(),
            fetchStats().catch(() => []),
            fetchProjects(),
            fetchInfra(),
        ]);
        state.projectContext = ctx;
        state.linkedIndexes = (ctx && ctx.linked_indexes) || [];
        state.allIndexes = Array.isArray(data) ? data : [data];
        state.allProjects = projects;

        // Show infra banner if any component is down
        if (infra && !infra.all_ok) {
            showInfraBanner(infra);
        }

        // Find unindexed projects (not already in allIndexes)
        const indexedNames = new Set(state.allIndexes.map(idx => idx.name));
        const unindexedProjects = state.allProjects.filter(p => !p.is_indexed && !indexedNames.has(p.index_name));

        const select = document.getElementById('indexSelect');
        const linkedSet = new Set(state.linkedIndexes);
        const indexOption = (idx, i) => {
            const prefix = linkedSet.has(idx.name) ? '[linked] ' : '';
            return `<option value="${i}">${prefix}${idx.name}</option>`;
        };
        let html = '';
        if (state.allIndexes.length > 0 && unindexedProjects.length > 0) {
            // Use optgroups when both indexed and unindexed exist
            html += '<optgroup label="Indexed">';
            html += state.allIndexes.map(indexOption).join('');
            html += '</optgroup>';
            html += '<optgroup label="Available (not indexed)">';
            html += unindexedProjects.map(p =>
                `<option value="project:${p.index_name}" data-project-path="${p.path}">${p.name}</option>`
            ).join('');
            html += '</optgroup>';
        } else {
            html = state.allIndexes.map(indexOption).join('');
            if (unindexedProjects.length > 0) {
                html += '<optgroup label="Available (not indexed)">';
                html += unindexedProjects.map(p =>
                    `<option value="project:${p.index_name}" data-project-path="${p.path}">${p.name}</option>`
                ).join('');
                html += '</optgroup>';
            }
        }
        select.innerHTML = html;

        // Show linked indexes hint next to "Search all indexes" checkbox
        const hint = document.getElementById('linkedIndexesHint');
        if (hint) {
            const mainName = (ctx && ctx.index_name) || '';
            if (mainName && state.linkedIndexes.length > 0) {
                hint.textContent = `(${mainName}, ${state.linkedIndexes.join(', ')})`;
            } else {
                hint.textContent = '';
            }
        }

        // Determine which index to select
        let selectedIndex = 0;
        let projectNotIndexed = false;
        if (state.projectContext && state.projectContext.has_project) {
            if (state.projectContext.is_indexed) {
                // Find the project's index in the list and auto-select it
                const matchIdx = state.allIndexes.findIndex(
                    idx => idx.name === state.projectContext.index_name
                );
                if (matchIdx >= 0) {
                    selectedIndex = matchIdx;
                    select.value = String(selectedIndex);
                }
            } else {
                // Project not indexed — show the banner, hide loading
                projectNotIndexed = true;
                document.getElementById('loadingMessage').style.display = 'none';
                const banner = document.getElementById('notIndexedBanner');
                document.getElementById('notIndexedPath').textContent = state.projectContext.project_path;
                banner.style.display = 'block';
            }
        }

        if (projectNotIndexed && state.allIndexes.length === 0) {
            // No indexes at all — only show the not-indexed banner
        } else if (state.allIndexes.length > 0) {
            await loadDashboard(selectedIndex);

            // Auto-poll if any index is currently being indexed
            // (e.g. indexing started from CLI, MCP tool, or another process)
            const selected = state.allIndexes[selectedIndex];
            if (selected && selected.status === 'indexing') {
                setButtonsDisabled(true);
                showStatusBanner('Indexing in progress...', 'info');
                startPolling();
            } else {
                startStalenessPolling();
            }
        } else if (unindexedProjects.length > 0) {
            // No indexed projects but discovered projects available
            document.getElementById('loadingMessage').style.display = 'none';
        } else if (infra && !infra.all_ok) {
            // No indexes and infra is down — hide loading, banner is already visible
            document.getElementById('loadingMessage').style.display = 'none';
        }
    } catch (error) {
        showError(`Failed to load index list: ${error.message}`);
    }
}

export function onIndexSelectChange(e) {
    const val = e.target.value;
    if (val.startsWith('project:')) {
        // Selected an unindexed project — show the not-indexed banner
        const option = e.target.selectedOptions[0];
        const projectPath = option.dataset.projectPath;
        const indexName = val.slice('project:'.length);
        document.getElementById('dashboardContent').style.display = 'none';
        document.getElementById('loadingMessage').style.display = 'none';
        const banner = document.getElementById('notIndexedBanner');
        document.getElementById('notIndexedPath').textContent = projectPath;
        banner.style.display = 'block';
        // Set projectContext so indexCurrentProject() works
        state.projectContext = {
            has_project: true,
            project_path: projectPath,
            index_name: indexName,
            is_indexed: false,
        };
    } else {
        // Selected an existing index
        document.getElementById('notIndexedBanner').style.display = 'none';
        const indexIndex = parseInt(val);
        loadDashboard(indexIndex);
    }
}

export async function reindex(fresh) {
    if (fresh && !confirm('Fresh Index will delete and rebuild the entire index. Continue?')) {
        return;
    }

    const select = document.getElementById('indexSelect');
    const indexIndex = parseInt(select.value);
    const stats = state.allIndexes[indexIndex];
    if (!stats) return;

    setButtonsDisabled(true);
    const action = fresh ? 'Fresh reindex' : 'Reindex';
    showStatusBanner(action + ' starting...', 'info');

    try {
        const resp = await fetch('/api/reindex', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                index_name: stats.name,
                fresh: fresh,
                source_path: stats.source_path || (state.projectContext && state.projectContext.project_path)
            })
        });
        const data = await resp.json();
        if (!resp.ok) {
            showStatusBanner('Error: ' + (data.error || 'Request failed'), 'error');
            setButtonsDisabled(false);
            return;
        }
        showStatusBanner(data.message, 'info');
        // Immediately reflect indexing status in the UI
        state.allIndexes[indexIndex].status = 'indexing';
        updateSummaryCards(state.allIndexes[indexIndex]);
        startPolling();
    } catch (err) {
        showStatusBanner('Error: ' + err.message, 'error');
        setButtonsDisabled(false);
    }
}

export async function stopIndexing() {
    const select = document.getElementById('indexSelect');
    const stats = state.allIndexes[parseInt(select.value)];
    if (!stats) return;

    try {
        const resp = await fetch('/api/stop-indexing', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({index_name: stats.name})
        });
        const data = await resp.json();
        if (resp.ok) {
            stopPolling();
            startStalenessPolling();
            setButtonsDisabled(false);
            showStatusBanner('Indexing stopped', 'info');
            setTimeout(hideStatusBanner, 5000);
        } else {
            showStatusBanner('Error: ' + (data.error || 'Stop failed'), 'error');
        }
    } catch (err) {
        showStatusBanner('Error: ' + err.message, 'error');
    }
}

export async function deleteIndex() {
    const select = document.getElementById('indexSelect');
    const stats = state.allIndexes[parseInt(select.value)];
    if (!stats) return;

    if (!confirm(`Permanently delete index "${stats.name}"? This cannot be undone.`)) {
        return;
    }

    setButtonsDisabled(true);
    showStatusBanner('Deleting index...', 'info');

    try {
        const resp = await fetch('/api/delete-index', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({index_name: stats.name})
        });
        const data = await resp.json();
        if (!resp.ok) {
            showStatusBanner('Error: ' + (data.error || 'Delete failed'), 'error');
            setButtonsDisabled(false);
            return;
        }
        showStatusBanner(`Index "${stats.name}" deleted`, 'success');
        setTimeout(() => {
            hideStatusBanner();
            loadIndexList();
        }, 1500);
    } catch (err) {
        showStatusBanner('Error: ' + err.message, 'error');
        setButtonsDisabled(false);
    }
}

export async function indexCurrentProject() {
    if (!state.projectContext) return;

    const btn = document.getElementById('indexNowBtn');
    btn.disabled = true;
    showStatusBanner('Indexing starting...', 'info');

    try {
        const resp = await fetch('/api/index', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                project_path: state.projectContext.project_path,
                index_name: state.projectContext.index_name,
            })
        });
        const data = await resp.json();
        if (!resp.ok) {
            showStatusBanner('Error: ' + (data.error || 'Request failed'), 'error');
            btn.disabled = false;
            return;
        }
        // Hide the not-indexed banner and loading message
        document.getElementById('notIndexedBanner').style.display = 'none';
        document.getElementById('loadingMessage').style.display = 'none';
        showStatusBanner(data.message, 'info');
        // Show dashboard immediately with indexing-in-progress state
        document.getElementById('dashboardContent').style.display = 'block';
        setButtonsDisabled(true);
        // Immediately reflect indexing status in the Status card
        const statusEl = document.getElementById('indexStatus');
        const statusLabelEl = document.getElementById('statusLabel');
        statusEl.textContent = 'Indexing...';
        statusEl.style.color = 'var(--accent-orange)';
        statusLabelEl.textContent = 'In progress';
        // Poll until indexing completes, then reload index list
        startPolling(true);
    } catch (err) {
        showStatusBanner('Error: ' + err.message, 'error');
        btn.disabled = false;
    }
}

export async function extractDeps() {
    const select = document.getElementById('indexSelect');
    const indexIndex = parseInt(select.value);
    const stats = state.allIndexes[indexIndex];
    if (!stats) return;

    setButtonsDisabled(true);
    showStatusBanner('Extracting dependencies...', 'info');

    try {
        const resp = await fetch('/api/extract-deps', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                index_name: stats.name,
                source_path: stats.source_path || (state.projectContext && state.projectContext.project_path)
            })
        });
        const data = await resp.json();
        if (!resp.ok) {
            showStatusBanner('Error: ' + (data.error || 'Request failed'), 'error');
            setButtonsDisabled(false);
            return;
        }
        showStatusBanner(data.message, 'success');
        setTimeout(hideStatusBanner, 5000);
        setButtonsDisabled(false);
    } catch (err) {
        showStatusBanner('Error: ' + err.message, 'error');
        setButtonsDisabled(false);
    }
}
