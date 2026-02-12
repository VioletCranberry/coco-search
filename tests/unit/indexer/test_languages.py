"""Tests for cocosearch.indexer.languages module."""

import re

import pytest

from cocosearch.handlers import get_custom_languages
from cocosearch.handlers.hcl import HclHandler
from cocosearch.handlers.dockerfile import DockerfileHandler
from cocosearch.handlers.bash import BashHandler

# Use handler constants directly
HCL_LANGUAGE = HclHandler.SEPARATOR_SPEC
DOCKERFILE_LANGUAGE = DockerfileHandler.SEPARATOR_SPEC
BASH_LANGUAGE = BashHandler.SEPARATOR_SPEC
HANDLER_CUSTOM_LANGUAGES = get_custom_languages()


class TestHclLanguage:
    """Tests for HCL CustomLanguageSpec."""

    def test_language_name(self):
        """HCL spec should have language_name 'hcl'."""
        assert HCL_LANGUAGE.language_name == "hcl"

    def test_aliases(self):
        """HCL spec should have tf and tfvars as aliases."""
        assert HCL_LANGUAGE.aliases == ["tf", "tfvars"]

    def test_has_separators(self):
        """HCL spec should have a non-empty separators_regex list."""
        assert len(HCL_LANGUAGE.separators_regex) > 0

    def test_level1_contains_all_block_keywords(self):
        """Level 1 separator should include all 12 top-level HCL block keywords."""
        level1 = HCL_LANGUAGE.separators_regex[0]
        expected_keywords = [
            "resource",
            "data",
            "variable",
            "output",
            "locals",
            "module",
            "provider",
            "terraform",
            "import",
            "moved",
            "removed",
            "check",
        ]
        for keyword in expected_keywords:
            assert keyword in level1, (
                f"Missing HCL keyword '{keyword}' in Level 1 separator"
            )

    def test_no_lookaheads_in_separators(self):
        """HCL separators must not contain lookahead or lookbehind patterns."""
        for sep in HCL_LANGUAGE.separators_regex:
            assert "(?=" not in sep, f"Lookahead found in HCL separator: {sep}"
            assert "(?<=" not in sep, f"Lookbehind found in HCL separator: {sep}"


class TestDockerfileLanguage:
    """Tests for Dockerfile CustomLanguageSpec."""

    def test_language_name(self):
        """Dockerfile spec should have language_name 'dockerfile'."""
        assert DOCKERFILE_LANGUAGE.language_name == "dockerfile"

    def test_aliases_empty(self):
        """Dockerfile spec should have no aliases (routing via extract_language)."""
        assert DOCKERFILE_LANGUAGE.aliases == []

    def test_has_separators(self):
        """Dockerfile spec should have a non-empty separators_regex list."""
        assert len(DOCKERFILE_LANGUAGE.separators_regex) > 0

    def test_from_is_separate_higher_priority(self):
        """FROM should be a separate separator at higher priority than other instructions."""
        separators = DOCKERFILE_LANGUAGE.separators_regex
        from_index = None
        instructions_index = None
        for i, sep in enumerate(separators):
            if "FROM" in sep and "RUN" not in sep:
                from_index = i
            if "RUN" in sep:
                instructions_index = i
        assert from_index is not None, "FROM separator not found"
        assert instructions_index is not None, "Instructions separator not found"
        assert from_index < instructions_index, (
            "FROM should be higher priority (lower index) than instructions"
        )

    def test_no_lookaheads_in_separators(self):
        """Dockerfile separators must not contain lookahead or lookbehind patterns."""
        for sep in DOCKERFILE_LANGUAGE.separators_regex:
            assert "(?=" not in sep, f"Lookahead found in Dockerfile separator: {sep}"
            assert "(?<=" not in sep, f"Lookbehind found in Dockerfile separator: {sep}"


class TestBashLanguage:
    """Tests for Bash CustomLanguageSpec."""

    def test_language_name(self):
        """Bash spec should have language_name 'bash'."""
        assert BASH_LANGUAGE.language_name == "bash"

    def test_aliases(self):
        """Bash spec should have sh, zsh, and shell as aliases."""
        assert BASH_LANGUAGE.aliases == ["sh", "zsh", "shell"]

    def test_has_separators(self):
        """Bash spec should have a non-empty separators_regex list."""
        assert len(BASH_LANGUAGE.separators_regex) > 0

    def test_function_keyword_is_highest_priority(self):
        """Function keyword should be Level 1 (first separator)."""
        assert "function" in BASH_LANGUAGE.separators_regex[0]

    def test_no_lookaheads_in_separators(self):
        """Bash separators must not contain lookahead or lookbehind patterns."""
        for sep in BASH_LANGUAGE.separators_regex:
            assert "(?=" not in sep, f"Lookahead found in Bash separator: {sep}"
            assert "(?<=" not in sep, f"Lookbehind found in Bash separator: {sep}"


class TestDevopsCustomLanguages:
    """Tests for HANDLER_CUSTOM_LANGUAGES aggregated list."""

    def test_contains_all_specs(self):
        """HANDLER_CUSTOM_LANGUAGES should contain 9 specs (4 language + 5 grammar)."""
        assert len(HANDLER_CUSTOM_LANGUAGES) == 11

    def test_contains_hcl(self):
        """HANDLER_CUSTOM_LANGUAGES should contain the HCL spec."""
        assert HCL_LANGUAGE in HANDLER_CUSTOM_LANGUAGES

    def test_contains_dockerfile(self):
        """HANDLER_CUSTOM_LANGUAGES should contain the Dockerfile spec."""
        assert DOCKERFILE_LANGUAGE in HANDLER_CUSTOM_LANGUAGES

    def test_contains_bash(self):
        """HANDLER_CUSTOM_LANGUAGES should contain the Bash spec."""
        assert BASH_LANGUAGE in HANDLER_CUSTOM_LANGUAGES


class TestAllSeparatorsNoLookaheads:
    """Guard test: no separator in any language uses lookahead or lookbehind."""

    def test_no_lookaheads_or_lookbehinds(self):
        """All separators across all languages must use standard Rust regex only."""
        for lang in HANDLER_CUSTOM_LANGUAGES:
            for sep in lang.separators_regex:
                assert "(?=" not in sep, (
                    f"Lookahead (?=) found in {lang.language_name} separator: {sep}"
                )
                assert "(?<=" not in sep, (
                    f"Lookbehind (?<=) found in {lang.language_name} separator: {sep}"
                )
                assert "(?!" not in sep, (
                    f"Negative lookahead (?!) found in {lang.language_name} separator: {sep}"
                )
                assert "(?<!" not in sep, (
                    f"Negative lookbehind (?<!) found in {lang.language_name} separator: {sep}"
                )

    def test_all_separators_are_valid_python_regex(self):
        """All separators should compile as valid Python regex (subset of Rust regex)."""
        for lang in HANDLER_CUSTOM_LANGUAGES:
            for sep in lang.separators_regex:
                try:
                    re.compile(sep)
                except re.error as e:
                    pytest.fail(f"Invalid regex in {lang.language_name}: {sep!r} - {e}")
