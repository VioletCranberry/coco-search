"""Tests for cocosearch.deps.extractors.gitlab_ci module."""

from cocosearch.deps.extractors.gitlab_ci import GitLabCIExtractor
from cocosearch.deps.models import DepType


def _extract(content: str, file_path: str = ".gitlab-ci.yml"):
    extractor = GitLabCIExtractor()
    return extractor.extract(file_path, content)


# ============================================================================
# Include references
# ============================================================================


class TestIncludeLocal:
    """Tests for include: local file references."""

    def test_simple_string_include(self):
        content = """\
include: 'templates/base.yml'
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "include_local"
        assert edges[0].target_file == "templates/base.yml"
        assert edges[0].metadata["ref"] == "templates/base.yml"
        assert edges[0].dep_type == DepType.REFERENCE

    def test_local_key_include(self):
        content = """\
include:
  - local: '/templates/base.yml'
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "include_local"
        assert edges[0].target_file == "templates/base.yml"
        assert edges[0].metadata["ref"] == "/templates/base.yml"

    def test_multiple_local_includes(self):
        content = """\
include:
  - local: '/templates/base.yml'
  - local: '/templates/deploy.yml'
"""
        edges = _extract(content)
        assert len(edges) == 2
        files = {e.target_file for e in edges}
        assert files == {"templates/base.yml", "templates/deploy.yml"}

    def test_mixed_include_list(self):
        content = """\
include:
  - local: '/templates/base.yml'
  - project: 'my-group/my-project'
    file: '/templates/ci.yml'
  - remote: 'https://example.com/ci.yml'
  - template: 'Auto-DevOps.gitlab-ci.yml'
"""
        edges = _extract(content)
        assert len(edges) == 4
        kinds = {e.metadata["kind"] for e in edges}
        assert kinds == {
            "include_local",
            "include_project",
            "include_remote",
            "include_template",
        }


class TestIncludeProject:
    """Tests for include: project references."""

    def test_project_include(self):
        content = """\
include:
  - project: 'my-group/my-project'
    file: '/templates/ci.yml'
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "include_project"
        assert edges[0].metadata["project"] == "my-group/my-project"
        assert edges[0].metadata["file"] == "/templates/ci.yml"
        assert edges[0].target_file is None

    def test_project_include_multiple_files(self):
        content = """\
include:
  - project: 'my-group/my-project'
    file:
      - '/templates/ci.yml'
      - '/templates/deploy.yml'
"""
        edges = _extract(content)
        assert len(edges) == 2
        files = {e.metadata["file"] for e in edges}
        assert files == {"/templates/ci.yml", "/templates/deploy.yml"}
        for e in edges:
            assert e.metadata["project"] == "my-group/my-project"


class TestIncludeRemote:
    """Tests for include: remote URL references."""

    def test_remote_include(self):
        content = """\
include:
  - remote: 'https://example.com/ci/template.yml'
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "include_remote"
        assert edges[0].metadata["ref"] == "https://example.com/ci/template.yml"
        assert edges[0].target_file is None


class TestIncludeTemplate:
    """Tests for include: template references."""

    def test_template_include(self):
        content = """\
include:
  - template: 'Auto-DevOps.gitlab-ci.yml'
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "include_template"
        assert edges[0].metadata["ref"] == "Auto-DevOps.gitlab-ci.yml"
        assert edges[0].target_file is None

    def test_single_dict_include(self):
        """A single dict (not in a list) should still be parsed."""
        content = """\
include:
  template: 'Terraform.gitlab-ci.yml'
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "include_template"


# ============================================================================
# Extends references
# ============================================================================


