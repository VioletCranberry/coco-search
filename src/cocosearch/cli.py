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
from typing import Any

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
from cocosearch.dashboard import run_terminal_dashboard
from cocosearch.indexer import IndexingConfig, load_config, run_index
from cocosearch.indexer.progress import IndexingProgress
from cocosearch.management import clear_index, derive_index_from_git, get_comprehensive_stats, get_language_stats, get_stats, list_indexes
from cocosearch.management import register_index_path
from cocosearch.search import search
from cocosearch.search.formatter import format_json, format_pretty
from cocosearch.search.query import DEVOPS_LANGUAGES, LANGUAGE_EXTENSIONS, SYMBOL_AWARE_LANGUAGES
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
    # Only override defaults if patterns are explicitly set in config
    config_kwargs: dict[str, Any] = {
        "chunk_size": project_config.indexing.chunkSize,
        "chunk_overlap": project_config.indexing.chunkOverlap,
    }
    if project_config.indexing.includePatterns:
        config_kwargs["include_patterns"] = project_config.indexing.includePatterns
    if project_config.indexing.excludePatterns:
        config_kwargs["exclude_patterns"] = project_config.indexing.excludePatterns
    config = IndexingConfig(**config_kwargs)

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

        # Register path-to-index mapping for collision detection
        try:
            register_index_path(index_name, codebase_path)
        except ValueError as collision_error:
            # Collision detected - show warning but indexing already succeeded
            console.print(f"[bold yellow]Warning:[/bold yellow] {collision_error}")
            console.print("[dim]Index was created but path mapping was not updated.[/dim]")

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

    # Determine context parameters
    context_before = args.before_context
    context_after = args.after_context
    if args.context is not None:
        context_before = context_before if context_before is not None else args.context
        context_after = context_after if context_after is not None else args.context
    smart_context = not args.no_smart

    # Handle interactive mode
    if args.interactive:
        # For interactive mode, use context value for backward compatibility
        interactive_context = args.context if args.context is not None else 5
        run_repl(
            index_name=index_name,
            limit=limit,
            context_lines=interactive_context,
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

    # Determine hybrid mode
    # args.hybrid is True if --hybrid specified, None otherwise (auto-detect)
    use_hybrid = True if getattr(args, "hybrid", None) else None

    # Get symbol filters from args
    symbol_type = getattr(args, "symbol_type", None)  # list[str] or None from action="append"
    symbol_name = getattr(args, "symbol_name", None)  # str or None

    # Get cache bypass flag
    no_cache = getattr(args, "no_cache", False)

    # Execute search
    try:
        results = search(
            query=query,
            index_name=index_name,
            limit=limit,
            min_score=min_score,
            language_filter=lang_filter,
            use_hybrid=use_hybrid,
            symbol_type=symbol_type,
            symbol_name=symbol_name,
            no_cache=no_cache,
        )
    except Exception as e:
        if args.pretty:
            console.print(f"[bold red]Error:[/bold red] {e}")
        else:
            print(json.dumps({"error": str(e)}))
        return 1

    # Output results
    if args.pretty:
        format_pretty(
            results,
            context_before=context_before,
            context_after=context_after,
            smart_context=smart_context,
            console=console,
        )
    else:
        print(format_json(
            results,
            context_before=context_before,
            context_after=context_after,
            smart_context=smart_context,
        ))

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


def print_warnings(warnings: list[str], console: Console) -> None:
    """Print warning banner if there are warnings.

    Args:
        warnings: List of warning messages.
        console: Rich console for output.
    """
    if not warnings:
        return
    from rich.panel import Panel

    warning_text = "\n".join(f"[yellow]! {w}[/yellow]" for w in warnings)
    console.print(Panel(
        warning_text,
        title="[bold yellow]Warnings[/bold yellow]",
        border_style="yellow"
    ))
    console.print()  # Blank line after


def format_language_table(languages: list[dict], console_width: int = 80) -> "Table":
    """Format language distribution table with Unicode bars.

    Args:
        languages: List of language stats dicts.
        console_width: Console width for bar sizing (default: 80).

    Returns:
        Rich Table with language distribution and Unicode bars.
    """
    from rich.table import Table
    from rich.bar import Bar

    table = Table(title="Language Distribution", show_header=True)
    table.add_column("Language", style="cyan", width=12)
    table.add_column("Files", justify="right", width=6)
    table.add_column("Chunks", justify="right", width=8)
    table.add_column("Distribution", width=30)

    max_chunks = max((l["chunk_count"] for l in languages), default=1)
    for lang in languages:
        ratio = lang["chunk_count"] / max_chunks if max_chunks > 0 else 0
        bar = Bar(size=30, begin=0, end=ratio * 30)
        table.add_row(
            lang["language"],
            str(lang["file_count"]),
            str(lang["chunk_count"]),
            bar
        )
    return table


def format_symbol_table(symbols: dict[str, int]) -> "Table | None":
    """Format symbol statistics table.

    Args:
        symbols: Dict mapping symbol types to counts.

    Returns:
        Rich Table with symbol statistics, or None if no symbols.
    """
    if not symbols:
        return None
    from rich.table import Table

    table = Table(title="Symbol Statistics")
    table.add_column("Type", style="magenta")
    table.add_column("Count", justify="right")
    for sym_type, count in sorted(symbols.items(), key=lambda x: -x[1]):
        table.add_row(sym_type, f"{count:,}")
    return table


def stats_command(args: argparse.Namespace) -> int:
    """Execute the stats command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    console = Console()

    # Validate --watch requires --live
    if args.watch and not args.live:
        console.print("[bold red]Error:[/bold red] --watch requires --live")
        return 1

    # Handle --live mode (terminal dashboard)
    if args.live:
        # Initialize CocoIndex
        cocoindex.init()

        # Dashboard requires a specific index
        if not args.index:
            # Auto-detect from cwd
            git_index = derive_index_from_git()
            if git_index:
                index_name = git_index
            else:
                index_name = derive_index_name(os.getcwd())
        else:
            index_name = args.index

        # Validate index exists before starting dashboard
        try:
            get_stats(index_name)  # Quick validation
        except ValueError as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            return 1

        # Run terminal dashboard
        run_terminal_dashboard(
            index_name=index_name,
            watch=args.watch,
            refresh_interval=args.refresh_interval,
        )
        return 0

    # Initialize CocoIndex
    cocoindex.init()

    # Determine output mode: visual is default, --json enables JSON output
    json_output = args.json

    # Determine which index(es) to show
    if args.all:
        # Show all indexes
        indexes = list_indexes()
        all_stats = []

        for idx in indexes:
            try:
                stats = get_comprehensive_stats(idx["name"], staleness_threshold=args.staleness_threshold)
                all_stats.append(stats)
            except ValueError:
                # Skip indexes that can't be queried
                continue

        if json_output:
            # JSON output for all indexes
            output = [s.to_dict() for s in all_stats]
            print(json.dumps(output, indent=2))
        else:
            # Pretty output for all indexes
            from rich.table import Table

            if not all_stats:
                console.print("[dim]No indexes found[/dim]")
            else:
                for i, stats in enumerate(all_stats):
                    if i > 0:
                        console.print()  # Blank line between indexes

                    # Show warnings first
                    print_warnings(stats.warnings, console)

                    # Summary header
                    console.print(f"[bold]Index:[/bold] {stats.name}")
                    console.print(f"[dim]Files: {stats.file_count:,} | Chunks: {stats.chunk_count:,} | Size: {stats.storage_size_pretty}[/dim]")

                    # Timestamps
                    if stats.created_at:
                        created_str = stats.created_at.strftime("%Y-%m-%d")
                        console.print(f"[dim]Created: {created_str}[/dim]")
                    if stats.updated_at:
                        updated_str = stats.updated_at.strftime("%Y-%m-%d")
                        days_ago = f"{stats.staleness_days} days ago" if stats.staleness_days >= 0 else "unknown"
                        console.print(f"[dim]Last Updated: {updated_str} ({days_ago})[/dim]")
                    console.print()

                    # Language distribution with bars
                    if stats.languages:
                        lang_table = format_language_table(stats.languages)
                        console.print(lang_table)

                    # Symbol statistics (verbose mode only)
                    if args.verbose and stats.symbols:
                        console.print()
                        symbol_table = format_symbol_table(stats.symbols)
                        if symbol_table:
                            console.print(symbol_table)

        return 0

    # Single index mode
    if args.index:
        index_name = args.index
    else:
        # Auto-detect from cwd (like search command)
        git_index = derive_index_from_git()
        if git_index:
            index_name = git_index
        else:
            index_name = derive_index_name(os.getcwd())

    # Get comprehensive stats for the index
    try:
        stats = get_comprehensive_stats(index_name, staleness_threshold=args.staleness_threshold)
    except ValueError as e:
        if json_output:
            print(json.dumps({"error": str(e)}))
        else:
            console.print(f"[bold red]Error:[/bold red] {e}")
        return 1

    if json_output:
        # JSON output
        print(json.dumps(stats.to_dict(), indent=2))
    else:
        # Pretty output with visual elements

        # Show warnings first
        print_warnings(stats.warnings, console)

        # Summary header
        console.print(f"\n[bold]Index:[/bold] {stats.name}")
        console.print(f"[dim]Files: {stats.file_count:,} | Chunks: {stats.chunk_count:,} | Size: {stats.storage_size_pretty}[/dim]")

        # Timestamps
        if stats.created_at:
            created_str = stats.created_at.strftime("%Y-%m-%d")
            console.print(f"[dim]Created: {created_str}[/dim]")
        if stats.updated_at:
            updated_str = stats.updated_at.strftime("%Y-%m-%d")
            days_ago = f"{stats.staleness_days} days ago" if stats.staleness_days >= 0 else "unknown"
            console.print(f"[dim]Last Updated: {updated_str} ({days_ago})[/dim]")
        console.print()

        # Language distribution with bars
        if stats.languages:
            lang_table = format_language_table(stats.languages)
            console.print(lang_table)

        # Symbol statistics (verbose mode only)
        if args.verbose and stats.symbols:
            console.print()
            symbol_table = format_symbol_table(stats.symbols)
            if symbol_table:
                console.print(symbol_table)
        elif args.verbose and not stats.symbols:
            console.print("\n[dim]No symbol statistics available (requires v1.7+ index with symbol extraction)[/dim]")

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


def languages_command(args: argparse.Namespace) -> int:
    """Execute the languages command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success).
    """
    console = Console()

    # Build language data from LANGUAGE_EXTENSIONS and DEVOPS_LANGUAGES
    # Combine all sources into unified list
    languages = []

    # Standard languages from LANGUAGE_EXTENSIONS
    for lang, exts in sorted(LANGUAGE_EXTENSIONS.items()):
        # Format display name
        if lang in ("sql", "xml", "css", "html", "json", "yaml", "toml", "dtd"):
            display_name = lang.upper()
        elif lang == "cpp":
            display_name = "C++"
        elif lang == "csharp":
            display_name = "C#"
        else:
            display_name = lang.title()

        languages.append({
            "name": display_name,
            "extensions": ", ".join(exts),
            "symbols": lang in SYMBOL_AWARE_LANGUAGES,
        })

    # DevOps languages
    devops_display = {"hcl": "HCL", "dockerfile": "Dockerfile", "bash": "Bash"}
    for lang in sorted(DEVOPS_LANGUAGES.keys()):
        ext_display = f".{lang}" if lang != "dockerfile" else "Dockerfile"
        languages.append({
            "name": devops_display.get(lang, lang.title()),
            "extensions": ext_display,
            "symbols": False,
        })

    if args.json:
        import json as json_module
        print(json_module.dumps(languages, indent=2))
    else:
        from rich.table import Table

        table = Table(title="Supported Languages")
        table.add_column("Language", style="cyan", no_wrap=True)
        table.add_column("Extensions", style="dim")
        table.add_column("Symbols", justify="center")

        for lang in languages:
            symbol_mark = "[green]✓[/green]" if lang["symbols"] else "[dim]✗[/dim]"
            table.add_row(lang["name"], lang["extensions"], symbol_mark)

        console.print(table)
        console.print("\n[dim]Symbol-aware languages support --symbol-type and --symbol-name filtering.[/dim]")

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
        Exit code (0 for success, 1 for error).
    """
    from cocosearch.mcp import run_server

    # Resolve transport: CLI > env > default
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")

    # Validate transport
    valid_transports = ("stdio", "sse", "http")
    if transport not in valid_transports:
        print(f"Error: Invalid transport '{transport}'. Valid options: {', '.join(valid_transports)}", file=sys.stderr)
        return 1

    # Resolve port: CLI > env > default
    if args.port is not None:
        port = args.port
    else:
        port_env = os.getenv("COCOSEARCH_MCP_PORT", "3000")
        try:
            port = int(port_env)
        except ValueError:
            print(f"Error: Invalid port value in COCOSEARCH_MCP_PORT: '{port_env}'", file=sys.stderr)
            return 1

    # Pass project path via environment variable if --project-from-cwd is set
    if args.project_from_cwd:
        project_path = os.getcwd()
        os.environ["COCOSEARCH_PROJECT_PATH"] = project_path

    try:
        run_server(transport=transport, host="0.0.0.0", port=port)
        return 0
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"Error: Port {port} is already in use", file=sys.stderr)
            return 1
        raise


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


