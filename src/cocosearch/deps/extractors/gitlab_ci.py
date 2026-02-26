"""GitLab CI dependency extractor.

Extracts references from GitLab CI configuration files:
- ``include:`` local/project/remote/template config includes
- ``extends:`` job template inheritance
- ``needs:`` inter-job DAG dependencies
- ``trigger:`` child/multi-project pipeline triggers
- ``image:`` Docker image references (global and per-job)
- ``services:`` service container image references

Local file includes and child pipeline triggers are resolvable to file
paths.  All edges use ``dep_type = DepType.REFERENCE``.
"""

import yaml

from cocosearch.deps.models import DependencyEdge, DepType


class GitLabCIExtractor:
    """Extractor for GitLab CI reference edges."""

    LANGUAGES: set[str] = {"gitlab-ci"}

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        if not content:
            return []

        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError:
            return []

        if not isinstance(data, dict):
            return []

        edges: list[DependencyEdge] = []

        # Global includes
        self._extract_includes(data, edges)

        # Global image
        self._extract_image(data.get("image"), "global", edges)

        # Global services
        self._extract_services(data.get("services"), "global", edges)

        # Per-job extraction
        for key, value in data.items():
            if not isinstance(value, dict):
                continue
            # Skip known top-level keywords that aren't jobs
            if key in _TOP_LEVEL_KEYS:
                continue

            job_name = key
            job_config = value

            self._extract_extends(job_config, job_name, edges)
            self._extract_needs(job_config, job_name, edges)
            self._extract_trigger(job_config, job_name, edges)
            self._extract_image(job_config.get("image"), job_name, edges)
            self._extract_services(job_config.get("services"), job_name, edges)

        return edges

    def _extract_includes(self, data: dict, edges: list[DependencyEdge]) -> None:
        """Extract include: references."""
        include = data.get("include")
        if include is None:
            return

        # Normalize to list
        if isinstance(include, str):
            include = [include]
        elif isinstance(include, dict):
            include = [include]

        if not isinstance(include, list):
            return

        for item in include:
            if isinstance(item, str):
                # Simple string = local file include
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=None,
                        target_file=item,
                        target_symbol=None,
                        dep_type=DepType.REFERENCE,
                        metadata={"kind": "include_local", "module": item, "ref": item},
                    )
                )
            elif isinstance(item, dict):
                self._extract_include_item(item, edges)

    def _extract_include_item(self, item: dict, edges: list[DependencyEdge]) -> None:
        """Extract a single include: dict entry."""
        if "local" in item:
            ref = item["local"]
            if isinstance(ref, str) and ref:
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=None,
                        target_file=ref.lstrip("/"),
                        target_symbol=None,
                        dep_type=DepType.REFERENCE,
                        metadata={
                            "kind": "include_local",
                            "module": ref,
                            "ref": ref,
                        },
                    )
                )
        elif "project" in item:
            project = item["project"]
            file_ref = item.get("file")
            if isinstance(project, str) and project:
                # file can be a string or list of strings
                files = file_ref if isinstance(file_ref, list) else [file_ref]
                for f in files:
                    if isinstance(f, str) and f:
                        ref_str = f"{project}:{f}"
                        edges.append(
                            DependencyEdge(
                                source_file="",
                                source_symbol=None,
                                target_file=None,
                                target_symbol=None,
                                dep_type=DepType.REFERENCE,
                                metadata={
                                    "kind": "include_project",
                                    "module": project,
                                    "ref": ref_str,
                                    "project": project,
                                    "file": f,
                                },
                            )
                        )
        elif "remote" in item:
            ref = item["remote"]
            if isinstance(ref, str) and ref:
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=None,
                        target_file=None,
                        target_symbol=None,
                        dep_type=DepType.REFERENCE,
                        metadata={
                            "kind": "include_remote",
                            "module": ref,
                            "ref": ref,
                        },
                    )
                )
        elif "template" in item:
            ref = item["template"]
            if isinstance(ref, str) and ref:
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=None,
                        target_file=None,
                        target_symbol=None,
                        dep_type=DepType.REFERENCE,
                        metadata={
                            "kind": "include_template",
                            "module": ref,
                            "ref": ref,
                        },
                    )
                )

    def _extract_extends(
        self, job_config: dict, job_name: str, edges: list[DependencyEdge]
    ) -> None:
        """Extract extends: template inheritance references."""
        extends = job_config.get("extends")
        if extends is None:
            return

        if isinstance(extends, str):
            extends = [extends]

        if not isinstance(extends, list):
            return

        for template in extends:
            if isinstance(template, str) and template:
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=job_name,
                        target_file=None,
                        target_symbol=template,
                        dep_type=DepType.REFERENCE,
                        metadata={
                            "kind": "extends",
                            "module": template,
                        },
                    )
                )

    def _extract_needs(
        self, job_config: dict, job_name: str, edges: list[DependencyEdge]
    ) -> None:
        """Extract needs: inter-job DAG dependencies."""
        needs = job_config.get("needs")
        if needs is None:
            return

        if isinstance(needs, str):
            needs = [needs]

        if not isinstance(needs, list):
            return

        for item in needs:
            dep_job: str | None = None
            if isinstance(item, str):
                dep_job = item
            elif isinstance(item, dict):
                job_ref = item.get("job")
                if isinstance(job_ref, str):
                    dep_job = job_ref

            if dep_job:
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=job_name,
                        target_file=None,
                        target_symbol=dep_job,
                        dep_type=DepType.REFERENCE,
                        metadata={
                            "kind": "needs",
                            "module": dep_job,
                        },
                    )
                )

    def _extract_trigger(
        self, job_config: dict, job_name: str, edges: list[DependencyEdge]
    ) -> None:
        """Extract trigger: child/multi-project pipeline references."""
        trigger = job_config.get("trigger")
        if trigger is None:
            return

        if isinstance(trigger, str):
            # trigger: project-path (multi-project shorthand)
            edges.append(
                DependencyEdge(
                    source_file="",
                    source_symbol=job_name,
                    target_file=None,
                    target_symbol=None,
                    dep_type=DepType.REFERENCE,
                    metadata={
                        "kind": "trigger",
                        "module": trigger,
                        "project": trigger,
                    },
                )
            )
        elif isinstance(trigger, dict):
            include = trigger.get("include")
            project = trigger.get("project")

            if isinstance(include, str) and include:
                # Child pipeline with local file
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=job_name,
                        target_file=include,
                        target_symbol=None,
                        dep_type=DepType.REFERENCE,
                        metadata={
                            "kind": "trigger",
                            "module": include,
                            "ref": include,
                        },
                    )
                )
            elif isinstance(include, list):
                # Child pipeline with list of local files
                for item in include:
                    if isinstance(item, str) and item:
                        edges.append(
                            DependencyEdge(
                                source_file="",
                                source_symbol=job_name,
                                target_file=item,
                                target_symbol=None,
                                dep_type=DepType.REFERENCE,
                                metadata={
                                    "kind": "trigger",
                                    "module": item,
                                    "ref": item,
                                },
                            )
                        )
                    elif isinstance(item, dict):
                        local = item.get("local")
                        if isinstance(local, str) and local:
                            edges.append(
                                DependencyEdge(
                                    source_file="",
                                    source_symbol=job_name,
                                    target_file=local.lstrip("/"),
                                    target_symbol=None,
                                    dep_type=DepType.REFERENCE,
                                    metadata={
                                        "kind": "trigger",
                                        "module": local,
                                        "ref": local,
                                    },
                                )
                            )

            if isinstance(project, str) and project:
                # Multi-project pipeline
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=job_name,
                        target_file=None,
                        target_symbol=None,
                        dep_type=DepType.REFERENCE,
                        metadata={
                            "kind": "trigger",
                            "module": project,
                            "project": project,
                        },
                    )
                )

    @staticmethod
    def _extract_image(
        image: object, context: str, edges: list[DependencyEdge]
    ) -> None:
        """Extract image: Docker image references."""
        if image is None:
            return

        ref: str | None = None
        if isinstance(image, str):
            ref = image
        elif isinstance(image, dict):
            name = image.get("name")
            if isinstance(name, str):
                ref = name

        if ref:
            edges.append(
                DependencyEdge(
                    source_file="",
                    source_symbol=context,
                    target_file=None,
                    target_symbol=None,
                    dep_type=DepType.REFERENCE,
                    metadata={
                        "kind": "image",
                        "module": ref,
                        "ref": ref,
                    },
                )
            )

    @staticmethod
    def _extract_services(
        services: object, context: str, edges: list[DependencyEdge]
    ) -> None:
        """Extract services: container image references."""
        if not isinstance(services, list):
            return

        for svc in services:
            ref: str | None = None
            if isinstance(svc, str):
                ref = svc
            elif isinstance(svc, dict):
                name = svc.get("name")
                if isinstance(name, str):
                    ref = name

            if ref:
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=context,
                        target_file=None,
                        target_symbol=None,
                        dep_type=DepType.REFERENCE,
                        metadata={
                            "kind": "service",
                            "module": ref,
                            "ref": ref,
                        },
                    )
                )


# GitLab CI top-level keywords that are not job names
_TOP_LEVEL_KEYS = frozenset(
    {
        "stages",
        "variables",
        "image",
        "services",
        "before_script",
        "after_script",
        "cache",
        "default",
        "include",
        "workflow",
        "pages",
    }
)