class TestExtends:
    """Tests for extends: template inheritance references."""

    def test_single_extends(self):
        content = """\
.base:
  image: ruby:3.2

build:
  extends: .base
  script: make
"""
        edges = _extract(content)
        extends_edges = [e for e in edges if e.metadata["kind"] == "extends"]
        assert len(extends_edges) == 1
        assert extends_edges[0].source_symbol == "build"
        assert extends_edges[0].target_symbol == ".base"
        assert extends_edges[0].metadata["module"] == ".base"

    def test_list_extends(self):
        content = """\
build:
  extends:
    - .base
    - .deploy_template
  script: make
"""
        edges = _extract(content)
        extends_edges = [e for e in edges if e.metadata["kind"] == "extends"]
        assert len(extends_edges) == 2
        targets = {e.target_symbol for e in extends_edges}
        assert targets == {".base", ".deploy_template"}

    def test_extends_target_file_is_none(self):
        content = """\
build:
  extends: .base
  script: make
"""
        edges = _extract(content)
        extends_edges = [e for e in edges if e.metadata["kind"] == "extends"]
        assert extends_edges[0].target_file is None

    def test_extends_dep_type(self):
        content = """\
build:
  extends: .base
  script: make
"""
        edges = _extract(content)
        extends_edges = [e for e in edges if e.metadata["kind"] == "extends"]
        assert extends_edges[0].dep_type == DepType.REFERENCE


# ============================================================================
# Needs references
# ============================================================================


class TestNeeds:
    """Tests for needs: inter-job DAG dependencies."""

    def test_single_string_needs(self):
        content = """\
build:
  script: make
deploy:
  needs: build
  script: deploy
"""
        edges = _extract(content)
        needs_edges = [e for e in edges if e.metadata["kind"] == "needs"]
        assert len(needs_edges) == 1
        assert needs_edges[0].source_symbol == "deploy"
        assert needs_edges[0].target_symbol == "build"
        assert needs_edges[0].metadata["module"] == "build"

    def test_list_needs(self):
        content = """\
lint:
  script: lint
test:
  script: test
deploy:
  needs: [lint, test]
  script: deploy
"""
        edges = _extract(content)
        needs_edges = [e for e in edges if e.metadata["kind"] == "needs"]
        assert len(needs_edges) == 2
        dep_jobs = {e.target_symbol for e in needs_edges}
        assert dep_jobs == {"lint", "test"}

    def test_dict_needs_with_job_key(self):
        content = """\
build:
  script: make
deploy:
  needs:
    - job: build
      artifacts: true
  script: deploy
"""
        edges = _extract(content)
        needs_edges = [e for e in edges if e.metadata["kind"] == "needs"]
        assert len(needs_edges) == 1
        assert needs_edges[0].target_symbol == "build"

    def test_needs_target_file_is_none(self):
        content = """\
build:
  script: make
deploy:
  needs: build
  script: deploy
"""
        edges = _extract(content)
        needs_edges = [e for e in edges if e.metadata["kind"] == "needs"]
        assert needs_edges[0].target_file is None

    def test_needs_dep_type(self):
        content = """\
build:
  script: make
deploy:
  needs: build
  script: deploy
"""
        edges = _extract(content)
        needs_edges = [e for e in edges if e.metadata["kind"] == "needs"]
        assert needs_edges[0].dep_type == DepType.REFERENCE


# ============================================================================
# Trigger references
# ============================================================================


class TestTrigger:
    """Tests for trigger: child/multi-project pipeline references."""

    def test_trigger_string_project(self):
        content = """\
deploy:
  trigger: my-group/my-deploy-project
"""
        edges = _extract(content)
        trigger_edges = [e for e in edges if e.metadata["kind"] == "trigger"]
        assert len(trigger_edges) == 1
        assert trigger_edges[0].metadata["project"] == "my-group/my-deploy-project"
        assert trigger_edges[0].target_file is None

    def test_trigger_dict_project(self):
        content = """\
deploy:
  trigger:
    project: my-group/my-deploy-project
"""
        edges = _extract(content)
        trigger_edges = [e for e in edges if e.metadata["kind"] == "trigger"]
        assert len(trigger_edges) == 1
        assert trigger_edges[0].metadata["project"] == "my-group/my-deploy-project"

    def test_trigger_child_pipeline(self):
        content = """\
deploy:
  trigger:
    include: child-pipeline.yml
"""
        edges = _extract(content)
        trigger_edges = [e for e in edges if e.metadata["kind"] == "trigger"]
        assert len(trigger_edges) == 1
        assert trigger_edges[0].target_file == "child-pipeline.yml"
        assert trigger_edges[0].metadata["ref"] == "child-pipeline.yml"

    def test_trigger_child_pipeline_list(self):
        content = """\
deploy:
  trigger:
    include:
      - child-a.yml
      - child-b.yml
"""
        edges = _extract(content)
        trigger_edges = [e for e in edges if e.metadata["kind"] == "trigger"]
        assert len(trigger_edges) == 2
        files = {e.target_file for e in trigger_edges}
        assert files == {"child-a.yml", "child-b.yml"}

    def test_trigger_child_pipeline_local_dict(self):
        content = """\
deploy:
  trigger:
    include:
      - local: '/pipelines/child.yml'
"""
        edges = _extract(content)
        trigger_edges = [e for e in edges if e.metadata["kind"] == "trigger"]
        assert len(trigger_edges) == 1
        assert trigger_edges[0].target_file == "pipelines/child.yml"

    def test_trigger_project_and_include(self):
        """trigger with both project and include emits edges for both."""
        content = """\
deploy:
  trigger:
    project: my-group/my-project
    include: child.yml
"""
        edges = _extract(content)
        trigger_edges = [e for e in edges if e.metadata["kind"] == "trigger"]
        assert len(trigger_edges) == 2


