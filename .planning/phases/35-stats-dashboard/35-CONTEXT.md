# Phase 35: Stats Dashboard - Context

**Gathered:** 2026-02-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Provide index observability via CLI, terminal dashboard, and web UI. Users can check index health, view per-language and symbol breakdowns, and get warnings about issues. This phase delivers stats viewing — index modification and management are separate concerns.

</domain>

<decisions>
## Implementation Decisions

### CLI Output Design
- Default `cocosearch stats` shows summary + per-language breakdown
- Per-language display uses Unicode bar charts showing relative distribution
- Symbol type counts included in verbose mode (`-v` flag)
- `--json` flag for machine-readable output
- `--all` flag to show stats for all indexed projects (default: current project only)

### Terminal Dashboard UX
- Multi-pane layout: summary left, details right
- Invoked via `cocosearch stats --live`
- Static snapshot by default, auto-refresh in `--watch` mode
- Unicode horizontal bar charts for language/symbol distribution
- No sparklines or history visualization

### Web UI Design
- Summary view with expandable details (quick glance + drilldown)
- Data-rich visual style (dense charts, tables, Grafana-like)
- Both dark and light mode with auto-detect from system preference
- Served either embedded in MCP server OR via standalone `cocosearch serve-dashboard`

### Staleness & Warnings
- Staleness threshold configurable (default: 7 days)
- Warnings displayed as prominent header block before stats
- Full health check always included: staleness + unsupported files + zero-chunk files + embedding failures
- Health info is part of regular stats output (no separate flag needed)

### Claude's Discretion
- Exact bar chart Unicode characters and scaling
- Color scheme for warnings (yellow/red)
- Auto-refresh interval for watch mode
- Web dashboard chart library choice
- Layout details for multi-pane terminal view

</decisions>

<specifics>
## Specific Ideas

- Terminal dashboard should feel like htop or btop — functional multi-pane layout
- Web dashboard should have Grafana-like density — lots of information at a glance
- Warnings should be impossible to miss — prominent header, not buried in output

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 35-stats-dashboard*
*Context gathered: 2026-02-04*
