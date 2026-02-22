"""GitHub Actions dependency extractor.

Extracts references from GitHub Actions workflow files:
- ``uses:`` action references (``actions/checkout@v4``)
- ``uses:`` reusable workflow references (``uses: ./.github/workflows/...``)

Local workflow refs (starting with ``./``) are resolvable to file paths.
All edges use ``dep_type = DepType.REFERENCE``.
"""

import yaml

from cocosearch.deps.models import DependencyEdge, DepType


class GitHubActionsExtractor:
    """Extractor for GitHub Actions reference edges."""

    LANGUAGES: set[str] = {"github-actions"}

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
        jobs = data.get("jobs", {})
        if not isinstance(jobs, dict):
            return edges

        for job_name, job_config in jobs.items():
            if not isinstance(job_config, dict):
                continue

            # Job-level uses: (reusable workflows)
            job_uses = job_config.get("uses")
            if isinstance(job_uses, str) and job_uses:
                kind = "workflow" if job_uses.startswith("./") else "action"
                target_file = job_uses if job_uses.startswith("./") else None
                # Strip leading ./ for local paths
                if target_file and target_file.startswith("./"):
                    target_file = target_file[2:]
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=job_name,
                        target_file=target_file,
                        target_symbol=None,
                        dep_type=DepType.REFERENCE,
                        metadata={"kind": kind, "ref": job_uses},
                    )
                )

            # Step-level uses:
            steps = job_config.get("steps", [])
            if not isinstance(steps, list):
                continue

            for step in steps:
                if not isinstance(step, dict):
                    continue
                step_uses = step.get("uses")
                if not isinstance(step_uses, str) or not step_uses:
                    continue

                kind = "workflow" if step_uses.startswith("./") else "action"
                target_file = step_uses if step_uses.startswith("./") else None
                if target_file and target_file.startswith("./"):
                    target_file = target_file[2:]

                step_name = step.get("name", step.get("id", job_name))
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=str(step_name),
                        target_file=target_file,
                        target_symbol=None,
                        dep_type=DepType.REFERENCE,
                        metadata={"kind": kind, "ref": step_uses},
                    )
                )

        return edges
