"""Template for creating new grammar handlers.

Grammar handlers provide domain-specific chunking and metadata for files
that share a base language but have distinct structure. For example,
GitHub Actions workflows are YAML files with a specific schema.

Copy this file to <grammar_name>.py and implement the TODOs.

For language handlers (matched by extension), see handlers/_template.py instead.
"""

import fnmatch
import re

import cocoindex


class TemplateGrammarHandler:
    """Grammar handler for <GRAMMAR> files.

    TODO: Replace <GRAMMAR> with grammar name (e.g., "GitHub Actions").
    """

    # TODO: Unique grammar identifier (lowercase, hyphenated)
    GRAMMAR_NAME = "template-grammar"

    # TODO: Base language this grammar extends (e.g., "yaml", "json")
    BASE_LANGUAGE = "yaml"

    # TODO: File path patterns that suggest this grammar (glob syntax)
    PATH_PATTERNS = ["**/example/*.yml"]

    # TODO: Define CustomLanguageSpec with hierarchical separators, or None for default
    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="template-grammar",
        separators_regex=[
            # Level 1: Top-level structural boundaries
            r"\n[a-zA-Z_][\w-]*:",
            # Level 2: Blank lines
            r"\n\n+",
            # Level 3: Single newlines
            r"\n",
            # Level 4: Whitespace (last resort)
            r" ",
        ],
        aliases=[],
    )

    # TODO: Define regex patterns for metadata extraction
    _BLOCK_RE = re.compile(r"^some_pattern")
    _COMMENT_LINE = re.compile(r"^\s*#.*$", re.MULTILINE)

    def matches(self, filepath: str, content: str | None = None) -> bool:
        """Check if this grammar applies to the given file.

        TODO: Implement matching logic:
        1. Check filepath against PATH_PATTERNS
        2. Optionally verify content markers

        Args:
            filepath: Relative file path within the project.
            content: Optional file content for deeper matching.

        Returns:
            True if this grammar should handle the file.
        """
        # Path-based matching
        for pattern in self.PATH_PATTERNS:
            if fnmatch.fnmatch(filepath, pattern):
                # TODO: Optionally check content markers
                return True
        return False

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from <GRAMMAR> chunk.

        TODO: Implement metadata extraction logic.

        Args:
            text: The chunk text content.

        Returns:
            Dict with metadata fields:
            - block_type: Type of block (e.g., "job", "service", "stage")
            - hierarchy: Structured identifier (e.g., "job:build", "service:web")
            - language_id: Grammar name (same as GRAMMAR_NAME)
        """
        return {
            "block_type": "",
            "hierarchy": "",
            "language_id": self.GRAMMAR_NAME,
        }
