"""CLI entry point for cocosearch.

Provides command-line interface for indexing codebases and searching
indexed code with progress feedback and completion summaries.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import cocoindex
from rich.console import Console

from cocosearch.config import (
    CocoSearchConfig,
    ConfigError as ConfigLoadError,
    ConfigResolver,
    config_key_to_env_var,
    find_config_file,
    generate_config,
    load_config as load_project_config,
)
from cocosearch.indexer import IndexingConfig, load_config, run_index
from cocosearch.indexer.progress import IndexingProgress
from cocosearch.management import clear_index, derive_index_from_git, get_stats, list_indexes
from cocosearch.search import search
from cocosearch.search.formatter import format_json, format_pretty
from cocosearch.search.repl import run_repl


def add_config_arg(parser: argparse.ArgumentParser, *flags, config_key: str, help_text: str, **kwargs) -> None:
    """Add argument with config key and env var in help text.

    Args:
        parser: Argument parser to add argument to.
        *flags: Flag names (e.g., '-n', '--name').
        config_key: Config key in dot.notation format.
        help_text: Base help text.
        **kwargs: Additional arguments for add_argument.
    """
    env_var = config_key_to_env_var(config_key)
    full_help = f"{help_text} [config: {config_key}] [env: {env_var}]"
    parser.add_argument(*flags, help=full_help, **kwargs)


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

    # Load config from cocosearch.yaml if present
    config_path = find_config_file()
    if config_path:
        console.print(f"[dim]Loading config from {config_path}[/dim]")
        try:
            project_config = load_project_config(config_path)
        except ConfigLoadError as e:
            console.print(f"[bold red]Configuration error:[/bold red]\n{e}")
            return 1
    else:
        console.print("[dim]No cocosearch.yaml found, using defaults[/dim]")
        project_config = CocoSearchConfig()

    # Create resolver with loaded config
    resolver = ConfigResolver(project_config, config_path)

    # Resolve index name with CLI > env > config > default precedence
    index_name, index_source = resolver.resolve(
        "indexName",
        cli_value=args.name,
        env_var="COCOSEARCH_INDEX_NAME"
    )
    if not index_name:
        index_name = derive_index_name(codebase_path)
        console.print(f"[dim]Using derived index name: {index_name}[/dim]")
    elif index_source not in ("default", "CLI flag"):
        console.print(f"[dim]Using index name: {index_name} ({index_source})[/dim]")
    elif index_source == "CLI flag":
        # CLI flag is explicit, no need to show source
        pass

    # Map project config to IndexingConfig
    config = IndexingConfig(
        include_patterns=project_config.indexing.includePatterns or [],
        exclude_patterns=project_config.indexing.excludePatterns or [],
        chunk_size=project_config.indexing.chunkSize,
        chunk_overlap=project_config.indexing.chunkOverlap,
    )

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


def parse_query_filters(query: str) -> tuple[str, str | None]:
    """Parse inline filters from query string.

    Extracts lang:xxx pattern from query.

    Args:
        query: User query possibly containing filters.

    Returns:
        Tuple of (clean_query, language_filter).
    """
    lang_filter = None

    # Extract lang:xxx pattern
    lang_match = re.search(r"\blang:(\w+)\b", query)
    if lang_match:
        lang_filter = lang_match.group(1)
        query = re.sub(r"\blang:\w+\b", "", query).strip()

    return query, lang_filter


def search_command(args: argparse.Namespace) -> int:
    """Execute the search command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    console = Console()

    # Initialize CocoIndex
    cocoindex.init()

    # Load config for search settings
    config_path = find_config_file()
    if config_path:
        try:
            project_config = load_project_config(config_path)
        except ConfigLoadError:
            project_config = CocoSearchConfig()
    else:
        project_config = CocoSearchConfig()

    # Create resolver with loaded config
    resolver = ConfigResolver(project_config, config_path)

    # Resolve index name with CLI > env > config > default precedence
    index_name, _ = resolver.resolve(
        "indexName",
        cli_value=args.index,
        env_var="COCOSEARCH_INDEX_NAME"
    )
    if not index_name:
        # Auto-detect: try git root first, fall back to cwd
        git_index = derive_index_from_git()
        if git_index:
            index_name = git_index
        else:
            index_name = derive_index_name(os.getcwd())

    # Resolve search settings with precedence
    limit, _ = resolver.resolve(
        "search.resultLimit",
        cli_value=args.limit if args.limit != 10 else None,  # Only use CLI if not default
        env_var="COCOSEARCH_SEARCH_RESULT_LIMIT"
    )
    min_score, _ = resolver.resolve(
        "search.minScore",
        cli_value=args.min_score if args.min_score != 0.3 else None,  # Only use CLI if not default
        env_var="COCOSEARCH_SEARCH_MIN_SCORE"
    )

    # Always print "Using index:" hint (per CONTEXT.md requirement)
    if args.pretty or args.interactive:
        console.print(f"[dim]Using index: {index_name}[/dim]")
    else:
        # For JSON mode, print to stderr to keep stdout clean
        import sys as _sys
        print(f"Using index: {index_name}", file=_sys.stderr)

    # Handle interactive mode
    if args.interactive:
        run_repl(
            index_name=index_name,
            limit=limit,
            context_lines=args.context,
            min_score=min_score,
        )
        return 0

    # Require query for non-interactive mode
    if not args.query:
        console.print("[bold red]Error:[/bold red] Query required (use --interactive for REPL mode)")
        return 1

    # Parse query for inline filters
    query, inline_lang = parse_query_filters(args.query)

    # CLI --lang overrides inline lang:
    lang_filter = args.lang or inline_lang

    # Execute search
    try:
        results = search(
            query=query,
            index_name=index_name,
            limit=limit,
            min_score=min_score,
            language_filter=lang_filter,
        )
    except Exception as e:
        if args.pretty:
            console.print(f"[bold red]Error:[/bold red] {e}")
        else:
            print(json.dumps({"error": str(e)}))
        return 1

    # Output results
    if args.pretty:
        format_pretty(results, context_lines=args.context, console=console)
    else:
        print(format_json(results, context_lines=args.context))

    return 0


