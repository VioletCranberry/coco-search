"""Grammar handler for Helm values.yaml files.

Provides domain-specific chunking and metadata extraction for Helm chart
values files, which can be large (up to 40KB) with section markers.

Matches: values.yaml, values-*.yaml (with 3+ common Helm keys)
"""

import re

import cocoindex

from cocosearch.handlers.grammars._base import YamlGrammarBase

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


class HelmValuesHandler(YamlGrammarBase):
    """Grammar handler for Helm values.yaml files."""

    GRAMMAR_NAME = "helm-values"
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
            # Level 4: second-level keys (2-space indent)
            r"\n  [a-zA-Z_][\w-]*:",
            # Level 5: third-level keys (4-space indent)
            r"\n    [a-zA-Z_][\w-]*:",
            # Level 6: blank lines
            r"\n\n+",
            # Level 7: newlines
            r"\n",
            # Level 8: whitespace
            r" ",
        ],
        aliases=[],
    )

    # Match ## @section annotations
    _SECTION_RE = re.compile(r"^## @section\s+(.+)$", re.MULTILINE)

    # Match indented YAML key (any indentation level)
    _NESTED_KEY_RE = re.compile(r"^\s+([a-zA-Z_][\w-]*):", re.MULTILINE)

    # Match top-level key at start of line for content detection
    _TOP_LEVEL_KEY_RE = re.compile(r"^[a-zA-Z_][\w-]*:", re.MULTILINE)

    def _has_content_markers(self, content: str) -> bool:
        """Check if content has enough common Helm values keys."""
        count = sum(1 for key in _HELM_VALUES_KEYS if key in content)
        return count >= _MIN_KEY_MATCHES

    def _extract_grammar_metadata(self, stripped: str, text: str) -> dict | None:
        """Extract metadata from Helm values chunk.

        Identifies section annotations, top-level keys, nested keys,
        list items, value continuations, and document separators.

        Examples:
            Section: block_type="section", hierarchy="section:Global parameters"
            Key: block_type="key", hierarchy="key:image"
            Nested: block_type="nested-key", hierarchy="nested-key:receivers"
            List item: block_type="list-item", hierarchy="list-item:name"
            Value: block_type="value", hierarchy="value"
        """
        # Check for @section annotation (search in original text, not stripped)
        section_match = self._SECTION_RE.search(text)
        if section_match:
            section_name = section_match.group(1).strip()
            return self._make_result("section", f"section:{section_name}")

        # Check for top-level key
        key_match = self._TOP_KEY_RE.match(stripped)
        if key_match:
            key_name = key_match.group(1)
            return self._make_result("key", f"key:{key_name}")

        # Check for YAML list item key (e.g., "- name: value")
        list_match = self._LIST_ITEM_KEY_RE.match(stripped)
        if list_match:
            key_name = list_match.group(1)
            return self._make_result("list-item", f"list-item:{key_name}")

        # Check for nested/indented key (sub-section of a top-level key)
        nested_match = self._NESTED_KEY_RE.match(stripped)
        if nested_match:
            key_name = nested_match.group(1)
            return self._make_result("nested-key", f"nested-key:{key_name}")

        return None
