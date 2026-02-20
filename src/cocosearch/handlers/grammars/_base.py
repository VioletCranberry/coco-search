"""Base class for YAML-based grammar handlers.

Provides shared functionality for grammar handlers that operate on YAML files:
- Comment stripping
- Path-based matching with content marker validation
- Fallback metadata chain (document -> value -> empty)
- Result construction helper

Subclasses must define:
- GRAMMAR_NAME, BASE_LANGUAGE, PATH_PATTERNS, SEPARATOR_SPEC
- _has_content_markers(content): content validation for matches()
- _extract_grammar_metadata(stripped): grammar-specific metadata extraction
"""

import fnmatch
import re


class YamlGrammarBase:
    """Base class for YAML-based grammar handlers.

    Provides shared comment stripping, matching, and fallback metadata chain.
    Subclasses implement _has_content_markers() and _extract_grammar_metadata().
    """

    BASE_LANGUAGE = "yaml"

    # Shared regex patterns (subclasses can override)
    _COMMENT_LINE = re.compile(r"^\s*#.*$", re.MULTILINE)
    _TOP_KEY_RE = re.compile(r"^([a-zA-Z_][\w-]*):", re.MULTILINE)
    _ITEM_RE = re.compile(r"^  ([a-zA-Z_][\w-]*):", re.MULTILINE)
    _NESTED_KEY_RE = re.compile(r"^\s{4,}([a-zA-Z_][\w-]*):", re.MULTILINE)
    _LIST_ITEM_KEY_RE = re.compile(r"^\s*-\s+([a-zA-Z_][\w-]*):", re.MULTILINE)

    def _strip_comments(self, text: str) -> str:
        """Strip leading comments from chunk text, preserving indentation."""
        lines = text.lstrip("\n").split("\n")
        for i, line in enumerate(lines):
            if line.strip() and not self._COMMENT_LINE.match(line):
                return "\n".join(lines[i:])
        return ""

    def _make_result(self, block_type: str, hierarchy: str) -> dict:
        """Build metadata dict with GRAMMAR_NAME as language_id."""
        return {
            "block_type": block_type,
            "hierarchy": hierarchy,
            "language_id": self.GRAMMAR_NAME,
        }

    def matches(self, filepath: str, content: str | None = None) -> bool:
        """Check if this grammar applies to the given file.

        Uses fnmatch with */{pattern} idiom so files are detected at any depth.
        When content is provided, delegates to _has_content_markers() for validation.

        Args:
            filepath: Relative file path within the project.
            content: Optional file content for deeper matching.

        Returns:
            True if this grammar should handle the file.
        """
        for pattern in self.PATH_PATTERNS:
            if fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(
                filepath, f"*/{pattern}"
            ):
                if content is not None:
                    return self._has_content_markers(content)
                return True
        return False

    def _has_content_markers(self, content: str) -> bool:
        """Check if file content has grammar-specific markers.

        Subclasses must override this to validate content.

        Args:
            content: File content string.

        Returns:
            True if content matches this grammar's expectations.
        """
        raise NotImplementedError

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from chunk text.

        Calls _extract_grammar_metadata() for grammar-specific logic,
        then falls through to shared fallback chain:
        document separator -> value continuation -> empty.

        Args:
            text: The chunk text content.

        Returns:
            Dict with block_type, hierarchy, language_id.
        """
        stripped = self._strip_comments(text)

        # Grammar-specific extraction
        result = self._extract_grammar_metadata(stripped, text)
        if result is not None:
            return result

        # Shared fallback chain
        if "---" in text:
            return self._make_result("document", "document")

        if stripped:
            return self._make_result("value", "value")

        return self._make_result("", "")

    def _extract_grammar_metadata(self, stripped: str, text: str) -> dict | None:
        """Extract grammar-specific metadata from stripped text.

        Subclasses must override this to implement their extraction logic.
        Return a dict to stop the chain, or None to fall through to defaults.

        Args:
            stripped: Comment-stripped text.
            text: Original text (for patterns that need comments/whitespace).

        Returns:
            Dict with block_type, hierarchy, language_id, or None for fallback.
        """
        raise NotImplementedError
