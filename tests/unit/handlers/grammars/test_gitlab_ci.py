"""Tests for cocosearch.handlers.grammars.gitlab_ci module."""

import pytest

from cocosearch.handlers.grammars.gitlab_ci import GitLabCIHandler


@pytest.mark.unit
class TestGitLabCIMatching:
    """Tests for GitLabCIHandler.matches()."""

    def test_matches_with_stages(self):
        """Matches .gitlab-ci.yml with 'stages:' content."""
        handler = GitLabCIHandler()
        content = "stages:\n  - build\n  - test\nbuild:\n  script: make"
        assert handler.matches(".gitlab-ci.yml", content) is True

    def test_matches_with_script_and_image(self):
        """Matches .gitlab-ci.yml with 'script:' and 'image:' content."""
        handler = GitLabCIHandler()
        content = "image: python:3.11\nbuild:\n  script: make build"
        assert handler.matches(".gitlab-ci.yml", content) is True

    def test_matches_with_script_and_stage(self):
        """Matches .gitlab-ci.yml with 'script:' and 'stage:' content."""
        handler = GitLabCIHandler()
        content = "build:\n  stage: build\n  script: make"
        assert handler.matches(".gitlab-ci.yml", content) is True

    def test_rejects_generic_yaml(self):
        """Rejects .gitlab-ci.yml without CI markers."""
        handler = GitLabCIHandler()
        content = "name: something\nkey: value"
        assert handler.matches(".gitlab-ci.yml", content) is False

    def test_rejects_non_gitlab_path(self):
        """Rejects files not named .gitlab-ci.yml."""
        handler = GitLabCIHandler()
        content = "stages:\n  - build"
        assert handler.matches("ci-config.yml", content) is False

    def test_matches_path_only_without_content(self):
        """Matches by path alone when content is None."""
        handler = GitLabCIHandler()
        assert handler.matches(".gitlab-ci.yml") is True

    def test_rejects_wrong_path_without_content(self):
        """Rejects wrong path when content is None."""
        handler = GitLabCIHandler()
        assert handler.matches("build.yml") is False

    def test_matches_nested_path(self):
        """Matches .gitlab-ci.yml in nested directories."""
        handler = GitLabCIHandler()
        content = "stages:\n  - build\nbuild:\n  script: make"
        assert (
            handler.matches("vendor/gitlab.com/org/repo/.gitlab-ci.yml", content)
            is True
        )

    def test_matches_nested_path_without_content(self):
        """Matches nested .gitlab-ci.yml by path alone."""
        handler = GitLabCIHandler()
        assert handler.matches("sub/dir/.gitlab-ci.yml") is True

    def test_matches_deeply_nested_path(self):
        """Matches .gitlab-ci.yml in deeply nested directory."""
        handler = GitLabCIHandler()
        content = "stages:\n  - build"
        assert handler.matches("a/b/c/.gitlab-ci.yml", content) is True

    def test_matches_deeply_nested_path_without_content(self):
        """Matches deeply nested .gitlab-ci.yml by path alone."""
        handler = GitLabCIHandler()
        assert handler.matches("a/b/c/.gitlab-ci.yml") is True

    def test_rejects_non_dot_prefix(self):
        """Rejects gitlab-ci.yml without the leading dot."""
        handler = GitLabCIHandler()
        content = "stages:\n  - build"
        assert handler.matches("gitlab-ci.yml", content) is False

    def test_rejects_yaml_extension(self):
        """Rejects .gitlab-ci.yaml (not in PATH_PATTERNS)."""
        handler = GitLabCIHandler()
        content = "stages:\n  - build"
        assert handler.matches(".gitlab-ci.yaml", content) is False


