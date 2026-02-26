"""Tests for cocosearch.deps.extractors.github_actions module."""

from cocosearch.deps.extractors.github_actions import (
    GitHubActionsExtractor,
    _parse_action_ref,
)
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
        assert edges[0].metadata["module"] == "actions/checkout"
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
        modules = {e.metadata["module"] for e in edges}
        assert "actions/checkout" in modules
        assert "actions/setup-node" in modules

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

    def test_action_metadata_has_parsed_parts(self):
        content = """\
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
"""
        edges = _extract(content)
        assert edges[0].metadata["owner"] == "actions"
        assert edges[0].metadata["repo"] == "checkout"
        assert edges[0].metadata["version"] == "v4"

    def test_action_with_subpath(self):
        content = """\
jobs:
  build:
    steps:
      - uses: google-github-actions/auth@v2
"""
        edges = _extract(content)
        assert edges[0].metadata["owner"] == "google-github-actions"
        assert edges[0].metadata["repo"] == "auth"
        assert edges[0].metadata["module"] == "google-github-actions/auth"

    def test_action_with_semver(self):
        content = """\
jobs:
  build:
    steps:
      - uses: slackapi/slack-github-action@v2.1.0
"""
        edges = _extract(content)
        assert edges[0].metadata["version"] == "v2.1.0"
        assert edges[0].metadata["module"] == "slackapi/slack-github-action"

    def test_action_with_sha_version(self):
        content = """\
jobs:
  build:
    steps:
      - uses: actions/checkout@a5ac7e51b41094c92402da3b24376905380afc29
"""
        edges = _extract(content)
        assert (
            edges[0].metadata["version"] == "a5ac7e51b41094c92402da3b24376905380afc29"
        )
        assert edges[0].metadata["module"] == "actions/checkout"


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
        assert edges[0].metadata["module"] == "./.github/workflows/deploy.yml"

    def test_local_step_action(self):
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


class TestNeedsDependencies:
    """Tests for needs: inter-job dependencies."""

    def test_single_needs(self):
        content = """\
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
  deploy:
    needs: build
    steps:
      - uses: actions/checkout@v4
"""
        edges = _extract(content)
        needs_edges = [e for e in edges if e.metadata["kind"] == "needs"]
        assert len(needs_edges) == 1
        assert needs_edges[0].source_symbol == "deploy"
        assert needs_edges[0].target_symbol == "build"
        assert needs_edges[0].metadata["module"] == "build"

    def test_list_needs(self):
        content = """\
jobs:
  lint:
    steps:
      - uses: actions/checkout@v4
  test:
    steps:
      - uses: actions/checkout@v4
  deploy:
    needs: [lint, test]
    steps:
      - uses: actions/checkout@v4
"""
        edges = _extract(content)
        needs_edges = [e for e in edges if e.metadata["kind"] == "needs"]
        assert len(needs_edges) == 2
        dep_jobs = {e.target_symbol for e in needs_edges}
        assert dep_jobs == {"lint", "test"}

    def test_needs_target_file_is_none(self):
        content = """\
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
  deploy:
    needs: build
    steps:
      - uses: actions/checkout@v4
"""
        edges = _extract(content)
        needs_edges = [e for e in edges if e.metadata["kind"] == "needs"]
        assert needs_edges[0].target_file is None

    def test_needs_dep_type(self):
        content = """\
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
  deploy:
    needs: build
    steps:
      - uses: actions/checkout@v4
"""
        edges = _extract(content)
        needs_edges = [e for e in edges if e.metadata["kind"] == "needs"]
        assert needs_edges[0].dep_type == DepType.REFERENCE


class TestParseActionRef:
    """Tests for _parse_action_ref helper."""

    def test_standard_action(self):
        result = _parse_action_ref("actions/checkout@v4")
        assert result == {"owner": "actions", "repo": "checkout", "version": "v4"}

    def test_action_with_subpath(self):
        result = _parse_action_ref("aws-actions/configure-aws-credentials@v4")
        assert result["owner"] == "aws-actions"
        assert result["repo"] == "configure-aws-credentials"
        assert result["version"] == "v4"

    def test_action_with_path(self):
        result = _parse_action_ref("owner/repo/some/path@v1")
        assert result["owner"] == "owner"
        assert result["repo"] == "repo"
        assert result["path"] == "some/path"
        assert result["version"] == "v1"

    def test_local_ref_returns_empty(self):
        result = _parse_action_ref("./.github/actions/my-action")
        assert result == {}

    def test_docker_ref_returns_empty(self):
        result = _parse_action_ref("docker://alpine:3.8")
        assert result == {}


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

    def test_non_dict_jobs(self):
        assert _extract("jobs: invalid\n") == []

    def test_non_dict_job_config(self):
        content = """\
jobs:
  build: invalid
"""
        assert _extract(content) == []

    def test_non_list_steps(self):
        content = """\
jobs:
  build:
    steps: invalid
"""
        assert _extract(content) == []

    def test_non_dict_step(self):
        content = """\
jobs:
  build:
    steps:
      - invalid
"""
        assert _extract(content) == []

    def test_step_without_uses(self):
        content = """\
jobs:
  build:
    steps:
      - name: Run tests
        run: npm test
"""
        assert _extract(content) == []

    def test_empty_uses_string(self):
        content = """\
jobs:
  build:
    steps:
      - uses: ""
"""
        assert _extract(content) == []


class TestRealWorldWorkflow:
    """Integration-style tests with realistic workflow content."""

    def test_ci_workflow(self):
        content = """\
name: CI
on:
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v5

  test:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Cache
        uses: actions/cache@v4
        with:
          path: .venv
          key: deps-${{ hashFiles('uv.lock') }}
      - name: Run tests
        run: uv run pytest
"""
        edges = _extract(content)

        action_edges = [e for e in edges if e.metadata["kind"] == "action"]
        needs_edges = [e for e in edges if e.metadata["kind"] == "needs"]

        # 4 action refs: checkout, setup-uv, checkout, cache
        assert len(action_edges) == 4
        modules = [e.metadata["module"] for e in action_edges]
        assert modules.count("actions/checkout") == 2
        assert "astral-sh/setup-uv" in modules
        assert "actions/cache" in modules

        # 1 needs dep: test -> lint
        assert len(needs_edges) == 1
        assert needs_edges[0].source_symbol == "test"
        assert needs_edges[0].target_symbol == "lint"

    def test_release_workflow_with_chain(self):
        content = """\
name: Release
on:
  push:
    tags: ["v*"]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

  build:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/upload-artifact@v4

  publish:
    needs: [validate, build]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
"""
        edges = _extract(content)

        needs_edges = [e for e in edges if e.metadata["kind"] == "needs"]
        assert len(needs_edges) == 3

        # build needs validate
        build_needs = [e for e in needs_edges if e.source_symbol == "build"]
        assert len(build_needs) == 1
        assert build_needs[0].target_symbol == "validate"

        # publish needs validate and build
        publish_needs = [e for e in needs_edges if e.source_symbol == "publish"]
        assert len(publish_needs) == 2
        assert {e.target_symbol for e in publish_needs} == {"validate", "build"}
