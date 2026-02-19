"""Tests for cocosearch.handlers.hcl module."""

import pytest

from cocosearch.handlers.hcl import HclHandler


@pytest.mark.unit
class TestHclHandlerExtensions:
    """Tests for HclHandler EXTENSIONS."""

    def test_extensions_contains_hcl_only(self):
        """EXTENSIONS should contain only .hcl."""
        handler = HclHandler()
        assert handler.EXTENSIONS == [".hcl"]
        assert len(handler.EXTENSIONS) == 1

    def test_does_not_contain_tf(self):
        """EXTENSIONS should not contain .tf (handled by Terraform grammar)."""
        handler = HclHandler()
        assert ".tf" not in handler.EXTENSIONS

    def test_does_not_contain_tfvars(self):
        """EXTENSIONS should not contain .tfvars (handled by Terraform grammar)."""
        handler = HclHandler()
        assert ".tfvars" not in handler.EXTENSIONS


@pytest.mark.unit
class TestHclHandlerSeparatorSpec:
    """Tests for HclHandler SEPARATOR_SPEC."""

    def test_language_name_is_hcl(self):
        """SEPARATOR_SPEC.language_name should be 'hcl'."""
        handler = HclHandler()
        assert handler.SEPARATOR_SPEC.language_name == "hcl"

    def test_aliases_is_empty(self):
        """SEPARATOR_SPEC.aliases should be empty (no tf/tfvars aliases)."""
        handler = HclHandler()
        assert handler.SEPARATOR_SPEC.aliases == []

    def test_has_separators(self):
        """SEPARATOR_SPEC should have a non-empty separators_regex list."""
        handler = HclHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) > 0

    def test_level1_is_generic_block_pattern(self):
        """Level 1 separator should be a generic identifier pattern, not Terraform keywords."""
        handler = HclHandler()
        level1 = handler.SEPARATOR_SPEC.separators_regex[0]
        # Should be a generic pattern matching any identifier
        assert "[a-z_]" in level1
        # Should NOT contain specific Terraform keywords
        assert "resource" not in level1
        assert "variable" not in level1

    def test_no_lookaheads_in_separators(self):
        """HCL separators must not contain lookahead or lookbehind patterns."""
        handler = HclHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep, f"Lookahead found in HCL separator: {sep}"
            assert "(?<=" not in sep, f"Lookbehind found in HCL separator: {sep}"
            assert "(?!" not in sep, f"Negative lookahead found in HCL separator: {sep}"
            assert "(?<!" not in sep, (
                f"Negative lookbehind found in HCL separator: {sep}"
            )


@pytest.mark.unit
class TestHclHandlerExtractMetadata:
    """Tests for HclHandler.extract_metadata()."""

    def test_generic_block_with_label(self):
        """Generic block with one label produces correct hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata('listener "http" {')
        assert m["block_type"] == "listener"
        assert m["hierarchy"] == "listener.http"
        assert m["language_id"] == "hcl"

    def test_generic_block_with_two_labels(self):
        """Generic block with two labels produces correct hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata('backend "consul" "primary" {')
        assert m["block_type"] == "backend"
        assert m["hierarchy"] == "backend.consul.primary"
        assert m["language_id"] == "hcl"

    def test_generic_block_no_labels(self):
        """Generic block with no labels produces block_type-only hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata("defaults {")
        assert m["block_type"] == "defaults"
        assert m["hierarchy"] == "defaults"
        assert m["language_id"] == "hcl"

    def test_nested_block(self):
        """Nested block (indented with brace) produces block metadata."""
        handler = HclHandler()
        m = handler.extract_metadata('  backend "file" {')
        assert m["block_type"] == "block"
        assert m["hierarchy"] == "block.backend.file"
        assert m["language_id"] == "hcl"

    def test_nested_block_no_label(self):
        """Nested block without label produces block metadata."""
        handler = HclHandler()
        m = handler.extract_metadata("  retry {")
        assert m["block_type"] == "block"
        assert m["hierarchy"] == "block.retry"
        assert m["language_id"] == "hcl"

    def test_attribute_assignment(self):
        """Attribute assignment produces attribute metadata."""
        handler = HclHandler()
        m = handler.extract_metadata("  max_retries = 3")
        assert m["block_type"] == "attribute"
        assert m["hierarchy"] == "attribute.max_retries"
        assert m["language_id"] == "hcl"

    def test_comment_before_block(self):
        """Comment line before block keyword is correctly skipped."""
        handler = HclHandler()
        m = handler.extract_metadata('# This block\nlistener "http" {')
        assert m["block_type"] == "listener"
        assert m["hierarchy"] == "listener.http"
        assert m["language_id"] == "hcl"

    def test_inline_comment_before_block(self):
        """HCL // comment before block is correctly skipped."""
        handler = HclHandler()
        m = handler.extract_metadata('// listener config\nlistener "http" {')
        assert m["block_type"] == "listener"
        assert m["hierarchy"] == "listener.http"
        assert m["language_id"] == "hcl"

    def test_block_comment_before_block(self):
        """HCL /* block comment */ before block is correctly skipped."""
        handler = HclHandler()
        m = handler.extract_metadata('/* block comment */\nlistener "http" {')
        assert m["block_type"] == "listener"
        assert m["hierarchy"] == "listener.http"
        assert m["language_id"] == "hcl"

    def test_multiline_block_comment(self):
        """Multi-line /* */ comment before block is correctly skipped."""
        handler = HclHandler()
        m = handler.extract_metadata(
            '/*\n * Listener configuration\n */\nlistener "http" {'
        )
        assert m["block_type"] == "listener"
        assert m["hierarchy"] == "listener.http"
        assert m["language_id"] == "hcl"

    def test_leading_newline(self):
        """Leading newline from separator split is handled."""
        handler = HclHandler()
        m = handler.extract_metadata('\nlistener "http" {')
        assert m["block_type"] == "listener"
        assert m["hierarchy"] == "listener.http"
        assert m["language_id"] == "hcl"

    def test_unrecognized_content_returns_empty(self):
        """Unrecognized content produces empty block_type and hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata("some random text without structure")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "hcl"

    def test_empty_content(self):
        """Empty content returns empty block_type and hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata("")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "hcl"

    def test_comment_with_keyword_no_block(self):
        """Comment containing block keyword does not produce false positive."""
        handler = HclHandler()
        m = handler.extract_metadata("# This listener was replaced\nsome_other_content")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "hcl"
