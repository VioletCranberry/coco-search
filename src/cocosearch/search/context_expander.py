"""Smart context expansion with tree-sitter boundary detection.

Provides intelligent context expansion for search results by finding
enclosing function/class boundaries using tree-sitter AST parsing.
Includes LRU caching for efficient file reading during search sessions.

Features:
- Smart boundary detection finds enclosing function or class
- LRU caching (128 files) prevents repeated I/O
- 50-line hard limit enforced on all results
- Graceful fallback on parse errors
"""

import logging
from functools import lru_cache
from pathlib import Path

from tree_sitter import Parser
from tree_sitter_language_pack import get_language

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

MAX_CONTEXT_LINES = 50  # Hard limit per CONTEXT.md
LINE_TRUNCATION_LENGTH = 200  # Truncate long lines at this length

# Definition node types by language for enclosing scope detection
DEFINITION_NODE_TYPES: dict[str, set[str]] = {
    "python": {"function_definition", "class_definition"},
    "javascript": {
        "function_declaration",
        "class_declaration",
        "method_definition",
        "arrow_function",
    },
    "typescript": {
        "function_declaration",
        "class_declaration",
        "method_definition",
        "arrow_function",
        "interface_declaration",
    },
    "go": {"function_declaration", "method_declaration", "type_declaration"},
    "rust": {"function_item", "impl_item", "struct_item", "trait_item"},
    "scala": {
        "class_definition",
        "trait_definition",
        "object_definition",
        "function_definition",
    },
    "hcl": {"block"},
    "terraform": {"block"},
}

# Languages that support smart context expansion (derived from DEFINITION_NODE_TYPES)
CONTEXT_EXPANSION_LANGUAGES: set[str] = set(DEFINITION_NODE_TYPES.keys())

# File extension to tree-sitter language mapping
EXTENSION_TO_LANGUAGE: dict[str, str] = {
    # Python
    ".py": "python",
    # JavaScript
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    # TypeScript
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    # Go
    ".go": "go",
    # Rust
    ".rs": "rust",
    # Scala
    ".scala": "scala",
    # HCL / Terraform
    ".tf": "terraform",
    ".hcl": "hcl",
    ".tfvars": "terraform",
}


# ============================================================================
# Helper Functions
# ============================================================================


def _get_language_from_path(filepath: str) -> str | None:
    """Extract tree-sitter language from file extension.

    Args:
        filepath: Path to the source file.

    Returns:
        Tree-sitter language name, or None if extension not supported.
    """
    ext = Path(filepath).suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(ext)


def _truncate_line(line: str, max_length: int = LINE_TRUNCATION_LENGTH) -> str:
    """Truncate line with '...' suffix if too long.

    Args:
        line: Line text to truncate.
        max_length: Maximum allowed length.

    Returns:
        Truncated line with '...' suffix, or original if short enough.
    """
    if len(line) <= max_length:
        return line
    return line[: max_length - 3] + "..."


def _line_to_byte(lines: list[str], line_number: int) -> int:
    """Convert 1-based line number to byte offset.

    Args:
        lines: List of file lines (with line endings stripped).
        line_number: 1-based line number.

    Returns:
        Byte offset of start of line in original file.
    """
    # Accumulate bytes for all lines before target
    byte_offset = 0
    for i in range(min(line_number - 1, len(lines))):
        # Add line length + 1 for newline
        byte_offset += len(lines[i].encode("utf-8")) + 1
    return byte_offset


def _byte_to_line(content: bytes, byte_offset: int) -> int:
    """Convert byte offset to 1-based line number.

    Args:
        content: File content as bytes.
        byte_offset: Byte offset in the file.

    Returns:
        1-based line number.
    """
    return content[:byte_offset].count(b"\n") + 1


# ============================================================================
# Context Expander Class
# ============================================================================


