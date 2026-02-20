"""Template for creating new grammar handlers.

Grammar handlers provide domain-specific chunking and metadata for files
that share a base language but have distinct structure. For example,
GitHub Actions workflows are YAML files with a specific schema.

Copy this file to <grammar_name>.py and implement the TODOs.

For language handlers (matched by extension), see handlers/_template.py instead.
"""

import re

import cocoindex

from cocosearch.handlers.grammars._base import YamlGrammarBase


class TemplateGrammarHandler(YamlGrammarBase):
    """Grammar handler for <GRAMMAR> files.

    TODO: Replace <GRAMMAR> with grammar name (e.g., "GitHub Actions").
    """

    # TODO: Unique grammar identifier (lowercase, hyphenated)
    GRAMMAR_NAME = "template-grammar"

    # TODO: Base language this grammar extends (override if not "yaml")
    # BASE_LANGUAGE = "yaml"  # inherited from YamlGrammarBase

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

    # TODO: Define additional regex patterns for metadata extraction
    _BLOCK_RE = re.compile(r"^some_pattern")

    def _has_content_markers(self, content: str) -> bool:
        """Check if file content has grammar-specific markers.

        TODO: Implement content validation (e.g., check for required keys).

        Args:
            content: File content string.

        Returns:
            True if content matches this grammar's expectations.
        """
        return True  # TODO: Add content checks

    def _extract_grammar_metadata(self, stripped: str, text: str) -> dict | None:
        """Extract grammar-specific metadata from chunk text.

        TODO: Implement metadata extraction logic. Return a dict to stop
        the fallback chain, or None to use the default (document/value/empty).

        Args:
            stripped: Comment-stripped text.
            text: Original text (for patterns that need comments/whitespace).

        Returns:
            Dict with block_type, hierarchy, language_id, or None for fallback.
        """
        # TODO: Add extraction logic using self._make_result()
        # Example: return self._make_result("job", f"job:{name}")
        return None
