"""Helm dependency extractor.

Extracts references from Helm template and values files:
- **helm-template**: ``{{ include "name" }}`` and ``{{ template "name" }}``
  template inclusions, ``{{ .Values.X }}`` value references
- **helm-values**: ``image.repository``/``image.tag`` container image refs

Also handles ``Chart.yaml`` subchart dependencies when language_id
matches (detected by filename).

All edges use ``dep_type = DepType.REFERENCE``.
"""

import re

import yaml

from cocosearch.deps.models import DependencyEdge, DepType

# Match {{ include "template-name" ... }} and {{ template "name" ... }}
_INCLUDE_RE = re.compile(r'\{\{-?\s*include\s+"([^"]+)"')
_TEMPLATE_RE = re.compile(r'\{\{-?\s*template\s+"([^"]+)"')

# Match {{ .Values.X.Y.Z ... }}
_VALUES_REF_RE = re.compile(r'\{\{-?\s*\.Values\.([\w.]+)')


class HelmExtractor:
    """Extractor for Helm template and values reference edges."""

    LANGUAGES: set[str] = {"helm-template", "helm-values"}

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        if not content:
            return []

        # Detect Chart.yaml by filename
        if file_path.endswith("Chart.yaml") or file_path.endswith("Chart.yml"):
            return self._extract_chart_yaml(content)

        # Detect values files by path pattern
        basename = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
        if basename.startswith("values") and (
            basename.endswith(".yaml") or basename.endswith(".yml")
        ):
            return self._extract_values(content)

        # Default: treat as template file
        return self._extract_template(content)

    def _extract_template(self, content: str) -> list[DependencyEdge]:
        """Extract template references from a Helm template file."""
        edges: list[DependencyEdge] = []

        for match in _INCLUDE_RE.finditer(content):
            name = match.group(1)
            edges.append(
                DependencyEdge(
                    source_file="",
                    source_symbol=None,
                    target_file=None,
                    target_symbol=name,
                    dep_type=DepType.REFERENCE,
                    metadata={"kind": "include", "name": name},
                )
            )

        for match in _TEMPLATE_RE.finditer(content):
            name = match.group(1)
            edges.append(
                DependencyEdge(
                    source_file="",
                    source_symbol=None,
                    target_file=None,
                    target_symbol=name,
                    dep_type=DepType.REFERENCE,
                    metadata={"kind": "template", "name": name},
                )
            )

        seen_refs: set[str] = set()
        for match in _VALUES_REF_RE.finditer(content):
            ref = match.group(1)
            if ref not in seen_refs:
                seen_refs.add(ref)
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=None,
                        target_file=None,
                        target_symbol=None,
                        dep_type=DepType.REFERENCE,
                        metadata={"kind": "values_ref", "name": ref},
                    )
                )

        return edges

    def _extract_values(self, content: str) -> list[DependencyEdge]:
        """Extract image references from a Helm values file."""
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError:
            return []

        if not isinstance(data, dict):
            return []

        edges: list[DependencyEdge] = []
        self._find_image_refs(data, edges, [])
        return edges

    def _find_image_refs(
        self, data: dict, edges: list[DependencyEdge], path: list[str]
    ) -> None:
        """Recursively find image references in a values dict."""
        if not isinstance(data, dict):
            return

        # Check for image.repository pattern
        if "repository" in data and isinstance(data["repository"], str):
            repo = data["repository"]
            tag = data.get("tag", "latest")
            ref = f"{repo}:{tag}" if isinstance(tag, str) else repo
            edges.append(
                DependencyEdge(
                    source_file="",
                    source_symbol=".".join(path) if path else None,
                    target_file=None,
                    target_symbol=None,
                    dep_type=DepType.REFERENCE,
                    metadata={"kind": "image", "name": ref},
                )
            )

        for key, value in data.items():
            if isinstance(value, dict):
                self._find_image_refs(value, edges, path + [key])

    def _extract_chart_yaml(self, content: str) -> list[DependencyEdge]:
        """Extract subchart dependencies from Chart.yaml."""
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError:
            return []

        if not isinstance(data, dict):
            return []

        edges: list[DependencyEdge] = []
        dependencies = data.get("dependencies", [])
        if not isinstance(dependencies, list):
            return edges

        for dep in dependencies:
            if not isinstance(dep, dict):
                continue
            name = dep.get("name")
            if not isinstance(name, str):
                continue

            repository = dep.get("repository", "")
            version = dep.get("version", "")
            is_local = isinstance(repository, str) and (
                repository.startswith("file://") or repository.startswith("./")
            )

            target_file = None
            if is_local:
                # Strip file:// prefix
                local_path = repository
                if local_path.startswith("file://"):
                    local_path = local_path[7:]
                if local_path.startswith("./"):
                    local_path = local_path[2:]
                target_file = local_path

            edges.append(
                DependencyEdge(
                    source_file="",
                    source_symbol=None,
                    target_file=target_file,
                    target_symbol=name,
                    dep_type=DepType.REFERENCE,
                    metadata={
                        "kind": "subchart",
                        "name": name,
                        "version": str(version),
                        "repository": str(repository),
                    },
                )
            )

        return edges
