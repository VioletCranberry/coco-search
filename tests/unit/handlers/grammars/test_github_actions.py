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

    def test_matches_nested_github_workflows(self):
        """Matches .github/workflows/ in nested directories."""
        handler = GitHubActionsHandler()
        content = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest"
        assert (
            handler.matches("monorepo/frontend/.github/workflows/ci.yml", content)
            is True
        )

    def test_matches_nested_path_without_content(self):
        """Matches nested .github/workflows/ by path alone."""
        handler = GitHubActionsHandler()
        assert handler.matches("sub/.github/workflows/deploy.yml") is True

    def test_matches_deeply_nested_path(self):
        """Matches .github/workflows/ in deeply nested directory."""
        handler = GitHubActionsHandler()
        content = "on: push\njobs:\n  test:"
        assert (
            handler.matches("org/project/sub/.github/workflows/test.yaml", content)
            is True
        )

    def test_matches_deeply_nested_path_without_content(self):
        """Matches deeply nested .github/workflows/ by path alone."""
        handler = GitHubActionsHandler()
        assert handler.matches("org/project/.github/workflows/ci.yml") is True

    def test_rejects_github_but_not_workflows(self):
        """Rejects .github/ paths that aren't in workflows/."""
        handler = GitHubActionsHandler()
        content = "on: push\njobs:\n  build:"
        assert handler.matches(".github/dependabot.yml", content) is False


@pytest.mark.unit
class TestGitHubActionsSeparatorSpec:
    """Tests for GitHubActionsHandler.SEPARATOR_SPEC."""

    def test_language_name(self):
        """SEPARATOR_SPEC.language_name should be 'github-actions'."""
        handler = GitHubActionsHandler()
        assert handler.SEPARATOR_SPEC._config.language_name == "github-actions"

    def test_separator_count(self):
        """SEPARATOR_SPEC should have 8 separator levels."""
        handler = GitHubActionsHandler()
        assert len(handler.SEPARATOR_SPEC._config.separators_regex) == 8

    def test_has_yaml_document_separator(self):
        """First separator should be YAML document separator (---)."""
        handler = GitHubActionsHandler()
        assert r"\n---" in handler.SEPARATOR_SPEC._config.separators_regex[0]

    def test_has_top_level_key_separator(self):
        """Second separator should split on top-level keys."""
        handler = GitHubActionsHandler()
        assert r"[a-zA-Z_]" in handler.SEPARATOR_SPEC._config.separators_regex[1]

    def test_has_job_boundary_separator(self):
        """Third separator should split on 2-space indented job keys."""
        handler = GitHubActionsHandler()
        assert r"\n  " in handler.SEPARATOR_SPEC._config.separators_regex[2]

    def test_has_nested_key_separator(self):
        """Fourth separator should split on 4-space indented keys."""
        handler = GitHubActionsHandler()
        assert r"\n    " in handler.SEPARATOR_SPEC._config.separators_regex[3]

    def test_has_step_boundary_separator(self):
        """Fifth separator should split on step boundaries (6-space dash)."""
        handler = GitHubActionsHandler()
        assert r"\n      - " in handler.SEPARATOR_SPEC._config.separators_regex[4]

    def test_no_lookaheads_in_separators(self):
        """Separators must not contain lookahead/lookbehind patterns."""
        handler = GitHubActionsHandler()
        for sep in handler.SEPARATOR_SPEC._config.separators_regex:
            assert "(?=" not in sep
            assert "(?<=" not in sep
            assert "(?!" not in sep
            assert "(?<!" not in sep


