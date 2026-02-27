"""Tests for cocosearch.handlers.bash module."""

import pytest

from cocosearch.handlers.bash import BashHandler


@pytest.mark.unit
class TestBashHandlerExtensions:
    """Tests for BashHandler EXTENSIONS."""

    def test_extensions_contains_sh_bash_zsh(self):
        """EXTENSIONS should contain .sh, .bash, and .zsh."""
        handler = BashHandler()
        assert ".sh" in handler.EXTENSIONS
        assert ".bash" in handler.EXTENSIONS
        assert ".zsh" in handler.EXTENSIONS


@pytest.mark.unit
class TestBashHandlerSeparatorSpec:
    """Tests for BashHandler SEPARATOR_SPEC."""

    def test_language_name_is_bash(self):
        """SEPARATOR_SPEC.language_name should be 'bash'."""
        handler = BashHandler()
        assert handler.SEPARATOR_SPEC.language_name == "bash"

    def test_aliases_contains_sh_zsh_shell(self):
        """SEPARATOR_SPEC.aliases should contain sh, zsh, and shell."""
        handler = BashHandler()
        assert handler.SEPARATOR_SPEC.aliases == ["sh", "zsh", "shell"]

    def test_has_separators(self):
        """SEPARATOR_SPEC should have a non-empty separators_regex list."""
        handler = BashHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) > 0

    def test_function_keyword_is_level_1(self):
        """Function keyword should be Level 1 (first separator)."""
        handler = BashHandler()
        assert "function" in handler.SEPARATOR_SPEC.separators_regex[0]

    def test_no_lookaheads_in_separators(self):
        """Bash separators must not contain lookahead or lookbehind patterns."""
        handler = BashHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep, f"Lookahead found in Bash separator: {sep}"
            assert "(?<=" not in sep, f"Lookbehind found in Bash separator: {sep}"
            assert "(?!" not in sep, (
                f"Negative lookahead found in Bash separator: {sep}"
            )
            assert "(?<!" not in sep, (
                f"Negative lookbehind found in Bash separator: {sep}"
            )


@pytest.mark.unit
class TestBashHandlerExtractMetadata:
    """Tests for BashHandler.extract_metadata()."""

    def test_posix_function_syntax(self):
        """POSIX function syntax 'name() {' is recognized."""
        handler = BashHandler()
        m = handler.extract_metadata("deploy_app() {")
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:deploy_app"
        assert m["language_id"] == "bash"

    def test_ksh_function_syntax(self):
        """ksh function syntax 'function name {' is recognized."""
        handler = BashHandler()
        m = handler.extract_metadata("function deploy_app {")
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:deploy_app"
        assert m["language_id"] == "bash"

    def test_hybrid_function_syntax(self):
        """Hybrid function syntax 'function name() {' is recognized."""
        handler = BashHandler()
        m = handler.extract_metadata("function deploy_app() {")
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:deploy_app"
        assert m["language_id"] == "bash"

    def test_function_with_underscores(self):
        """Function name with underscores is correctly extracted."""
        handler = BashHandler()
        m = handler.extract_metadata("my_long_func_name() {")
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:my_long_func_name"
        assert m["language_id"] == "bash"

    def test_function_with_alphanumeric_name(self):
        """Function name with alphanumeric characters is correctly extracted."""
        handler = BashHandler()
        m = handler.extract_metadata("deploy2app() {")
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:deploy2app"
        assert m["language_id"] == "bash"

    def test_posix_function_with_spaces(self):
        """POSIX function with extra spaces is recognized."""
        handler = BashHandler()
        m = handler.extract_metadata("deploy_app  ()  {")
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:deploy_app"
        assert m["language_id"] == "bash"

    def test_ksh_function_no_opening_brace(self):
        """ksh function without opening brace on same line is recognized."""
        handler = BashHandler()
        m = handler.extract_metadata("function deploy_app")
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:deploy_app"
        assert m["language_id"] == "bash"

    def test_comment_before_function(self):
        """Comment line before function definition is correctly skipped."""
        handler = BashHandler()
        m = handler.extract_metadata("# Deploy the app\ndeploy_app() {")
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:deploy_app"
        assert m["language_id"] == "bash"

    def test_non_function_content_returns_empty(self):
        """Non-function content produces empty block_type and hierarchy."""
        handler = BashHandler()
        m = handler.extract_metadata('echo "hello world"')
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "bash"

    def test_if_block_not_function(self):
        """if block is not recognized as a function."""
        handler = BashHandler()
        m = handler.extract_metadata("if [ -f /etc/hosts ]; then")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "bash"

    def test_for_block_not_function(self):
        """for block is not recognized as a function."""
        handler = BashHandler()
        m = handler.extract_metadata("for i in *.txt; do")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "bash"

    def test_while_block_not_function(self):
        """while block is not recognized as a function."""
        handler = BashHandler()
        m = handler.extract_metadata("while read line; do")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "bash"

    def test_leading_newline(self):
        """Leading newline from separator split is handled."""
        handler = BashHandler()
        m = handler.extract_metadata("\nfunction deploy_app {")
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:deploy_app"
        assert m["language_id"] == "bash"

    def test_leading_whitespace_and_newline(self):
        """Leading whitespace and newline is handled."""
        handler = BashHandler()
        m = handler.extract_metadata("   \n# comment\ndeploy_app() {")
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:deploy_app"
        assert m["language_id"] == "bash"
