"""Grammar handler for Helm template YAML files.

Provides domain-specific chunking and metadata extraction for Kubernetes
manifest templates rendered by Helm with Go template directives.

Matches: templates/*.yaml, templates/**/*.yaml (with Helm content markers)
Content markers: {{ .Values, {{ .Release, {{ .Chart, {{ include
"""

import re

import cocoindex

from cocosearch.handlers.grammars._base import YamlGrammarBase

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


class HelmTemplateHandler(YamlGrammarBase):
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

    # Go template define block: {{- define "mychart.fullname" }}
    _DEFINE_RE = re.compile(r'\{\{-?\s*define\s+"([^"]+)"')

    # Match K8s kind field
    _KIND_RE = re.compile(r"^kind:\s*(\S+)", re.MULTILINE)

    # Match Go template control flow
    _CONTROL_RE = re.compile(r"\{\{-?\s*(if|range|with)\b")

    def _has_content_markers(self, content: str) -> bool:
        return any(marker in content for marker in _HELM_MARKERS)

    def _extract_grammar_metadata(self, stripped: str, text: str) -> dict | None:
        """Extract metadata from Helm template chunk.

        Identifies Go template definitions, K8s resource kinds, Go template
        control flow, YAML structural keys, document separators, and value
        continuations.

        Examples:
            Define chunk: block_type="define", hierarchy="define:mychart.fullname"
            Kind chunk: block_type="Deployment", hierarchy="kind:Deployment"
            Control flow: block_type="if", hierarchy="if"
            Key chunk: block_type="key", hierarchy="key:containers"
            Nested key: block_type="nested-key", hierarchy="nested-key:ports"
            List item: block_type="list-item", hierarchy="list-item:name"
            Top-level: block_type="metadata", hierarchy="metadata"
        """
        # Check for Go template define block
        define_match = self._DEFINE_RE.search(stripped)
        if define_match:
            name = define_match.group(1)
            return self._make_result("define", f"define:{name}")

        # Check for K8s kind
        kind_match = self._KIND_RE.search(stripped)
        if kind_match:
            kind = kind_match.group(1)
            return self._make_result(kind, f"kind:{kind}")

        # Check for Go template control flow
        control_match = self._CONTROL_RE.search(stripped)
        if control_match:
            control_type = control_match.group(1)
            return self._make_result(control_type, control_type)

        # Check for 2-space indented YAML key
        item_match = self._ITEM_RE.match(stripped)
        if item_match:
            key = item_match.group(1)
            return self._make_result("key", f"key:{key}")

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

        # Check for top-level YAML key
        top_match = self._TOP_KEY_RE.match(stripped)
        if top_match:
            key = top_match.group(1)
            return self._make_result(key, key)

        return None
