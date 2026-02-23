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
        assert edges[0].target_file == "../common/Chart.yaml"
        assert edges[0].metadata["kind"] == "subchart"

    def test_local_subchart_resolved_from_nested_chart(self):
        content = """\
dependencies:
  - name: common
    version: "1.0.0"
    repository: "file://../common"
"""
        edges = _extract(content, file_path="stable/suse-observability/Chart.yaml")
        assert len(edges) == 1
        assert edges[0].target_file == "stable/common/Chart.yaml"
        assert edges[0].metadata["kind"] == "subchart"

    def test_local_subchart_with_trailing_slash(self):
        content = """\
dependencies:
  - name: common
    version: "1.0.0"
    repository: "file://../common/"
"""
        edges = _extract(content, file_path="stable/parent/Chart.yaml")
        assert len(edges) == 1
        assert edges[0].target_file == "stable/common/Chart.yaml"

    def test_local_subchart_dot_slash_prefix(self):
        content = """\
dependencies:
  - name: redis
    version: "1.0.0"
    repository: "./charts/redis"
"""
        edges = _extract(content, file_path="stable/myapp/Chart.yaml")
        assert len(edges) == 1
        assert edges[0].target_file == "stable/myapp/charts/redis/Chart.yaml"

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
        assert extractor.LANGUAGES == {"helm-template", "helm-values", "helm-chart"}


# ============================================================================
# Tests: Chart membership edges
# ============================================================================


class TestChartMembership:
    """Tests for chart membership edges (template/values -> Chart.yaml)."""

    def test_template_to_chart_yaml(self):
        """Template file should have chart_member edge to Chart.yaml."""
        content = '{{ include "mychart.fullname" . }}'
        edges = _extract(content, file_path="mychart/templates/deployment.yaml")
        members = [e for e in edges if e.metadata.get("kind") == "chart_member"]
        assert len(members) == 1
        assert members[0].target_file == "mychart/Chart.yaml"
        assert members[0].metadata["member_type"] == "template"
        assert members[0].dep_type == DepType.REFERENCE

    def test_values_to_chart_yaml(self):
        """Values file should have chart_member edge to Chart.yaml."""
        content = "image:\n  repository: nginx\n  tag: latest\n"
        edges = _extract(content, file_path="mychart/values.yaml")
        members = [e for e in edges if e.metadata.get("kind") == "chart_member"]
        assert len(members) == 1
        assert members[0].target_file == "mychart/Chart.yaml"
        assert members[0].metadata["member_type"] == "values"

    def test_subchart_template_to_subchart_chart_yaml(self):
        """Subchart template should link to subchart's Chart.yaml."""
        content = '{{ include "sub.name" . }}'
        edges = _extract(content, file_path="parent/charts/sub/templates/deploy.yaml")
        members = [e for e in edges if e.metadata.get("kind") == "chart_member"]
        assert len(members) == 1
        assert members[0].target_file == "parent/charts/sub/Chart.yaml"

    def test_template_membership_coexists_with_include(self):
        """Chart membership edge coexists with include edges."""
        content = '{{ include "mychart.fullname" . }}'
        edges = _extract(content, file_path="mychart/templates/deployment.yaml")
        includes = [e for e in edges if e.metadata.get("kind") == "include"]
        members = [e for e in edges if e.metadata.get("kind") == "chart_member"]
        assert len(includes) == 1
        assert len(members) == 1

    def test_values_membership(self):
        """Values file should only produce a chart_member edge."""
        content = "image:\n  repository: nginx\n  tag: latest\n"
        edges = _extract(content, file_path="mychart/values.yaml")
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "chart_member"
        assert edges[0].metadata["member_type"] == "values"

    def test_subchart_template_has_is_subchart(self):
        """Template inside /charts/ should have is_subchart flag."""
        content = '{{ include "sub.name" . }}'
        edges = _extract(content, file_path="parent/charts/sub/templates/deploy.yaml")
        members = [e for e in edges if e.metadata.get("kind") == "chart_member"]
        assert len(members) == 1
        assert members[0].metadata["is_subchart"] is True

    def test_subchart_values_has_is_subchart(self):
        """Values file inside /charts/ should have is_subchart flag."""
        content = "replicaCount: 1\n"
        edges = _extract(content, file_path="parent/charts/sub/values.yaml")
        members = [e for e in edges if e.metadata.get("kind") == "chart_member"]
        assert len(members) == 1
        assert members[0].metadata["is_subchart"] is True

    def test_root_template_no_is_subchart(self):
        """Root chart template should not have is_subchart key."""
        content = '{{ include "mychart.fullname" . }}'
        edges = _extract(content, file_path="mychart/templates/deployment.yaml")
        members = [e for e in edges if e.metadata.get("kind") == "chart_member"]
        assert len(members) == 1
        assert "is_subchart" not in members[0].metadata

    def test_root_values_no_is_subchart(self):
        """Root chart values should not have is_subchart key."""
        content = "replicaCount: 1\n"
        edges = _extract(content, file_path="mychart/values.yaml")
        members = [e for e in edges if e.metadata.get("kind") == "chart_member"]
        assert len(members) == 1
        assert "is_subchart" not in members[0].metadata

    def test_bare_template_no_membership(self):
        """Template file without /templates/ in path has no membership edge."""
        content = '{{ include "mychart.fullname" . }}'
        edges = _extract(content, file_path="deployment.yaml")
        members = [e for e in edges if e.metadata.get("kind") == "chart_member"]
        assert len(members) == 0

    def test_bare_values_no_membership(self):
        """Values file without parent directory has no membership edge."""
        content = "image:\n  repository: nginx\n  tag: latest\n"
        edges = _extract(content, file_path="values.yaml")
        members = [e for e in edges if e.metadata.get("kind") == "chart_member"]
        assert len(members) == 0