def list_command(args: argparse.Namespace) -> int:
    """Execute the list command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success).
    """
    console = Console()

    # Initialize CocoIndex
    cocoindex.init()

    indexes = list_indexes()

    if args.pretty:
        from rich.table import Table

        if not indexes:
            console.print("[dim]No indexes found[/dim]")
        else:
            table = Table(title="Indexes")
            table.add_column("Name", style="cyan")
            table.add_column("Table", style="dim")

            for idx in indexes:
                table.add_row(idx["name"], idx["table_name"])

            console.print(table)
    else:
        print(json.dumps(indexes, indent=2))

    return 0


def stats_command(args: argparse.Namespace) -> int:
    """Execute the stats command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    console = Console()

    # Initialize CocoIndex
    cocoindex.init()

    if args.index:
        # Stats for specific index
        try:
            stats = get_stats(args.index)
            stats["name"] = args.index
        except ValueError as e:
            if args.pretty:
                console.print(f"[bold red]Error:[/bold red] {e}")
            else:
                print(json.dumps({"error": str(e)}))
            return 1

        if args.pretty:
            from rich.table import Table

            table = Table(title=f"Index: {args.index}")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Files", str(stats["file_count"]))
            table.add_row("Chunks", str(stats["chunk_count"]))
            table.add_row("Size", stats["storage_size_pretty"])

            console.print(table)
        else:
            print(json.dumps(stats, indent=2))
    else:
        # Stats for all indexes
        indexes = list_indexes()
        all_stats = []

        for idx in indexes:
            try:
                stats = get_stats(idx["name"])
                stats["name"] = idx["name"]
                all_stats.append(stats)
            except ValueError:
                # Skip indexes that can't be queried
                continue

        if args.pretty:
            from rich.table import Table

            if not all_stats:
                console.print("[dim]No indexes found[/dim]")
            else:
                table = Table(title="Index Statistics")
                table.add_column("Name", style="cyan")
                table.add_column("Files", justify="right")
                table.add_column("Chunks", justify="right")
                table.add_column("Size", justify="right")

                for stats in all_stats:
                    table.add_row(
                        stats["name"],
                        str(stats["file_count"]),
                        str(stats["chunk_count"]),
                        stats["storage_size_pretty"],
                    )

                console.print(table)
        else:
            print(json.dumps(all_stats, indent=2))

    return 0


def clear_command(args: argparse.Namespace) -> int:
    """Execute the clear command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    console = Console()

    # Initialize CocoIndex
    cocoindex.init()

    index_name = args.index

    # Get stats first to validate existence and show what will be deleted
    try:
        stats = get_stats(index_name)
    except ValueError as e:
        if args.pretty:
            console.print(f"[bold red]Error:[/bold red] {e}")
        else:
            print(json.dumps({"error": str(e)}))
        return 1

    # Show confirmation prompt unless --force
    if not args.force:
        console.print(f"\nIndex '[cyan]{index_name}[/cyan]' contains:")
        console.print(f"  Files:  {stats['file_count']}")
        console.print(f"  Chunks: {stats['chunk_count']}")
        console.print(f"  Size:   {stats['storage_size_pretty']}")
        console.print()

        response = input(f"Delete index '{index_name}'? [y/N] ")
        if response.lower() != "y":
            console.print("Cancelled.")
            return 0

    # Perform deletion
    try:
        result = clear_index(index_name)
    except ValueError as e:
        if args.pretty:
            console.print(f"[bold red]Error:[/bold red] {e}")
        else:
            print(json.dumps({"error": str(e)}))
        return 1

    # Output result
    if args.pretty:
        console.print(f"[green]Index '{index_name}' deleted successfully[/green]")
    else:
        print(json.dumps(result, indent=2))

    return 0


