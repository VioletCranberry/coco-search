# Phase 35: Stats Dashboard - Research

**Researched:** 2026-02-04
**Domain:** CLI output formatting, terminal dashboards, web UI, HTTP API endpoints
**Confidence:** HIGH

## Summary

This phase implements index observability across three interfaces: enhanced CLI output with bar charts and warnings, a terminal dashboard with multi-pane layout, and a web UI served via HTTP API. The research confirms that all components can be built using libraries already in the project (Rich, FastMCP) with minimal new dependencies (Chart.js for web UI).

The key insight is that Rich already provides all terminal dashboard capabilities needed (Layout, Live, Panel, Table, Bar) and the existing MCP server's `@mcp.custom_route` decorator enables HTTP endpoints for both the API and web UI serving without adding new dependencies. For web UI charts, Chart.js offers minimal setup via CDN with excellent bar chart support.

**Primary recommendation:** Use Rich's Layout + Live for terminal dashboard, Rich's Bar class for CLI bar charts, Chart.js via CDN for web UI, and FastMCP custom_route for HTTP API endpoints.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Rich | 13.0.0+ | Terminal output, tables, bar charts, layouts, live display | Already in project, comprehensive terminal UI |
| FastMCP | (via mcp package) | HTTP API endpoints via @mcp.custom_route | Already in project, enables /api/stats endpoint |
| Chart.js | 4.x | Web UI charts | Lightweight, CDN-ready, excellent bar charts |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| argparse | stdlib | CLI flags (--json, -v, --live, --watch, --all) | Already in project |
| json | stdlib | Machine-readable output | For --json flag |
| datetime | stdlib | Staleness calculation | For 7-day threshold check |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Chart.js | Plotly.js | Heavier (~1MB vs ~60KB), more features not needed |
| Chart.js | D3.js | Steep learning curve, overkill for simple bar charts |
| Rich Layout | Textual | Separate framework, not needed for this scope |
| Embedded HTML | Dash/Streamlit | Heavy frameworks, separate process, overkill |

**Installation:**
```bash
# No new Python dependencies needed - Rich and FastMCP already installed
# Chart.js loaded via CDN in HTML:
# <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
```

## Architecture Patterns

### Recommended Project Structure
```
src/cocosearch/
├── management/
│   └── stats.py              # Enhanced: add symbol stats, staleness, health checks
├── cli.py                    # Enhanced: add -v, --json, --live, --watch, --all flags
├── dashboard/
│   ├── __init__.py           # Dashboard module exports
│   ├── terminal.py           # Rich Layout + Live terminal dashboard
│   └── web/
│       ├── __init__.py       # Web dashboard server
│       ├── api.py            # Stats API endpoint logic
│       └── static/
│           ├── index.html    # Single-page dashboard
│           ├── style.css     # Dark/light mode styles
│           └── app.js        # Chart.js initialization
└── mcp/
    └── server.py             # Enhanced: add /api/stats and /dashboard routes
```

### Pattern 1: Stats Data Model
**What:** Centralized stats collection returning a consistent data structure
**When to use:** All interfaces (CLI, terminal dashboard, web UI, MCP tool)
**Example:**
```python
# Source: Based on existing stats.py patterns
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class IndexStats:
    """Comprehensive index statistics."""
    # Basic metrics
    name: str
    file_count: int
    chunk_count: int
    storage_size: int
    storage_size_pretty: str

    # Timestamps
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    # Health indicators
    is_stale: bool  # updated_at > staleness_threshold
    staleness_days: int

    # Per-language breakdown
    languages: list[dict]  # [{language, file_count, chunk_count, line_count}]

    # Symbol statistics
    symbols: dict  # {symbol_type: count}

    # Health warnings
    warnings: list[str]  # ["Index is stale (15 days)", "3 files with zero chunks"]
```

