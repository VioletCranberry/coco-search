"""Interactive REPL for cocosearch.

Provides a command-line REPL for continuous search sessions without
needing to restart the CLI for each query.
"""

import cmd
import re

try:
    import readline  # noqa: F401 - Enables history/editing in cmd.Cmd
except ImportError:
    pass  # readline unavailable on Windows; history/editing won't work

from rich.console import Console

from cocosearch.search.formatter import format_pretty
from cocosearch.search.query import search


def _parse_query_filters(query: str) -> tuple[str, str | None]:
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


class SearchREPL(cmd.Cmd):
    """Interactive search REPL.

    Commands:
        <query>     - Search for query
        :limit N    - Set result limit
        :lang X     - Set language filter (empty to clear)
        :context N  - Set context lines
        :index X    - Switch index
        :help       - Show help
        quit/exit   - Exit REPL
    """

    intro = None  # Set in __init__ for Rich formatting
    prompt = "cocosearch> "

    def __init__(
        self,
        index_name: str,
        limit: int = 10,
        context_lines: int = 5,
        min_score: float = 0.3,
    ):
        """Initialize the REPL.

        Args:
            index_name: Name of the index to search.
            limit: Initial result limit.
            context_lines: Initial context lines.
            min_score: Minimum score threshold.
        """
        super().__init__()
        self.console = Console()
        self.index_name = index_name
        self.limit = limit
        self.context_lines = context_lines
        self.min_score = min_score
        self.lang_filter: str | None = None

        # Show intro with Rich
        self.console.print("[bold]CocoSearch Interactive Mode[/bold]")
        self.console.print(
            f"[dim]Index: {index_name} | Limit: {limit} | Context: {context_lines} lines[/dim]"
        )
        self.console.print("[dim]Type :help for commands, quit to exit[/dim]\n")

    def default(self, line: str) -> bool:
        """Handle search queries (default action)."""
        if not line.strip():
            return False

        # Check for settings commands
        if line.startswith(":"):
            return self.handle_setting(line)

        # Parse inline filters
        query, inline_lang = _parse_query_filters(line)
        lang = inline_lang or self.lang_filter

        try:
            results = search(
                query=query,
                index_name=self.index_name,
                limit=self.limit,
                min_score=self.min_score,
                language_filter=lang,
            )
            format_pretty(
                results, context_lines=self.context_lines, console=self.console
            )
        except Exception as e:
            self.console.print(f"[bold red]Error:[/bold red] {e}")

        return False

    def handle_setting(self, line: str) -> bool:
        """Handle :setting commands."""
        parts = line[1:].split(maxsplit=1)
        cmd_name = parts[0].lower()
        value = parts[1] if len(parts) > 1 else ""

        if cmd_name == "limit":
            try:
                self.limit = int(value)
                self.console.print(f"[dim]Limit set to {self.limit}[/dim]")
            except ValueError:
                self.console.print("[red]Usage: :limit N[/red]")

        elif cmd_name == "lang":
            if value:
                self.lang_filter = value
                self.console.print(f"[dim]Language filter: {self.lang_filter}[/dim]")
            else:
                self.lang_filter = None
                self.console.print("[dim]Language filter cleared[/dim]")

        elif cmd_name == "context":
            try:
                self.context_lines = int(value)
                self.console.print(
                    f"[dim]Context lines set to {self.context_lines}[/dim]"
                )
            except ValueError:
                self.console.print("[red]Usage: :context N[/red]")

        elif cmd_name == "index":
            if value:
                self.index_name = value
                self.console.print(f"[dim]Switched to index: {self.index_name}[/dim]")
            else:
                self.console.print("[red]Usage: :index NAME[/red]")

        elif cmd_name == "help":
            self.do_help("")

        else:
            self.console.print(f"[red]Unknown command: :{cmd_name}[/red]")

        return False

    def do_help(self, arg: str) -> bool:
        """Show help message."""
        self.console.print(
            """
[bold]Commands:[/bold]
  <query>       Search for code matching query
  :limit N      Set max results (current: {limit})
  :lang X       Set language filter (current: {lang})
  :context N    Set context lines (current: {context})
  :index X      Switch to different index
  :help         Show this help
  quit, exit    Exit interactive mode

[bold]Tips:[/bold]
  - Use lang:python in query for inline filtering
  - Press Up/Down for command history
  - Press Ctrl-D to exit
""".format(
                limit=self.limit,
                lang=self.lang_filter or "none",
                context=self.context_lines,
            )
        )
        return False

    def do_quit(self, arg: str) -> bool:
        """Exit the REPL."""
        self.console.print("[dim]Goodbye![/dim]")
        return True

    def do_exit(self, arg: str) -> bool:
        """Exit the REPL."""
        return self.do_quit(arg)

    def do_EOF(self, arg: str) -> bool:
        """Handle Ctrl-D."""
        self.console.print()  # Newline after ^D
        return self.do_quit(arg)

    def emptyline(self) -> bool:
        """Do nothing on empty line (don't repeat last command)."""
        return False


def run_repl(
    index_name: str,
    limit: int = 10,
    context_lines: int = 5,
    min_score: float = 0.3,
) -> None:
    """Run the interactive search REPL.

    Args:
        index_name: Name of the index to search.
        limit: Initial result limit.
        context_lines: Initial context lines.
        min_score: Minimum score threshold.
    """
    repl = SearchREPL(
        index_name=index_name,
        limit=limit,
        context_lines=context_lines,
        min_score=min_score,
    )
    try:
        repl.cmdloop()
    except KeyboardInterrupt:
        repl.console.print("\n[dim]Interrupted. Goodbye![/dim]")
