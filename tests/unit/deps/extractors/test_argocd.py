"""Tests for cocosearch.deps.extractors.argocd module."""

from cocosearch.deps.extractors.argocd import ArgoCDExtractor
from cocosearch.deps.models import DepType


def _extract(content: str, file_path: str = "app.yaml"):
    extractor = ArgoCDExtractor()
    return extractor.extract(file_path, content)


def _edges_by_kind(edges, kind):
    return [e for e in edges if e.metadata.get("kind") == kind]


class TestLanguagesSet:
    def test_languages(self):
        assert ArgoCDExtractor().LANGUAGES == {"argocd"}


class TestApplicationProjectRef:
    def test_extracts_project_ref(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
spec:
  project: default
  source:
    repoURL: https://github.com/org/repo.git
"""
        edges = _extract(content)
        proj = _edges_by_kind(edges, "project")
        assert len(proj) == 1
        assert proj[0].target_symbol == "default"
        assert proj[0].source_symbol == "my-app"
        assert proj[0].dep_type == DepType.REFERENCE
        assert proj[0].metadata["ref"] == "default"


class TestApplicationSourceRef:
    def test_extracts_source_repo(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
spec:
  source:
    repoURL: https://github.com/org/repo.git
"""
        edges = _extract(content)
        repos = _edges_by_kind(edges, "source_repo")
        assert len(repos) == 1
        assert repos[0].metadata["ref"] == "https://github.com/org/repo.git"
        assert repos[0].source_symbol == "my-app"

    def test_extracts_source_chart(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
spec:
  source:
    repoURL: https://charts.example.com
    chart: my-chart
"""
        edges = _extract(content)
        charts = _edges_by_kind(edges, "source_chart")
        assert len(charts) == 1
        assert charts[0].target_symbol == "my-chart"
        assert charts[0].metadata["ref"] == "my-chart"

    def test_extracts_source_path(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
spec:
  source:
    repoURL: https://github.com/org/repo.git
    path: deploy/manifests
"""
        edges = _extract(content)
        paths = _edges_by_kind(edges, "source_path")
        assert len(paths) == 1
        assert paths[0].metadata["ref"] == "deploy/manifests"

    def test_multiple_sources(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
spec:
  sources:
    - repoURL: https://github.com/org/repo1.git
      path: manifests
    - repoURL: https://charts.example.com
      chart: nginx
"""
        edges = _extract(content)
        repos = _edges_by_kind(edges, "source_repo")
        assert len(repos) == 2
        refs = {e.metadata["ref"] for e in repos}
        assert "https://github.com/org/repo1.git" in refs
        assert "https://charts.example.com" in refs
        charts = _edges_by_kind(edges, "source_chart")
        assert len(charts) == 1
        assert charts[0].target_symbol == "nginx"


class TestApplicationDestination:
    def test_server_only(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
spec:
  destination:
    server: https://kubernetes.default.svc
"""
        edges = _extract(content)
        dests = _edges_by_kind(edges, "destination")
        assert len(dests) == 1
        assert dests[0].metadata["ref"] == "https://kubernetes.default.svc"

    def test_server_and_namespace(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
spec:
  destination:
    server: https://kubernetes.default.svc
    namespace: production
"""
        edges = _extract(content)
        dests = _edges_by_kind(edges, "destination")
        assert len(dests) == 1
        assert dests[0].metadata["ref"] == "https://kubernetes.default.svc/production"


class TestApplicationSetGenerators:
    def test_git_generator_repo(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: my-appset
spec:
  generators:
    - git:
        repoURL: https://github.com/org/config.git
  template:
    spec:
      project: default
"""
        edges = _extract(content)
        gen_repos = _edges_by_kind(edges, "generator_repo")
        assert len(gen_repos) == 1
        assert gen_repos[0].metadata["ref"] == "https://github.com/org/config.git"
        assert gen_repos[0].source_symbol == "my-appset"

    def test_non_git_generator_no_edge(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: my-appset
spec:
  generators:
    - list:
        elements:
          - cluster: dev
  template:
    spec:
      project: default
"""
        edges = _extract(content)
        gen_repos = _edges_by_kind(edges, "generator_repo")
        assert len(gen_repos) == 0


class TestApplicationSetTemplate:
    def test_template_processed_as_application(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: my-appset
spec:
  generators:
    - list:
        elements: []
  template:
    spec:
      project: team-project
      source:
        repoURL: https://github.com/org/repo.git
        path: apps
      destination:
        server: https://kubernetes.default.svc
        namespace: staging
"""
        edges = _extract(content)
        proj = _edges_by_kind(edges, "project")
        assert len(proj) == 1
        assert proj[0].target_symbol == "team-project"
        repos = _edges_by_kind(edges, "source_repo")
        assert len(repos) == 1
        dests = _edges_by_kind(edges, "destination")
        assert len(dests) == 1


class TestAppProject:
    def test_source_repos(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: my-project
spec:
  sourceRepos:
    - https://github.com/org/repo1.git
    - https://github.com/org/repo2.git
"""
        edges = _extract(content)
        repos = _edges_by_kind(edges, "source_repo")
        assert len(repos) == 2
        refs = {e.metadata["ref"] for e in repos}
        assert "https://github.com/org/repo1.git" in refs
        assert "https://github.com/org/repo2.git" in refs

    def test_wildcard_skipped(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: my-project
spec:
  sourceRepos:
    - "*"
    - https://github.com/org/repo.git
"""
        edges = _extract(content)
        repos = _edges_by_kind(edges, "source_repo")
        assert len(repos) == 1
        assert repos[0].metadata["ref"] == "https://github.com/org/repo.git"

    def test_destinations(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: my-project
spec:
  destinations:
    - server: https://kubernetes.default.svc
      namespace: prod
    - server: https://staging.cluster.local
"""
        edges = _extract(content)
        dests = _edges_by_kind(edges, "destination")
        assert len(dests) == 2
        refs = {e.metadata["ref"] for e in dests}
        assert "https://kubernetes.default.svc/prod" in refs
        assert "https://staging.cluster.local" in refs


class TestMultiDocumentYaml:
    def test_multiple_documents(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: my-project
spec:
  sourceRepos:
    - https://github.com/org/repo.git
---
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
spec:
  project: my-project
  source:
    repoURL: https://github.com/org/repo.git
"""
        edges = _extract(content)
        # AppProject contributes source_repo, Application contributes project + source_repo
        proj = _edges_by_kind(edges, "project")
        assert len(proj) == 1
        assert proj[0].target_symbol == "my-project"
        repos = _edges_by_kind(edges, "source_repo")
        assert len(repos) == 2

    def test_empty_document_in_stream(self):
        content = """\
---
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
spec:
  project: default
---
---
"""
        edges = _extract(content)
        proj = _edges_by_kind(edges, "project")
        assert len(proj) == 1
        assert proj[0].target_symbol == "default"


class TestEdgeCases:
    def test_empty_string(self):
        assert _extract("") == []

    def test_invalid_yaml(self):
        assert _extract("{{invalid") == []

    def test_non_argocd_kind(self):
        content = """\
apiVersion: v1
kind: ConfigMap
metadata:
  name: test
"""
        assert _extract(content) == []

    def test_missing_spec(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
"""
        assert _extract(content) == []

    def test_spec_not_dict(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
spec: "invalid"
"""
        assert _extract(content) == []

    def test_missing_metadata_name(self):
        content = """\
apiVersion: argoproj.io/v1alpha1
kind: Application
spec:
  project: default
"""
        edges = _extract(content)
        proj = _edges_by_kind(edges, "project")
        assert len(proj) == 1
        assert proj[0].source_symbol == ""
