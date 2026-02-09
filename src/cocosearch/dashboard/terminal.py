"""Terminal dashboard for cocosearch.

Provides Rich-based multi-pane dashboard with live updates.
"""

import time
from datetime import datetime

from rich.bar import Bar
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from cocosearch.management.stats import get_comprehensive_stats, IndexStats


def create_layout() -> Layout:
    """Create htop-style multi-pane layout.

    Layout structure:
    +------------------+
    |      header      |
    +--------+---------+
    | summary| details |
    +--------+---------+
    """
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="body"),
    )
    layout["body"].split_row(
        Layout(name="summary", ratio=1),
        Layout(name="details", ratio=2),
    )
    return layout


def format_header(stats: IndexStats, last_refresh: datetime) -> Panel:
    """Format header panel with warnings and refresh time."""
    lines = []

    # Warnings first (prominent)
    if stats.warnings:
        for w in stats.warnings:
            lines.append(f"[bold yellow]! {w}[/bold yellow]")
        lines.append("")

    # Title and refresh time
    lines.append(
        f"[bold]Index: {stats.name}[/bold]  |  Last refresh: {last_refresh.strftime('%H:%M:%S')}"
    )

    return Panel(
        "\n".join(lines), title="[bold]Stats Dashboard[/bold]", border_style="blue"
    )


def format_summary_panel(stats: IndexStats) -> Panel:
    """Format left summary panel with key metrics."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bold")

    table.add_row("Files", f"{stats.file_count:,}")
    table.add_row("Chunks", f"{stats.chunk_count:,}")
    table.add_row("Size", stats.storage_size_pretty)
    if stats.source_path:
        table.add_row("Source", stats.source_path)
    if stats.status:
        if stats.status == "indexing":
            table.add_row("Status", "[yellow]Indexing...[/yellow]")
        else:
            table.add_row("Status", f"[dim]{stats.status.title()}[/dim]")
    if stats.parse_stats:
        pct = stats.parse_stats.get("parse_health_pct", 100.0)
        total_ok = stats.parse_stats.get("total_ok", 0)
        total_files = stats.parse_stats.get("total_files", 0)
        color = "green" if pct >= 95 else "yellow" if pct >= 80 else "red"
        table.add_row(
            "Parse Health", f"[{color}]{pct}% ({total_ok}/{total_files})[/{color}]"
        )
    table.add_row("", "")

    # Timestamps
    if stats.created_at:
        table.add_row("Created", stats.created_at.strftime("%Y-%m-%d"))
    if stats.updated_at:
        table.add_row("Updated", stats.updated_at.strftime("%Y-%m-%d"))
        table.add_row("", f"({stats.staleness_days}d ago)")

    return Panel(table, title="Summary", border_style="green")


def format_details_panel(stats: IndexStats) -> Panel:
    """Format right details panel with language and symbol breakdown."""
    # Language distribution with bars
    lang_table = Table(title="Languages", show_header=True, expand=True)
    lang_table.add_column("Lang", style="cyan", width=10)
    lang_table.add_column("Files", justify="right", width=6)
    lang_table.add_column("Chunks", justify="right", width=7)
    lang_table.add_column("Distribution", width=20)

    max_chunks = max((lang["chunk_count"] for lang in stats.languages), default=1)
    for lang in stats.languages[:10]:  # Top 10
        ratio = lang["chunk_count"] / max_chunks if max_chunks > 0 else 0
        bar = Bar(size=20, begin=0, end=ratio * 20)
        lang_table.add_row(
            lang["language"][:10],
            str(lang["file_count"]),
            str(lang["chunk_count"]),
            bar,
        )

    # Symbol distribution (if available)
    if stats.symbols:
        sym_table = Table(title="Symbols", show_header=True, expand=True)
        sym_table.add_column("Type", style="magenta", width=10)
        sym_table.add_column("Count", justify="right", width=8)

        for sym_type, count in sorted(stats.symbols.items(), key=lambda x: -x[1])[:5]:
            sym_table.add_row(sym_type, f"{count:,}")

    # Parse health by language (if available)
    parse_table = None
    if stats.parse_stats and stats.parse_stats.get("by_language"):
        parse_table = Table(title="Parse Health", show_header=True, expand=True)
        parse_table.add_column("Lang", style="cyan", width=10)
        parse_table.add_column("Files", justify="right", width=6)
        parse_table.add_column("OK", justify="right", width=6)
        parse_table.add_column("Issues", justify="right", width=7)
        parse_table.add_column("Status", width=12)

        by_lang = stats.parse_stats["by_language"]
        # Tracked languages first, then skipped
        tracked = sorted(
            [(l, d) for l, d in by_lang.items() if not d.get("skipped")],
            key=lambda x: -x[1]["files"],
        )
        skipped = sorted(
            [(l, d) for l, d in by_lang.items() if d.get("skipped")],
            key=lambda x: -x[1]["files"],
        )
        for lang, data in tracked:
            issues = data.get("partial", 0) + data.get("error", 0) + data.get("no_grammar", 0)
            pct = (data["ok"] / data["files"] * 100) if data["files"] > 0 else 100
            color = "green" if pct >= 95 else "yellow" if pct >= 80 else "red"
            parse_table.add_row(
                lang[:10],
                str(data["files"]),
                str(data["ok"]),
                str(issues) if issues else "-",
                f"[{color}]{pct:.0f}%[/{color}]",
            )
        for lang, data in skipped:
            parse_table.add_row(
                lang[:10],
                str(data["files"]),
                "-",
                "-",
                "[dim]skipped[/dim]",
            )

    # Combine tables vertically
    from rich.console import Group

    parts = [lang_table]
    if stats.symbols:
        parts.extend(["", sym_table])
    if parse_table:
        parts.extend(["", parse_table])
    content = Group(*parts)

    return Panel(content, title="Details", border_style="cyan")


def run_terminal_dashboard(
    index_name: str,
    watch: bool = False,
    refresh_interval: float = 1.0,
) -> None:
    """Run the terminal dashboard.

    Args:
        index_name: Name of the index to display
        watch: If True, auto-refresh stats periodically
        refresh_interval: Seconds between refreshes (default: 1)
    """
    console = Console()
    layout = create_layout()

    # Initial stats fetch
    try:
        stats = get_comprehensive_stats(index_name)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return

    last_refresh = datetime.now()

    if watch:
        # Live updating mode
        with Live(layout, console=console, refresh_per_second=4, screen=True):
            try:
                while True:
                    # Update layout
                    layout["header"].update(format_header(stats, last_refresh))
                    layout["summary"].update(format_summary_panel(stats))
                    layout["details"].update(format_details_panel(stats))

                    time.sleep(refresh_interval)

                    # Refresh stats
                    try:
                        stats = get_comprehensive_stats(index_name)
                        last_refresh = datetime.now()
                    except Exception:
                        pass  # Keep showing last good stats

            except KeyboardInterrupt:
                pass  # Clean exit on Ctrl+C
    else:
        # Static snapshot mode (--live without --watch)
        layout["header"].update(format_header(stats, last_refresh))
        layout["summary"].update(format_summary_panel(stats))
        layout["details"].update(format_details_panel(stats))

        # Display once and return
        console.print(layout)
        console.print(
            "\n[dim]Press Ctrl+C to exit. Use --watch for auto-refresh.[/dim]"
        )
