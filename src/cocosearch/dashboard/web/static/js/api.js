export async function loadProjectContext() {
    try {
        const resp = await fetch('/api/project');
        if (!resp.ok) return null;
        const data = await resp.json();
        return data.has_project ? data : null;
    } catch { return null; }
}

export async function fetchProjects() {
    try {
        const resp = await fetch('/api/projects');
        if (!resp.ok) return [];
        return await resp.json();
    } catch { return []; }
}

export async function fetchDepsGraph(file, indexName, depth = 3) {
    const params = new URLSearchParams({ file, index: indexName, depth: String(depth) });
    const resp = await fetch(`/api/deps/graph?${params}`);
    if (!resp.ok) throw new Error((await resp.json()).error || 'Failed to load graph');
    return await resp.json();
}

export async function fetchInfra() {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);
    try {
        const response = await fetch('/api/infra', { signal: controller.signal });
        if (!response.ok) return null;
        return await response.json();
    } catch {
        return null;
    } finally {
        clearTimeout(timeoutId);
    }
}

export async function fetchStats(indexName = null) {
    let url = indexName
        ? `/api/stats?index=${encodeURIComponent(indexName)}&include_failures=true`
        : '/api/stats?include_failures=true';

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);
    try {
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    } catch (err) {
        if (err.name === 'AbortError') {
            throw new Error('Stats request timed out — is the database running?');
        }
        throw err;
    } finally {
        clearTimeout(timeoutId);
    }
}