### Pattern 2: Rich Layout for Terminal Dashboard
**What:** Multi-pane terminal dashboard using Rich's Layout class
**When to use:** `cocosearch stats --live` command
**Example:**
```python
# Source: https://rich.readthedocs.io/en/stable/layout.html
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table

def create_dashboard_layout():
    """Create htop-style multi-pane layout."""
    layout = Layout()

    # Split into header + body
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
    )

    # Split body into left (summary) + right (details)
    layout["body"].split_row(
        Layout(name="summary", ratio=1),
        Layout(name="details", ratio=2),
    )

    return layout

def run_live_dashboard(stats: IndexStats, refresh_rate: int = 4):
    """Run live-updating dashboard."""
    layout = create_dashboard_layout()

    with Live(layout, refresh_per_second=refresh_rate, screen=True):
        while True:
            layout["header"].update(Panel(format_warnings(stats)))
            layout["summary"].update(Panel(format_summary_panel(stats)))
            layout["details"].update(Panel(format_details_panel(stats)))
            time.sleep(1)  # Refresh interval
```

### Pattern 3: Unicode Bar Charts in CLI
**What:** Simple Unicode horizontal bars showing relative distribution
**When to use:** Default `cocosearch stats` output for language breakdown
**Example:**
```python
# Source: Based on Rich capabilities
from rich.bar import Bar
from rich.table import Table
from rich.console import Console

def format_language_bars(languages: list[dict], max_width: int = 30) -> Table:
    """Create table with Unicode bar charts for language distribution."""
    table = Table(show_header=True)
    table.add_column("Language", style="cyan", width=12)
    table.add_column("Files", justify="right", width=6)
    table.add_column("Distribution", width=max_width)

    # Find max for scaling
    max_files = max(lang["file_count"] for lang in languages)

    for lang in languages:
        # Create proportional bar
        ratio = lang["file_count"] / max_files if max_files > 0 else 0
        bar = Bar(size=max_width, begin=0, end=ratio * max_width)
        table.add_row(lang["language"], str(lang["file_count"]), bar)

    return table
```

### Pattern 4: HTTP API via FastMCP custom_route
**What:** Add /api/stats endpoint to existing MCP server
**When to use:** Web UI data source, programmatic access
**Example:**
```python
# Source: Existing mcp/server.py pattern
from starlette.responses import JSONResponse

@mcp.custom_route("/api/stats", methods=["GET"])
async def api_stats(request):
    """Stats API endpoint for web dashboard."""
    index_name = request.query_params.get("index")

    if index_name:
        stats = get_comprehensive_stats(index_name)
    else:
        stats = [get_comprehensive_stats(idx["name"]) for idx in list_indexes()]

    return JSONResponse(stats)

@mcp.custom_route("/api/stats/{index_name}", methods=["GET"])
async def api_stats_single(request):
    """Stats for a single index."""
    index_name = request.path_params["index_name"]
    stats = get_comprehensive_stats(index_name)
    return JSONResponse(stats)
```

### Pattern 5: Single-Page Web Dashboard
**What:** Embedded HTML/JS dashboard served from MCP server
**When to use:** `cocosearch serve-dashboard` or MCP server at /dashboard
**Example:**
```python
# Source: Based on FastAPI/Starlette patterns
from starlette.responses import HTMLResponse

@mcp.custom_route("/dashboard", methods=["GET"])
async def serve_dashboard(request):
    """Serve the web dashboard HTML."""
    # Read embedded HTML file
    html_path = Path(__file__).parent / "dashboard" / "web" / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text())

# For static assets (CSS, JS)
# Option 1: Inline everything in HTML (simplest)
# Option 2: Use data URIs for small assets
# Option 3: Add multiple custom_routes for /dashboard/style.css, /dashboard/app.js
```

### Anti-Patterns to Avoid
- **Adding heavy dashboard frameworks (Dash, Streamlit):** Overkill for displaying stats, adds process management complexity
- **Creating separate server process for web UI:** Use existing MCP server with custom_route
- **Polling database in Live loop:** Refresh on user action or timer, cache stats
- **Storing stats history in database:** Out of scope - show current state only
- **Complex charting for CLI:** Use Rich's built-in Bar class, not external plotting libraries

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Terminal bar charts | Custom Unicode strings | Rich Bar class | Handles terminal width, colors, scaling |
| Multi-pane layout | Manual cursor control | Rich Layout + Panel | Handles resize, overflow, borders |
| Live refresh | Manual clear + print | Rich Live class | Handles flicker, terminal capabilities |
| JSON serialization | Custom formatting | json.dumps with dataclasses | Handles edge cases, encoding |
| Web charts | Canvas drawing code | Chart.js | Handles responsiveness, tooltips, animations |
| Dark/light mode | Manual CSS switching | CSS prefers-color-scheme | Automatic, no JS needed |
| HTTP endpoints | Custom socket server | FastMCP custom_route | Already configured, handles CORS |

