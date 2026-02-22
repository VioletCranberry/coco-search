"""Tests for cocosearch.deps.extractors.helm module."""

from cocosearch.deps.extractors.helm import HelmExtractor
from cocosearch.deps.models import DepType


def _extract(content: str, file_path: str = "templates/deployment.yaml"):
    extractor = HelmExtractor()
    return extractor.extract(file_path, content)


# ============================================================================
# Tests: Template references
# ============================================================================


class TestTemplateIncludes:
    """Tests for template include/template references."""

    def test_include_ref(self):
        content = '{{ include "mychart.fullname" . }}'
        edges = _extract(content)
        includes = [e for e in edges if e.metadata.get("kind") == "include"]
        assert len(includes) == 1
        assert includes[0].metadata["name"] == "mychart.fullname"
        assert includes[0].target_symbol == "mychart.fullname"
        assert includes[0].dep_type == DepType.REFERENCE

    def test_template_ref(self):
        content = '{{ template "mychart.labels" . }}'
        edges = _extract(content)
        tmpl = [e for e in edges if e.metadata.get("kind") == "template"]
        assert len(tmpl) == 1
        assert tmpl[0].metadata["name"] == "mychart.labels"

    def test_include_with_dash(self):
        content = '{{- include "mychart.name" . -}}'
        edges = _extract(content)
        includes = [e for e in edges if e.metadata.get("kind") == "include"]
        assert len(includes) == 1
        assert includes[0].metadata["name"] == "mychart.name"


class TestValuesReferences:
    """Tests for .Values.X template references."""

    def test_values_ref(self):
        content = '{{ .Values.replicaCount }}'
        edges = _extract(content)
        refs = [e for e in edges if e.metadata.get("kind") == "values_ref"]
        assert len(refs) == 1
        assert refs[0].metadata["name"] == "replicaCount"

    def test_nested_values_ref(self):
        content = '{{ .Values.image.repository }}'
        edges = _extract(content)
        refs = [e for e in edges if e.metadata.get("kind") == "values_ref"]
        assert len(refs) == 1
        assert refs[0].metadata["name"] == "image.repository"

    def test_deduplicated_values_refs(self):
        content = """\
{{ .Values.replicaCount }}
{{ .Values.replicaCount }}
"""
        edges = _extract(content)
        refs = [e for e in edges if e.metadata.get("kind") == "values_ref"]
        assert len(refs) == 1


# ============================================================================
# Tests: Values file image references
# ============================================================================


class TestValuesFileImages:
    """Tests for image extraction from values files."""

    def test_image_ref(self):
        content = """\
image:
  repository: nginx
  tag: "1.21"
"""
        edges = _extract(content, file_path="values.yaml")
        images = [e for e in edges if e.metadata.get("kind") == "image"]
        assert len(images) == 1
        assert images[0].metadata["name"] == "nginx:1.21"

    def test_nested_image_ref(self):
        content = """\
web:
  image:
    repository: myapp
    tag: latest
"""
        edges = _extract(content, file_path="values.yaml")
        images = [e for e in edges if e.metadata.get("kind") == "image"]
        assert len(images) == 1
        assert images[0].metadata["name"] == "myapp:latest"

    def test_image_without_tag_defaults_to_latest(self):
        content = """\
image:
  repository: nginx
"""
        edges = _extract(content, file_path="values.yaml")
        images = [e for e in edges if e.metadata.get("kind") == "image"]
        assert len(images) == 1
        assert images[0].metadata["name"] == "nginx:latest"


# ============================================================================
# Tests: Chart.yaml subchart dependencies
# ============================================================================


class TestChartYamlDependencies:
    """Tests for Chart.yaml subchart extraction."""

    def test_subchart_dependency(self):
        content = """\
dependencies:
  - name: postgresql
    version: "12.0.0"
    repository: "https://charts.bitnami.com/bitnami"
"""
        edges = _extract(content, file_path="Chart.yaml")
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "subchart"
        assert edges[0].target_symbol == "postgresql"
        assert edges[0].target_file is None  # remote repo

    def test_local_subchart(self):
        content = """\
dependencies:
  - name: common
    version: "1.0.0"
    repository: "file://../common"
"""
        edges = _extract(content, file_path="Chart.yaml")
        assert len(edges) == 1
        assert edges[0].target_file == "../common"
        assert edges[0].metadata["kind"] == "subchart"

    def test_multiple_dependencies(self):
        content = """\
dependencies:
  - name: postgresql
    version: "12.0.0"
    repository: "https://charts.bitnami.com/bitnami"
  - name: redis
    version: "17.0.0"
    repository: "https://charts.bitnami.com/bitnami"
"""
        edges = _extract(content, file_path="Chart.yaml")
        names = {e.target_symbol for e in edges}
        assert names == {"postgresql", "redis"}


# ============================================================================
# Tests: Edge cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_file(self):
        assert _extract("") == []

    def test_languages_set(self):
        extractor = HelmExtractor()
        assert extractor.LANGUAGES == {"helm-template", "helm-values"}