@pytest.mark.unit
class TestGitHubActionsExtractMetadata:
    """Tests for GitHubActionsHandler.extract_metadata()."""

    # --- Step detection ---

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

    def test_step_name_with_quotes(self):
        """Step name with surrounding quotes has quotes stripped."""
        handler = GitHubActionsHandler()
        text = "      - name: 'Run tests'\n        run: pytest"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "step"
        assert m["hierarchy"] == "step:Run tests"
        assert m["language_id"] == "github-actions"

    def test_step_name_with_double_quotes(self):
        """Step name with double quotes has quotes stripped."""
        handler = GitHubActionsHandler()
        text = '      - name: "Deploy to prod"\n        run: deploy.sh'
        m = handler.extract_metadata(text)
        assert m["block_type"] == "step"
        assert m["hierarchy"] == "step:Deploy to prod"

    def test_step_with_run(self):
        """Step with 'name:' and 'run:' extracts step name."""
        handler = GitHubActionsHandler()
        text = "      - name: Run linting\n        run: npm run lint"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "step"
        assert m["hierarchy"] == "step:Run linting"

    # --- Job detection (2-space indented) ---

    def test_job_definition(self):
        """Job definition (2-space indented) extracts job name."""
        handler = GitHubActionsHandler()
        text = "  build:\n    runs-on: ubuntu-latest"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job"
        assert m["hierarchy"] == "job:build"
        assert m["language_id"] == "github-actions"

    def test_job_deploy(self):
        """Deploy job extracts correctly."""
        handler = GitHubActionsHandler()
        text = "  deploy:\n    needs: build\n    runs-on: ubuntu-latest"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job"
        assert m["hierarchy"] == "job:deploy"

    def test_job_with_hyphen(self):
        """Job name with hyphen extracts correctly."""
        handler = GitHubActionsHandler()
        text = "  integration-test:\n    runs-on: ubuntu-latest"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job"
        assert m["hierarchy"] == "job:integration-test"

    # --- Nested key detection (4+ space indented) ---

    def test_nested_key_runs_on(self):
        """4-space indented 'runs-on:' detected as nested-key."""
        handler = GitHubActionsHandler()
        text = "    runs-on: ubuntu-latest"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:runs-on"
        assert m["language_id"] == "github-actions"

    def test_nested_key_steps(self):
        """4-space indented 'steps:' detected as nested-key."""
        handler = GitHubActionsHandler()
        text = "    steps:"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:steps"

    def test_nested_key_strategy(self):
        """4-space indented 'strategy:' detected as nested-key."""
        handler = GitHubActionsHandler()
        text = "    strategy:\n      matrix:\n        node: [16, 18]"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:strategy"

    def test_nested_key_env(self):
        """4-space indented 'env:' detected as nested-key."""
        handler = GitHubActionsHandler()
        text = "    env:\n      CI: true"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:env"

    def test_deeply_nested_key(self):
        """6-space indented key still detected as nested-key."""
        handler = GitHubActionsHandler()
        text = "      matrix:\n        node: [16, 18, 20]"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:matrix"

    # --- List item detection ---

    def test_list_item_key(self):
        """YAML list item with key detected as list-item."""
        handler = GitHubActionsHandler()
        text = "- path: ./src"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:path"
        assert m["language_id"] == "github-actions"

    def test_list_item_indented(self):
        """Indented YAML list item with key detected as list-item."""
        handler = GitHubActionsHandler()
        text = "      - key: value\n        other: data"
        m = handler.extract_metadata(text)
        # step detection takes priority when 'name:' or 'uses:' present,
        # but generic list items without those trigger list-item
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:key"

    # --- Top-level key detection ---

    def test_top_level_name_key(self):
        """Top-level 'name:' key is identified as top-level."""
        handler = GitHubActionsHandler()
        text = "name: CI Pipeline"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "name"
        assert m["hierarchy"] == "name"
        assert m["language_id"] == "github-actions"

    def test_top_level_on_key(self):
        """Top-level 'on:' key is identified."""
        handler = GitHubActionsHandler()
        text = "on:\n  push:\n    branches: [main]"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "on"
        assert m["hierarchy"] == "on"

    def test_top_level_jobs_key(self):
        """Top-level 'jobs:' key is identified."""
        handler = GitHubActionsHandler()
        text = "jobs:\n"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "jobs"
        assert m["hierarchy"] == "jobs"
        assert m["language_id"] == "github-actions"

    def test_top_level_permissions_key(self):
        """Top-level 'permissions:' key is identified."""
        handler = GitHubActionsHandler()
        text = "permissions:\n  contents: read"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "permissions"
        assert m["hierarchy"] == "permissions"

    def test_top_level_env_key(self):
        """Top-level 'env:' key with inline value is identified."""
        handler = GitHubActionsHandler()
        text = "env:\n  NODE_ENV: production"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "env"
        assert m["hierarchy"] == "env"

    # --- Document separator detection ---

    def test_document_separator(self):
        """Chunk with --- detected as document."""
        handler = GitHubActionsHandler()
        text = "---"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "document"
        assert m["hierarchy"] == "document"
        assert m["language_id"] == "github-actions"

    def test_document_separator_with_whitespace(self):
        """Chunk containing --- among whitespace detected as document."""
        handler = GitHubActionsHandler()
        text = "\n---\n"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "document"
        assert m["hierarchy"] == "document"

    # --- Value continuation detection ---

    def test_value_continuation(self):
        """Chunk with content but no recognizable key detected as value."""
        handler = GitHubActionsHandler()
        text = "    some deeply indented content"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "value"
        assert m["hierarchy"] == "value"
        assert m["language_id"] == "github-actions"

    # --- Comment handling ---

    def test_comment_before_step(self):
        """Comment before step is correctly skipped."""
        handler = GitHubActionsHandler()
        text = "# Build step\n      - name: Build\n        run: make build"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "step"
        assert m["hierarchy"] == "step:Build"
        assert m["language_id"] == "github-actions"

    def test_comment_before_job(self):
        """Comment before job definition is correctly skipped."""
        handler = GitHubActionsHandler()
        text = "# Build job\n  build:\n    runs-on: ubuntu-latest"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job"
        assert m["hierarchy"] == "job:build"

    def test_comment_before_top_level(self):
        """Comment before top-level key is correctly skipped."""
        handler = GitHubActionsHandler()
        text = "# Workflow name\nname: CI"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "name"
        assert m["hierarchy"] == "name"

    # --- Empty / whitespace ---

    def test_empty_content(self):
        """Empty content returns empty block_type."""
        handler = GitHubActionsHandler()
        m = handler.extract_metadata("")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "github-actions"

    def test_whitespace_only(self):
        """Whitespace-only content returns empty block_type."""
        handler = GitHubActionsHandler()
        m = handler.extract_metadata("   \n   \n")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""

    def test_unrecognized_content(self):
        """Unrecognized content without key returns value."""
        handler = GitHubActionsHandler()
        m = handler.extract_metadata("  some random indented text")
        assert m["block_type"] == "value"
        assert m["hierarchy"] == "value"
        assert m["language_id"] == "github-actions"

    # --- Indentation precision ---

    def test_two_space_is_job_not_top_level(self):
        """2-space indented key is job, not top-level."""
        handler = GitHubActionsHandler()
        text = "  test:\n    runs-on: ubuntu-latest"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "job"
        assert m["hierarchy"] == "job:test"

    def test_four_space_is_nested_not_job(self):
        """4-space indented key is nested-key, not job."""
        handler = GitHubActionsHandler()
        text = "    needs: [build, lint]"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:needs"


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

    def test_has_top_level_keys(self):
        """_TOP_LEVEL_KEYS should be a frozenset with expected keywords."""
        handler = GitHubActionsHandler()
        assert isinstance(handler._TOP_LEVEL_KEYS, frozenset)
        assert "name" in handler._TOP_LEVEL_KEYS
        assert "on" in handler._TOP_LEVEL_KEYS
        assert "jobs" in handler._TOP_LEVEL_KEYS
        assert "permissions" in handler._TOP_LEVEL_KEYS