class ContextExpander:
    """Manages context expansion with caching.

    Provides smart context expansion using tree-sitter to find enclosing
    function/class boundaries. Caches file content and parser instances
    for efficient repeated access during search sessions.

    Usage:
        expander = ContextExpander()
        before, match, after, is_bof, is_eof = expander.get_context_lines(
            filepath="src/main.py",
            start_line=10,
            end_line=15,
            smart=True,
        )
        # After search session
        expander.clear_cache()
    """

    def __init__(self):
        """Initialize context expander with empty caches."""
        self._parsers: dict[str, Parser] = {}
        # Create instance-level LRU cache for file reading
        self._read_file_cached = lru_cache(maxsize=128)(self._read_file_impl)

    def _get_parser(self, language: str) -> Parser:
        """Get or create parser for language.

        Args:
            language: Tree-sitter language name.

        Returns:
            Parser instance configured for the language.
        """
        if language not in self._parsers:
            lang = get_language(language)
            parser = Parser(lang)
            self._parsers[language] = parser
        return self._parsers[language]

    def _read_file_impl(self, filepath: str) -> list[str]:
        """Read file lines (implementation for LRU cache).

        Args:
            filepath: Path to the source file.

        Returns:
            List of lines with line endings stripped.
        """
        try:
            with open(filepath, encoding="utf-8", errors="replace") as f:
                return [line.rstrip("\n\r") for line in f.readlines()]
        except (FileNotFoundError, IOError, OSError) as e:
            logger.debug(f"Cannot read file {filepath}: {e}")
            return []

    def get_file_lines(self, filepath: str) -> list[str]:
        """Get file lines with LRU caching (max 128 files).

        Args:
            filepath: Path to the source file.

        Returns:
            List of lines with line endings stripped, or empty list on error.
        """
        return self._read_file_cached(filepath)

    def find_enclosing_scope(
        self, filepath: str, start_line: int, end_line: int, language: str
    ) -> tuple[int, int]:
        """Find enclosing function/class boundaries using tree-sitter.

        Parses the file and walks up the AST parent chain from the given
        position to find the nearest enclosing function or class definition.

        Args:
            filepath: Path to the source file.
            start_line: 1-based start line of the match.
            end_line: 1-based end line of the match.
            language: Tree-sitter language name.

        Returns:
            Tuple of (start_line, end_line) of enclosing scope,
            or original range if no enclosing scope found or on error.
        """
        try:
            # Check if language is supported for scope detection
            if language not in DEFINITION_NODE_TYPES:
                logger.debug(f"Language {language} not supported for scope detection")
                return (start_line, end_line)

            # Read file as bytes for tree-sitter
            with open(filepath, "rb") as f:
                content = f.read()

            # Parse with tree-sitter
            parser = self._get_parser(language)
            tree = parser.parse(content)

            # Log if parse has errors (still try to use partial tree)
            if tree.root_node.has_error:
                logger.debug(
                    f"Parse errors in {filepath}, using best-effort boundaries"
                )

            # Get file lines for byte offset calculation
            lines = self.get_file_lines(filepath)
            if not lines:
                return (start_line, end_line)

            # Calculate byte offset for start line
            start_byte = _line_to_byte(lines, start_line)

            # Find node at position
            node = tree.root_node.descendant_for_byte_range(start_byte, start_byte)
            if node is None:
                return (start_line, end_line)

            # Walk up parent chain looking for definition types
            definition_types = DEFINITION_NODE_TYPES[language]
            current = node
            while current is not None:
                if current.type in definition_types:
                    # Found enclosing scope - convert byte range to lines
                    scope_start = _byte_to_line(content, current.start_byte)
                    scope_end = _byte_to_line(content, current.end_byte)
                    return (scope_start, scope_end)
                current = current.parent

            # No enclosing scope found
            return (start_line, end_line)

        except Exception as e:
            logger.debug(f"Error finding enclosing scope in {filepath}: {e}")
            return (start_line, end_line)

    def get_context_lines(
        self,
        filepath: str,
        start_line: int,
        end_line: int,
        context_before: int = 0,
        context_after: int = 0,
        smart: bool = True,
        language: str | None = None,
    ) -> tuple[
        list[tuple[int, str]], list[tuple[int, str]], list[tuple[int, str]], bool, bool
    ]:
        """Get context lines with smart boundary expansion.

        When smart=True, expands context to enclosing function/class boundaries
        using tree-sitter, then applies 50-line hard limit centered on original
        match. When smart=False, uses explicit context_before/context_after values.

        Args:
            filepath: Path to the source file.
            start_line: 1-based start line of the match.
            end_line: 1-based end line of the match.
            context_before: Lines to include before match (when smart=False).
            context_after: Lines to include after match (when smart=False).
            smart: Whether to use smart boundary detection.
            language: Tree-sitter language name (auto-detected if None).

        Returns:
            Tuple of (before_lines, match_lines, after_lines, is_bof, is_eof).
            Each line is (line_number, line_text).
            is_bof is True if context starts at beginning of file.
            is_eof is True if context ends at end of file.
        """
        # Read file lines
        lines = self.get_file_lines(filepath)
        if not lines:
            # File not accessible
            return ([], [], [], False, False)

        total_lines = len(lines)

        # Auto-detect language if not provided
        if language is None:
            language = _get_language_from_path(filepath)

        # Determine context range
        if smart and language:
            # Use tree-sitter to find enclosing scope
            scope_start, scope_end = self.find_enclosing_scope(
                filepath, start_line, end_line, language
            )

            # Calculate total scope size
            total_scope_lines = scope_end - scope_start + 1

            if total_scope_lines > MAX_CONTEXT_LINES:
                # Apply 50-line cap centered on original match
                original_center = (start_line + end_line) // 2
                half_limit = MAX_CONTEXT_LINES // 2

                # Calculate centered range
                capped_start = max(scope_start, original_center - half_limit)
                capped_end = min(scope_end, capped_start + MAX_CONTEXT_LINES - 1)

                # Adjust if we hit the end boundary first
                if capped_end > scope_end:
                    capped_end = scope_end
                    capped_start = max(scope_start, capped_end - MAX_CONTEXT_LINES + 1)

                context_start = capped_start
                context_end = capped_end
            else:
                context_start = scope_start
                context_end = scope_end
        else:
            # Use explicit context values
            context_start = max(1, start_line - context_before)
            context_end = min(total_lines, end_line + context_after)

        # Ensure we don't exceed 50-line limit even in non-smart mode
        total_context = context_end - context_start + 1
        if total_context > MAX_CONTEXT_LINES:
            original_center = (start_line + end_line) // 2
            half_limit = MAX_CONTEXT_LINES // 2
            context_start = max(1, original_center - half_limit)
            context_end = min(total_lines, context_start + MAX_CONTEXT_LINES - 1)

        # Extract lines (convert to 0-indexed for list access)
        before_lines: list[tuple[int, str]] = []
        match_lines: list[tuple[int, str]] = []
        after_lines: list[tuple[int, str]] = []

        for line_num in range(context_start, context_end + 1):
            if line_num < 1 or line_num > total_lines:
                continue

            line_text = _truncate_line(lines[line_num - 1])

            if line_num < start_line:
                before_lines.append((line_num, line_text))
            elif line_num <= end_line:
                match_lines.append((line_num, line_text))
            else:
                after_lines.append((line_num, line_text))

        # Determine BOF/EOF flags
        is_bof = context_start <= 1
        is_eof = context_end >= total_lines

        return (before_lines, match_lines, after_lines, is_bof, is_eof)

    def clear_cache(self):
        """Clear file cache after search session.

        Should be called after each search to free memory.
        """
        self._read_file_cached.cache_clear()


