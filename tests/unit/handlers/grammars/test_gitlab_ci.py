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


@pytest.mark.unit
class TestGitLabCISeparatorSpec:
    """Tests for GitLabCIHandler.SEPARATOR_SPEC."""

    def test_language_name(self):
        """SEPARATOR_SPEC.language_name should be 'gitlab-ci'."""
        handler = GitLabCIHandler()
        assert handler.SEPARATOR_SPEC.language_name == "gitlab-ci"

    def test_has_separators(self):
        """SEPARATOR_SPEC should have a non-empty separators_regex list."""
        handler = GitLabCIHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) > 0

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

    def test_job_with_stage(self):
        """Job with 'stage:' extracts job name."""
        handler = GitLabCIHandler()
        text = "build:\n  stage: build\n  script:\n    - make build"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job"
        assert m["hierarchy"] == "job:build"
        assert m["language_id"] == "gitlab-ci"

    def test_job_without_stage(self):
        """Job without 'stage:' still extracts as job."""
        handler = GitLabCIHandler()
        text = "lint:\n  script:\n    - ruff check ."
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job"
        assert m["hierarchy"] == "job:lint"
        assert m["language_id"] == "gitlab-ci"

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
        assert m["language_id"] == "gitlab-ci"

    def test_hidden_template(self):
        """Hidden job (starting with .) is identified as template."""
        handler = GitLabCIHandler()
        text = ".base_job:\n  image: python:3.11\n  before_script:\n    - pip install"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "template"
        assert m["hierarchy"] == "template:.base_job"
        assert m["language_id"] == "gitlab-ci"

    def test_unrecognized_content(self):
        """Unrecognized content returns empty block_type."""
        handler = GitLabCIHandler()
        m = handler.extract_metadata("  some indented content")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "gitlab-ci"

    def test_comment_before_job(self):
        """Comment before job is correctly skipped."""
        handler = GitLabCIHandler()
        text = "# Build job\nbuild:\n  script: make"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job"
        assert m["hierarchy"] == "job:build"
        assert m["language_id"] == "gitlab-ci"


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
