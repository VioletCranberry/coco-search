"""ArgoCD dependency extractor.

Extracts references from ArgoCD Application, ApplicationSet, and AppProject
manifests:
- ``project`` — Application/AppSet → AppProject name
- ``source_repo`` — Git repository URL references
- ``source_chart`` — Helm chart references
- ``source_path`` — Source path within a repository
- ``destination`` — Target cluster/namespace references
- ``generator_repo`` — ApplicationSet generator repository URLs

Handles multi-document YAML (``---`` separators) via ``yaml.safe_load_all()``.
All edges use ``dep_type = DepType.REFERENCE`` with ``metadata.kind``
distinguishing the reference type.
"""

import yaml

from cocosearch.deps.models import DependencyEdge, DepType

_ARGOCD_KINDS = {"Application", "ApplicationSet", "AppProject"}


class ArgoCDExtractor:
    """Extractor for ArgoCD reference edges."""

    LANGUAGES: set[str] = {"argocd"}

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        if not content:
            return []

        try:
            docs = list(yaml.safe_load_all(content))
        except yaml.YAMLError:
            return []

        edges: list[DependencyEdge] = []

        for data in docs:
            if not isinstance(data, dict):
                continue

            kind = data.get("kind")
            if kind not in _ARGOCD_KINDS:
                continue

            name = ""
            metadata = data.get("metadata")
            if isinstance(metadata, dict):
                n = metadata.get("name")
                if isinstance(n, str):
                    name = n

            if kind == "Application":
                self._extract_application(data, name, edges)
            elif kind == "ApplicationSet":
                self._extract_application_set(data, name, edges)
            elif kind == "AppProject":
                self._extract_app_project(data, name, edges)

        return edges

    def _extract_application(
        self,
        data: dict,
        name: str,
        edges: list[DependencyEdge],
    ) -> None:
        """Extract edges from an Application resource."""
        spec = data.get("spec")
        if not isinstance(spec, dict):
            return

        self._extract_app_spec(spec, name, edges)

    def _extract_app_spec(
        self,
        spec: dict,
        source_symbol: str,
        edges: list[DependencyEdge],
    ) -> None:
        """Extract edges from an Application spec (shared with AppSet template)."""
        # project reference
        project = spec.get("project")
        if isinstance(project, str) and project:
            edges.append(
                DependencyEdge(
                    source_file="",
                    source_symbol=source_symbol,
                    target_file=None,
                    target_symbol=project,
                    dep_type=DepType.REFERENCE,
                    metadata={"kind": "project", "ref": project},
                )
            )

        # single source
        source = spec.get("source")
        if isinstance(source, dict):
            self._extract_source(source, source_symbol, edges)

        # multiple sources
        sources = spec.get("sources")
        if isinstance(sources, list):
            for s in sources:
                if isinstance(s, dict):
                    self._extract_source(s, source_symbol, edges)

        # destination
        dest = spec.get("destination")
        if isinstance(dest, dict):
            self._extract_destination(dest, source_symbol, edges)

    def _extract_source(
        self,
        source: dict,
        source_symbol: str,
        edges: list[DependencyEdge],
    ) -> None:
        """Extract edges from a source block (repoURL, chart, path)."""
        repo_url = source.get("repoURL")
        if isinstance(repo_url, str) and repo_url:
            edges.append(
                DependencyEdge(
                    source_file="",
                    source_symbol=source_symbol,
                    target_file=None,
                    target_symbol=None,
                    dep_type=DepType.REFERENCE,
                    metadata={"kind": "source_repo", "ref": repo_url},
                )
            )

        chart = source.get("chart")
        if isinstance(chart, str) and chart:
            edges.append(
                DependencyEdge(
                    source_file="",
                    source_symbol=source_symbol,
                    target_file=None,
                    target_symbol=chart,
                    dep_type=DepType.REFERENCE,
                    metadata={"kind": "source_chart", "ref": chart},
                )
            )

        path = source.get("path")
        if isinstance(path, str) and path:
            edges.append(
                DependencyEdge(
                    source_file="",
                    source_symbol=source_symbol,
                    target_file=None,
                    target_symbol=None,
                    dep_type=DepType.REFERENCE,
                    metadata={"kind": "source_path", "ref": path},
                )
            )

    def _extract_destination(
        self,
        dest: dict,
        source_symbol: str,
        edges: list[DependencyEdge],
    ) -> None:
        """Extract a destination edge (server + optional namespace)."""
        server = dest.get("server")
        namespace = dest.get("namespace")
        if not isinstance(server, str) or not server:
            return

        ref = server
        if isinstance(namespace, str) and namespace:
            ref = f"{server}/{namespace}"

        edges.append(
            DependencyEdge(
                source_file="",
                source_symbol=source_symbol,
                target_file=None,
                target_symbol=None,
                dep_type=DepType.REFERENCE,
                metadata={"kind": "destination", "ref": ref},
            )
        )

    def _extract_application_set(
        self,
        data: dict,
        name: str,
        edges: list[DependencyEdge],
    ) -> None:
        """Extract edges from an ApplicationSet resource."""
        spec = data.get("spec")
        if not isinstance(spec, dict):
            return

        # generators
        generators = spec.get("generators")
        if isinstance(generators, list):
            for gen in generators:
                if not isinstance(gen, dict):
                    continue
                git = gen.get("git")
                if isinstance(git, dict):
                    repo_url = git.get("repoURL")
                    if isinstance(repo_url, str) and repo_url:
                        edges.append(
                            DependencyEdge(
                                source_file="",
                                source_symbol=name,
                                target_file=None,
                                target_symbol=None,
                                dep_type=DepType.REFERENCE,
                                metadata={
                                    "kind": "generator_repo",
                                    "ref": repo_url,
                                },
                            )
                        )

        # template spec — treat as Application
        template = spec.get("template")
        if isinstance(template, dict):
            template_spec = template.get("spec")
            if isinstance(template_spec, dict):
                self._extract_app_spec(template_spec, name, edges)

    def _extract_app_project(
        self,
        data: dict,
        name: str,
        edges: list[DependencyEdge],
    ) -> None:
        """Extract edges from an AppProject resource."""
        spec = data.get("spec")
        if not isinstance(spec, dict):
            return

        # sourceRepos (skip wildcard "*")
        source_repos = spec.get("sourceRepos")
        if isinstance(source_repos, list):
            for repo in source_repos:
                if isinstance(repo, str) and repo and repo != "*":
                    edges.append(
                        DependencyEdge(
                            source_file="",
                            source_symbol=name,
                            target_file=None,
                            target_symbol=None,
                            dep_type=DepType.REFERENCE,
                            metadata={"kind": "source_repo", "ref": repo},
                        )
                    )

        # destinations
        destinations = spec.get("destinations")
        if isinstance(destinations, list):
            for dest in destinations:
                if isinstance(dest, dict):
                    self._extract_destination(dest, name, edges)
