"""HTTP client for remote CocoSearch server.

Forwards CLI commands to a running CocoSearch server via HTTP API.
Uses stdlib urllib.request to avoid adding dependencies.
"""

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from cocosearch.exceptions import CocoSearchError


class CocoSearchConnectionError(CocoSearchError):
    """Raised when the client cannot connect to the server."""


class CocoSearchClientError(CocoSearchError):
    """Raised when the server returns an error response."""


class CocoSearchClient:
    """HTTP client for communicating with a remote CocoSearch server."""

    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")
        self._path_prefix = os.environ.get("COCOSEARCH_PATH_PREFIX", "")

    def _translate_path_to_container(self, path: str) -> str:
        """Translate a host path to a container path."""
        if not self._path_prefix:
            return path
        parts = self._path_prefix.split(":")
        if len(parts) != 2:
            return path
        host_prefix, container_prefix = parts
        host_prefix = os.path.expanduser(host_prefix)
        if path.startswith(host_prefix):
            return container_prefix + path[len(host_prefix) :]
        return path

    def _translate_path_to_host(self, path: str) -> str:
        """Translate a container path to a host path."""
        if not self._path_prefix:
            return path
        parts = self._path_prefix.split(":")
        if len(parts) != 2:
            return path
        host_prefix, container_prefix = parts
        host_prefix = os.path.expanduser(host_prefix)
        if path.startswith(container_prefix):
            return host_prefix + path[len(container_prefix) :]
        return path

    def _request(self, method: str, path: str, body: dict | None = None) -> dict | list:
        """Make an HTTP request to the server."""
        url = f"{self.server_url}{path}"

        if body is not None:
            data = json.dumps(body).encode("utf-8")
        else:
            data = None

        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                error_body = json.loads(e.read().decode("utf-8"))
                msg = error_body.get("error", str(e))
            except Exception:
                msg = str(e)
            raise CocoSearchClientError(msg) from e
        except urllib.error.URLError as e:
            raise CocoSearchConnectionError(
                f"Cannot connect to CocoSearch server at {self.server_url}: {e.reason}"
            ) from e

    def search(
        self,
        query: str,
        index_name: str,
        limit: int = 10,
        min_score: float = 0.3,
        language: str | None = None,
        use_hybrid: bool | None = None,
        symbol_type: list[str] | None = None,
        symbol_name: str | None = None,
        no_cache: bool = False,
        smart_context: bool = False,
        context_before: int | None = None,
        context_after: int | None = None,
    ) -> dict:
        """Search indexed code."""
        body: dict[str, Any] = {
            "query": query,
            "index_name": index_name,
            "limit": limit,
            "min_score": min_score,
        }
        if language:
            body["language"] = language
        if use_hybrid is not None:
            body["use_hybrid"] = use_hybrid
        if symbol_type:
            body["symbol_type"] = symbol_type
        if symbol_name:
            body["symbol_name"] = symbol_name
        if no_cache:
            body["no_cache"] = True
        if smart_context:
            body["smart_context"] = True
        if context_before is not None:
            body["context_before"] = context_before
        if context_after is not None:
            body["context_after"] = context_after

        result = self._request("POST", "/api/search", body)

        # Translate container paths back to host paths
        if isinstance(result, dict) and "results" in result:
            for r in result["results"]:
                if "file_path" in r:
                    r["file_path"] = self._translate_path_to_host(r["file_path"])

        return result

    def index(
        self,
        project_path: str,
        index_name: str | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        no_gitignore: bool = False,
        fresh: bool = False,
        poll_interval: float = 2.0,
        poll_timeout: float = 600.0,
    ) -> dict:
        """Index a codebase. Starts indexing and polls until complete."""
        container_path = self._translate_path_to_container(project_path)
        body: dict[str, Any] = {"project_path": container_path}
        if index_name:
            body["index_name"] = index_name
        if include_patterns:
            body["include_patterns"] = include_patterns
        if exclude_patterns:
            body["exclude_patterns"] = exclude_patterns
        if no_gitignore:
            body["no_gitignore"] = True
        if fresh:
            body["fresh"] = True

        result = self._request("POST", "/api/index", body)
        resolved_name = result.get("index_name", index_name or "")

        # Poll for completion
        if resolved_name:
            start = time.monotonic()
            while time.monotonic() - start < poll_timeout:
                time.sleep(poll_interval)
                try:
                    stats = self._request("GET", f"/api/stats/{resolved_name}")
                    status = stats.get("status", "")
                    if status != "indexing":
                        return stats
                except (CocoSearchClientError, CocoSearchConnectionError):
                    break

        return result

    def stats(self, index_name: str | None = None) -> dict | list:
        """Get index statistics."""
        if index_name:
            return self._request("GET", f"/api/stats/{index_name}")
        return self._request("GET", "/api/stats")

    def list_indexes(self) -> list:
        """List all indexes."""
        result = self._request("GET", "/api/list")
        return result if isinstance(result, list) else []

    def clear(self, index_name: str) -> dict:
        """Delete an index."""
        return self._request("POST", "/api/delete-index", {"index_name": index_name})

    def analyze(
        self,
        query: str,
        index_name: str,
        limit: int = 10,
        min_score: float = 0.3,
        language: str | None = None,
        use_hybrid: bool | None = None,
        symbol_type: list[str] | None = None,
        symbol_name: str | None = None,
    ) -> dict:
        """Analyze the search pipeline."""
        body: dict[str, Any] = {
            "query": query,
            "index_name": index_name,
            "limit": limit,
            "min_score": min_score,
        }
        if language:
            body["language"] = language
        if use_hybrid is not None:
            body["use_hybrid"] = use_hybrid
        if symbol_type:
            body["symbol_type"] = symbol_type
        if symbol_name:
            body["symbol_name"] = symbol_name
        return self._request("POST", "/api/analyze", body)

    def languages(self) -> list:
        """List supported languages."""
        result = self._request("GET", "/api/languages")
        return result if isinstance(result, list) else []

    def grammars(self) -> list:
        """List supported grammars."""
        result = self._request("GET", "/api/grammars")
        return result if isinstance(result, list) else []


