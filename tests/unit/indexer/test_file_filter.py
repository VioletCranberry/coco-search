"""Tests for cocosearch.indexer.file_filter module."""

from cocosearch.indexer.file_filter import (
    DEFAULT_EXCLUDES,
    build_exclude_patterns,
    load_gitignore_patterns,
)


class TestDefaultExcludes:
    """Tests for DEFAULT_EXCLUDES constant."""

    def test_contains_node_modules(self):
        """DEFAULT_EXCLUDES should contain node_modules pattern."""
        assert "**/node_modules" in DEFAULT_EXCLUDES

    def test_contains_pycache(self):
        """DEFAULT_EXCLUDES should contain __pycache__ pattern."""
        assert "**/__pycache__" in DEFAULT_EXCLUDES

    def test_contains_git(self):
        """DEFAULT_EXCLUDES should contain .git pattern."""
        assert "**/.git" in DEFAULT_EXCLUDES

    def test_does_not_blanket_exclude_dotfiles(self):
        """DEFAULT_EXCLUDES should NOT blanket-exclude all dotfiles.

        The old '.*' pattern blocked CI config files like .gitlab-ci.yml.
        Instead, specific hidden directories are excluded individually.
        """
        assert ".*" not in DEFAULT_EXCLUDES

    def test_contains_hidden_directories(self):
        """DEFAULT_EXCLUDES should exclude common hidden directories."""
        assert "**/.venv" in DEFAULT_EXCLUDES
        assert "**/.idea" in DEFAULT_EXCLUDES
        assert "**/.vscode" in DEFAULT_EXCLUDES

    def test_contains_build_directories(self):
        """DEFAULT_EXCLUDES should contain common build directories."""
        assert "**/dist" in DEFAULT_EXCLUDES
        assert "**/build" in DEFAULT_EXCLUDES


class TestLoadGitignorePatterns:
    """Tests for load_gitignore_patterns function."""

    def test_returns_empty_when_no_gitignore(self, tmp_path):
        """Returns empty list when .gitignore doesn't exist."""
        patterns = load_gitignore_patterns(str(tmp_path))
        assert patterns == []

    def test_loads_patterns_from_file(self, tmp_path):
        """Reads non-empty, non-comment lines from .gitignore."""
        gitignore_content = "*.pyc\n__pycache__/\n*.egg-info/\n"
        (tmp_path / ".gitignore").write_text(gitignore_content)

        patterns = load_gitignore_patterns(str(tmp_path))

        assert "*.pyc" in patterns
        assert "__pycache__/" in patterns
        assert "*.egg-info/" in patterns

    def test_ignores_comments_and_empty(self, tmp_path):
        """Filters out # comments and blank lines."""
        gitignore_content = """# This is a comment
*.pyc

# Another comment
__pycache__/

"""
        (tmp_path / ".gitignore").write_text(gitignore_content)

        patterns = load_gitignore_patterns(str(tmp_path))

        assert len(patterns) == 2
        assert "*.pyc" in patterns
        assert "__pycache__/" in patterns
        # Verify comments are not included
        assert not any(p.startswith("#") for p in patterns)

    def test_strips_whitespace(self, tmp_path):
        """Strips leading/trailing whitespace from patterns."""
        gitignore_content = "  *.pyc  \n\t__pycache__/\t\n"
        (tmp_path / ".gitignore").write_text(gitignore_content)

        patterns = load_gitignore_patterns(str(tmp_path))

        assert "*.pyc" in patterns
        assert "__pycache__/" in patterns


class TestBuildExcludePatterns:
    """Tests for build_exclude_patterns function."""

    def test_includes_defaults(self, tmp_path):
        """Always includes DEFAULT_EXCLUDES patterns."""
        patterns = build_exclude_patterns(str(tmp_path))

        for default in DEFAULT_EXCLUDES:
            assert default in patterns

    def test_adds_gitignore_when_enabled(self, tmp_path):
        """Includes .gitignore patterns when respect_gitignore=True."""
        (tmp_path / ".gitignore").write_text("custom_ignore/\n")

        patterns = build_exclude_patterns(str(tmp_path), respect_gitignore=True)

        assert "custom_ignore/" in patterns

    def test_skips_gitignore_when_disabled(self, tmp_path):
        """Excludes .gitignore patterns when respect_gitignore=False."""
        (tmp_path / ".gitignore").write_text("custom_ignore/\n")

        patterns = build_exclude_patterns(str(tmp_path), respect_gitignore=False)

        assert "custom_ignore/" not in patterns

    def test_adds_user_excludes(self, tmp_path):
        """Appends user-provided patterns."""
        user_patterns = ["my_custom_pattern/", "*.secret"]

        patterns = build_exclude_patterns(str(tmp_path), user_excludes=user_patterns)

        assert "my_custom_pattern/" in patterns
        assert "*.secret" in patterns

    def test_combines_all_sources(self, tmp_path):
        """Combines defaults, gitignore, and user excludes."""
        (tmp_path / ".gitignore").write_text("gitignore_pattern/\n")
        user_patterns = ["user_pattern/"]

        patterns = build_exclude_patterns(
            str(tmp_path),
            user_excludes=user_patterns,
            respect_gitignore=True,
        )

        # Check all sources present
        assert "**/node_modules" in patterns  # default
        assert "gitignore_pattern/" in patterns  # gitignore
        assert "user_pattern/" in patterns  # user

    def test_filters_empty_strings(self, tmp_path):
        """Filters out empty strings from final pattern list."""
        user_patterns = ["valid/", "", "also_valid/"]

        patterns = build_exclude_patterns(str(tmp_path), user_excludes=user_patterns)

        assert "" not in patterns
        assert "valid/" in patterns
        assert "also_valid/" in patterns

    def test_handles_none_user_excludes(self, tmp_path):
        """Handles None user_excludes without error."""
        patterns = build_exclude_patterns(str(tmp_path), user_excludes=None)

        # Should just have defaults (+ gitignore if present)
        assert len(patterns) >= len(DEFAULT_EXCLUDES)