# ============================================================================
# Image references
# ============================================================================


class TestImage:
    """Tests for image: Docker image references."""

    def test_global_image_string(self):
        content = """\
image: ruby:3.2
build:
  script: make
"""
        edges = _extract(content)
        image_edges = [e for e in edges if e.metadata["kind"] == "image"]
        assert len(image_edges) == 1
        assert image_edges[0].metadata["ref"] == "ruby:3.2"
        assert image_edges[0].source_symbol == "global"
        assert image_edges[0].target_file is None

    def test_global_image_dict(self):
        content = """\
image:
  name: ruby:3.2
  entrypoint: ["/bin/bash"]
build:
  script: make
"""
        edges = _extract(content)
        image_edges = [e for e in edges if e.metadata["kind"] == "image"]
        assert len(image_edges) == 1
        assert image_edges[0].metadata["ref"] == "ruby:3.2"

    def test_job_image(self):
        content = """\
build:
  image: node:20
  script: npm build
"""
        edges = _extract(content)
        image_edges = [e for e in edges if e.metadata["kind"] == "image"]
        assert len(image_edges) == 1
        assert image_edges[0].metadata["ref"] == "node:20"
        assert image_edges[0].source_symbol == "build"

    def test_global_and_job_images(self):
        content = """\
image: ruby:3.2
build:
  image: node:20
  script: npm build
"""
        edges = _extract(content)
        image_edges = [e for e in edges if e.metadata["kind"] == "image"]
        assert len(image_edges) == 2
        refs = {e.metadata["ref"] for e in image_edges}
        assert refs == {"ruby:3.2", "node:20"}


# ============================================================================
# Services references
# ============================================================================


class TestServices:
    """Tests for services: container image references."""

    def test_global_services_strings(self):
        content = """\
services:
  - postgres:14
  - redis:7
build:
  script: make
"""
        edges = _extract(content)
        svc_edges = [e for e in edges if e.metadata["kind"] == "service"]
        assert len(svc_edges) == 2
        refs = {e.metadata["ref"] for e in svc_edges}
        assert refs == {"postgres:14", "redis:7"}

    def test_services_dict_form(self):
        content = """\
services:
  - name: postgres:14
    alias: db
build:
  script: make
"""
        edges = _extract(content)
        svc_edges = [e for e in edges if e.metadata["kind"] == "service"]
        assert len(svc_edges) == 1
        assert svc_edges[0].metadata["ref"] == "postgres:14"

    def test_job_services(self):
        content = """\
build:
  services:
    - mysql:8
  script: make
"""
        edges = _extract(content)
        svc_edges = [e for e in edges if e.metadata["kind"] == "service"]
        assert len(svc_edges) == 1
        assert svc_edges[0].metadata["ref"] == "mysql:8"
        assert svc_edges[0].source_symbol == "build"


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_file(self):
        assert _extract("") == []

    def test_invalid_yaml(self):
        assert _extract("{{invalid") == []

    def test_no_jobs_or_includes(self):
        assert _extract("stages:\n  - build\n") == []

    def test_languages_set(self):
        extractor = GitLabCIExtractor()
        assert extractor.LANGUAGES == {"gitlab-ci"}

    def test_non_dict_root(self):
        assert _extract("- item1\n- item2\n") == []

    def test_non_dict_job_config_skipped(self):
        content = """\
build: invalid_string
"""
        edges = _extract(content)
        assert edges == []

    def test_empty_string_includes_skipped(self):
        content = """\
include:
  - local: ''
"""
        assert _extract(content) == []

    def test_empty_string_needs_skipped(self):
        content = """\
build:
  needs:
    - ''
  script: make
"""
        assert _extract(content) == []


