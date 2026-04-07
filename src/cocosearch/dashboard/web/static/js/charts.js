import { state } from './state.js';
import { THEME_CHANGE_EVENT } from './theme.js';

// Read chart palette from CSS custom properties so charts always reflect
// the current theme. Called on chart create AND on every theme change.
function getChartColors() {
    const cs = getComputedStyle(document.documentElement);
    const read = (n) => cs.getPropertyValue(n).trim();
    return {
        textColor:  read('--text-secondary'),
        gridColor:  read('--shadow'),
        langBorder: read('--accent-blue'),
        langFill:   read('--accent-blue') + '99',   // ~60% alpha via hex
        symBorder:  read('--accent-green'),
        symFill:    read('--accent-green') + '99',
        gramBorder: read('--accent-orange'),
        gramFill:   read('--accent-orange') + '99',
    };
}

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

    const colors = getChartColors();

    state.languageChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Chunks',
                data: data,
                backgroundColor: colors.langFill,
                borderColor: colors.langBorder,
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
                        color: colors.textColor,
                        font: { family: "'IBM Plex Mono', monospace", size: 10 }
                    },
                    grid: {
                        color: colors.gridColor,
                        borderDash: [4, 4]
                    }
                },
                x: {
                    ticks: {
                        color: colors.textColor,
                        font: { family: "'IBM Plex Mono', monospace", size: 10 }
                    },
                    grid: {
                        color: colors.gridColor
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

    const colors = getChartColors();

    state.symbolChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Count',
                data: data,
                backgroundColor: colors.symFill,
                borderColor: colors.symBorder,
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
                        color: colors.textColor,
                        font: { family: "'IBM Plex Mono', monospace", size: 10 }
                    },
                    grid: {
                        color: colors.gridColor,
                        borderDash: [4, 4]
                    }
                },
                x: {
                    ticks: {
                        color: colors.textColor,
                        font: { family: "'IBM Plex Mono', monospace", size: 10 }
                    },
                    grid: {
                        color: colors.gridColor
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

    const colors = getChartColors();

    state.grammarChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Chunks',
                data: data,
                backgroundColor: colors.gramFill,
                borderColor: colors.gramBorder,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, ticks: { color: colors.textColor, font: { family: "'IBM Plex Mono', monospace", size: 10 } }, grid: { color: colors.gridColor, borderDash: [4, 4] } },
                x: { ticks: { color: colors.textColor, font: { family: "'IBM Plex Mono', monospace", size: 10 } }, grid: { color: colors.gridColor } }
            }
        }
    });

    section.style.display = 'block';
}

// Re-theme existing chart instances when the user toggles light/dark mode.
// Mutates options + dataset colors and calls update() — no destroy/recreate,
// so no data churn or animation artifacts.
document.addEventListener(THEME_CHANGE_EVENT, () => {
    const colors = getChartColors();
    const map = {
        languageChart: ['langBorder', 'langFill'],
        symbolChart:   ['symBorder',  'symFill'],
        grammarChart:  ['gramBorder', 'gramFill'],
    };
    for (const [key, [borderKey, fillKey]] of Object.entries(map)) {
        const chart = state[key];
        if (!chart) continue;
        chart.options.scales.x.ticks.color = colors.textColor;
        chart.options.scales.y.ticks.color = colors.textColor;
        chart.options.scales.x.grid.color = colors.gridColor;
        chart.options.scales.y.grid.color = colors.gridColor;
        chart.data.datasets[0].borderColor = colors[borderKey];
        chart.data.datasets[0].backgroundColor = colors[fillKey];
        chart.update();
    }
});
