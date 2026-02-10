"""Grammar handler for Helm values.yaml files.

Provides domain-specific chunking and metadata extraction for Helm chart
values files, which can be large (up to 40KB) with section markers.

Matches: values.yaml, values-*.yaml (with 3+ common Helm keys)
"""

import fnmatch
import re

import cocoindex

# Common top-level keys found in Helm values.yaml files
_HELM_VALUES_KEYS = [
    "replicaCount:",
    "image:",
    "nameOverride:",
    "fullnameOverride:",
    "serviceAccount:",
    "service:",
    "ingress:",
    "resources:",
    "nodeSelector:",
    "tolerations:",
    "affinity:",
]

# Minimum number of keys required to match as Helm values
_MIN_KEY_MATCHES = 3


class HelmValuesHandler:
    """Grammar handler for Helm values.yaml files."""

    GRAMMAR_NAME = "helm-values"
    BASE_LANGUAGE = "yaml"
    PATH_PATTERNS = ["**/values.yaml", "**/values-*.yaml"]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="helm-values",
        separators_regex=[
            # Level 1: annotated section boundaries
            r"\n## @section ",
            # Level 2: comment section headers
            r"\n## ",
            # Level 3: top-level YAML keys (no indent)
            r"\n[a-zA-Z_][\w-]*:",
            # Level 4: blank lines
            r"\n\n+",
            # Level 5: newlines
            r"\n",
            # Level 6: whitespace
            r" ",
        ],
        aliases=[],
    )

    _COMMENT_LINE = re.compile(r"^\s*#.*$", re.MULTILINE)

    # Match ## @section annotations
    _SECTION_RE = re.compile(r"^## @section\s+(.+)$", re.MULTILINE)

    # Match top-level YAML key (no indentation)
    _TOP_KEY_RE = re.compile(r"^([a-zA-Z_][\w-]*):", re.MULTILINE)

    # Match top-level key at start of line for content detection
    _TOP_LEVEL_KEY_RE = re.compile(r"^[a-zA-Z_][\w-]*:", re.MULTILINE)

    def matches(self, filepath: str, content: str | None = None) -> bool:
        """Check if file is a Helm values file.

        Matches by path pattern and verifies content has 3+ common Helm keys.

        Args:
            filepath: Relative file path within the project.
            content: Optional file content for deeper matching.

        Returns:
            True if this is a Helm values file.
        """
        for pattern in self.PATH_PATTERNS:
            if fnmatch.fnmatch(filepath, pattern):
                if content is not None:
                    return self._has_helm_keys(content)
                return True
        return False

    def _has_helm_keys(self, content: str) -> bool:
        """Check if content has enough common Helm values keys."""
        count = sum(1 for key in _HELM_VALUES_KEYS if key in content)
        return count >= _MIN_KEY_MATCHES

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from Helm values chunk.

        Identifies section annotations and top-level YAML keys.

        Args:
            text: The chunk text content.

        Returns:
            Dict with block_type, hierarchy, language_id.

        Examples:
            Section: block_type="section", hierarchy="section:Global parameters"
            Key: block_type="key", hierarchy="key:image"
        """
        stripped = self._strip_comments_for_key(text)

        # Check for @section annotation
        section_match = self._SECTION_RE.search(text)
        if section_match:
            section_name = section_match.group(1).strip()
            return {
                "block_type": "section",
                "hierarchy": f"section:{section_name}",
                "language_id": self.GRAMMAR_NAME,
            }

        # Check for top-level key
        key_match = self._TOP_KEY_RE.match(stripped)
        if key_match:
            key_name = key_match.group(1)
            return {
                "block_type": "key",
                "hierarchy": f"key:{key_name}",
                "language_id": self.GRAMMAR_NAME,
            }

        return {
            "block_type": "",
            "hierarchy": "",
            "language_id": self.GRAMMAR_NAME,
        }

    def _strip_comments_for_key(self, text: str) -> str:
        """Strip leading comments for key detection (not section detection).

        Preserves indentation so that indented keys are not matched as
        top-level keys by _TOP_KEY_RE.

        Args:
            text: The chunk text content.

        Returns:
            Text from first non-comment, non-blank line onward
        """
        lines = text.lstrip("\n").split("\n")
        for i, line in enumerate(lines):
            if line.strip() and not self._COMMENT_LINE.match(line):
                return "\n".join(lines[i:])
        return ""
