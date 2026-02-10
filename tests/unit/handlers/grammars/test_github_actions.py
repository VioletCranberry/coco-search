"""Tests for cocosearch.handlers.grammars.github_actions module."""

import pytest

from cocosearch.handlers.grammars.github_actions import GitHubActionsHandler


@pytest.mark.unit
class TestGitHubActionsMatching:
    """Tests for GitHubActionsHandler.matches()."""

    def test_matches_workflow_yml(self):
        """Matches .github/workflows/*.yml with valid content."""
        handler = GitHubActionsHandler()
        content = "name: CI\non: push\njobs:\n  build:"
        assert handler.matches(".github/workflows/ci.yml", content) is True

    def test_matches_workflow_yaml(self):
        """Matches .github/workflows/*.yaml with valid content."""
        handler = GitHubActionsHandler()
        content = "name: Deploy\non:\n  push:\njobs:\n  deploy:"
        assert handler.matches(".github/workflows/deploy.yaml", content) is True

    def test_rejects_missing_on_key(self):
        """Rejects workflow file without 'on:' key."""
        handler = GitHubActionsHandler()
        content = "name: CI\njobs:\n  build:"
        assert handler.matches(".github/workflows/ci.yml", content) is False

    def test_rejects_missing_jobs_key(self):
        """Rejects workflow file without 'jobs:' key."""
        handler = GitHubActionsHandler()
        content = "name: CI\non: push"
        assert handler.matches(".github/workflows/ci.yml", content) is False

    def test_rejects_non_workflow_path(self):
        """Rejects YAML files outside .github/workflows/."""
        handler = GitHubActionsHandler()
        content = "on: push\njobs:\n  build:"
        assert handler.matches("config/ci.yml", content) is False

    def test_matches_path_only_without_content(self):
        """Matches by path alone when content is None."""
        handler = GitHubActionsHandler()
        assert handler.matches(".github/workflows/ci.yml") is True

    def test_rejects_wrong_path_without_content(self):
        """Rejects wrong path when content is None."""
        handler = GitHubActionsHandler()
        assert handler.matches("random/file.yml") is False


@pytest.mark.unit
class TestGitHubActionsSeparatorSpec:
    """Tests for GitHubActionsHandler.SEPARATOR_SPEC."""

    def test_language_name(self):
        """SEPARATOR_SPEC.language_name should be 'github-actions'."""
        handler = GitHubActionsHandler()
        assert handler.SEPARATOR_SPEC.language_name == "github-actions"

    def test_has_separators(self):
        """SEPARATOR_SPEC should have a non-empty separators_regex list."""
        handler = GitHubActionsHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) > 0

    def test_no_lookaheads_in_separators(self):
        """Separators must not contain lookahead/lookbehind patterns."""
        handler = GitHubActionsHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep
            assert "(?<=" not in sep
            assert "(?!" not in sep
            assert "(?<!" not in sep


@pytest.mark.unit
class TestGitHubActionsExtractMetadata:
    """Tests for GitHubActionsHandler.extract_metadata()."""

    def test_step_with_name(self):
        """Step with 'name:' extracts step name."""
        handler = GitHubActionsHandler()
        text = "      - name: Checkout code\n        uses: actions/checkout@v4"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "step"
        assert m["hierarchy"] == "step:Checkout code"
        assert m["language_id"] == "github-actions"

    def test_step_with_uses_only(self):
        """Step with 'uses:' but no 'name:' extracts action reference."""
        handler = GitHubActionsHandler()
        text = "      - uses: actions/checkout@v4"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "step"
        assert m["hierarchy"] == "step:actions/checkout@v4"
        assert m["language_id"] == "github-actions"

    def test_job_definition(self):
        """Job definition extracts job name."""
        handler = GitHubActionsHandler()
        text = "build:\n    runs-on: ubuntu-latest"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job"
        assert m["hierarchy"] == "job:build"
        assert m["language_id"] == "github-actions"

    def test_top_level_name_key(self):
        """Top-level 'name:' key is identified as top-level."""
        handler = GitHubActionsHandler()
        text = "name: CI Pipeline"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "name"
        assert m["language_id"] == "github-actions"

    def test_unrecognized_content(self):
        """Unrecognized content returns empty block_type."""
        handler = GitHubActionsHandler()
        m = handler.extract_metadata("  some random indented text")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "github-actions"

    def test_comment_before_step(self):
        """Comment before step is correctly skipped."""
        handler = GitHubActionsHandler()
        text = "# Build step\n      - name: Build\n        run: make build"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "step"
        assert m["hierarchy"] == "step:Build"
        assert m["language_id"] == "github-actions"

    def test_step_name_with_quotes(self):
        """Step name with surrounding quotes has quotes stripped."""
        handler = GitHubActionsHandler()
        text = "      - name: 'Run tests'\n        run: pytest"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "step"
        assert m["hierarchy"] == "step:Run tests"
        assert m["language_id"] == "github-actions"


@pytest.mark.unit
class TestGitHubActionsProtocol:
    """Tests for GitHubActionsHandler protocol compliance."""

    def test_has_grammar_name(self):
        handler = GitHubActionsHandler()
        assert handler.GRAMMAR_NAME == "github-actions"

    def test_has_base_language(self):
        handler = GitHubActionsHandler()
        assert handler.BASE_LANGUAGE == "yaml"

    def test_has_path_patterns(self):
        handler = GitHubActionsHandler()
        assert len(handler.PATH_PATTERNS) > 0