def init_command(args: argparse.Namespace) -> int:
    """Execute the init command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    console = Console()
    config_path = Path.cwd() / "cocosearch.yaml"

    try:
        generate_config(config_path)
        console.print("[green]Created cocosearch.yaml[/green]")
        console.print("[dim]Edit this file to customize CocoSearch behavior.[/dim]")
        return 0
    except ConfigLoadError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return 1


def mcp_command(args: argparse.Namespace) -> int:
    """Start the MCP server.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, never reached as server runs until killed).
    """
    from cocosearch.mcp import run_server

    run_server()
    return 0  # Never reached, server runs until killed


def config_show_command(args: argparse.Namespace) -> int:
    """Execute the config show command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    from rich.table import Table

    console = Console()

    # Load config
    config_path = find_config_file()
    if config_path:
        try:
            project_config = load_project_config(config_path)
        except ConfigLoadError as e:
            console.print(f"[bold red]Configuration error:[/bold red]\n{e}")
            return 1
    else:
        project_config = CocoSearchConfig()

    # Create resolver
    resolver = ConfigResolver(project_config, config_path)

    # Build table
    table = Table(title="Configuration")
    table.add_column("KEY", style="cyan")
    table.add_column("VALUE", style="white")
    table.add_column("SOURCE", style="dim")

    # Get all field paths and resolve each
    for field_path in resolver.all_field_paths():
        env_var = config_key_to_env_var(field_path)
        value, source = resolver.resolve(field_path, cli_value=None, env_var=env_var)

        # Format value for display
        if value is None:
            value_str = "[dim]null[/dim]"
        elif isinstance(value, list):
            value_str = ", ".join(str(v) for v in value) if value else "[dim]empty[/dim]"
        else:
            value_str = str(value)

        table.add_row(field_path, value_str, source)

    console.print(table)
    return 0