def config_check_command(args: argparse.Namespace) -> int:
    """Execute the config check command.

    Validates environment variables without connecting to services.
    Lightweight check for troubleshooting and CI/CD validation.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for valid, 1 for errors).
    """
    from rich.table import Table

    from cocosearch.config import mask_password, validate_required_env_vars, get_database_url, DEFAULT_DATABASE_URL

    console = Console()

    # Validate required variables
    errors = validate_required_env_vars()

    if errors:
        console.print("[bold red]Environment configuration errors:[/bold red]")
        for error in errors:
            console.print(f"  - {error.hint}")
        console.print("\n[dim]See .env.example for configuration format.[/dim]")
        return 1

    # Show success + current values
    console.print("[green]Environment configuration is valid[/green]\n")

    # Display current environment variables
    table = Table(title="Environment Variables")
    table.add_column("Variable", style="cyan")
    table.add_column("Value", style="white")
    table.add_column("Source", style="dim")

    # DATABASE_URL (has default)
    db_url_env = os.getenv("COCOSEARCH_DATABASE_URL")
    if db_url_env:
        table.add_row("COCOSEARCH_DATABASE_URL", mask_password(db_url_env), "environment")
    else:
        table.add_row("COCOSEARCH_DATABASE_URL", mask_password(DEFAULT_DATABASE_URL), "default")

    # OLLAMA_URL (optional with default)
    ollama_url = os.getenv("COCOSEARCH_OLLAMA_URL")
    if ollama_url:
        table.add_row("COCOSEARCH_OLLAMA_URL", ollama_url, "environment")
    else:
        table.add_row(
            "COCOSEARCH_OLLAMA_URL",
            "http://localhost:11434",
            "default"
        )

    console.print(table)
    return 0


