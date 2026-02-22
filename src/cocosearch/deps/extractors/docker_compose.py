"""Docker Compose dependency extractor.

Extracts references from Docker Compose files:
- ``image:`` container image references
- ``depends_on:`` service dependency references
- ``extends.service`` service inheritance references

All edges use ``dep_type = DepType.REFERENCE`` with ``metadata.kind``
distinguishing the reference type.
"""

import yaml

from cocosearch.deps.models import DependencyEdge, DepType


class DockerComposeExtractor:
    """Extractor for Docker Compose reference edges."""

    LANGUAGES: set[str] = {"docker-compose"}

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
        services = data.get("services", {})
        if not isinstance(services, dict):
            return edges

        for service_name, service_config in services.items():
            if not isinstance(service_config, dict):
                continue

            # image: references
            image = service_config.get("image")
            if isinstance(image, str) and image:
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=service_name,
                        target_file=None,
                        target_symbol=None,
                        dep_type=DepType.REFERENCE,
                        metadata={"kind": "image", "service": service_name, "ref": image},
                    )
                )

            # depends_on: references
            depends_on = service_config.get("depends_on")
            if isinstance(depends_on, list):
                for dep in depends_on:
                    if isinstance(dep, str):
                        edges.append(
                            DependencyEdge(
                                source_file="",
                                source_symbol=service_name,
                                target_file=None,
                                target_symbol=dep,
                                dep_type=DepType.REFERENCE,
                                metadata={
                                    "kind": "depends_on",
                                    "service": service_name,
                                },
                            )
                        )
            elif isinstance(depends_on, dict):
                for dep in depends_on:
                    edges.append(
                        DependencyEdge(
                            source_file="",
                            source_symbol=service_name,
                            target_file=None,
                            target_symbol=dep,
                            dep_type=DepType.REFERENCE,
                            metadata={
                                "kind": "depends_on",
                                "service": service_name,
                            },
                        )
                    )

            # extends: references
            extends = service_config.get("extends")
            if isinstance(extends, dict):
                ext_service = extends.get("service")
                ext_file = extends.get("file")
                if isinstance(ext_service, str):
                    edges.append(
                        DependencyEdge(
                            source_file="",
                            source_symbol=service_name,
                            target_file=ext_file if isinstance(ext_file, str) else None,
                            target_symbol=ext_service,
                            dep_type=DepType.REFERENCE,
                            metadata={
                                "kind": "extends",
                                "service": service_name,
                            },
                        )
                    )

        return edges
