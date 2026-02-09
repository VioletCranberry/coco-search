"""Tests for cocosearch.handlers.hcl module."""

import pytest

from cocosearch.handlers.hcl import HclHandler


@pytest.mark.unit
class TestHclHandlerExtensions:
    """Tests for HclHandler EXTENSIONS."""

    def test_extensions_contains_tf_hcl_tfvars(self):
        """EXTENSIONS should contain .tf, .hcl, and .tfvars."""
        handler = HclHandler()
        assert ".tf" in handler.EXTENSIONS
        assert ".hcl" in handler.EXTENSIONS
        assert ".tfvars" in handler.EXTENSIONS
        assert len(handler.EXTENSIONS) == 3


@pytest.mark.unit
class TestHclHandlerSeparatorSpec:
    """Tests for HclHandler SEPARATOR_SPEC."""

    def test_language_name_is_hcl(self):
        """SEPARATOR_SPEC.language_name should be 'hcl'."""
        handler = HclHandler()
        assert handler.SEPARATOR_SPEC.language_name == "hcl"

    def test_aliases_contains_tf_tfvars(self):
        """SEPARATOR_SPEC.aliases should contain tf and tfvars."""
        handler = HclHandler()
        assert handler.SEPARATOR_SPEC.aliases == ["tf", "tfvars"]

    def test_has_separators(self):
        """SEPARATOR_SPEC should have a non-empty separators_regex list."""
        handler = HclHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) > 0

    def test_level1_contains_all_block_keywords(self):
        """Level 1 separator should include all 12 top-level HCL block keywords."""
        handler = HclHandler()
        level1 = handler.SEPARATOR_SPEC.separators_regex[0]
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

    def test_resource_two_labels(self):
        """resource with two labels produces correct block_type and hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata('resource "aws_s3_bucket" "data" {')
        assert m["block_type"] == "resource"
        assert m["hierarchy"] == "resource.aws_s3_bucket.data"
        assert m["language_id"] == "hcl"

    def test_data_two_labels(self):
        """data with two labels produces correct hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata('data "aws_iam_policy" "admin" {')
        assert m["block_type"] == "data"
        assert m["hierarchy"] == "data.aws_iam_policy.admin"
        assert m["language_id"] == "hcl"

    def test_module_one_label(self):
        """module with one label produces correct hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata('module "vpc" {')
        assert m["block_type"] == "module"
        assert m["hierarchy"] == "module.vpc"
        assert m["language_id"] == "hcl"

    def test_variable_one_label(self):
        """variable with one label produces correct hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata('variable "name" {')
        assert m["block_type"] == "variable"
        assert m["hierarchy"] == "variable.name"
        assert m["language_id"] == "hcl"

    def test_output_one_label(self):
        """output with one label produces correct hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata('output "id" {')
        assert m["block_type"] == "output"
        assert m["hierarchy"] == "output.id"
        assert m["language_id"] == "hcl"

    def test_provider_one_label(self):
        """provider with one label produces correct hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata('provider "aws" {')
        assert m["block_type"] == "provider"
        assert m["hierarchy"] == "provider.aws"
        assert m["language_id"] == "hcl"

    def test_check_one_label(self):
        """check with one label produces correct hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata('check "health" {')
        assert m["block_type"] == "check"
        assert m["hierarchy"] == "check.health"
        assert m["language_id"] == "hcl"

    def test_terraform_no_labels(self):
        """terraform with no labels produces block_type-only hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata("terraform {")
        assert m["block_type"] == "terraform"
        assert m["hierarchy"] == "terraform"
        assert m["language_id"] == "hcl"

    def test_locals_no_labels(self):
        """locals with no labels produces block_type-only hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata("locals {")
        assert m["block_type"] == "locals"
        assert m["hierarchy"] == "locals"
        assert m["language_id"] == "hcl"

    def test_import_no_labels(self):
        """import with no labels produces block_type-only hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata("import {")
        assert m["block_type"] == "import"
        assert m["hierarchy"] == "import"
        assert m["language_id"] == "hcl"

    def test_moved_no_labels(self):
        """moved with no labels produces block_type-only hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata("moved {")
        assert m["block_type"] == "moved"
        assert m["hierarchy"] == "moved"
        assert m["language_id"] == "hcl"

    def test_removed_no_labels(self):
        """removed with no labels produces block_type-only hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata("removed {")
        assert m["block_type"] == "removed"
        assert m["hierarchy"] == "removed"
        assert m["language_id"] == "hcl"

    def test_comment_before_block(self):
        """Comment line before block keyword is correctly skipped."""
        handler = HclHandler()
        m = handler.extract_metadata(
            '# This resource\nresource "aws_s3_bucket" "data" {'
        )
        assert m["block_type"] == "resource"
        assert m["hierarchy"] == "resource.aws_s3_bucket.data"
        assert m["language_id"] == "hcl"

    def test_inline_comment_before_block(self):
        """HCL // comment before block is correctly skipped."""
        handler = HclHandler()
        m = handler.extract_metadata(
            '// resource declaration\nresource "type" "name" {'
        )
        assert m["block_type"] == "resource"
        assert m["hierarchy"] == "resource.type.name"
        assert m["language_id"] == "hcl"

    def test_block_comment_before_block(self):
        """HCL /* block comment */ before block is correctly skipped."""
        handler = HclHandler()
        m = handler.extract_metadata('/* block comment */\nresource "type" "name" {')
        assert m["block_type"] == "resource"
        assert m["hierarchy"] == "resource.type.name"
        assert m["language_id"] == "hcl"

    def test_leading_newline(self):
        """Leading newline from separator split is handled."""
        handler = HclHandler()
        m = handler.extract_metadata('\nresource "aws_s3_bucket" "data" {')
        assert m["block_type"] == "resource"
        assert m["hierarchy"] == "resource.aws_s3_bucket.data"
        assert m["language_id"] == "hcl"

    def test_unrecognized_content_returns_empty(self):
        """Unrecognized content produces empty block_type and hierarchy."""
        handler = HclHandler()
        m = handler.extract_metadata("unknown_block {")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "hcl"

    def test_comment_with_keyword_no_block(self):
        """Comment containing block keyword does not produce false positive."""
        handler = HclHandler()
        m = handler.extract_metadata("# This resource was replaced\nsome_other_content")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "hcl"