# ============================================================================
# Tests: Subchart parent edges
# ============================================================================


class TestSubchartParent:
    """Tests for subchart-to-parent Chart.yaml edges."""

    def test_subchart_to_parent(self):
        """Subchart Chart.yaml should link to parent Chart.yaml."""
        content = "apiVersion: v2\nname: sub\n"
        edges = _extract(content, file_path="parent/charts/sub/Chart.yaml")
        parents = [e for e in edges if e.metadata.get("kind") == "subchart_of"]
        assert len(parents) == 1
        assert parents[0].target_file == "parent/Chart.yaml"
        assert parents[0].dep_type == DepType.REFERENCE

    def test_nested_subchart(self):
        """Nested subchart links to its immediate parent."""
        content = "apiVersion: v2\nname: deep\n"
        edges = _extract(content, file_path="root/charts/mid/charts/deep/Chart.yaml")
        parents = [e for e in edges if e.metadata.get("kind") == "subchart_of"]
        assert len(parents) == 1
        assert parents[0].target_file == "root/charts/mid/Chart.yaml"

    def test_root_chart_no_parent(self):
        """Root Chart.yaml should have no subchart_of edge."""
        content = "apiVersion: v2\nname: root\n"
        edges = _extract(content, file_path="root/Chart.yaml")
        parents = [e for e in edges if e.metadata.get("kind") == "subchart_of"]
        assert len(parents) == 0

    def test_subchart_parent_coexists_with_subchart_deps(self):
        """Subchart parent edge coexists with subchart dependency edges."""
        content = """\
apiVersion: v2
name: sub
dependencies:
  - name: postgresql
    version: "12.0.0"
    repository: "https://charts.bitnami.com/bitnami"
"""
        edges = _extract(content, file_path="parent/charts/sub/Chart.yaml")
        parents = [e for e in edges if e.metadata.get("kind") == "subchart_of"]
        subcharts = [e for e in edges if e.metadata.get("kind") == "subchart"]
        assert len(parents) == 1
        assert len(subcharts) == 1
