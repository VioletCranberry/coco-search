import { state } from './state.js';
import { loadProjectContext, fetchStats, fetchProjects } from './api.js';
import { updateDashboard, updateSummaryCards } from './dashboard.js';

export function setButtonsDisabled(disabled) {
    document.getElementById('reindexBtn').disabled = disabled;
    document.getElementById('freshIndexBtn').disabled = disabled;
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

export function startPolling(reloadListOnComplete = false) {
    stopPolling();
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
                    select.innerHTML = state.allIndexes.map((idx, i) =>
                        `<option value="${i}">${idx.name}</option>`
                    ).join('');
                    select.value = String(matchIdx);
                    // Ensure dashboard is visible (may already be from indexCurrentProject)
                    document.getElementById('loadingMessage').style.display = 'none';
                    document.getElementById('dashboardContent').style.display = 'block';
                    updateDashboard(state.allIndexes[matchIdx]);

                    const status = state.allIndexes[matchIdx].status || 'indexed';
                    if (status !== 'indexing') {
                        stopPolling();
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

export async function loadIndexList() {
    try {
        // Load project context, stats, and discovered projects in parallel
        const [ctx, data, projects] = await Promise.all([
            loadProjectContext(),
            fetchStats(),
            fetchProjects(),
        ]);
        state.projectContext = ctx;
        state.allIndexes = Array.isArray(data) ? data : [data];
        state.allProjects = projects;

        // Find unindexed projects (not already in allIndexes)
        const indexedNames = new Set(state.allIndexes.map(idx => idx.name));
        const unindexedProjects = state.allProjects.filter(p => !p.is_indexed && !indexedNames.has(p.index_name));

        const select = document.getElementById('indexSelect');
        let html = '';
        if (state.allIndexes.length > 0 && unindexedProjects.length > 0) {
            // Use optgroups when both indexed and unindexed exist
            html += '<optgroup label="Indexed">';
            html += state.allIndexes.map((idx, i) =>
                `<option value="${i}">${idx.name}</option>`
            ).join('');
            html += '</optgroup>';
            html += '<optgroup label="Available (not indexed)">';
            html += unindexedProjects.map(p =>
                `<option value="project:${p.index_name}" data-project-path="${p.path}">${p.name}</option>`
            ).join('');
            html += '</optgroup>';
        } else {
            html = state.allIndexes.map((idx, i) =>
                `<option value="${i}">${idx.name}</option>`
            ).join('');
            if (unindexedProjects.length > 0) {
                html += '<optgroup label="Available (not indexed)">';
                html += unindexedProjects.map(p =>
                    `<option value="project:${p.index_name}" data-project-path="${p.path}">${p.name}</option>`
                ).join('');
                html += '</optgroup>';
            }
        }
        select.innerHTML = html;

        // Determine which index to select
        let selectedIndex = 0;
        let projectNotIndexed = false;
        if (state.projectContext) {
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

        if (projectNotIndexed) {
            // Don't load dashboard data — just show the not-indexed banner
        } else if (state.allIndexes.length > 0) {
            await loadDashboard(selectedIndex);

            // Auto-poll if any index is currently being indexed
            // (e.g. indexing started from CLI, MCP tool, or another process)
            const selected = state.allIndexes[selectedIndex];
            if (selected && selected.status === 'indexing') {
                setButtonsDisabled(true);
                showStatusBanner('Indexing in progress...', 'info');
                startPolling();
            }
        } else if (unindexedProjects.length > 0) {
            // No indexed projects but discovered projects available
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