**Key insight:** Rich is already comprehensive for terminal UI - don't add Textual or ncurses. Chart.js via CDN is sufficient for web - don't add Python charting frameworks.

## Common Pitfalls

### Pitfall 1: Live Display Blocking Main Thread
**What goes wrong:** Terminal dashboard becomes unresponsive when fetching fresh stats
**Why it happens:** Database queries in Live loop block refresh
**How to avoid:** Fetch stats outside the Live context, use cached stats for display, refresh stats on timer or keypress
**Warning signs:** Dashboard freezes during database operations

### Pitfall 2: Staleness Threshold Confusion
**What goes wrong:** Staleness warning based on `updated_at` but index hasn't changed, or warning not showing when it should
**Why it happens:** `updated_at` updates on any index operation, not just content changes
**How to avoid:** Use `updated_at` from `cocosearch_index_metadata` table (set during indexing), document that staleness means "not re-indexed recently"
**Warning signs:** Users confused by staleness warnings on unchanged repos

### Pitfall 3: JSON Output Inconsistency
**What goes wrong:** Different JSON structure between CLI and API endpoints
**Why it happens:** Separate formatting in CLI vs API
**How to avoid:** Use single stats dataclass that serializes consistently, both CLI --json and API use same serialization
**Warning signs:** Scripts break when switching between CLI and API

### Pitfall 4: Terminal Dashboard Size Assumptions
**What goes wrong:** Dashboard renders incorrectly in small terminals or tmux panes
**Why it happens:** Hardcoded widths and heights
**How to avoid:** Use Rich Layout ratio-based sizing, set minimum_size, test in 80x24 terminal
**Warning signs:** Truncated text, broken layouts in split terminals

### Pitfall 5: Web Dashboard Caching Issues
**What goes wrong:** Stats don't refresh, showing stale data
**Why it happens:** Browser caching API responses
**How to avoid:** Add Cache-Control: no-cache header, or timestamp query param for API calls
**Warning signs:** Users reporting stats don't update after re-indexing

### Pitfall 6: Symbol Stats on Pre-v1.7 Indexes
**What goes wrong:** Symbol stats show empty or error for older indexes
**Why it happens:** Pre-v1.7 indexes lack symbol columns
**How to avoid:** Check column existence (existing pattern in db.py), graceful degradation with "N/A" and hint to re-index
**Warning signs:** Errors when running stats on old indexes

## Code Examples

Verified patterns from official sources:

### Rich Live Dashboard
```python
# Source: https://rich.readthedocs.io/en/latest/live.html
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel

layout = Layout()
layout.split_column(
    Layout(name="header", size=3),
    Layout(name="body"),
)

with Live(layout, refresh_per_second=4, screen=True) as live:
    while True:
        # Update layout components
        layout["header"].update(Panel("[bold]Stats Dashboard[/bold]"))
        layout["body"].update(make_stats_table())
        time.sleep(0.25)
```

### Rich Bar in Table
```python
# Source: https://rich.readthedocs.io/en/stable/ (Bar class)
from rich.bar import Bar
from rich.table import Table
from rich.console import Console

console = Console()
table = Table(title="Language Distribution")
table.add_column("Language")
table.add_column("Bar")

# Bar(size=width, begin=start, end=current_value)
table.add_row("Python", Bar(size=40, begin=0, end=30))  # 75% filled
table.add_row("JavaScript", Bar(size=40, begin=0, end=20))  # 50% filled

console.print(table)
```

### Chart.js Bar Chart
```html
<!-- Source: https://www.chartjs.org/docs/latest/getting-started/ -->
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    @media (prefers-color-scheme: dark) {
      body { background: #1a1a1a; color: #fff; }
    }
  </style>
</head>
<body>
  <canvas id="languageChart"></canvas>
  <script>
    async function loadStats() {
      const response = await fetch('/api/stats');
      const stats = await response.json();

      new Chart(document.getElementById('languageChart'), {
        type: 'bar',
        data: {
          labels: stats.languages.map(l => l.language),
          datasets: [{
            label: 'File Count',
            data: stats.languages.map(l => l.file_count),
            backgroundColor: 'rgba(54, 162, 235, 0.8)'
          }]
        },
        options: {
          responsive: true,
          scales: { y: { beginAtZero: true } }
        }
      });
    }
    loadStats();
  </script>
</body>
</html>
```