def config_path_command(args: argparse.Namespace) -> int:
    """Execute the config path command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success).
    """
    console = Console()

    config_path = find_config_file()
    if config_path:
        console.print(str(config_path))
    else:
        console.print("No config file found")

    return 0


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
    add_config_arg(
        index_parser,
        "-n", "--name",
        config_key="indexName",
        help_text="Index name (default: derived from directory name)",
    )
    add_config_arg(
        index_parser,
        "-i", "--include",
        config_key="indexing.includePatterns",
        help_text="Additional file patterns to include (can be repeated)",
        action="append",
    )
    add_config_arg(
        index_parser,
        "-e", "--exclude",
        config_key="indexing.excludePatterns",
        help_text="Additional file patterns to exclude (can be repeated)",
        action="append",
    )
    index_parser.add_argument(
        "--no-gitignore",
        action="store_true",
        help="Disable .gitignore pattern respect",
    )

    # Search subcommand (also works as default action)
    search_parser = subparsers.add_parser(
        "search",
        help="Search indexed code (also works as default action)",
        description="Search for code using natural language queries.",
    )
    search_parser.add_argument(
        "query",
        nargs="?",  # Make optional (required unless --interactive)
        default=None,
        help="Natural language search query (not needed with --interactive)",
    )
    search_parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Enter interactive search mode",
    )
    add_config_arg(
        search_parser,
        "-n", "--index",
        config_key="indexName",
        help_text="Index name (default: auto-detect from cwd)",
    )
    add_config_arg(
        search_parser,
        "-l", "--limit",
        config_key="search.resultLimit",
        help_text="Maximum results (default: 10)",
        type=int,
        default=10,
    )
    search_parser.add_argument(
        "--lang",
        help="Filter by language (e.g., python, typescript, hcl, dockerfile, bash). Aliases: terraform=hcl, shell/sh=bash",
    )
    add_config_arg(
        search_parser,
        "--min-score",
        config_key="search.minScore",
        help_text="Minimum similarity score 0-1 (default: 0.3)",
        type=float,
        default=0.3,
    )
    search_parser.add_argument(
        "-c", "--context",
        type=int,
        default=5,
        help="Context lines to include (default: 5)",
    )
    search_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Human-readable output (default: JSON)",
    )

    # List subcommand
    list_parser = subparsers.add_parser(
        "list",
        help="List all indexes",
        description="Show all available indexes.",
    )
    list_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Human-readable output (default: JSON)",
    )

    # Stats subcommand
    stats_parser = subparsers.add_parser(
        "stats",
        help="Show index statistics",
        description="Display statistics for one or all indexes.",
    )
    stats_parser.add_argument(
        "index",
        nargs="?",
        default=None,
        help="Index name (if omitted, show stats for all indexes)",
    )
    stats_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Human-readable output (default: JSON)",
    )

    # Clear subcommand
    clear_parser = subparsers.add_parser(
        "clear",
        help="Delete an index",
        description="Delete an index and all its data. Prompts for confirmation by default.",
    )
    clear_parser.add_argument(
        "index",
        help="Index name to delete",
    )
    clear_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt",
    )
    clear_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Human-readable output (default: JSON)",
    )

    # Init subcommand
    subparsers.add_parser(
        "init",
        help="Create a cocosearch.yaml configuration file",
        description="Generate a starter configuration file with all options documented.",
    )

    # MCP subcommand
    subparsers.add_parser(
        "mcp",
        help="Start MCP server for LLM integration",
        description="Start the Model Context Protocol server for use with Claude and other LLM clients.",
    )

    # Config subcommand
    config_parser = subparsers.add_parser(
        "config",
        help="Configuration management",
        description="Inspect and manage CocoSearch configuration.",
    )
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    # Config show subcommand
    config_subparsers.add_parser(
        "show",
        help="Show effective configuration with sources",
        description="Display all configuration values and their sources (CLI, env, config file, or default).",
    )

    # Config path subcommand
    config_subparsers.add_parser(
        "path",
        help="Show config file location",
        description="Display the path to the config file, or indicate if none is found.",
    )

    # Known subcommands for routing
    known_subcommands = ("index", "search", "list", "stats", "clear", "init", "mcp", "config", "-h", "--help")

    # Handle default action (query without subcommand)
    # Check before parsing if first argument is not a known subcommand
    # Supports: `cocosearch "query"` or `cocosearch --interactive`
    if len(sys.argv) > 1 and sys.argv[1] not in known_subcommands:
        first_arg = sys.argv[1]
        # If it's a flag (like --interactive) or a query, insert "search"
        if first_arg.startswith("-") or not first_arg.startswith("-"):
            sys.argv.insert(1, "search")

    # Parse args
    args = parser.parse_args()

    if args.command == "index":
        sys.exit(index_command(args))
    elif args.command == "search":
        sys.exit(search_command(args))
    elif args.command == "list":
        sys.exit(list_command(args))
    elif args.command == "stats":
        sys.exit(stats_command(args))
    elif args.command == "clear":
        sys.exit(clear_command(args))
    elif args.command == "init":
        sys.exit(init_command(args))
    elif args.command == "mcp":
        sys.exit(mcp_command(args))
    elif args.command == "config":
        if args.config_command == "show":
            sys.exit(config_show_command(args))
        elif args.config_command == "path":
            sys.exit(config_path_command(args))
        else:
            parser.print_help()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
