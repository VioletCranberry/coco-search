"""Handler for Go Template files.

Provides language-aware chunking and metadata extraction for Go template
files commonly used in Helm charts and other Go-based templating systems.

Handles .tpl and .gotmpl file extensions.
"""

import re

import cocoindex


class GoTmplHandler:
    """Handler for Go Template files."""

    EXTENSIONS = [".tpl", ".gotmpl"]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="gotmpl",
        separators_regex=[
            # Level 1: template define blocks (each is a "function")
            r"\n\{\{-? define ",
            # Level 2: Go template comment blocks (docs for defines)
            r"\n\{\{/\*",
            # Level 3: blank lines
            r"\n\n+",
            # Level 4: single newlines
            r"\n",
            # Level 5: whitespace
            r" ",
        ],
        aliases=["tpl"],
    )

    # Match {{- define "chart-name.helper-name" -}} or {{define "name"}}
    _DEFINE_RE = re.compile(r'\{\{-?\s*define\s+"([^"]+)"')

    # Go template comment lines
    _COMMENT_LINE = re.compile(r"^\s*\{\{/\*.*$", re.MULTILINE)

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from Go Template chunk.

        Identifies define blocks and extracts the template name.

        Args:
            text: The chunk text content.

        Returns:
            Dict with metadata fields:
            - block_type: "define" for template define blocks
            - hierarchy: "define:<name>" where name is the template name
            - language_id: "gotmpl"

        Example:
            Input: '{{- define "mychart.labels" -}}'
            Output: {
                "block_type": "define",
                "hierarchy": "define:mychart.labels",
                "language_id": "gotmpl"
            }
        """
        stripped = self._strip_comments(text)

        match = self._DEFINE_RE.search(stripped)
        if match:
            name = match.group(1)
            return {
                "block_type": "define",
                "hierarchy": f"define:{name}",
                "language_id": "gotmpl",
            }

        return {"block_type": "", "hierarchy": "", "language_id": "gotmpl"}

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