# ============================================================================
# Real-world integration-style tests
# ============================================================================


class TestRealWorldPipeline:
    """Integration-style tests with realistic GitLab CI content."""

    def test_full_pipeline(self):
        content = """\
include:
  - template: 'Workflows/MergeRequest-Pipelines.gitlab-ci.yml'
  - local: '/templates/base.yml'

image: ruby:3.2

services:
  - postgres:14

stages:
  - lint
  - test
  - deploy

.base:
  before_script:
    - bundle install

lint:
  extends: .base
  stage: lint
  script: rubocop

test:
  extends: .base
  stage: test
  needs: [lint]
  services:
    - name: redis:7
      alias: cache
  script: rspec

deploy:
  stage: deploy
  needs: [lint, test]
  image: alpine:3.18
  trigger:
    project: my-group/deploy-project
"""
        edges = _extract(content)

        # Includes: 1 template + 1 local
        include_edges = [e for e in edges if e.metadata["kind"].startswith("include_")]
        assert len(include_edges) == 2
        kinds = {e.metadata["kind"] for e in include_edges}
        assert kinds == {"include_template", "include_local"}

        # Global image
        global_images = [
            e
            for e in edges
            if e.metadata["kind"] == "image" and e.source_symbol == "global"
        ]
        assert len(global_images) == 1
        assert global_images[0].metadata["ref"] == "ruby:3.2"

        # Global services
        global_svcs = [
            e
            for e in edges
            if e.metadata["kind"] == "service" and e.source_symbol == "global"
        ]
        assert len(global_svcs) == 1
        assert global_svcs[0].metadata["ref"] == "postgres:14"

        # Extends: lint -> .base, test -> .base
        extends_edges = [e for e in edges if e.metadata["kind"] == "extends"]
        assert len(extends_edges) == 2
        assert {e.source_symbol for e in extends_edges} == {"lint", "test"}
        assert all(e.target_symbol == ".base" for e in extends_edges)

        # Needs: test -> lint, deploy -> lint, deploy -> test
        needs_edges = [e for e in edges if e.metadata["kind"] == "needs"]
        assert len(needs_edges) == 3

        # Job services: test -> redis:7
        job_svcs = [
            e
            for e in edges
            if e.metadata["kind"] == "service" and e.source_symbol == "test"
        ]
        assert len(job_svcs) == 1
        assert job_svcs[0].metadata["ref"] == "redis:7"

        # Deploy image override
        deploy_images = [
            e
            for e in edges
            if e.metadata["kind"] == "image" and e.source_symbol == "deploy"
        ]
        assert len(deploy_images) == 1
        assert deploy_images[0].metadata["ref"] == "alpine:3.18"

        # Trigger: deploy -> my-group/deploy-project
        trigger_edges = [e for e in edges if e.metadata["kind"] == "trigger"]
        assert len(trigger_edges) == 1
        assert trigger_edges[0].metadata["project"] == "my-group/deploy-project"

    def test_child_pipeline_pattern(self):
        content = """\
stages:
  - triggers

trigger_child:
  stage: triggers
  trigger:
    include:
      - local: '/pipelines/child.yml'
    strategy: depend
"""
        edges = _extract(content)
        trigger_edges = [e for e in edges if e.metadata["kind"] == "trigger"]
        assert len(trigger_edges) == 1
        assert trigger_edges[0].target_file == "pipelines/child.yml"
        assert trigger_edges[0].source_symbol == "trigger_child"