def serve_dashboard_command(args: argparse.Namespace) -> int:
    """Execute the serve-dashboard command.

    Starts a minimal HTTP server serving the web dashboard and API.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    from cocosearch.mcp import run_server

    console = Console()
    console.print("[bold]Starting CocoSearch Dashboard[/bold]")
    console.print(f"  Dashboard: http://{args.host}:{args.port}/dashboard")
    console.print(f"  API: http://{args.host}:{args.port}/api/stats")
    console.print()
    console.print("[dim]Press Ctrl+C to stop[/dim]")

    # Use MCP server with SSE transport (provides HTTP routes)
    try:
        run_server(transport="sse", host=args.host, port=args.port)
        return 0
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard stopped[/dim]")
        return 0
    except OSError as e:
        if "Address already in use" in str(e):
            console.print(f"[bold red]Error:[/bold red] Port {args.port} is already in use")
            return 1
        raise


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
        "-A", "--after-context",
        type=int,
        default=None,
        metavar="NUM",
        help="Show NUM lines after each match (overrides smart expansion)",
    )
    search_parser.add_argument(
        "-B", "--before-context",
        type=int,
        default=None,
        metavar="NUM",
        help="Show NUM lines before each match (overrides smart expansion)",
    )
    search_parser.add_argument(
        "-C", "--context",
        type=int,
        default=None,
        metavar="NUM",
        help="Show NUM lines before and after each match (overrides smart expansion)",
    )
    search_parser.add_argument(
        "--no-smart",
        action="store_true",
        help="Disable smart context expansion (use exact line counts instead of function boundaries)",
    )
    search_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Human-readable output (default: JSON)",
    )
    search_parser.add_argument(
        "--hybrid",
        action="store_true",
        default=None,
        help="Enable hybrid search (vector + keyword). Auto-enabled for identifier patterns (camelCase/snake_case).",
    )
    search_parser.add_argument(
        "--symbol-type",
        help="Filter by symbol type. Options: function, class, method, interface. "
             "Can be specified multiple times for OR filtering (e.g., --symbol-type function --symbol-type method).",
        action="append",
        dest="symbol_type",
    )
    search_parser.add_argument(
        "--symbol-name",
        help="Filter by symbol name pattern (glob). "
             "Examples: 'get*', 'User*Service', '*Handler'. Case-insensitive matching.",
    )
    search_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass query cache (force fresh search)",
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
        help="Index name (default: auto-detect from cwd, or use --all for all indexes)",
    )
    stats_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Human-readable output (default: JSON)",
    )
    stats_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show symbol type breakdown (verbose mode)",
    )
    stats_parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON (replaces --pretty inversion)",
    )
    stats_parser.add_argument(
        "--all",
        action="store_true",
        help="Show stats for all indexed projects",
    )
    stats_parser.add_argument(
        "--staleness-threshold",
        type=int,
        default=7,
        help="Days before staleness warning (default: 7)",
    )
    stats_parser.add_argument(
        "--live",
        action="store_true",
        help="Show terminal dashboard (multi-pane layout with bar charts)",
    )
    stats_parser.add_argument(
        "--watch",
        action="store_true",
        help="Auto-refresh terminal dashboard (requires --live)",
    )
    stats_parser.add_argument(
        "--refresh-interval",
        type=float,
        default=1.0,
        metavar="SECONDS",
        help="Refresh interval for --watch mode (default: 1.0)",
    )

    # Languages subcommand
    languages_parser = subparsers.add_parser(
        "languages",
        help="List supported languages",
        description="Show all languages CocoSearch can index with file extensions and symbol support.",
    )
    languages_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON (default: table)",
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
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="Start MCP server for LLM integration",
        description="Start the Model Context Protocol server for use with Claude and other LLM clients.",
    )
    mcp_parser.add_argument(
        "--transport", "-t",
        choices=["stdio", "sse", "http"],
        default=None,
        help="Transport protocol (default: stdio). [env: MCP_TRANSPORT]",
    )
    mcp_parser.add_argument(
        "--port", "-p",
        type=int,
        default=None,
        help="Port for SSE/HTTP transports (default: 3000). [env: COCOSEARCH_MCP_PORT]",
    )
    mcp_parser.add_argument(
        "--project-from-cwd",
        action="store_true",
        default=False,
        help="Auto-detect project from current working directory. Required for user-scope MCP registration.",
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

    # Config check subcommand
    config_subparsers.add_parser(
        "check",
        help="Validate environment variables",
        description="Validate required environment variables without connecting to services.",
    )

    # Serve-dashboard subcommand
    serve_parser = subparsers.add_parser(
        "serve-dashboard",
        help="Start standalone web dashboard server",
        description="Start a web server to view the stats dashboard in a browser.",
    )
    serve_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Port to serve dashboard on (default: 8080)",
    )
    serve_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )

    # Known subcommands for routing
    known_subcommands = ("index", "search", "list", "stats", "languages", "clear", "init", "mcp", "config", "serve-dashboard", "-h", "--help")

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

    # Ensure database URL default and CocoIndex bridge are set early
    from cocosearch.config.env_validation import get_database_url
    get_database_url()

    if args.command == "index":
        sys.exit(index_command(args))
    elif args.command == "search":
        sys.exit(search_command(args))
    elif args.command == "list":
        sys.exit(list_command(args))
    elif args.command == "stats":
        sys.exit(stats_command(args))
    elif args.command == "languages":
        sys.exit(languages_command(args))
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
        elif args.config_command == "check":
            sys.exit(config_check_command(args))
        else:
            parser.print_help()
            sys.exit(1)
    elif args.command == "serve-dashboard":
        sys.exit(serve_dashboard_command(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
