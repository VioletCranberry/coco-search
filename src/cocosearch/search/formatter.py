"""Result formatters for search output.

Provides JSON and pretty (Rich) output formatters for search results.
"""

import json
import os

from rich.console import Console
from rich.syntax import Syntax

from cocosearch.search.query import SearchResult
from cocosearch.search.utils import byte_to_line, get_context_lines, read_chunk_content


def format_json(
    results: list[SearchResult],
    context_lines: int = 5,
    include_content: bool = True,
) -> str:
    """Format results as JSON.

    Args:
        results: List of SearchResult objects.
        context_lines: Number of surrounding lines to include.
        include_content: Whether to include chunk content.

    Returns:
        JSON string.
    """
    output = []
    for r in results:
        start_line = byte_to_line(r.filename, r.start_byte)
        end_line = byte_to_line(r.filename, r.end_byte)

        item = {
            "file_path": r.filename,
            "start_line": start_line,
            "end_line": end_line,
            "score": round(r.score, 4),
        }

        if include_content:
            item["content"] = read_chunk_content(r.filename, r.start_byte, r.end_byte)

            if context_lines > 0:
                before, after = get_context_lines(
                    r.filename, start_line, end_line, context_lines
                )
                item["context_before"] = before
                item["context_after"] = after

        output.append(item)

    return json.dumps(output, indent=2)


# Extension to language mapping for syntax highlighting
EXTENSION_LANG_MAP = {
    "py": "python",
    "pyw": "python",
    "pyi": "python",
    "js": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "ts": "typescript",
    "tsx": "typescript",
    "mts": "typescript",
    "cts": "typescript",
    "rs": "rust",
    "go": "go",
    "java": "java",
    "rb": "ruby",
    "php": "php",
    "c": "c",
    "h": "c",
    "cpp": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "hpp": "cpp",
    "hxx": "cpp",
    "cs": "csharp",
    "swift": "swift",
    "kt": "kotlin",
    "kts": "kotlin",
    "scala": "scala",
    "sh": "bash",
    "bash": "bash",
    "zsh": "bash",
    "md": "markdown",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "sql": "sql",
}


def format_pretty(
    results: list[SearchResult],
    context_lines: int = 5,
    console: Console | None = None,
) -> None:
    """Print results in human-readable format.

    Args:
        results: List of SearchResult objects.
        context_lines: Number of surrounding lines to include.
        console: Rich Console instance (creates new if None).
    """
    if console is None:
        console = Console()

    if not results:
        console.print("[dim]No results found.[/dim]")
        return

    console.print(f"[bold]Found {len(results)} results:[/bold]\n")

    # Group results by file
    by_file: dict[str, list[SearchResult]] = {}
    for r in results:
        if r.filename not in by_file:
            by_file[r.filename] = []
        by_file[r.filename].append(r)

    for filepath, file_results in by_file.items():
        # File header
        rel_path = os.path.relpath(filepath) if os.path.exists(filepath) else filepath
        console.print(f"[bold blue]{rel_path}[/bold blue]")

        for r in file_results:
            start_line = byte_to_line(r.filename, r.start_byte)
            end_line = byte_to_line(r.filename, r.end_byte)

            # Score and line info
            score_color = "green" if r.score > 0.7 else "yellow" if r.score > 0.5 else "red"
            console.print(
                f"  [{score_color}]{r.score:.2f}[/{score_color}] Lines {start_line}-{end_line}"
            )

            # Show content with syntax highlighting
            content = read_chunk_content(r.filename, r.start_byte, r.end_byte)
            if content:
                # Determine language from extension
                ext = os.path.splitext(filepath)[1].lstrip(".")
                lang = EXTENSION_LANG_MAP.get(ext, ext)

                try:
                    syntax = Syntax(
                        content,
                        lang,
                        line_numbers=True,
                        start_line=start_line,
                        theme="monokai",
                    )
                    console.print(syntax)
                except Exception:
                    # Fallback to plain text if syntax highlighting fails
                    console.print(content)

        console.print()  # Blank line between files
