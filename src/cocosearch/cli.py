"""CLI entry point for cocosearch.

Provides command-line interface for indexing codebases with progress
feedback and completion summaries.
"""

import argparse
import os
import re
import sys
from pathlib import Path

from rich.console import Console

from cocosearch.indexer import IndexingConfig, load_config, run_index
from cocosearch.indexer.progress import IndexingProgress


def derive_index_name(path: str) -> str:
    """Derive an index name from a directory path.

    Converts a path to a sanitized index name by:
    1. Converting to absolute path
    2. Extracting the last directory component
    3. Converting to lowercase
    4. Replacing non-alphanumeric characters with underscores

    Args:
        path: Path to derive name from.

    Returns:
        Sanitized index name suitable for database table names.

    Examples:
        >>> derive_index_name("/home/user/MyProject")
        'myproject'
        >>> derive_index_name("/tmp/test-repo/")
        'test_repo'
    """
    # Convert to absolute and resolve any symlinks
    abs_path = os.path.abspath(path)

    # Remove trailing slashes
    abs_path = abs_path.rstrip(os.sep)

    # Handle root path edge case
    if not abs_path or abs_path == os.sep:
        return "root"

    # Get the last component (directory name)
    name = os.path.basename(abs_path)

    # Lowercase
    name = name.lower()

    # Replace non-alphanumeric with underscore
    name = re.sub(r"[^a-z0-9]", "_", name)

    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name)

    # Remove leading/trailing underscores
    name = name.strip("_")

    # Handle empty result
    if not name:
        return "index"

    return name


def index_command(args: argparse.Namespace) -> int:
    """Execute the index command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    console = Console()

    # Validate path exists
    codebase_path = os.path.abspath(args.path)
    if not os.path.isdir(codebase_path):
        console.print(f"[bold red]Error:[/bold red] Path does not exist or is not a directory: {args.path}")
        return 1

    # Determine index name
    if args.name:
        index_name = args.name
    else:
        index_name = derive_index_name(codebase_path)
        console.print(f"[dim]Using derived index name: {index_name}[/dim]")

    # Load config from .cocosearch.yaml if present
    config_path = Path(codebase_path) / ".cocosearch.yaml"
    if config_path.exists():
        console.print(f"[dim]Loading config from {config_path}[/dim]")
        config = load_config(config_path)
    else:
        config = IndexingConfig()

    # Merge CLI args with config (CLI overrides config)
    if args.include:
        # Append CLI includes to config includes
        config = IndexingConfig(
            include_patterns=list(config.include_patterns) + list(args.include),
            exclude_patterns=config.exclude_patterns,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )
    if args.exclude:
        # Append CLI excludes to config excludes
        config = IndexingConfig(
            include_patterns=config.include_patterns,
            exclude_patterns=list(config.exclude_patterns) + list(args.exclude),
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )

    # Run indexing with progress display
    try:
        with IndexingProgress(console) as progress:
            progress.start_indexing(codebase_path)

            # Run the indexing flow
            # Note: respect_gitignore is handled internally by run_index
            # based on whether --no-gitignore was passed (we pass this via config)
            update_info = run_index(
                index_name=index_name,
                codebase_path=codebase_path,
                config=config,
                respect_gitignore=not args.no_gitignore,
            )

            # Extract stats from update_info
            # CocoIndex returns IndexUpdateInfo with stats dict
            # stats structure: {'files': {'num_insertions': N, 'num_deletions': N, ...}}
            stats = {
                "files_added": 0,
                "files_removed": 0,
                "files_updated": 0,
            }

            # Extract actual stats from CocoIndex response
            if hasattr(update_info, "stats") and isinstance(update_info.stats, dict):
                file_stats = update_info.stats.get("files", {})
                stats["files_added"] = file_stats.get("num_insertions", 0)
                stats["files_removed"] = file_stats.get("num_deletions", 0)
                stats["files_updated"] = file_stats.get("num_updates", 0)

            progress.complete(stats)

        return 0

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Indexing failed: {e}")
        return 1


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="cocosearch",
        description="Local-first semantic code search",
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Index subcommand
    index_parser = subparsers.add_parser(
        "index",
        help="Index a codebase for semantic search",
        description="Index a codebase directory, creating embeddings for code search.",
    )
    index_parser.add_argument(
        "path",
        help="Path to the codebase directory to index",
    )
    index_parser.add_argument(
        "-n", "--name",
        help="Index name (default: derived from directory name)",
    )
    index_parser.add_argument(
        "-i", "--include",
        action="append",
        help="Additional file patterns to include (can be repeated)",
    )
    index_parser.add_argument(
        "-e", "--exclude",
        action="append",
        help="Additional file patterns to exclude (can be repeated)",
    )
    index_parser.add_argument(
        "--no-gitignore",
        action="store_true",
        help="Disable .gitignore pattern respect",
    )

    # Parse and dispatch
    args = parser.parse_args()

    if args.command == "index":
        sys.exit(index_command(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
