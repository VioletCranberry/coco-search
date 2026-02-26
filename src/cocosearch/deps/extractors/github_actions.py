"""GitHub Actions dependency extractor.

Extracts references from GitHub Actions workflow files:
- ``uses:`` action references (``actions/checkout@v4``)
- ``uses:`` reusable workflow references (``uses: ./.github/workflows/...``)
- ``needs:`` inter-job dependencies within a workflow

Local workflow/action refs (starting with ``./``) are resolvable to file
paths.  External action refs are parsed into owner/repo/version parts.
All edges use ``dep_type = DepType.REFERENCE``.
"""

import re

import yaml

from cocosearch.deps.models import DependencyEdge, DepType

# External action ref: owner/repo@version or owner/repo/path@version
_ACTION_REF_RE = re.compile(
    r"^(?P<owner>[^/]+)/(?P<repo>[^/@]+)(?:/(?P<path>[^@]+))?@(?P<version>.+)$"
)


def _parse_action_ref(ref: str) -> dict:
    """Parse an external action ref into structured parts.

    ``actions/checkout@v4`` → ``{owner: actions, repo: checkout, version: v4}``
    ``google-github-actions/auth@v2`` → ``{owner: google-github-actions, repo: auth, version: v2}``
    ``slackapi/slack-github-action@v2.1.0`` → ``{owner: slackapi, repo: slack-github-action, version: v2.1.0}``
    """
    m = _ACTION_REF_RE.match(ref)
    if not m:
        return {}
    parts: dict = {"owner": m.group("owner"), "repo": m.group("repo")}
    if m.group("path"):
        parts["path"] = m.group("path")
    if m.group("version"):
        parts["version"] = m.group("version")
    return parts


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
                edges.append(self._make_uses_edge(job_uses, job_name))

            # Job-level needs: (inter-job dependencies)
            needs = job_config.get("needs")
            if isinstance(needs, str):
                needs = [needs]
            if isinstance(needs, list):
                for dep_job in needs:
                    if isinstance(dep_job, str) and dep_job:
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

                step_name = step.get("name", step.get("id", job_name))
                edges.append(self._make_uses_edge(step_uses, str(step_name)))

        return edges

    @staticmethod
    def _make_uses_edge(ref: str, source_symbol: str) -> DependencyEdge:
        """Create a DependencyEdge from a ``uses:`` reference."""
        is_local = ref.startswith("./")

        if is_local:
            target_file = ref[2:]  # strip ./
            kind = "workflow"
            metadata: dict = {
                "kind": kind,
                "module": ref,
                "ref": ref,
            }
        else:
            target_file = None
            kind = "action"
            parts = _parse_action_ref(ref)
            action_name = f"{parts['owner']}/{parts['repo']}" if parts else ref
            metadata = {
                "kind": kind,
                "module": action_name,
                "ref": ref,
            }
            if parts:
                metadata.update(parts)

        return DependencyEdge(
            source_file="",
            source_symbol=source_symbol,
            target_file=target_file,
            target_symbol=None,
            dep_type=DepType.REFERENCE,
            metadata=metadata,
        )