@pytest.mark.unit
class TestGitLabCISeparatorSpec:
    """Tests for GitLabCIHandler.SEPARATOR_SPEC."""

    def test_language_name(self):
        """SEPARATOR_SPEC.language_name should be 'gitlab-ci'."""
        handler = GitLabCIHandler()
        assert handler.SEPARATOR_SPEC.language_name == "gitlab-ci"

    def test_separator_count(self):
        """SEPARATOR_SPEC should have exactly 7 separator levels."""
        handler = GitLabCIHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) == 7

    def test_has_yaml_document_separator(self):
        """First separator should be YAML document separator (---)."""
        handler = GitLabCIHandler()
        assert r"\n---" in handler.SEPARATOR_SPEC.separators_regex[0]

    def test_has_top_level_key_separator(self):
        """Second separator should split on top-level keys."""
        handler = GitLabCIHandler()
        assert r"[a-zA-Z_.]" in handler.SEPARATOR_SPEC.separators_regex[1]

    def test_no_lookaheads_in_separators(self):
        """Separators must not contain lookahead/lookbehind patterns."""
        handler = GitLabCIHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep
            assert "(?<=" not in sep
            assert "(?!" not in sep
            assert "(?<!" not in sep


@pytest.mark.unit
class TestGitLabCIExtractMetadata:
    """Tests for GitLabCIHandler.extract_metadata()."""

    # --- Job detection (top-level key, not keyword/template) ---

    def test_job_definition(self):
        """Top-level key that's not a keyword is detected as job."""
        handler = GitLabCIHandler()
        text = "build:\n  stage: build\n  script:\n    - make build"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job"
        assert m["hierarchy"] == "job:build"
        assert m["language_id"] == "gitlab-ci"

    def test_job_with_hyphen(self):
        """Job name with hyphen extracts correctly."""
        handler = GitLabCIHandler()
        text = "integration-test:\n  script:\n    - pytest"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job"
        assert m["hierarchy"] == "job:integration-test"

    def test_template_job(self):
        """Hidden job (starting with .) is identified as template."""
        handler = GitLabCIHandler()
        text = ".base_job:\n  image: python:3.11\n  before_script:\n    - pip install"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "template"
        assert m["hierarchy"] == "template:.base_job"
        assert m["language_id"] == "gitlab-ci"

    # --- Job-key detection (2-space indented) ---

    def test_job_key_script(self):
        """2-space indented 'script:' detected as job-key."""
        handler = GitLabCIHandler()
        text = "  script:\n    - make build"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job-key"
        assert m["hierarchy"] == "job-key:script"
        assert m["language_id"] == "gitlab-ci"

    def test_job_key_image(self):
        """2-space indented 'image:' detected as job-key."""
        handler = GitLabCIHandler()
        text = "  image: python:3.11"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job-key"
        assert m["hierarchy"] == "job-key:image"

    def test_job_key_stage(self):
        """2-space indented 'stage:' detected as job-key."""
        handler = GitLabCIHandler()
        text = "  stage: build"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job-key"
        assert m["hierarchy"] == "job-key:stage"

    # --- Nested key detection (4+ space indented) ---

    def test_nested_key_only(self):
        """4-space indented 'only:' detected as nested-key."""
        handler = GitLabCIHandler()
        text = "    only:\n      - main"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:only"
        assert m["language_id"] == "gitlab-ci"

    def test_nested_key_rules(self):
        """4-space indented 'rules:' detected as nested-key."""
        handler = GitLabCIHandler()
        text = "    rules:\n      - if: $CI_COMMIT_BRANCH == 'main'"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:rules"

    def test_deeply_nested_key(self):
        """6-space indented key still detected as nested-key."""
        handler = GitLabCIHandler()
        text = "      variables:\n        GIT_STRATEGY: fetch"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:variables"

    # --- List item detection ---

    def test_list_item_key(self):
        """YAML list item with key detected as list-item."""
        handler = GitLabCIHandler()
        text = "- project: mygroup/myproject"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:project"
        assert m["language_id"] == "gitlab-ci"

    def test_list_item_indented(self):
        """Indented YAML list item with key detected as list-item."""
        handler = GitLabCIHandler()
        text = "      - local: /templates/.ci-template.yml"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:local"

    # --- Top-level key detection (global keywords) ---

    def test_stages_keyword(self):
        """'stages:' block is identified as global keyword."""
        handler = GitLabCIHandler()
        text = "stages:\n  - build\n  - test\n  - deploy"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "stages"
        assert m["hierarchy"] == "stages"
        assert m["language_id"] == "gitlab-ci"

    def test_variables_keyword(self):
        """'variables:' block is identified as global keyword."""
        handler = GitLabCIHandler()
        text = "variables:\n  CI_DEBUG: 'true'"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "variables"
        assert m["hierarchy"] == "variables"

    def test_include_keyword(self):
        """'include:' block is identified as global keyword."""
        handler = GitLabCIHandler()
        text = "include:\n  - local: /templates/.ci-template.yml"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "include"
        assert m["hierarchy"] == "include"

    def test_default_keyword(self):
        """'default:' block is identified as global keyword."""
        handler = GitLabCIHandler()
        text = "default:\n  image: ruby:3.0"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "default"
        assert m["hierarchy"] == "default"

    def test_workflow_keyword(self):
        """'workflow:' block is identified as global keyword."""
        handler = GitLabCIHandler()
        text = "workflow:\n  rules:\n    - if: $CI_COMMIT_BRANCH"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "workflow"
        assert m["hierarchy"] == "workflow"

    # --- Document separator detection ---

    def test_document_separator(self):
        """Chunk with --- detected as document."""
        handler = GitLabCIHandler()
        text = "---"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "document"
        assert m["hierarchy"] == "document"
        assert m["language_id"] == "gitlab-ci"

    def test_document_separator_with_whitespace(self):
        """Chunk containing --- among whitespace detected as document."""
        handler = GitLabCIHandler()
        text = "\n---\n"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "document"
        assert m["hierarchy"] == "document"

    # --- Value continuation detection ---

    def test_value_continuation(self):
        """Chunk with content but no recognizable key detected as value."""
        handler = GitLabCIHandler()
        text = "    some deeply indented content"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "value"
        assert m["hierarchy"] == "value"
        assert m["language_id"] == "gitlab-ci"

    # --- Comment handling ---

    def test_comment_before_job(self):
        """Comment before job is correctly skipped."""
        handler = GitLabCIHandler()
        text = "# Build job\nbuild:\n  script: make"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job"
        assert m["hierarchy"] == "job:build"
        assert m["language_id"] == "gitlab-ci"

    def test_comment_before_global_keyword(self):
        """Comment before global keyword is correctly skipped."""
        handler = GitLabCIHandler()
        text = "# Pipeline stages\nstages:\n  - build\n  - deploy"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "stages"
        assert m["hierarchy"] == "stages"

    def test_comment_before_template(self):
        """Comment before template is correctly skipped."""
        handler = GitLabCIHandler()
        text = "# Base template\n.base_job:\n  image: alpine"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "template"
        assert m["hierarchy"] == "template:.base_job"

    # --- Empty / whitespace ---

    def test_empty_content(self):
        """Empty content returns empty block_type."""
        handler = GitLabCIHandler()
        m = handler.extract_metadata("")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "gitlab-ci"

    def test_whitespace_only(self):
        """Whitespace-only content returns empty block_type."""
        handler = GitLabCIHandler()
        m = handler.extract_metadata("   \n   \n")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""

    # --- Indentation precision ---

    def test_two_space_is_job_key_not_top_level(self):
        """2-space indented key is job-key, not top-level."""
        handler = GitLabCIHandler()
        text = "  script:\n    - echo hello"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job-key"
        assert m["hierarchy"] == "job-key:script"

    def test_four_space_is_nested_not_job_key(self):
        """4-space indented key is nested-key, not job-key."""
        handler = GitLabCIHandler()
        text = "    only:\n      - main\n      - develop"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:only"


@pytest.mark.unit
class TestGitLabCIProtocol:
    """Tests for GitLabCIHandler protocol compliance."""

    def test_has_grammar_name(self):
        handler = GitLabCIHandler()
        assert handler.GRAMMAR_NAME == "gitlab-ci"

    def test_has_base_language(self):
        handler = GitLabCIHandler()
        assert handler.BASE_LANGUAGE == "yaml"

    def test_has_path_patterns(self):
        handler = GitLabCIHandler()
        assert len(handler.PATH_PATTERNS) > 0

    def test_has_top_level_keys(self):
        """_TOP_LEVEL_KEYS should be a frozenset with expected keywords."""
        handler = GitLabCIHandler()
        assert isinstance(handler._TOP_LEVEL_KEYS, frozenset)
        assert "stages" in handler._TOP_LEVEL_KEYS
        assert "variables" in handler._TOP_LEVEL_KEYS
        assert "include" in handler._TOP_LEVEL_KEYS