# Commands that don't make sense in client mode
_LOCAL_ONLY_COMMANDS = {"mcp", "dashboard", "init", "config"}


def run_client_command(args, server_url: str) -> int:
    """Dispatch CLI args to remote server via HTTP client.

    Args:
        args: Parsed argparse namespace.
        server_url: Base URL of the CocoSearch server.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    from rich.console import Console

    console = Console()
    command = getattr(args, "command", None)

    if command in _LOCAL_ONLY_COMMANDS:
        console.print(
            f"[yellow]'{command}' runs locally only and cannot be forwarded to a remote server.[/yellow]"
        )
        return 1

    client = CocoSearchClient(server_url)

    try:
        if command == "search":
            return _client_search(client, args, console)
        elif command == "index":
            return _client_index(client, args, console)
        elif command == "stats":
            return _client_stats(client, args, console)
        elif command == "list":
            return _client_list(client, args, console)
        elif command == "clear":
            return _client_clear(client, args, console)
        elif command == "analyze":
            return _client_analyze(client, args, console)
        elif command == "languages":
            return _client_languages(client, args, console)
        elif command == "grammars":
            return _client_grammars(client, args, console)
        else:
            console.print(f"[red]Unknown command: {command}[/red]")
            return 1
    except CocoSearchConnectionError as e:
        console.print(f"[bold red]Connection error:[/bold red] {e}")
        return 1
    except CocoSearchClientError as e:
        console.print(f"[bold red]Server error:[/bold red] {e}")
        return 1


def _client_search(client: CocoSearchClient, args, console) -> int:
    """Handle search command in client mode."""
    if getattr(args, "interactive", False):
        console.print(
            "[yellow]Interactive mode is not supported in client mode.[/yellow]"
        )
        return 1

    query = getattr(args, "query", None)
    if not query:
        console.print("[red]Query required[/red]")
        return 1

    # Parse inline filters
    from cocosearch.cli import parse_query_filters

    query, inline_lang = parse_query_filters(query)
    lang_filter = getattr(args, "lang", None) or inline_lang

    index_name = getattr(args, "index", None) or os.environ.get(
        "COCOSEARCH_INDEX_NAME", ""
    )
    if not index_name:
        console.print(
            "[red]Index name required in client mode. Use -n/--index or set COCOSEARCH_INDEX_NAME.[/red]"
        )
        return 1

    use_hybrid = True if getattr(args, "hybrid", None) else None
    symbol_type = getattr(args, "symbol_type", None)
    symbol_name = getattr(args, "symbol_name", None)
    no_cache = getattr(args, "no_cache", False)

    # Context parameters
    context_before = getattr(args, "before_context", None)
    context_after = getattr(args, "after_context", None)
    context = getattr(args, "context", None)
    if context is not None:
        context_before = context_before if context_before is not None else context
        context_after = context_after if context_after is not None else context
    smart_context = not getattr(args, "no_smart", False)

    result = client.search(
        query=query,
        index_name=index_name,
        limit=getattr(args, "limit", 10),
        min_score=getattr(args, "min_score", 0.3),
        language=lang_filter,
        use_hybrid=use_hybrid,
        symbol_type=symbol_type,
        symbol_name=symbol_name,
        no_cache=no_cache,
        smart_context=smart_context,
        context_before=context_before,
        context_after=context_after,
    )

    if getattr(args, "pretty", False):
        _print_search_results_pretty(result, console)
    else:
        print(json.dumps(result, indent=2))
    return 0


def _client_index(client: CocoSearchClient, args, console) -> int:
    """Handle index command in client mode."""
    path = os.path.abspath(args.path)
    index_name = getattr(args, "name", None)
    include = getattr(args, "include", None)
    exclude = getattr(args, "exclude", None)
    no_gitignore = getattr(args, "no_gitignore", False)
    fresh = getattr(args, "fresh", False)

    console.print(f"[dim]Indexing {path} on remote server...[/dim]")
    result = client.index(
        project_path=path,
        index_name=index_name,
        include_patterns=include,
        exclude_patterns=exclude,
        no_gitignore=no_gitignore,
        fresh=fresh,
    )

    if isinstance(result, dict):
        if result.get("success") or result.get("name"):
            console.print("[green]Indexing complete.[/green]")
        print(json.dumps(result, indent=2))
    return 0


def _client_stats(client: CocoSearchClient, args, console) -> int:
    """Handle stats command in client mode."""
    index_name = getattr(args, "index", None)
    if getattr(args, "all", False):
        index_name = None

    result = client.stats(index_name)
    print(json.dumps(result, indent=2))
    return 0


def _client_list(client: CocoSearchClient, args, console) -> int:
    """Handle list command in client mode."""
    indexes = client.list_indexes()
    if getattr(args, "pretty", False):
        if not indexes:
            console.print("[dim]No indexes found[/dim]")
        else:
            from rich.table import Table

            table = Table(title="Indexes")
            table.add_column("Name", style="cyan")
            table.add_column("Status", style="dim")
            table.add_column("Branch", style="green")
            for idx in indexes:
                table.add_row(
                    idx.get("name", ""),
                    (idx.get("status") or "-").title(),
                    idx.get("branch") or "-",
                )
            console.print(table)
    else:
        print(json.dumps(indexes, indent=2))
    return 0


def _client_clear(client: CocoSearchClient, args, console) -> int:
    """Handle clear command in client mode."""
    index_name = args.index
    if not getattr(args, "force", False):
        response = input(f"Delete index '{index_name}' on remote server? [y/N] ")
        if response.lower() != "y":
            console.print("Cancelled.")
            return 0

    result = client.clear(index_name)
    print(json.dumps(result, indent=2))
    return 0


def _client_analyze(client: CocoSearchClient, args, console) -> int:
    """Handle analyze command in client mode."""
    query = getattr(args, "query", None)
    if not query:
        console.print("[red]Query required[/red]")
        return 1

    from cocosearch.cli import parse_query_filters

    query, inline_lang = parse_query_filters(query)
    lang_filter = getattr(args, "lang", None) or inline_lang

    index_name = getattr(args, "index", None) or os.environ.get(
        "COCOSEARCH_INDEX_NAME", ""
    )
    if not index_name:
        console.print(
            "[red]Index name required in client mode. Use -n/--index or set COCOSEARCH_INDEX_NAME.[/red]"
        )
        return 1

    use_hybrid = True if getattr(args, "hybrid", None) else None
    symbol_type = getattr(args, "symbol_type", None)
    symbol_name = getattr(args, "symbol_name", None)

    result = client.analyze(
        query=query,
        index_name=index_name,
        limit=getattr(args, "limit", 10),
        min_score=getattr(args, "min_score", 0.3),
        language=lang_filter,
        use_hybrid=use_hybrid,
        symbol_type=symbol_type,
        symbol_name=symbol_name,
    )
    print(json.dumps(result, indent=2))
    return 0


def _client_languages(client: CocoSearchClient, args, console) -> int:
    """Handle languages command in client mode."""
    languages = client.languages()
    if getattr(args, "json", False):
        print(json.dumps(languages, indent=2))
    else:
        from rich.table import Table

        table = Table(title="Supported Languages")
        table.add_column("Language", style="cyan")
        table.add_column("Extensions", style="dim")
        table.add_column("Symbols", justify="center")
        table.add_column("Context", justify="center")
        for lang in languages:
            exts = ", ".join(lang.get("extensions", []))
            sym = (
                "[green]\u2713[/green]" if lang.get("symbols") else "[dim]\u2717[/dim]"
            )
            ctx = (
                "[green]\u2713[/green]" if lang.get("context") else "[dim]\u2717[/dim]"
            )
            table.add_row(lang.get("name", ""), exts, sym, ctx)
        console.print(table)
    return 0


def _client_grammars(client: CocoSearchClient, args, console) -> int:
    """Handle grammars command in client mode."""
    grammars = client.grammars()
    if getattr(args, "json", False):
        print(json.dumps(grammars, indent=2))
    else:
        from rich.table import Table

        table = Table(title="Supported Grammars")
        table.add_column("Grammar", style="cyan")
        table.add_column("File Format", style="dim")
        table.add_column("Path Patterns", style="dim")
        for g in grammars:
            table.add_row(
                g.get("name", ""),
                g.get("base_language", ""),
                ", ".join(g.get("path_patterns", [])),
            )
        console.print(table)
    return 0


def _print_search_results_pretty(result: dict, console) -> None:
    """Print search results in a human-readable format."""
    results = result.get("results", [])
    total = result.get("total", len(results))
    query_time = result.get("query_time_ms", 0)

    console.print(f"\n[dim]{total} results ({query_time}ms)[/dim]\n")

    for i, r in enumerate(results, 1):
        file_path = r.get("file_path", "")
        start_line = r.get("start_line", 0)
        end_line = r.get("end_line", 0)
        score = r.get("score", 0)
        content = r.get("content", "")
        language_id = r.get("language_id", "")

        console.print(
            f"[bold cyan]{i}.[/bold cyan] {file_path}:{start_line}-{end_line} "
            f"[dim](score: {score:.3f}, {language_id})[/dim]"
        )

        if r.get("context_before"):
            console.print(f"[dim]{r['context_before']}[/dim]")
        if content:
            # Truncate long content for display
            lines = content.split("\n")
            if len(lines) > 20:
                display = "\n".join(lines[:20])
                console.print(f"  {display}")
                console.print(f"  [dim]... ({len(lines) - 20} more lines)[/dim]")
            else:
                console.print(f"  {content}")
        if r.get("context_after"):
            console.print(f"[dim]{r['context_after']}[/dim]")
        console.print()
