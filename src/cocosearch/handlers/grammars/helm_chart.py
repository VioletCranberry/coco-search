"""Grammar handler for Helm Chart.yaml files.

Provides domain-specific chunking and metadata extraction for Helm chart
definition files containing chart metadata and dependency declarations.

Matches: Chart.yaml, Chart.yml (with apiVersion: and name: markers)
"""

import re

import cocoindex

from cocosearch.handlers.grammars._base import YamlGrammarBase


class HelmChartHandler(YamlGrammarBase):
    """Grammar handler for Helm Chart.yaml files."""

    GRAMMAR_NAME = "helm-chart"
    PATH_PATTERNS = ["**/Chart.yaml", "**/Chart.yml"]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="helm-chart",
        separators_regex=[
            # Level 1: YAML document separator
            r"\n---",
            # Level 2: top-level YAML keys (no indent)
            r"\n[a-zA-Z_][\w-]*:",
            # Level 3: YAML list items
            r"\n\s*- ",
            # Level 4: nested keys (2+ space indent)
            r"\n\s{2,}[a-zA-Z_][\w-]*:",
            # Level 5: blank lines
            r"\n\n+",
            # Level 6: newlines
            r"\n",
            # Level 7: whitespace
            r" ",
        ],
        aliases=[],
    )

    # Match dependency list item: "- name: X"
    _DEP_NAME_RE = re.compile(r"^\s*-\s+name:\s*(\S+)", re.MULTILINE)

    def _has_content_markers(self, content: str) -> bool:
        """Check if content has both apiVersion: and name: markers."""
        return "apiVersion:" in content and "name:" in content

    def _extract_grammar_metadata(self, stripped: str, text: str) -> dict | None:
        """Extract metadata from Helm Chart.yaml chunk.

        Identifies dependency list items and top-level keys.

        Examples:
            Dependency: block_type="dependency", hierarchy="dependency:postgresql"
            Key: block_type="key", hierarchy="key:name"
        """
        # Check for dependency list item (- name: X)
        dep_match = self._DEP_NAME_RE.match(stripped)
        if dep_match:
            dep_name = dep_match.group(1)
            return self._make_result("dependency", f"dependency:{dep_name}")

        # Check for YAML list item key
        list_match = self._LIST_ITEM_KEY_RE.match(stripped)
        if list_match:
            key_name = list_match.group(1)
            return self._make_result("list-item", f"list-item:{key_name}")

        # Check for top-level key
        key_match = self._TOP_KEY_RE.match(stripped)
        if key_match:
            key_name = key_match.group(1)
            return self._make_result("key", f"key:{key_name}")

        return None
