"""Foreground `cocosearch watch` command.

Runs an incremental reindex in a loop at a fixed interval. Because
``flow.update()`` (called by ``run_index``) is already content-hash
incremental, each tick only reprocesses changed files — so polling is
cheap in steady state and immediate after a file edit.

A future iteration may swap the polling loop for
``cocoindex.FlowLiveUpdater`` once we've validated it plays well with
``create_code_index_flow``. That's a pure internal swap — the CLI UX
stays the same.
"""

from __future__ import annotations

import signal
import threading
import time
from pathlib import Path

from rich.console import Console

from cocosearch.auto_reindex import run_reindex_sync


def run_watch(
    project_path: Path,
    index_name: str,
    *,
    interval_seconds: int = 30,
    include_deps: bool = True,
    console: Console | None = None,
    stop_event: threading.Event | None = None,
) -> int:
    """Run the watch loop until interrupted.

    Args:
        project_path: Absolute path to the project to watch.
        index_name: Index name to keep in sync.
        interval_seconds: Poll interval between incremental updates.
        include_deps: Whether to refresh the dependency graph each tick.
        console: Optional Rich console (defaults to a new one).
        stop_event: Optional pre-built stop event. If provided, setting it
            exits the loop after the current tick. Tests use this to drive
            the loop deterministically; the CLI path lets run_watch create
            its own and bind it to SIGINT.

    Returns:
        Process exit code (0 on clean shutdown, 1 on fatal error).
    """
    if console is None:
        console = Console()

    if stop_event is None:
        stop_event = threading.Event()

    def _handle_sigint(signum, frame):
        # First Ctrl+C → set the event; the loop below will finish its tick
        # and exit cleanly. Second Ctrl+C is the user's escape hatch.
        console.print("\n[dim]Stopping watch — press Ctrl+C again to abort.[/dim]")
        stop_event.set()

    old_handler = signal.signal(signal.SIGINT, _handle_sigint)

    console.print(
        f"[bold]Watching[/bold] {project_path} → index [cyan]{index_name}[/cyan]"
    )
    console.print(
        f"[dim]Polling every {interval_seconds}s. "
        f"Deps refresh: {'on' if include_deps else 'off'}. "
        f"Ctrl+C to stop.[/dim]\n"
    )

    tick = 0
    try:
        while not stop_event.is_set():
            tick += 1
            t0 = time.monotonic()
            try:
                result = run_reindex_sync(
                    index_name,
                    str(project_path),
                    fresh=False,
                    include_deps=include_deps,
                )
            except Exception as exc:  # defensive — run_reindex_sync already catches
                console.print(f"[red]Tick #{tick} failed:[/red] {exc}")
                # Don't bail out — a transient DB hiccup shouldn't kill the loop.
                result = None

            elapsed = time.monotonic() - t0
            if result and result.get("success"):
                deps_note = (
                    " [green]+ deps[/green]" if result.get("deps_extracted") else ""
                )
                console.print(
                    f"[dim]tick {tick}[/dim] "
                    f"[green]ok[/green] in {elapsed:.1f}s{deps_note}"
                )
            elif result:
                console.print(
                    f"[dim]tick {tick}[/dim] "
                    f"[red]error[/red]: {result.get('error') or 'unknown'}"
                )

            # Sleep in small chunks so SIGINT is responsive.
            remaining = interval_seconds
            while remaining > 0 and not stop_event.is_set():
                chunk = min(0.5, remaining)
                time.sleep(chunk)
                remaining -= chunk
    finally:
        signal.signal(signal.SIGINT, old_handler)

    console.print("[dim]Watch stopped.[/dim]")
    return 0