# ============================================================================
# Module-level convenience function
# ============================================================================


def get_context_with_boundaries(
    filepath: str,
    start_line: int,
    end_line: int,
    context_before: int = 0,
    context_after: int = 0,
    smart: bool = True,
    language: str | None = None,
) -> tuple[
    list[tuple[int, str]], list[tuple[int, str]], list[tuple[int, str]], bool, bool
]:
    """Get context lines with smart boundary expansion (module-level function).

    Convenience wrapper that creates a temporary ContextExpander instance.
    For repeated use in a search session, prefer creating a ContextExpander
    instance directly to benefit from caching.

    Args:
        filepath: Path to the source file.
        start_line: 1-based start line of the match.
        end_line: 1-based end line of the match.
        context_before: Lines to include before match (when smart=False).
        context_after: Lines to include after match (when smart=False).
        smart: Whether to use smart boundary detection.
        language: Tree-sitter language name (auto-detected if None).

    Returns:
        Tuple of (before_lines, match_lines, after_lines, is_bof, is_eof).
        Each line is (line_number, line_text).
    """
    expander = ContextExpander()
    return expander.get_context_lines(
        filepath=filepath,
        start_line=start_line,
        end_line=end_line,
        context_before=context_before,
        context_after=context_after,
        smart=smart,
        language=language,
    )


__all__ = [
    "CONTEXT_EXPANSION_LANGUAGES",
    "ContextExpander",
    "get_context_with_boundaries",
    "MAX_CONTEXT_LINES",
    "LINE_TRUNCATION_LENGTH",
]
