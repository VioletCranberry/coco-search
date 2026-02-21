import { state } from './state.js';

export function updateLanguageChart(languages) {
    const ctx = document.getElementById('languageChart');

    // Sort by chunk count and take top 10
    const topLanguages = languages
        .sort((a, b) => b.chunk_count - a.chunk_count)
        .slice(0, 10);

    const labels = topLanguages.map(l => l.language);
    const data = topLanguages.map(l => l.chunk_count);

    // Destroy existing chart
    if (state.languageChart) {
        state.languageChart.destroy();
    }

    // Terminal chart colors
    const textColor = '#d0b090';
    const gridColor = 'rgba(240, 160, 96, 0.15)';

    state.languageChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Chunks',
                data: data,
                backgroundColor: 'rgba(240, 160, 96, 0.6)',
                borderColor: '#f0a060',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: textColor,
                        font: { family: "'IBM Plex Mono', monospace", size: 10 }
                    },
                    grid: {
                        color: gridColor,
                        borderDash: [4, 4]
                    }
                },
                x: {
                    ticks: {
                        color: textColor,
                        font: { family: "'IBM Plex Mono', monospace", size: 10 }
                    },
                    grid: {
                        color: gridColor
                    }
                }
            }
        }
    });
}

export function updateSymbolChart(symbols) {
    const ctx = document.getElementById('symbolChart');

    if (!symbols || Object.keys(symbols).length === 0) {
        // No symbols - show message
        if (state.symbolChart) {
            state.symbolChart.destroy();
            state.symbolChart = null;
        }
        ctx.parentElement.innerHTML = '<p style="text-align: center; padding: 40px; color: var(--text-secondary);">No symbol data available</p>';
        return;
    }

    const entries = Object.entries(symbols).sort((a, b) => b[1] - a[1]);
    const labels = entries.map(e => e[0]);
    const data = entries.map(e => e[1]);

    // Destroy existing chart
    if (state.symbolChart) {
        state.symbolChart.destroy();
    }

    // Terminal chart colors
    const textColor = '#d0b090';
    const gridColor = 'rgba(240, 160, 96, 0.15)';

    state.symbolChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Count',
                data: data,
                backgroundColor: 'rgba(192, 160, 96, 0.6)',
                borderColor: '#c0a060',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: textColor,
                        font: { family: "'IBM Plex Mono', monospace", size: 10 }
                    },
                    grid: {
                        color: gridColor,
                        borderDash: [4, 4]
                    }
                },
                x: {
                    ticks: {
                        color: textColor,
                        font: { family: "'IBM Plex Mono', monospace", size: 10 }
                    },
                    grid: {
                        color: gridColor
                    }
                }
            }
        }
    });
}

export function updateGrammarChart(grammars) {
    const section = document.getElementById('grammarDistributionSection');
    const ctx = document.getElementById('grammarChart');

    if (!grammars || grammars.length === 0) {
        section.style.display = 'none';
        if (state.grammarChart) {
            state.grammarChart.destroy();
            state.grammarChart = null;
        }
        return;
    }

    const labels = grammars.map(g => g.grammar_name);
    const data = grammars.map(g => g.chunk_count);

    if (state.grammarChart) {
        state.grammarChart.destroy();
    }

    // Terminal chart colors
    const textColor = '#d0b090';
    const gridColor = 'rgba(240, 160, 96, 0.15)';

    state.grammarChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Chunks',
                data: data,
                backgroundColor: 'rgba(224, 120, 64, 0.6)',
                borderColor: '#e07840',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, ticks: { color: textColor, font: { family: "'IBM Plex Mono', monospace", size: 10 } }, grid: { color: gridColor, borderDash: [4, 4] } },
                x: { ticks: { color: textColor, font: { family: "'IBM Plex Mono', monospace", size: 10 } }, grid: { color: gridColor } }
            }
        }
    });

    section.style.display = 'block';
}
