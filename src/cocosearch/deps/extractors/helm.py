"""Helm dependency extractor.

Extracts references from Helm template and values files:
- **helm-template**: ``{{ include "name" }}`` and ``{{ template "name" }}``
  template inclusions
- **helm-values**: chart membership edges linking values files to Chart.yaml

Also handles ``Chart.yaml`` subchart dependencies when language_id
matches (detected by filename).

All edges use ``dep_type = DepType.REFERENCE``.  Chart membership edges
carry ``is_subchart: True`` when the file belongs to a subchart
(i.e. its Chart.yaml sits inside a ``/charts/`` directory).
"""

import posixpath
import re

import yaml

from cocosearch.deps.models import DependencyEdge, DepType

# Match {{ include "template-name" ... }} and {{ template "name" ... }}
_INCLUDE_RE = re.compile(r'\{\{-?\s*include\s+"([^"]+)"')
_TEMPLATE_RE = re.compile(r'\{\{-?\s*template\s+"([^"]+)"')


class HelmExtractor:
    """Extractor for Helm template and values reference edges."""

    LANGUAGES: set[str] = {"helm-template", "helm-values", "helm-chart"}

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        if not content:
            return []

        # Detect Chart.yaml by filename
        if file_path.endswith("Chart.yaml") or file_path.endswith("Chart.yml"):
            edges = self._extract_chart_yaml(content, file_path)
            parent_edge = self._extract_subchart_parent(file_path)
            if parent_edge:
                edges.append(parent_edge)
            return edges

        # Detect values files by path pattern
        basename = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
        if basename.startswith("values") and (
            basename.endswith(".yaml") or basename.endswith(".yml")
        ):
            membership = self._extract_chart_membership(file_path, "values")
            return [membership] if membership else []

        # Default: treat as template file
        edges = self._extract_template(content)
        membership = self._extract_chart_membership(file_path, "template")
        if membership:
            edges.append(membership)
        return edges

    @staticmethod
    def _infer_chart_yaml(file_path: str, member_type: str) -> str | None:
        """Infer the Chart.yaml path for a file within a Helm chart.

        For templates: find /templates/ in path, chart root = everything before it.
        For values: parent directory is the chart root.

        Returns the inferred Chart.yaml path, or None if it can't be determined.
        """
        if member_type == "template":
            idx = file_path.find("/templates/")
            if idx == -1:
                return None
            chart_root = file_path[:idx]
            return f"{chart_root}/Chart.yaml"
        # values: parent directory is chart root
        if "/" not in file_path:
            return None
        chart_root = file_path.rsplit("/", 1)[0]
        return f"{chart_root}/Chart.yaml"

    def _extract_chart_membership(
        self, file_path: str, member_type: str
    ) -> DependencyEdge | None:
        """Create a chart membership edge from a template/values file to its Chart.yaml."""
        chart_yaml = self._infer_chart_yaml(file_path, member_type)
        if not chart_yaml:
            return None
        return DependencyEdge(
            source_file="",
            source_symbol=None,
            target_file=chart_yaml,
            target_symbol=None,
            dep_type=DepType.REFERENCE,
            metadata={"kind": "chart_member", "member_type": member_type}
            | ({"is_subchart": True} if "/charts/" in chart_yaml else {}),
        )

    @staticmethod
    def _extract_subchart_parent(file_path: str) -> DependencyEdge | None:
        """Create a subchart-to-parent edge for Chart.yaml inside a /charts/ directory."""
        idx = file_path.rfind("/charts/")
        if idx == -1:
            return None
        parent_root = file_path[:idx]
        return DependencyEdge(
            source_file="",
            source_symbol=None,
            target_file=f"{parent_root}/Chart.yaml",
            target_symbol=None,
            dep_type=DepType.REFERENCE,
            metadata={"kind": "subchart_of"},
        )

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

        return edges

    def _extract_chart_yaml(self, content: str, file_path: str) -> list[DependencyEdge]:
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

        chart_dir = posixpath.dirname(file_path)

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
                local_path = repository
                if local_path.startswith("file://"):
                    local_path = local_path[7:]
                resolved = posixpath.normpath(
                    posixpath.join(chart_dir, local_path) if chart_dir else local_path
                )
                target_file = resolved + "/Chart.yaml"

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
