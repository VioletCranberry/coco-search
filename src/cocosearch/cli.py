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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.table import Table

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
from cocosearch.indexer import IndexingConfig, run_index
from cocosearch.indexer.progress import IndexingProgress
from cocosearch.management import (
    clear_index,
    derive_index_from_git,
    get_comprehensive_stats,
    get_stats,
    list_indexes,
)
from cocosearch.management import (
    ensure_metadata_table,
    register_index_path,
    set_index_status,
)
from cocosearch.search import search
from cocosearch.search.formatter import format_json, format_pretty
from cocosearch.search.query import (
    LANGUAGE_EXTENSIONS,
    SYMBOL_AWARE_LANGUAGES,
)
from cocosearch.search.repl import run_repl


def add_config_arg(
    parser: argparse.ArgumentParser, *flags, config_key: str, help_text: str, **kwargs
) -> None:
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


def _resolve_index_name(
    resolver: ConfigResolver,
    cli_value: str | None,
    fallback_path: str | None = None,
) -> tuple[str, str]:
    """Resolve index name with CLI > env > config > git > path fallback.

    Args:
        resolver: Config resolver instance.
        cli_value: Value from CLI flag (--name or --index).
        fallback_path: Path to derive name from if all else fails.
            Defaults to os.getcwd().

    Returns:
        Tuple of (index_name, source) where source describes where
        the name came from.
    """
    name, source = resolver.resolve(
        "indexName", cli_value=cli_value, env_var="COCOSEARCH_INDEX_NAME"
    )
    if name:
        return name, source
    # Auto-detect: try git root first, fall back to path
    git_index = derive_index_from_git()
    if git_index:
        return git_index, "git"
    return derive_index_name(fallback_path or os.getcwd()), "derived"


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
        console.print(
            f"[bold red]Error:[/bold red] Path does not exist or is not a directory: {args.path}"
        )
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

    # Resolve index name with CLI > env > config > git > path fallback
    index_name, index_source = _resolve_index_name(
        resolver, cli_value=args.name, fallback_path=codebase_path
    )
    if index_source == "derived":
        console.print(f"[dim]Using derived index name: {index_name}[/dim]")
    elif index_source not in ("default", "CLI flag"):
        console.print(f"[dim]Using index name: {index_name} ({index_source})[/dim]")

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

    # Detect git branch/commit for metadata tracking
    from cocosearch.management.git import (
        get_current_branch,
        get_commit_hash,
        get_branch_commit_count,
    )

    branch = get_current_branch(codebase_path)
    commit_hash = get_commit_hash(codebase_path)
    branch_commit_count = get_branch_commit_count(codebase_path)
    if branch:
        branch_info = f"{branch}"
        if commit_hash:
            branch_info += f" ({commit_hash})"
        console.print(f"[dim]Branch: {branch_info}[/dim]")

    # Set status to 'indexing' before starting (best-effort)
    try:
        ensure_metadata_table()
        register_index_path(
            index_name,
            codebase_path,
            branch=branch,
            commit_hash=commit_hash,
            branch_commit_count=branch_commit_count,
        )
        set_index_status(index_name, "indexing")
    except Exception:
        pass  # Best-effort — don't block indexing on metadata failures

    # Run indexing with progress display
    indexing_failed = False
    try:
        with IndexingProgress(console) as progress:
            if args.fresh:
                console.print(f"[dim]Fresh index requested for '{index_name}'[/dim]")
            progress.start_indexing(codebase_path)

            # Run the indexing flow
            # Note: respect_gitignore is handled internally by run_index
            # based on whether --no-gitignore was passed (we pass this via config)
            update_info = run_index(
                index_name=index_name,
                codebase_path=codebase_path,
                config=config,
                respect_gitignore=not args.no_gitignore,
                fresh=args.fresh,
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
            register_index_path(
                index_name, codebase_path, branch=branch, commit_hash=commit_hash
            )
        except ValueError as collision_error:
            # Collision detected - show warning but indexing already succeeded
            console.print(f"[bold yellow]Warning:[/bold yellow] {collision_error}")
            console.print(
                "[dim]Index was created but path mapping was not updated.[/dim]"
            )

        return 0

    except Exception as e:
        indexing_failed = True
        console.print(f"[bold red]Error:[/bold red] Indexing failed: {e}")
        return 1

    finally:
        try:
            set_index_status(index_name, "error" if indexing_failed else "indexed")
        except Exception:
            pass


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

    # Initialize CocoIndex (required for embedding generation)
    try:
        cocoindex.init()
    except Exception:
        console.print("[dim]No indexes found. Index a codebase first:[/dim]")
        console.print("  cocosearch index <path>")
        return 1

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

    # Resolve index name with CLI > env > config > git > cwd fallback
    index_name, _ = _resolve_index_name(resolver, cli_value=args.index)

    # Resolve search settings with precedence
    limit, _ = resolver.resolve(
        "search.resultLimit",
        cli_value=args.limit
        if args.limit != 10
        else None,  # Only use CLI if not default
        env_var="COCOSEARCH_SEARCH_RESULT_LIMIT",
    )
    min_score, _ = resolver.resolve(
        "search.minScore",
        cli_value=args.min_score
        if args.min_score != 0.3
        else None,  # Only use CLI if not default
        env_var="COCOSEARCH_SEARCH_MIN_SCORE",
    )

    # Always print "Using index:" hint (per CONTEXT.md requirement)
    if args.pretty or args.interactive:
        console.print(f"[dim]Using index: {index_name}[/dim]")
    else:
        # For JSON mode, print to stderr to keep stdout clean
        import sys as _sys

        print(f"Using index: {index_name}", file=_sys.stderr)

    # Check for branch staleness and warn if needed
    if args.pretty or args.interactive:
        try:
            from cocosearch.management.stats import check_branch_staleness

            staleness = check_branch_staleness(index_name)
            if staleness.get("branch_changed") or staleness.get("commits_changed"):
                from rich.panel import Panel

                indexed_branch = staleness.get("indexed_branch", "unknown")
                indexed_commit = staleness.get("indexed_commit", "")
                current_branch = staleness.get("current_branch", "unknown")
                current_commit = staleness.get("current_commit", "")

                indexed_ref = f"'{indexed_branch}'"
                if indexed_commit:
                    indexed_ref += f" ({indexed_commit})"
                current_ref = f"'{current_branch}'"
                if current_commit:
                    current_ref += f" ({current_commit})"

                commits_behind = staleness.get("commits_behind")
                behind_part = ""
                if commits_behind is not None and commits_behind > 0:
                    behind_part = f" {commits_behind} commits behind."
                warning_msg = (
                    f"Index built from {indexed_ref}, "
                    f"current branch is {current_ref}."
                    f"{behind_part} "
                    f"Results may be stale."
                )
                console.print(
                    Panel(
                        f"[yellow]{warning_msg}[/yellow]",
                        title="[bold yellow]Warning[/bold yellow]",
                        border_style="yellow",
                    )
                )
        except Exception:
            pass  # Best-effort — don't block search on staleness check

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
        console.print(
            "[bold red]Error:[/bold red] Query required (use --interactive for REPL mode)"
        )
        return 1

    # Parse query for inline filters
    query, inline_lang = parse_query_filters(args.query)

    # CLI --lang overrides inline lang:
    lang_filter = args.lang or inline_lang

    # Determine hybrid mode
    # args.hybrid is True if --hybrid specified, None otherwise (auto-detect)
    use_hybrid = True if getattr(args, "hybrid", None) else None

    # Get symbol filters from args
    symbol_type = getattr(
        args, "symbol_type", None
    )  # list[str] or None from action="append"
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
        print(
            format_json(
                results,
                context_before=context_before,
                context_after=context_after,
                smart_context=smart_context,
            )
        )

    return 0


def list_command(args: argparse.Namespace) -> int:
    """Execute the list command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success).
    """
    console = Console()

    try:
        indexes = list_indexes()
    except Exception:
        # Database not reachable or not set up
        console.print("[dim]No indexes found. Index a codebase first:[/dim]")
        console.print("  cocosearch index <path>")
        return 0

    # Fetch metadata for each index (best-effort)
    from cocosearch.management.metadata import get_index_metadata

    metadata_map: dict[str, dict] = {}
    for idx in indexes:
        try:
            meta = get_index_metadata(idx["name"])
            if meta:
                metadata_map[idx["name"]] = meta
        except Exception:
            pass

    if args.pretty:
        from rich.table import Table

        if not indexes:
            console.print("[dim]No indexes found[/dim]")
        else:
            table = Table(title="Indexes")
            table.add_column("Name", style="cyan")
            table.add_column("Table", style="dim")
            table.add_column("Branch", style="green")
            table.add_column("Status", style="dim")

            for idx in indexes:
                meta = metadata_map.get(idx["name"])
                branch_display = "-"
                status_display = "-"
                if meta:
                    if meta.get("branch"):
                        branch_display = meta["branch"]
                        if meta.get("commit_hash"):
                            branch_display += f" ({meta['commit_hash']})"
                        # Compact git status indicator (best-effort)
                        try:
                            from cocosearch.management.git import (
                                get_commit_hash,
                                get_commits_behind,
                            )

                            check_path = meta.get("canonical_path")
                            indexed_commit = meta.get("commit_hash")
                            if check_path and indexed_commit:
                                current = get_commit_hash(check_path)
                                if current and current == indexed_commit:
                                    branch_display += " \u2713"
                                elif current and current != indexed_commit:
                                    behind = get_commits_behind(
                                        check_path, indexed_commit
                                    )
                                    if behind is not None and behind > 0:
                                        branch_display += f" \u2193{behind}"
                                    else:
                                        branch_display += " \u2193"
                        except Exception:
                            pass
                    status_display = (meta.get("status") or "-").title()
                table.add_row(
                    idx["name"], idx["table_name"], branch_display, status_display
                )

            console.print(table)
    else:
        # Enrich JSON output with metadata
        for idx in indexes:
            meta = metadata_map.get(idx["name"])
            if meta:
                idx["branch"] = meta.get("branch")
                idx["commit_hash"] = meta.get("commit_hash")
                idx["status"] = meta.get("status")
        print(json.dumps(indexes, indent=2))

    return 0


def _format_branch_display(stats) -> str:
    """Format enriched branch display for stats output.

    Returns string like:
        main (abc1234) · up to date · 1,234 commits
        main (abc1234) · 5 commits behind · 1,234 commits
    """
    parts = [stats.branch]
    if stats.commit_hash:
        parts[0] += f" ({stats.commit_hash})"

    if stats.commits_behind is not None:
        if stats.commits_behind == 0:
            parts.append("up to date")
        else:
            parts.append(f"{stats.commits_behind} commits behind")

    if stats.branch_commit_count is not None:
        parts.append(f"{stats.branch_commit_count:,} commits")

    return " · ".join(parts)


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
    console.print(
        Panel(
            warning_text,
            title="[bold yellow]Warnings[/bold yellow]",
            border_style="yellow",
        )
    )
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

    max_chunks = max((lang["chunk_count"] for lang in languages), default=1)
    for lang in languages:
        ratio = lang["chunk_count"] / max_chunks if max_chunks > 0 else 0
        bar = Bar(size=30, begin=0, end=ratio * 30)
        table.add_row(
            lang["language"], str(lang["file_count"]), str(lang["chunk_count"]), bar
        )
    return table


def format_grammar_table(grammars: list[dict]) -> "Table":
    """Format grammar distribution table.

    Args:
        grammars: List of grammar stats dicts from get_grammar_stats().

    Returns:
        Rich Table with grammar distribution.
    """
    from rich.table import Table

    table = Table(title="Grammar Distribution", show_header=True)
    table.add_column("Grammar", style="cyan", width=20)
    table.add_column("Base Language", style="dim", width=14)
    table.add_column("Files", justify="right", width=6)
    table.add_column("Chunks", justify="right", width=8)
    table.add_column("Recognition %", justify="right", width=14)

    for g in grammars:
        pct = g.get("recognition_pct", 0.0)
        pct_style = "green" if pct >= 90 else "yellow" if pct >= 70 else "red"
        table.add_row(
            g["grammar_name"],
            g["base_language"],
            str(g["file_count"]),
            str(g["chunk_count"]),
            f"[{pct_style}]{pct}%[/{pct_style}]",
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


def format_parse_health(parse_stats: dict, console: Console) -> None:
    """Display parse health summary and per-language breakdown.

    Shows a color-coded summary line (green >= 95%, yellow >= 80%, red < 80%)
    followed by a per-language table with ok/partial/error/no_grammar columns.

    Args:
        parse_stats: Parse stats dict from get_parse_stats().
        console: Rich console for output.
    """
    if not parse_stats:
        return

    pct = parse_stats.get("parse_health_pct", 100.0)
    total = parse_stats.get("total_files", 0)
    ok = parse_stats.get("total_ok", 0)

    # Summary line with color coding
    color = "green" if pct >= 95 else "yellow" if pct >= 80 else "red"
    console.print(
        f"\n[{color}]Parse health: {pct}% clean ({ok}/{total} files)[/{color}]"
    )

    # Per-language table
    from rich.table import Table

    table = Table(title="Parse Status by Language")
    table.add_column("Language", style="cyan")
    table.add_column("Files", justify="right")
    table.add_column("OK", justify="right", style="green")
    table.add_column("Partial", justify="right", style="yellow")
    table.add_column("Error", justify="right", style="red")
    table.add_column("No Grammar", justify="right", style="dim")

    by_language = parse_stats.get("by_language", {})
    # Tracked languages first (by file count desc), then skipped
    tracked = sorted(
        [(la, c) for la, c in by_language.items() if not c.get("skipped")],
        key=lambda x: -x[1]["files"],
    )
    skipped = sorted(
        [(la, c) for la, c in by_language.items() if c.get("skipped")],
        key=lambda x: -x[1]["files"],
    )
    for lang, counts in tracked:
        table.add_row(
            lang,
            str(counts["files"]),
            str(counts["ok"]),
            str(counts["partial"]),
            str(counts["error"]),
            str(counts["no_grammar"]),
        )
    for lang, counts in skipped:
        table.add_row(
            lang,
            str(counts["files"]),
            "[dim]-[/dim]",
            "[dim]-[/dim]",
            "[dim]-[/dim]",
            "[dim]-[/dim]",
            style="dim",
        )
    console.print(table)


def format_parse_failures(failures: list[dict], console: Console) -> None:
    """Display individual file parse failure details.

    Shows a table of files that had non-ok parse status with their
    language, status, and error message.

    Args:
        failures: List of failure dicts from get_parse_failures().
        console: Rich console for output.
    """
    if not failures:
        console.print("\n[dim]No parse failures found[/dim]")
        return

    from rich.table import Table

    table = Table(title="Parse Failures")
    table.add_column("File", style="white", no_wrap=True)
    table.add_column("Language", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Error", style="red", max_width=60)

    for f in failures:
        status_style = (
            "red"
            if f["parse_status"] == "error"
            else "yellow"
            if f["parse_status"] == "partial"
            else "dim"
        )
        table.add_row(
            f["file_path"],
            f["language"],
            f"[{status_style}]{f['parse_status']}[/{status_style}]",
            f.get("error_message") or "",
        )
    console.print(table)


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
        try:
            cocoindex.init()
        except Exception:
            console.print("[dim]No indexes found. Index a codebase first:[/dim]")
            console.print("  cocosearch index <path>")
            return 1

        # Resolve index name with config precedence (positional > env > config > auto)
        config_path = find_config_file()
        if config_path:
            try:
                project_config = load_project_config(config_path)
            except ConfigLoadError:
                project_config = CocoSearchConfig()
        else:
            project_config = CocoSearchConfig()
        resolver = ConfigResolver(project_config, config_path)
        index_name, _ = _resolve_index_name(resolver, cli_value=args.index)

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

    # Initialize CocoIndex (optional for stats — own pool used for queries)
    try:
        cocoindex.init()
    except Exception:
        pass  # Fresh database — stats queries use CocoSearch's own pool

    # Determine output mode: visual is default, --json enables JSON output
    json_output = args.json

    # Determine which index(es) to show
    if args.all:
        # Show all indexes
        indexes = list_indexes()
        all_stats = []

        for idx in indexes:
            try:
                stats = get_comprehensive_stats(
                    idx["name"], staleness_threshold=args.staleness_threshold
                )
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
                    if stats.source_path:
                        console.print(f"[dim]Source: {stats.source_path}[/dim]")
                    if stats.branch:
                        branch_info = _format_branch_display(stats)
                        console.print(f"[dim]Branch: {branch_info}[/dim]")
                    if stats.status:
                        if stats.status == "indexing":
                            console.print("[yellow]Status: Indexing...[/yellow]")
                        else:
                            console.print(f"[dim]Status: {stats.status.title()}[/dim]")
                    console.print(
                        f"[dim]Files: {stats.file_count:,} | Chunks: {stats.chunk_count:,} | Size: {stats.storage_size_pretty}[/dim]"
                    )

                    # Timestamps
                    if stats.created_at:
                        created_str = stats.created_at.strftime("%Y-%m-%d %H:%M")
                        console.print(f"[dim]Created: {created_str}[/dim]")
                    if stats.updated_at:
                        updated_str = stats.updated_at.strftime("%Y-%m-%d %H:%M")
                        days_ago = (
                            f"{stats.staleness_days} days ago"
                            if stats.staleness_days >= 0
                            else "unknown"
                        )
                        console.print(
                            f"[dim]Last Updated: {updated_str} ({days_ago})[/dim]"
                        )
                    console.print()

                    # Language distribution with bars
                    if stats.languages:
                        lang_table = format_language_table(stats.languages)
                        console.print(lang_table)

                    # Grammar distribution
                    if stats.grammars:
                        console.print()
                        grammar_table = format_grammar_table(stats.grammars)
                        console.print(grammar_table)

                    # Symbol statistics
                    if stats.symbols:
                        console.print()
                        symbol_table = format_symbol_table(stats.symbols)
                        if symbol_table:
                            console.print(symbol_table)

                    # Parse health
                    if stats.parse_stats:
                        format_parse_health(stats.parse_stats, console)

        return 0

    # Single index mode — resolve with config precedence (positional > env > config > auto)
    config_path = find_config_file()
    if config_path:
        try:
            project_config = load_project_config(config_path)
        except ConfigLoadError:
            project_config = CocoSearchConfig()
    else:
        project_config = CocoSearchConfig()
    resolver = ConfigResolver(project_config, config_path)
    index_name, _ = _resolve_index_name(resolver, cli_value=args.index)

    # Get comprehensive stats for the index
    try:
        stats = get_comprehensive_stats(
            index_name, staleness_threshold=args.staleness_threshold
        )
    except ValueError as e:
        if json_output:
            print(json.dumps({"error": str(e)}))
        else:
            console.print(f"[bold red]Error:[/bold red] {e}")
        return 1

    if json_output:
        # JSON output
        data = stats.to_dict()
        if args.show_failures:
            from cocosearch.management.stats import get_parse_failures

            data["parse_failures"] = get_parse_failures(index_name)
        print(json.dumps(data, indent=2))
    else:
        # Pretty output with visual elements

        # Show warnings first
        print_warnings(stats.warnings, console)

        # Summary header
        console.print(f"\n[bold]Index:[/bold] {stats.name}")
        if stats.source_path:
            console.print(f"[dim]Source: {stats.source_path}[/dim]")
        if stats.branch:
            branch_info = _format_branch_display(stats)
            console.print(f"[dim]Branch: {branch_info}[/dim]")
        if stats.status:
            if stats.status == "indexing":
                console.print("[yellow]Status: Indexing...[/yellow]")
            else:
                console.print(f"[dim]Status: {stats.status.title()}[/dim]")
        console.print(
            f"[dim]Files: {stats.file_count:,} | Chunks: {stats.chunk_count:,} | Size: {stats.storage_size_pretty}[/dim]"
        )

        # Timestamps
        if stats.created_at:
            created_str = stats.created_at.strftime("%Y-%m-%d %H:%M")
            console.print(f"[dim]Created: {created_str}[/dim]")
        if stats.updated_at:
            updated_str = stats.updated_at.strftime("%Y-%m-%d %H:%M")
            days_ago = (
                f"{stats.staleness_days} days ago"
                if stats.staleness_days >= 0
                else "unknown"
            )
            console.print(f"[dim]Last Updated: {updated_str} ({days_ago})[/dim]")
        console.print()

        # Language distribution with bars
        if stats.languages:
            lang_table = format_language_table(stats.languages)
            console.print(lang_table)

        # Grammar distribution
        if stats.grammars:
            console.print()
            grammar_table = format_grammar_table(stats.grammars)
            console.print(grammar_table)

        # Symbol statistics
        if stats.symbols:
            console.print()
            symbol_table = format_symbol_table(stats.symbols)
            if symbol_table:
                console.print(symbol_table)

        # Parse health (always shown if available)
        if stats.parse_stats:
            format_parse_health(stats.parse_stats, console)

        # Parse failure details (only with --show-failures flag)
        if args.show_failures and stats.parse_stats:
            from cocosearch.management.stats import get_parse_failures

            failures = get_parse_failures(index_name)
            format_parse_failures(failures, console)
        elif args.show_failures and not stats.parse_stats:
            console.print(
                "\n[dim]No parse statistics available (requires re-indexing with v1.10+)[/dim]"
            )

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
    try:
        cocoindex.init()
    except Exception:
        console.print("[dim]No indexes found. Nothing to clear.[/dim]")
        return 0

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

    # Build language data from LANGUAGE_EXTENSIONS and handler registry
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

        languages.append(
            {
                "name": display_name,
                "extensions": ", ".join(exts),
                "symbols": lang in SYMBOL_AWARE_LANGUAGES,
            }
        )

    # Handler languages (derived from handler registry)
    from cocosearch.handlers import get_registered_handlers

    display_names = {"hcl": "HCL", "dockerfile": "Dockerfile", "bash": "Bash"}
    display_exts = {"dockerfile": "Dockerfile"}
    for handler in sorted(
        get_registered_handlers(), key=lambda h: h.SEPARATOR_SPEC.language_name
    ):
        lang = handler.SEPARATOR_SPEC.language_name
        languages.append(
            {
                "name": display_names.get(lang, lang.title()),
                "extensions": display_exts.get(lang, ", ".join(handler.EXTENSIONS)),
                "symbols": lang in SYMBOL_AWARE_LANGUAGES,
            }
        )

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
        console.print(
            "\n[dim]Symbol-aware languages support --symbol-type and --symbol-name filtering.[/dim]"
        )

    return 0


def grammars_command(args: argparse.Namespace) -> int:
    """Execute the grammars command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success).
    """
    console = Console()

    from cocosearch.handlers import get_registered_grammars

    grammars = []
    for handler in sorted(get_registered_grammars(), key=lambda h: h.GRAMMAR_NAME):
        grammars.append(
            {
                "name": handler.GRAMMAR_NAME,
                "base_language": handler.BASE_LANGUAGE,
                "path_patterns": handler.PATH_PATTERNS,
            }
        )

    if args.json:
        import json as json_module

        print(json_module.dumps(grammars, indent=2))
    else:
        from rich.table import Table

        table = Table(title="Supported Grammars")
        table.add_column("Grammar", style="cyan", no_wrap=True)
        table.add_column("File Format", style="dim")
        table.add_column("Path Patterns", style="dim")

        for g in grammars:
            table.add_row(
                g["name"],
                g["base_language"],
                ", ".join(g["path_patterns"]),
            )

        console.print(table)
        console.print(
            "\n[dim]Grammars provide domain-specific chunking for specific file formats.[/dim]"
        )

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
        print(
            f"Error: Invalid transport '{transport}'. Valid options: {', '.join(valid_transports)}",
            file=sys.stderr,
        )
        return 1

    # Resolve port: CLI > env > default
    if args.port is not None:
        port = args.port
    else:
        port_env = os.getenv("COCOSEARCH_MCP_PORT", "3000")
        try:
            port = int(port_env)
        except ValueError:
            print(
                f"Error: Invalid port value in COCOSEARCH_MCP_PORT: '{port_env}'",
                file=sys.stderr,
            )
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
            value_str = (
                ", ".join(str(v) for v in value) if value else "[dim]empty[/dim]"
            )
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

    Validates environment variables and checks connectivity to
    PostgreSQL, Ollama, and the embedding model.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 if all checks pass, 1 if any fail).
    """
    from rich.table import Table

    from cocosearch.config import (
        mask_password,
        validate_required_env_vars,
        DEFAULT_DATABASE_URL,
    )
    from cocosearch.indexer.preflight import (
        check_postgres,
        check_ollama,
        check_ollama_model,
        DEFAULT_OLLAMA_URL,
    )

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
    db_url = os.getenv("COCOSEARCH_DATABASE_URL", DEFAULT_DATABASE_URL)
    db_url_source = "environment" if os.getenv("COCOSEARCH_DATABASE_URL") else "default"
    table.add_row("COCOSEARCH_DATABASE_URL", mask_password(db_url), db_url_source)

    # OLLAMA_URL (optional with default)
    ollama_url = os.getenv("COCOSEARCH_OLLAMA_URL", DEFAULT_OLLAMA_URL)
    ollama_url_source = (
        "environment" if os.getenv("COCOSEARCH_OLLAMA_URL") else "default"
    )
    table.add_row("COCOSEARCH_OLLAMA_URL", ollama_url, ollama_url_source)

    # EMBEDDING_MODEL (optional with default)
    embedding_model = os.getenv("COCOSEARCH_EMBEDDING_MODEL", "nomic-embed-text")
    embedding_model_source = (
        "environment" if os.getenv("COCOSEARCH_EMBEDDING_MODEL") else "default"
    )
    table.add_row("COCOSEARCH_EMBEDDING_MODEL", embedding_model, embedding_model_source)

    console.print(table)
    console.print()

    # Connectivity checks
    conn_table = Table(title="Connectivity")
    conn_table.add_column("Service", style="cyan")
    conn_table.add_column("Status", style="white")
    conn_table.add_column("Details", style="dim")

    has_failure = False
    ollama_reachable = False

    # PostgreSQL
    try:
        check_postgres(db_url)
        conn_table.add_row("PostgreSQL", "[green]✓ connected[/green]", "")
    except ConnectionError:
        has_failure = True
        conn_table.add_row(
            "PostgreSQL",
            "[red]✗ unreachable[/red]",
            "Run: docker compose up -d",
        )

    # Ollama
    try:
        check_ollama(ollama_url)
        conn_table.add_row("Ollama", "[green]✓ connected[/green]", "")
        ollama_reachable = True
    except ConnectionError:
        has_failure = True
        conn_table.add_row(
            "Ollama",
            "[red]✗ unreachable[/red]",
            "Run: docker compose up -d",
        )

    # Embedding model
    if ollama_reachable:
        try:
            check_ollama_model(ollama_url, embedding_model)
            conn_table.add_row(
                f"Model ({embedding_model})",
                "[green]✓ available[/green]",
                "",
            )
        except ConnectionError:
            has_failure = True
            conn_table.add_row(
                f"Model ({embedding_model})",
                "[red]✗ not found[/red]",
                f"Run: ollama pull {embedding_model}",
            )
    else:
        conn_table.add_row(
            f"Model ({embedding_model})",
            "[dim]- skipped[/dim]",
            "Ollama is unreachable",
        )

    console.print(conn_table)

    if has_failure:
        return 1

    console.print("\n[green]All checks passed[/green]")
    return 0


def dashboard_command(args: argparse.Namespace) -> int:
    """Execute the dashboard command.

    Starts a minimal HTTP server serving the web dashboard and API.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    import threading
    import webbrowser

    from cocosearch.mcp import run_server

    console = Console()

    # Resolve port: CLI > env > default
    if args.port is not None:
        port = args.port
    else:
        port_env = os.getenv("COCOSEARCH_DASHBOARD_PORT", "8080")
        try:
            port = int(port_env)
        except ValueError:
            console.print(
                f"[red]Error: Invalid port in COCOSEARCH_DASHBOARD_PORT: '{port_env}'[/red]"
            )
            return 1

    console.print("[bold]Starting CocoSearch Dashboard[/bold]")
    dashboard_url = f"http://{args.host}:{port}/dashboard"
    console.print(f"  Dashboard: {dashboard_url}")
    console.print(f"  API: http://{args.host}:{port}/api/stats")
    console.print()
    console.print("[dim]Press Ctrl+C to stop[/dim]")

    # Auto-open browser (opt-out via COCOSEARCH_NO_DASHBOARD=1)
    no_dashboard = os.environ.get("COCOSEARCH_NO_DASHBOARD", "").strip() == "1"
    if not no_dashboard:
        timer = threading.Timer(1.5, lambda: webbrowser.open(dashboard_url))
        timer.daemon = True
        timer.start()

    # Use MCP server with SSE transport (provides HTTP routes)
    try:
        run_server(transport="sse", host=args.host, port=port)
        return 0
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard stopped[/dim]")
        return 0
    except OSError as e:
        if "Address already in use" in str(e):
            console.print(
                f"[bold red]Error:[/bold red] Port {args.port} is already in use"
            )
            console.print(
                f"[dim]Hint: The MCP server may already be serving the dashboard. "
                f"Check http://127.0.0.1:{args.port}/dashboard or use --port to pick a different port.[/dim]"
            )
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
        "-n",
        "--name",
        config_key="indexName",
        help_text="Index name (default: derived from directory name)",
    )
    add_config_arg(
        index_parser,
        "-i",
        "--include",
        config_key="indexing.includePatterns",
        help_text="Additional file patterns to include (can be repeated)",
        action="append",
    )
    add_config_arg(
        index_parser,
        "-e",
        "--exclude",
        config_key="indexing.excludePatterns",
        help_text="Additional file patterns to exclude (can be repeated)",
        action="append",
    )
    index_parser.add_argument(
        "--no-gitignore",
        action="store_true",
        help="Disable .gitignore pattern respect",
    )
    index_parser.add_argument(
        "--fresh",
        action="store_true",
        help="Clear existing index before re-indexing (start from clean state)",
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
        "-i",
        "--interactive",
        action="store_true",
        help="Enter interactive search mode",
    )
    add_config_arg(
        search_parser,
        "-n",
        "--index",
        config_key="indexName",
        help_text="Index name (default: auto-detect from cwd)",
    )
    add_config_arg(
        search_parser,
        "-l",
        "--limit",
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
        "-A",
        "--after-context",
        type=int,
        default=None,
        metavar="NUM",
        help="Show NUM lines after each match (overrides smart expansion)",
    )
    search_parser.add_argument(
        "-B",
        "--before-context",
        type=int,
        default=None,
        metavar="NUM",
        help="Show NUM lines before each match (overrides smart expansion)",
    )
    search_parser.add_argument(
        "-C",
        "--context",
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
    stats_parser.add_argument(
        "--show-failures",
        action="store_true",
        help="Show individual file parse failure details",
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

    # Grammars subcommand
    grammars_parser = subparsers.add_parser(
        "grammars",
        help="List supported grammars",
        description="Show domain-specific grammars that provide structured chunking for specific file formats.",
    )
    grammars_parser.add_argument(
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
        "--transport",
        "-t",
        choices=["stdio", "sse", "http"],
        default=None,
        help="Transport protocol (default: stdio). [env: MCP_TRANSPORT]",
    )
    mcp_parser.add_argument(
        "--port",
        "-p",
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
        help="Validate environment and check service connectivity",
        description="Validate environment variables and check connectivity to PostgreSQL, Ollama, and the embedding model.",
    )

    # Dashboard subcommand
    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Start standalone web dashboard server",
        description="Start a web server to view the stats dashboard in a browser.",
    )
    dashboard_parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=None,
        help="Port to serve dashboard on (default: 8080). [env: COCOSEARCH_DASHBOARD_PORT]",
    )
    dashboard_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )

    # Known subcommands for routing
    known_subcommands = (
        "index",
        "search",
        "list",
        "stats",
        "languages",
        "grammars",
        "clear",
        "init",
        "mcp",
        "config",
        "dashboard",
        "-h",
        "--help",
    )

    # Handle <index_name> <subcommand> shorthand
    # e.g., `cocosearch helm_charts stats` → `cocosearch stats helm_charts`
    # e.g., `cocosearch helm_charts search "query"` → `cocosearch search -n helm_charts "query"`
    index_positional_subcommands = {"stats", "clear"}
    index_flag_subcommands = {"search", "index"}
    index_aware_subcommands = index_positional_subcommands | index_flag_subcommands

    if (
        len(sys.argv) > 2
        and sys.argv[1] not in known_subcommands
        and not sys.argv[1].startswith("-")
        and sys.argv[2] in index_aware_subcommands
    ):
        index_name_arg = sys.argv[1]
        subcmd = sys.argv[2]
        if subcmd in index_positional_subcommands:
            sys.argv = [sys.argv[0], subcmd, index_name_arg] + sys.argv[3:]
        else:
            sys.argv = [sys.argv[0], subcmd, "-n", index_name_arg] + sys.argv[3:]

    # Handle default action (query without subcommand)
    # Check before parsing if first argument is not a known subcommand
    # Supports: `cocosearch "query"` or `cocosearch --interactive`
    elif len(sys.argv) > 1 and sys.argv[1] not in known_subcommands:
        sys.argv.insert(1, "search")

    # Parse args
    args = parser.parse_args()

    # Ensure database URL default and CocoIndex bridge are set early
    from cocosearch.config.env_validation import get_database_url

    get_database_url()

    # Command routing via registry
    _command_registry: dict[str, Any] = {
        "index": index_command,
        "search": search_command,
        "list": list_command,
        "stats": stats_command,
        "languages": languages_command,
        "grammars": grammars_command,
        "clear": clear_command,
        "init": init_command,
        "mcp": mcp_command,
        "dashboard": dashboard_command,
    }

    _config_command_registry: dict[str, Any] = {
        "show": config_show_command,
        "path": config_path_command,
        "check": config_check_command,
    }

    if args.command == "config":
        handler = _config_command_registry.get(args.config_command)
        if handler:
            sys.exit(handler(args))
        else:
            config_parser.print_help()
            sys.exit(1)
    else:
        handler = _command_registry.get(args.command)
        if handler:
            sys.exit(handler(args))
        else:
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()