### Staleness Check
```python
# Source: Based on existing metadata.py pattern
from datetime import datetime, timedelta

def check_staleness(index_name: str, threshold_days: int = 7) -> tuple[bool, int]:
    """Check if index is stale.

    Returns:
        Tuple of (is_stale, days_since_update)
    """
    metadata = get_index_metadata(index_name)
    if metadata is None or metadata["updated_at"] is None:
        return True, -1  # No metadata means stale

    age = datetime.now() - metadata["updated_at"]
    days = age.days
    return days > threshold_days, days
```

### Warning Banner in CLI Output
```python
# Source: Based on Rich console patterns
from rich.console import Console
from rich.panel import Panel

def print_warnings(warnings: list[str], console: Console) -> None:
    """Print prominent warning banner before stats."""
    if not warnings:
        return

    warning_text = "\n".join(f"[yellow]! {w}[/yellow]" for w in warnings)
    console.print(Panel(
        warning_text,
        title="[bold yellow]Warnings[/bold yellow]",
        border_style="yellow"
    ))
    console.print()  # Blank line after warnings
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate stats server | FastMCP custom_route | MCP SDK 1.0+ | Single process, no extra dependency |
| ncurses for TUI | Rich Layout + Live | Rich 10.0+ | Pythonic API, no C dependency |
| Matplotlib for CLI charts | Rich Bar class | Rich 10.0+ | No heavy dependency, terminal-native |
| jQuery for web UI | Vanilla JS + fetch | 2020s | Lighter, no build step |

**Deprecated/outdated:**
- **curses/ncurses for Python TUIs:** Use Rich or Textual instead
- **jQuery for simple dashboards:** Vanilla JS is sufficient, smaller bundle
- **Flask for MCP endpoint serving:** FastMCP custom_route is built-in

## Open Questions

Things that couldn't be fully resolved:

1. **Auto-refresh interval for --watch mode**
   - What we know: Rich Live supports configurable refresh_per_second (default: 4)
   - What's unclear: Optimal interval for stats that change infrequently
   - Recommendation: Use 1-second refresh for watch mode (Claude's discretion per CONTEXT.md)

2. **Web dashboard chart library CDN fallback**
   - What we know: Chart.js CDN is reliable, jsdelivr has high availability
   - What's unclear: Behavior if CDN is unreachable (air-gapped environments)
   - Recommendation: Document that web UI requires internet for CDN; alternatively, bundle Chart.js minified in HTML (increases file size by ~60KB)

3. **Symbol stats aggregation performance**
   - What we know: GROUP BY symbol_type on large indexes could be slow
   - What's unclear: Performance threshold for when this matters
   - Recommendation: Implement with simple GROUP BY first, optimize if proven slow

## Sources

### Primary (HIGH confidence)
- [Rich Layout Documentation](https://rich.readthedocs.io/en/stable/layout.html) - Layout class, split_row, split_column, ratio sizing
- [Rich Live Display Documentation](https://rich.readthedocs.io/en/latest/live.html) - Live class, refresh_per_second, screen mode
- [Chart.js Getting Started](https://www.chartjs.org/docs/latest/getting-started/) - CDN installation, bar chart configuration
- Existing codebase: mcp/server.py - @mcp.custom_route pattern for HTTP endpoints

### Secondary (MEDIUM confidence)
- [Building Rich Terminal Dashboards](https://www.willmcgugan.com/blog/tech/post/building-rich-terminal-dashboards/) - Multi-pane dashboard patterns
- [JavaScript Chart Libraries 2026](https://www.luzmo.com/blog/javascript-chart-libraries) - Chart.js comparison, bundle size

### Tertiary (LOW confidence)
- CLI UX best practices search results - General patterns, not library-specific

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in project or well-documented
- Architecture: HIGH - Patterns verified in official docs and existing codebase
- Pitfalls: MEDIUM - Some based on general experience, not verified issues

**Research date:** 2026-02-04
**Valid until:** 2026-03-04 (30 days - stable libraries, low churn)
