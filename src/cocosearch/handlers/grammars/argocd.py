"""Grammar handler for ArgoCD manifest YAML files.

Provides domain-specific chunking and metadata extraction for ArgoCD
Application, ApplicationSet, and AppProject custom resources.

Matches: *.yaml, *.yml (broad -- content validation filters to ArgoCD manifests)
Content markers: 'apiVersion:' with 'argoproj.io/' and 'kind:'
"""

import fnmatch
import re

from cocoindex.ops.text import CustomLanguageConfig

from cocosearch.handlers.grammars._base import YamlGrammarBase
from cocosearch.handlers.grammars.helm_template import _HELM_MARKERS

_ARGOCD_MARKER = "argoproj.io/"


class ArgoCDHandler(YamlGrammarBase):
    """Grammar handler for ArgoCD manifest YAML files."""

    GRAMMAR_NAME = "argocd"
    PATH_PATTERNS = ["*.yaml", "*.yml"]

    SEPARATOR_SPEC = CustomLanguageConfig(
        language_name="argocd",
        separators_regex=[
            # Level 1: YAML document separator (multi-resource files)
            r"\n---",
            # Level 2: ArgoCD resource boundary
            r"\napiVersion:",
            # Level 3: Top-level keys (kind, metadata, spec, operation, status)
            r"\n[a-zA-Z_][\w-]*:",
            # Level 4: Second-level keys (source, destination, syncPolicy)
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

    # Match ArgoCD kind field
    _KIND_RE = re.compile(r"^kind:\s*(\S+)", re.MULTILINE)

    # ArgoCD CRD kinds
    _ARGOCD_KINDS = frozenset({"Application", "ApplicationSet", "AppProject"})

    # ArgoCD top-level keywords
    _TOP_LEVEL_KEYS = frozenset(
        {
            "apiVersion",
            "kind",
            "metadata",
            "spec",
            "operation",
            "status",
        }
    )

    def matches(self, filepath: str, content: str | None = None) -> bool:
        """Check if file is an ArgoCD manifest.

        Uses broad path patterns (any YAML file), so always requires content
        validation. Returns False when content is None.

        Args:
            filepath: Relative file path within the project.
            content: Optional file content for deeper matching.

        Returns:
            True if this is an ArgoCD manifest file.
        """
        basename = filepath.rsplit("/", 1)[-1] if "/" in filepath else filepath
        for pattern in self.PATH_PATTERNS:
            if fnmatch.fnmatch(basename, pattern):
                if content is None:
                    return False
                if "apiVersion:" not in content or "kind:" not in content:
                    return False
                if _ARGOCD_MARKER not in content:
                    return False
                if any(marker in content for marker in _HELM_MARKERS):
                    return False
                return True
        return False

    def _has_content_markers(self, content: str) -> bool:
        # Not used -- matches() is fully overridden
        return (
            "apiVersion:" in content
            and "kind:" in content
            and _ARGOCD_MARKER in content
        )

    def _extract_grammar_metadata(self, stripped: str, text: str) -> dict | None:
        """Extract metadata from ArgoCD manifest chunk.

        Identifies ArgoCD resource kinds (Application, ApplicationSet, AppProject),
        then falls through to section-key/nested-key/list-item/top-level-key.

        Examples:
            Kind chunk: block_type="Application", hierarchy="kind:Application"
            Section key: block_type="section-key", hierarchy="section-key:source"
            Nested: block_type="nested-key", hierarchy="nested-key:repoURL"
            List item: block_type="list-item", hierarchy="list-item:name"
        """
        # Check for ArgoCD kind
        kind_match = self._KIND_RE.search(stripped)
        if kind_match:
            kind = kind_match.group(1)
            return self._make_result(kind, f"kind:{kind}")

        # Check for section key (2-space indented)
        item_match = self._ITEM_RE.match(stripped)
        if item_match:
            key = item_match.group(1)
            return self._make_result("section-key", f"section-key:{key}")

        # Check for nested key (4+ space indented)
        nested_match = self._NESTED_KEY_RE.match(stripped)
        if nested_match:
            key = nested_match.group(1)
            return self._make_result("nested-key", f"nested-key:{key}")

        # Check for YAML list item key (e.g., "- name: value")
        list_match = self._LIST_ITEM_KEY_RE.match(stripped)
        if list_match:
            key = list_match.group(1)
            return self._make_result("list-item", f"list-item:{key}")

        # Check for top-level section key
        top_match = self._TOP_KEY_RE.match(stripped)
        if top_match:
            key = top_match.group(1)
            return self._make_result(key, key)

        return None
