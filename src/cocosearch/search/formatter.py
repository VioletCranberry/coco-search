"""Result formatters for search output.

Provides JSON and pretty (Rich) output formatters for search results.
Supports both smart context expansion (tree-sitter boundaries) and
explicit line counts via -A/-B/-C flags.
"""

import json
import os

from rich.console import Console
from rich.syntax import Syntax

from cocosearch.search.context_expander import ContextExpander
from cocosearch.search.query import SearchResult
from cocosearch.search.utils import byte_to_line, get_context_lines, read_chunk_content


def format_json(
    results: list[SearchResult],
    context_lines: int | None = None,
    context_before: int | None = None,
    context_after: int | None = None,
    smart_context: bool = True,
    include_content: bool = True,
) -> str:
    """Format results as JSON.

    Args:
        results: List of SearchResult objects.
        context_lines: Legacy parameter for backward compatibility.
        context_before: Lines to include before match (overrides smart).
        context_after: Lines to include after match (overrides smart).
        smart_context: Whether to use smart boundary expansion.
        include_content: Whether to include chunk content.

    Returns:
        JSON string.
    """
    # Handle backward compatibility for context_lines parameter
    if context_lines is not None:
        context_before = context_before if context_before is not None else context_lines
        context_after = context_after if context_after is not None else context_lines

    # Determine if context expansion should be done
    should_expand_context = (
        context_before is not None or context_after is not None or smart_context
    )

    # Create expander instance for session caching
    expander = ContextExpander() if should_expand_context else None

    output = []
    for r in results:
        start_line = byte_to_line(r.filename, r.start_byte)
        end_line = byte_to_line(r.filename, r.end_byte)

        item = {
            "file_path": r.filename,
            "start_line": start_line,
            "end_line": end_line,
            "score": round(r.score, 4),
            "block_type": r.block_type,
            "hierarchy": r.hierarchy,
            "language_id": r.language_id,
        }

        # Add hybrid search fields only when they have values (clean output for non-hybrid)
        if hasattr(r, "match_type") and r.match_type:
            item["match_type"] = r.match_type
        if hasattr(r, "vector_score") and r.vector_score is not None:
            item["vector_score"] = round(r.vector_score, 4)
        if hasattr(r, "keyword_score") and r.keyword_score is not None:
            item["keyword_score"] = round(r.keyword_score, 4)

        # Add symbol fields when present (clean output - omit if None)
        if hasattr(r, "symbol_type") and r.symbol_type:
            item["symbol_type"] = r.symbol_type
        if hasattr(r, "symbol_name") and r.symbol_name:
            item["symbol_name"] = r.symbol_name
        if hasattr(r, "symbol_signature") and r.symbol_signature:
            item["symbol_signature"] = r.symbol_signature

        if include_content:
            item["content"] = read_chunk_content(r.filename, r.start_byte, r.end_byte)

            if should_expand_context and expander is not None:
                # Use ContextExpander for smart or explicit context
                before_lines, _, after_lines, _, _ = expander.get_context_lines(
                    r.filename,
                    start_line,
                    end_line,
                    context_before=context_before or 0,
                    context_after=context_after or 0,
                    smart=smart_context and context_before is None and context_after is None,
                    language=_get_tree_sitter_language(r.filename),
                )
                # Format as newline-separated strings
                item["context_before"] = "\n".join(line for _, line in before_lines)
                item["context_after"] = "\n".join(line for _, line in after_lines)

        output.append(item)

    # Clear cache after processing
    if expander is not None:
        expander.clear_cache()

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
    "tf": "hcl",
    "hcl": "hcl",
    "tfvars": "hcl",
}

# Mapping from display language name to Pygments lexer name
# Only needed when display name differs from Pygments lexer name
_PYGMENTS_LEXER_MAP = {
    "dockerfile": "docker",
}

# Mapping from extension to tree-sitter language names for context expansion
_TREE_SITTER_LANG_MAP = {
    "py": "python",
    "pyw": "python",
    "pyi": "python",
    "js": "javascript",
    "jsx": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "ts": "typescript",
    "tsx": "typescript",
    "mts": "typescript",
    "cts": "typescript",
    "go": "go",
    "rs": "rust",
}


def _get_tree_sitter_language(filepath: str) -> str | None:
    """Get tree-sitter language name from file extension.

    Args:
        filepath: Path to the source file.

    Returns:
        Tree-sitter language name, or None if not supported.
    """
    ext = os.path.splitext(filepath)[1].lstrip(".")
    return _TREE_SITTER_LANG_MAP.get(ext)


def _get_display_language(result: SearchResult, filepath: str) -> str:
    """Determine the display language for a search result.

    If the result has a language_id (DevOps file), use that directly.
    Otherwise, derive from file extension using EXTENSION_LANG_MAP.

    Args:
        result: SearchResult with optional language_id.
        filepath: File path for extension-based fallback.

    Returns:
        Language name string (e.g., "hcl", "python", "dockerfile").
    """
    if result.language_id:
        return result.language_id
    ext = os.path.splitext(filepath)[1].lstrip(".")
    return EXTENSION_LANG_MAP.get(ext, ext)


