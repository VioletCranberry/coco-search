"""Grammar handler for Helm template YAML files.

Provides domain-specific chunking and metadata extraction for Kubernetes
manifest templates rendered by Helm with Go template directives.

Matches: templates/*.yaml, templates/**/*.yaml (with Helm content markers)
Content markers: {{ .Values, {{ .Release, {{ .Chart, {{ include
"""

import fnmatch
import re

import cocoindex

# Helm-specific Go template markers (not found in Jinja2 or other systems)
_HELM_MARKERS = [
    "{{ .Values",
    "{{- .Values",
    "{{ .Release",
    "{{- .Release",
    "{{ .Chart",
    "{{- .Chart",
    "{{ include",
    "{{- include",
    "{{ template",
    "{{- template",
    "{{ define",
    "{{- define",
]


class HelmTemplateHandler:
    """Grammar handler for Helm template YAML files."""

    GRAMMAR_NAME = "helm-template"
    BASE_LANGUAGE = "gotmpl"
    PATH_PATTERNS = [
        "**/templates/*.yaml",
        "**/templates/**/*.yaml",
        "**/templates/*.yml",
        "**/templates/**/*.yml",
    ]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="helm-template",
        separators_regex=[
            # Level 1: YAML document separator
            r"\n---",
            # Level 2: K8s resource boundary
            r"\napiVersion:",
            # Level 3: Go template named definitions
            r"\n\{\{-? define ",
            # Level 4: Top-level YAML keys (metadata:, spec:, data:)
            r"\n[a-zA-Z_][\w-]*:\s*\n",
            # Level 5: Go template control flow (if, range, with, else)
            r"\n\{\{-? (?:if|range|with|else)",
            # Level 6: 2-space indented YAML keys (containers:, template:)
            r"\n  [a-zA-Z_][\w-]*:",
            # Level 7: blank lines
            r"\n\n+",
            # Level 8: newlines
            r"\n",
            # Level 9: whitespace
            r" ",
        ],
        aliases=[],
    )

    _COMMENT_LINE = re.compile(r"^\s*#.*$", re.MULTILINE)

    # Go template define block: {{- define "mychart.fullname" }}
    _DEFINE_RE = re.compile(r'\{\{-?\s*define\s+"([^"]+)"')

    # Match K8s kind field
    _KIND_RE = re.compile(r"^kind:\s*(\S+)", re.MULTILINE)

    # Match Go template control flow
    _CONTROL_RE = re.compile(r"\{\{-?\s*(if|range|with)\b")

    # Top-level key at start of line
    _TOP_KEY_RE = re.compile(r"^([a-zA-Z_][\w-]*):", re.MULTILINE)

    # 2-space indented key (spec section keys like containers:, template:)
    _ITEM_RE = re.compile(r"^  ([a-zA-Z_][\w-]*):", re.MULTILINE)

    # Nested key (4+ space indented key)
    _NESTED_KEY_RE = re.compile(r"^\s{4,}([a-zA-Z_][\w-]*):", re.MULTILINE)

    # YAML list item key (e.g., "- name: value", "  - containerPort: 80")
    _LIST_ITEM_KEY_RE = re.compile(r"^\s*-\s+([a-zA-Z_][\w-]*):", re.MULTILINE)

    def matches(self, filepath: str, content: str | None = None) -> bool:
        """Check if file is a Helm template.

        Uses fnmatch with */{pattern} idiom so templates/ files are
        detected at any depth.

        Args:
            filepath: Relative file path within the project.
            content: Optional file content for deeper matching.

        Returns:
            True if this is a Helm template file.
        """
        for pattern in self.PATH_PATTERNS:
            if fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(
                filepath, f"*/{pattern}"
            ):
                if content is not None:
                    return any(marker in content for marker in _HELM_MARKERS)
                return True
        return False

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from Helm template chunk.

        Identifies Go template definitions, K8s resource kinds, Go template
        control flow, YAML structural keys, document separators, and value
        continuations.

        Args:
            text: The chunk text content.

        Returns:
            Dict with block_type, hierarchy, language_id.

        Examples:
            Define chunk: block_type="define", hierarchy="define:mychart.fullname"
            Kind chunk: block_type="Deployment", hierarchy="kind:Deployment"
            Control flow: block_type="if", hierarchy="if"
            Key chunk: block_type="key", hierarchy="key:containers"
            Nested key: block_type="nested-key", hierarchy="nested-key:ports"
            List item: block_type="list-item", hierarchy="list-item:name"
            Top-level: block_type="metadata", hierarchy="metadata"
        """
        stripped = self._strip_comments(text)

        # Check for Go template define block
        define_match = self._DEFINE_RE.search(stripped)
        if define_match:
            name = define_match.group(1)
            return {
                "block_type": "define",
                "hierarchy": f"define:{name}",
                "language_id": self.GRAMMAR_NAME,
            }

        # Check for K8s kind
        kind_match = self._KIND_RE.search(stripped)
        if kind_match:
            kind = kind_match.group(1)
            return {
                "block_type": kind,
                "hierarchy": f"kind:{kind}",
                "language_id": self.GRAMMAR_NAME,
            }

        # Check for Go template control flow
        control_match = self._CONTROL_RE.search(stripped)
        if control_match:
            control_type = control_match.group(1)
            return {
                "block_type": control_type,
                "hierarchy": control_type,
                "language_id": self.GRAMMAR_NAME,
            }

        # Check for 2-space indented YAML key
        item_match = self._ITEM_RE.match(stripped)
        if item_match:
            key = item_match.group(1)
            return {
                "block_type": "key",
                "hierarchy": f"key:{key}",
                "language_id": self.GRAMMAR_NAME,
            }

        # Check for nested key (4+ space indented)
        nested_match = self._NESTED_KEY_RE.match(stripped)
        if nested_match:
            key = nested_match.group(1)
            return {
                "block_type": "nested-key",
                "hierarchy": f"nested-key:{key}",
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

        # Check for top-level YAML key
        top_match = self._TOP_KEY_RE.match(stripped)
        if top_match:
            key = top_match.group(1)
            return {
                "block_type": key,
                "hierarchy": key,
                "language_id": self.GRAMMAR_NAME,
            }

        # YAML document separator (--- chunks)
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
        """Strip leading comments from chunk text, preserving indentation."""
        lines = text.lstrip("\n").split("\n")
        for i, line in enumerate(lines):
            if line.strip() and not self._COMMENT_LINE.match(line):
                return "\n".join(lines[i:])
        return ""
