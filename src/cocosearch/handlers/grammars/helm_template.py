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
]


class HelmTemplateHandler:
    """Grammar handler for Helm template YAML files."""

    GRAMMAR_NAME = "helm-template"
    BASE_LANGUAGE = "yaml"
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
            # Level 3: Go template conditionals
            r"\n\{\{-? if ",
            # Level 4: Go template loops
            r"\n\{\{-? range ",
            # Level 5: Go template scoping
            r"\n\{\{-? with ",
            # Level 6: else branches
            r"\n\{\{-? else",
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

    # Match K8s kind field
    _KIND_RE = re.compile(r"^kind:\s*(\S+)", re.MULTILINE)

    # Match Go template control flow
    _CONTROL_RE = re.compile(r"\{\{-?\s*(if|range|with)\b")

    def matches(self, filepath: str, content: str | None = None) -> bool:
        """Check if file is a Helm template.

        Args:
            filepath: Relative file path within the project.
            content: Optional file content for deeper matching.

        Returns:
            True if this is a Helm template file.
        """
        for pattern in self.PATH_PATTERNS:
            if fnmatch.fnmatch(filepath, pattern):
                if content is not None:
                    return any(marker in content for marker in _HELM_MARKERS)
                return True
        return False

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from Helm template chunk.

        Identifies K8s resource kinds and Go template control flow blocks.

        Args:
            text: The chunk text content.

        Returns:
            Dict with block_type, hierarchy, language_id.

        Examples:
            Kind chunk: block_type="Deployment", hierarchy="kind:Deployment"
            Control flow: block_type="if", hierarchy="if"
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

        # Check for Go template control flow
        control_match = self._CONTROL_RE.search(stripped)
        if control_match:
            control_type = control_match.group(1)
            return {
                "block_type": control_type,
                "hierarchy": control_type,
                "language_id": self.GRAMMAR_NAME,
            }

        return {
            "block_type": "",
            "hierarchy": "",
            "language_id": self.GRAMMAR_NAME,
        }

    def _strip_comments(self, text: str) -> str:
        """Strip leading comments from chunk text."""
        lines = text.lstrip().split("\n")
        for i, line in enumerate(lines):
            if line.strip() and not self._COMMENT_LINE.match(line):
                return "\n".join(lines[i:])
        return ""
