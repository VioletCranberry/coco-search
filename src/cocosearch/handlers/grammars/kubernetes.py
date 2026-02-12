"""Grammar handler for Kubernetes manifest YAML files.

Provides domain-specific chunking and metadata extraction for plain Kubernetes
manifests (Deployments, Services, ConfigMaps, etc.) without Helm directives.

Matches: *.yaml, *.yml (broad — content validation filters to K8s manifests)
Content markers: 'apiVersion:' and 'kind:'
"""

import fnmatch
import re

import cocoindex

from cocosearch.handlers.grammars.helm_template import _HELM_MARKERS


class KubernetesHandler:
    """Grammar handler for Kubernetes manifest YAML files."""

    GRAMMAR_NAME = "kubernetes"
    BASE_LANGUAGE = "yaml"
    PATH_PATTERNS = ["*.yaml", "*.yml"]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="kubernetes",
        separators_regex=[
            # Level 1: YAML document separator (multi-resource files)
            r"\n---",
            # Level 2: K8s resource boundary
            r"\napiVersion:",
            # Level 3: Top-level keys (kind, metadata, spec, data, status)
            r"\n[a-zA-Z_][\w-]*:",
            # Level 4: Second-level keys (name, namespace, replicas, containers)
            r"\n  [a-zA-Z_][\w-]*:",
            # Level 5: Blank lines
            r"\n\n+",
            # Level 6: Single newlines
            r"\n",
            # Level 7: Whitespace (last resort)
            r" ",
        ],
        aliases=[],
    )

    _COMMENT_LINE = re.compile(r"^\s*#.*$", re.MULTILINE)

    # Match K8s kind field
    _KIND_RE = re.compile(r"^kind:\s*(\S+)", re.MULTILINE)

    # Match top-level section key (at start of line, not indented)
    _TOP_KEY_RE = re.compile(r"^([a-zA-Z_][\w-]*):", re.MULTILINE)

    # Match YAML list item key (e.g., "- name: value", "  - name: value")
    _LIST_ITEM_KEY_RE = re.compile(r"^\s*-\s+([a-zA-Z_][\w-]*):", re.MULTILINE)

    # Match indented YAML key (any indentation level)
    _NESTED_KEY_RE = re.compile(r"^\s+([a-zA-Z_][\w-]*):", re.MULTILINE)

    def matches(self, filepath: str, content: str | None = None) -> bool:
        """Check if file is a Kubernetes manifest.

        Uses broad path patterns (any YAML file), so always requires content
        validation. Returns False when content is None.

        Args:
            filepath: Relative file path within the project.
            content: Optional file content for deeper matching.

        Returns:
            True if this is a Kubernetes manifest file.
        """
        basename = filepath.rsplit("/", 1)[-1] if "/" in filepath else filepath
        for pattern in self.PATH_PATTERNS:
            if fnmatch.fnmatch(basename, pattern):
                if content is None:
                    return False
                if "apiVersion:" not in content or "kind:" not in content:
                    return False
                if any(marker in content for marker in _HELM_MARKERS):
                    return False
                return True
        return False

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from Kubernetes manifest chunk.

        Identifies K8s resource kinds, top-level sections, nested keys,
        list items, and value continuations.

        Args:
            text: The chunk text content.

        Returns:
            Dict with block_type, hierarchy, language_id.

        Examples:
            Kind chunk: block_type="Deployment", hierarchy="kind:Deployment"
            Section chunk: block_type="spec", hierarchy="spec"
            Nested: block_type="nested-key", hierarchy="nested-key:containers"
            List item: block_type="list-item", hierarchy="list-item:name"
        """
        stripped = self._strip_comments(text)

        # Check for K8s kind
        kind_match = self._KIND_RE.search(stripped)
        if kind_match:
            kind = kind_match.group(1)
            return {
                "block_type": kind,
                "hierarchy": f"kind:{kind}",
                "language_id": self.GRAMMAR_NAME,
            }

        # Check for top-level section key
        top_match = self._TOP_KEY_RE.match(stripped)
        if top_match:
            key = top_match.group(1)
            return {
                "block_type": key,
                "hierarchy": key,
                "language_id": self.GRAMMAR_NAME,
            }

        # Check for YAML list item key (e.g., "- name: value")
        list_match = self._LIST_ITEM_KEY_RE.match(stripped)
        if list_match:
            key = list_match.group(1)
            return {
                "block_type": "list-item",
                "hierarchy": f"list-item:{key}",
                "language_id": self.GRAMMAR_NAME,
            }

        # Check for nested/indented key
        nested_match = self._NESTED_KEY_RE.match(stripped)
        if nested_match:
            key = nested_match.group(1)
            return {
                "block_type": "nested-key",
                "hierarchy": f"nested-key:{key}",
                "language_id": self.GRAMMAR_NAME,
            }

        # YAML document separator (--- header chunks)
        if "---" in text:
            return {
                "block_type": "document",
                "hierarchy": "document",
                "language_id": self.GRAMMAR_NAME,
            }

        # Value continuation (chunk has content but no recognizable key)
        if stripped:
            return {
                "block_type": "value",
                "hierarchy": "value",
                "language_id": self.GRAMMAR_NAME,
            }

        return {
            "block_type": "",
            "hierarchy": "",
            "language_id": self.GRAMMAR_NAME,
        }

    def _strip_comments(self, text: str) -> str:
        """Strip leading comments and document separators from chunk text."""
        from cocosearch.handlers.utils import strip_leading_comments

        return strip_leading_comments(text, [self._COMMENT_LINE], skip_strings=["---"])