def _get_annotation(result: SearchResult, display_lang: str) -> str:
    """Build annotation string for pretty output.

    If hierarchy is available, shows [lang] hierarchy.
    Otherwise, shows [lang] only.

    Args:
        result: SearchResult with optional hierarchy.
        display_lang: Language name from _get_display_language.

    Returns:
        Annotation string (e.g., "[hcl] resource.aws_s3_bucket.data" or "[python]").
    """
    if result.hierarchy:
        return f"[{display_lang}] {result.hierarchy}"
    return f"[{display_lang}]"


def format_pretty(
    results: list[SearchResult],
    context_lines: int | None = None,
    context_before: int | None = None,
    context_after: int | None = None,
    smart_context: bool = True,
    console: Console | None = None,
) -> None:
    """Print results in human-readable format with grep-style context.

    Args:
        results: List of SearchResult objects.
        context_lines: Legacy parameter for backward compatibility.
        context_before: Lines to include before match (overrides smart).
        context_after: Lines to include after match (overrides smart).
        smart_context: Whether to use smart boundary expansion.
        console: Rich Console instance (creates new if None).
    """
    if console is None:
        console = Console()

    if not results:
        console.print("[dim]No results found.[/dim]")
        return

    # Handle backward compatibility for context_lines parameter
    if context_lines is not None:
        context_before = context_before if context_before is not None else context_lines
        context_after = context_after if context_after is not None else context_lines

    # Determine if context expansion should be done
    should_expand_context = (
        context_before is not None or context_after is not None or smart_context
    )

    # Create expander instance for session caching
    expander = ContextExpander() if should_expand_context else None

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

            # Build match type indicator for hybrid search results
            match_indicator = ""
            if hasattr(r, "match_type") and r.match_type:
                if r.match_type == "semantic":
                    match_indicator = " [cyan]\\[semantic][/cyan]"
                elif r.match_type == "keyword":
                    match_indicator = " [green]\\[keyword][/green]"
                elif r.match_type == "both":
                    match_indicator = " [yellow]\\[both][/yellow]"

            # Score and line info
            score_color = "green" if r.score > 0.7 else "yellow" if r.score > 0.5 else "red"
            console.print(
                f"  [{score_color}]{r.score:.2f}[/{score_color}] "
                f"Lines {start_line}-{end_line}{match_indicator}"
            )

            # Language annotation (escape brackets for Rich markup)
            display_lang = _get_display_language(r, filepath)
            annotation = _get_annotation(r, display_lang)
            # Rich interprets [...] as markup; escape with backslash
            escaped = annotation.replace("[", "\\[")
            console.print(f"  [dim cyan]{escaped}[/dim cyan]")

            # Show symbol info if present (after language annotation, before context)
            if hasattr(r, "symbol_name") and r.symbol_name:
                symbol_type = getattr(r, "symbol_type", "symbol") or "symbol"
                # Escape brackets for Rich markup
                symbol_display = f"[{symbol_type}] {r.symbol_name}"
                symbol_escaped = symbol_display.replace("[", "\\[")
                console.print(f"  [dim magenta]{symbol_escaped}[/dim magenta]")
                # Show signature if available (truncated for display)
                if hasattr(r, "symbol_signature") and r.symbol_signature:
                    sig = r.symbol_signature
                    if len(sig) > 60:
                        sig = sig[:57] + "..."
                    console.print(f"  [dim]{sig}[/dim]")

            # Get context lines if context expansion is enabled
            if should_expand_context and expander is not None:
                before_lines, match_lines, after_lines, is_bof, is_eof = expander.get_context_lines(
                    r.filename,
                    start_line,
                    end_line,
                    context_before=context_before or 0,
                    context_after=context_after or 0,
                    smart=smart_context and context_before is None and context_after is None,
                    language=_get_tree_sitter_language(r.filename),
                )

                # Show BOF marker if at file start
                if is_bof and before_lines:
                    console.print("[dim]  [Beginning of file][/dim]")

                # Show context before with grep-style markers (: for context)
                for line_num, line_text in before_lines:
                    console.print(f"  [dim]{line_num}: {line_text}[/dim]")

                # Show matched lines with grep-style markers (> for match)
                for line_num, line_text in match_lines:
                    console.print(f"  [bold]{line_num}> {line_text}[/bold]")

                # Show context after with grep-style markers (: for context)
                for line_num, line_text in after_lines:
                    console.print(f"  [dim]{line_num}: {line_text}[/dim]")

                # Show EOF marker if at file end
                if is_eof and after_lines:
                    console.print("[dim]  [End of file][/dim]")
            else:
                # No context expansion - show content with syntax highlighting (legacy mode)
                content = read_chunk_content(r.filename, r.start_byte, r.end_byte)
                if content:
                    lexer = _PYGMENTS_LEXER_MAP.get(display_lang, display_lang)
                    try:
                        syntax = Syntax(
                            content,
                            lexer,
                            line_numbers=True,
                            start_line=start_line,
                            theme="monokai",
                        )
                        console.print(syntax)
                    except Exception:
                        console.print(content)

        console.print()  # Blank line between files

    # Clear cache after processing
    if expander is not None:
        expander.clear_cache()
