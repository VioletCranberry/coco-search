"""Handler for Bash/Shell script files.

Provides language-aware chunking and metadata extraction for Bash, Shell,
and Zsh scripts.

Handles .sh, .bash, and .zsh file extensions.
"""

import re

import cocoindex


class BashHandler:
    """Handler for Bash/Shell script files."""

    EXTENSIONS = [".sh", ".bash", ".zsh"]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="bash",
        separators_regex=[
            # Level 1: Function keyword definitions
            r"\nfunction ",
            # Level 2: Blank lines (logical section separators in scripts)
            r"\n\n+",
            # Level 3: Comment-based section headers
            r"\n#+",
            # Level 4: Control flow keywords
            r"\n(?:if |for |while |case |until )",
            # Level 5: Single newlines
            r"\n",
            # Level 6: Whitespace (last resort)
            r" ",
        ],
        aliases=["sh", "zsh", "shell"],
    )

    # Bash comment pattern
    _COMMENT_LINE = re.compile(r"^\s*#.*$", re.MULTILINE)

    # Three function definition syntaxes (POSIX, ksh, hybrid)
    _FUNCTION_RE = re.compile(
        r"^(?:"
        r"function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\(\s*\))?\s*\{?"
        r"|"
        r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*\)\s*\{?"
        r")"
    )

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from Bash chunk.

        Matches all 3 Bash function definition syntaxes (POSIX, ksh, hybrid).

        Args:
            text: The chunk text content.

        Returns:
            Dict with metadata fields:
            - block_type: "function" for function definitions, empty otherwise
            - hierarchy: "function:name" for functions, empty otherwise
            - language_id: "bash"

        Example:
            Input: 'function deploy_app {'
            Output: {
                "block_type": "function",
                "hierarchy": "function:deploy_app",
                "language_id": "bash"
            }
        """
        stripped = self._strip_comments(text)
        match = self._FUNCTION_RE.match(stripped)
        if not match:
            return {"block_type": "", "hierarchy": "", "language_id": "bash"}

        # group(1) is the ksh/hybrid form, group(2) is the POSIX form
        func_name = match.group(1) or match.group(2)
        return {
            "block_type": "function",
            "hierarchy": f"function:{func_name}",
            "language_id": "bash",
        }

    def _strip_comments(self, text: str) -> str:
        """Strip leading comments from chunk text.

        Args:
            text: The chunk text content.

        Returns:
            Text from first non-comment, non-blank line onward
        """
        lines = text.lstrip().split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not self._COMMENT_LINE.match(line):
                return "\n".join(lines[i:])
        return ""
