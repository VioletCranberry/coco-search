"""Progress reporting utilities for indexing.

Uses Rich library for attractive console output with progress indicators
and formatted summaries.
"""

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table


class IndexingProgress:
    """Context manager for displaying indexing progress.

    Uses Rich progress bars with spinner, description, and elapsed time.
    Since CocoIndex handles file processing internally, this mainly shows
    start/end status rather than per-file progress.

    Example:
        with IndexingProgress() as progress:
            progress.start_indexing("/path/to/codebase")
            progress.update_status("Processing files...")
            # ... indexing happens ...
            progress.complete({"files_added": 10, "files_removed": 0})
    """

    def __init__(self, console: Console | None = None) -> None:
        """Initialize progress display.

        Args:
            console: Rich console to use. If None, creates a new one.
        """
        self._console = console or Console()
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self._console,
            transient=True,  # Remove progress bar on completion
        )
        self._task_id: int | None = None

    def __enter__(self) -> "IndexingProgress":
        """Enter context manager - start progress display."""
        self._progress.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager - stop progress display."""
        self._progress.stop()

    def start_indexing(self, codebase_path: str) -> None:
        """Display initial indexing message.

        Args:
            codebase_path: Path to the codebase being indexed.
        """
        # Add a task with indeterminate progress (no total)
        self._task_id = self._progress.add_task(
            f"Indexing [bold blue]{codebase_path}[/bold blue]...",
            total=None,
        )

    def update_status(self, message: str) -> None:
        """Update the progress description.

        Args:
            message: New status message to display.
        """
        if self._task_id is not None:
            self._progress.update(self._task_id, description=message)

    def complete(self, stats: dict) -> None:
        """Mark indexing as complete and print summary.

        Args:
            stats: Dictionary with indexing statistics (files_added, etc.)
        """
        if self._task_id is not None:
            self._progress.update(
                self._task_id,
                description="[bold green]Indexing complete[/bold green]",
                completed=100,
                total=100,
            )
        # Print summary after progress bar completes
        print_summary(stats, self._console)


def print_summary(stats: dict, console: Console | None = None) -> None:
    """Print a formatted summary of indexing results.

    Args:
        stats: Dictionary with indexing statistics. Expected keys:
            - files_added: Number of new files indexed
            - files_removed: Number of files removed from index
            - files_updated: Number of files updated (optional)
            - chunks_created: Total chunks created (optional)
            - duration: Time elapsed (optional)
        console: Rich console to use. If None, creates a new one.
    """
    console = console or Console()

    # Create summary table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="bold")
    table.add_column("Value", style="cyan")

    # Add rows for available stats
    files_added = stats.get("files_added", 0)
    files_removed = stats.get("files_removed", 0)
    files_updated = stats.get("files_updated", 0)

    table.add_row("Files added", str(files_added))
    table.add_row("Files updated", str(files_updated))
    table.add_row("Files removed", str(files_removed))

    if "chunks_created" in stats:
        table.add_row("Chunks created", str(stats["chunks_created"]))

    if "duration" in stats:
        table.add_row("Duration", stats["duration"])

    # Wrap in a panel
    panel = Panel(
        table,
        title="[bold]Indexing Summary[/bold]",
        border_style="green",
    )

    console.print()  # Blank line before summary
    console.print(panel)
