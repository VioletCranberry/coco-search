"""Tests for cocosearch.deps.extractors.github_actions module."""

from cocosearch.deps.extractors.github_actions import GitHubActionsExtractor
from cocosearch.deps.models import DepType


def _extract(content: str, file_path: str = ".github/workflows/ci.yml"):
    extractor = GitHubActionsExtractor()
    return extractor.extract(file_path, content)


class TestActionReferences:
    """Tests for uses: action references."""

    def test_extracts_step_action(self):
        content = """\
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "action"
        assert edges[0].metadata["ref"] == "actions/checkout@v4"
        assert edges[0].dep_type == DepType.REFERENCE
        assert edges[0].target_file is None

    def test_multiple_step_actions(self):
        content = """\
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
"""
        edges = _extract(content)
        refs = {e.metadata["ref"] for e in edges}
        assert "actions/checkout@v4" in refs
        assert "actions/setup-node@v4" in refs

    def test_step_with_name(self):
        content = """\
jobs:
  build:
    steps:
      - name: Checkout
        uses: actions/checkout@v4
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].source_symbol == "Checkout"


class TestReusableWorkflows:
    """Tests for reusable workflow references."""

    def test_job_level_workflow(self):
        content = """\
jobs:
  deploy:
    uses: ./.github/workflows/deploy.yml
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "workflow"
        assert edges[0].target_file == ".github/workflows/deploy.yml"

    def test_local_step_workflow(self):
        content = """\
jobs:
  build:
    steps:
      - uses: ./.github/actions/my-action
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "workflow"
        assert edges[0].target_file == ".github/actions/my-action"


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_file(self):
        assert _extract("") == []

    def test_invalid_yaml(self):
        assert _extract("{{invalid") == []

    def test_no_jobs(self):
        assert _extract("name: CI\non: push\n") == []

    def test_languages_set(self):
        extractor = GitHubActionsExtractor()
        assert extractor.LANGUAGES == {"github-actions"}
