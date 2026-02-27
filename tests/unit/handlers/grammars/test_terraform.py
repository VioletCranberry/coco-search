"""Tests for cocosearch.handlers.grammars.terraform module."""

import pytest

from cocosearch.handlers.grammars.terraform import TerraformHandler


@pytest.mark.unit
class TestTerraformMatching:
    """Tests for TerraformHandler.matches()."""

    def test_matches_tf_file(self):
        """Matches *.tf files."""
        handler = TerraformHandler()
        assert handler.matches("main.tf") is True

    def test_matches_tfvars_file(self):
        """Matches *.tfvars files."""
        handler = TerraformHandler()
        assert handler.matches("terraform.tfvars") is True

    def test_matches_nested_tf_path(self):
        """Matches .tf files in nested directories."""
        handler = TerraformHandler()
        assert handler.matches("infra/modules/vpc/main.tf") is True

    def test_matches_nested_tfvars_path(self):
        """Matches .tfvars files in nested directories."""
        handler = TerraformHandler()
        assert handler.matches("environments/prod/vars.tfvars") is True

    def test_rejects_non_hcl_extension(self):
        """Rejects non-HCL file extensions."""
        handler = TerraformHandler()
        assert handler.matches("config.yaml") is False
        assert handler.matches("main.py") is False
        assert handler.matches("deploy.json") is False

    def test_rejects_plain_hcl(self):
        """Rejects .hcl files (handled by HCL language handler)."""
        handler = TerraformHandler()
        assert handler.matches("config.hcl") is False

    def test_matches_with_content_none(self):
        """Path alone is sufficient — content=None still matches."""
        handler = TerraformHandler()
        assert handler.matches("main.tf", None) is True
        assert handler.matches("terraform.tfvars", None) is True

    def test_matches_with_content(self):
        """Content is ignored — matches on path alone."""
        handler = TerraformHandler()
        assert handler.matches("main.tf", 'resource "aws_s3_bucket" "data" {') is True


@pytest.mark.unit
class TestTerraformSeparatorSpec:
    """Tests for TerraformHandler.SEPARATOR_SPEC."""

    def test_language_name(self):
        """SEPARATOR_SPEC.language_name should be 'terraform'."""
        handler = TerraformHandler()
        assert handler.SEPARATOR_SPEC.language_name == "terraform"

    def test_separator_count(self):
        """SEPARATOR_SPEC should have 6 separator levels."""
        handler = TerraformHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) == 6

    def test_has_all_12_keywords(self):
        """Level 1 separator should include all 12 Terraform block keywords."""
        handler = TerraformHandler()
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
                f"Missing Terraform keyword '{keyword}' in Level 1 separator"
            )

    def test_has_nested_block_separator(self):
        """Level 2 separator should match nested block openings."""
        handler = TerraformHandler()
        level2 = handler.SEPARATOR_SPEC.separators_regex[1]
        assert r"\n  " in level2

    def test_aliases(self):
        """SEPARATOR_SPEC.aliases should contain tf and tfvars."""
        handler = TerraformHandler()
        assert handler.SEPARATOR_SPEC.aliases == ["tf", "tfvars"]

    def test_no_lookaheads_in_separators(self):
        """Separators must not contain lookahead/lookbehind patterns."""
        handler = TerraformHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep, f"Lookahead found in separator: {sep}"
            assert "(?<=" not in sep, f"Lookbehind found in separator: {sep}"
            assert "(?!" not in sep, f"Negative lookahead found in separator: {sep}"
            assert "(?<!" not in sep, f"Negative lookbehind found in separator: {sep}"


@pytest.mark.unit
class TestTerraformExtractMetadata:
    """Tests for TerraformHandler.extract_metadata()."""

    # --- Top-level blocks (12 Terraform keywords) ---

    def test_resource_two_labels(self):
        """resource with two labels produces correct block_type and hierarchy."""
        handler = TerraformHandler()
        m = handler.extract_metadata('resource "aws_s3_bucket" "data" {')
        assert m["block_type"] == "resource"
        assert m["hierarchy"] == "resource.aws_s3_bucket.data"
        assert m["language_id"] == "terraform"

    def test_data_two_labels(self):
        """data with two labels produces correct hierarchy."""
        handler = TerraformHandler()
        m = handler.extract_metadata('data "aws_iam_policy" "admin" {')
        assert m["block_type"] == "data"
        assert m["hierarchy"] == "data.aws_iam_policy.admin"
        assert m["language_id"] == "terraform"

    def test_module_one_label(self):
        """module with one label produces correct hierarchy."""
        handler = TerraformHandler()
        m = handler.extract_metadata('module "vpc" {')
        assert m["block_type"] == "module"
        assert m["hierarchy"] == "module.vpc"
        assert m["language_id"] == "terraform"

    def test_variable_one_label(self):
        """variable with one label produces correct hierarchy."""
        handler = TerraformHandler()
        m = handler.extract_metadata('variable "name" {')
        assert m["block_type"] == "variable"
        assert m["hierarchy"] == "variable.name"
        assert m["language_id"] == "terraform"

    def test_output_one_label(self):
        """output with one label produces correct hierarchy."""
        handler = TerraformHandler()
        m = handler.extract_metadata('output "id" {')
        assert m["block_type"] == "output"
        assert m["hierarchy"] == "output.id"
        assert m["language_id"] == "terraform"

    def test_provider_one_label(self):
        """provider with one label produces correct hierarchy."""
        handler = TerraformHandler()
        m = handler.extract_metadata('provider "aws" {')
        assert m["block_type"] == "provider"
        assert m["hierarchy"] == "provider.aws"
        assert m["language_id"] == "terraform"

    def test_check_one_label(self):
        """check with one label produces correct hierarchy."""
        handler = TerraformHandler()
        m = handler.extract_metadata('check "health" {')
        assert m["block_type"] == "check"
        assert m["hierarchy"] == "check.health"
        assert m["language_id"] == "terraform"

    def test_terraform_no_labels(self):
        """terraform with no labels produces block_type-only hierarchy."""
        handler = TerraformHandler()
        m = handler.extract_metadata("terraform {")
        assert m["block_type"] == "terraform"
        assert m["hierarchy"] == "terraform"
        assert m["language_id"] == "terraform"

    def test_locals_no_labels(self):
        """locals with no labels produces block_type-only hierarchy."""
        handler = TerraformHandler()
        m = handler.extract_metadata("locals {")
        assert m["block_type"] == "locals"
        assert m["hierarchy"] == "locals"
        assert m["language_id"] == "terraform"

    def test_import_no_labels(self):
        """import with no labels produces block_type-only hierarchy."""
        handler = TerraformHandler()
        m = handler.extract_metadata("import {")
        assert m["block_type"] == "import"
        assert m["hierarchy"] == "import"
        assert m["language_id"] == "terraform"

    def test_moved_no_labels(self):
        """moved with no labels produces block_type-only hierarchy."""
        handler = TerraformHandler()
        m = handler.extract_metadata("moved {")
        assert m["block_type"] == "moved"
        assert m["hierarchy"] == "moved"
        assert m["language_id"] == "terraform"

    def test_removed_no_labels(self):
        """removed with no labels produces block_type-only hierarchy."""
        handler = TerraformHandler()
        m = handler.extract_metadata("removed {")
        assert m["block_type"] == "removed"
        assert m["hierarchy"] == "removed"
        assert m["language_id"] == "terraform"

    # --- Nested blocks ---

    def test_nested_block_lifecycle(self):
        """Nested lifecycle block produces block metadata."""
        handler = TerraformHandler()
        m = handler.extract_metadata("  lifecycle {")
        assert m["block_type"] == "block"
        assert m["hierarchy"] == "block.lifecycle"
        assert m["language_id"] == "terraform"

    def test_nested_block_provisioner_with_label(self):
        """Nested provisioner block with label produces block metadata."""
        handler = TerraformHandler()
        m = handler.extract_metadata('  provisioner "local-exec" {')
        assert m["block_type"] == "block"
        assert m["hierarchy"] == "block.provisioner.local-exec"
        assert m["language_id"] == "terraform"

    # --- Attributes ---

    def test_attribute_ami(self):
        """Attribute assignment produces attribute metadata."""
        handler = TerraformHandler()
        m = handler.extract_metadata('  ami = "ami-12345678"')
        assert m["block_type"] == "attribute"
        assert m["hierarchy"] == "attribute.ami"
        assert m["language_id"] == "terraform"

    def test_attribute_prevent_destroy(self):
        """Boolean attribute produces attribute metadata."""
        handler = TerraformHandler()
        m = handler.extract_metadata("    prevent_destroy = true")
        assert m["block_type"] == "attribute"
        assert m["hierarchy"] == "attribute.prevent_destroy"
        assert m["language_id"] == "terraform"

    # --- Comment handling ---

    def test_comment_hash_before_block(self):
        """# comment before block keyword is correctly skipped."""
        handler = TerraformHandler()
        m = handler.extract_metadata(
            '# This resource\nresource "aws_s3_bucket" "data" {'
        )
        assert m["block_type"] == "resource"
        assert m["hierarchy"] == "resource.aws_s3_bucket.data"
        assert m["language_id"] == "terraform"

    def test_comment_slash_before_block(self):
        """// comment before block is correctly skipped."""
        handler = TerraformHandler()
        m = handler.extract_metadata(
            '// resource declaration\nresource "type" "name" {'
        )
        assert m["block_type"] == "resource"
        assert m["hierarchy"] == "resource.type.name"
        assert m["language_id"] == "terraform"

    def test_block_comment_before_block(self):
        """/* block comment */ before block is correctly skipped."""
        handler = TerraformHandler()
        m = handler.extract_metadata('/* block comment */\nresource "type" "name" {')
        assert m["block_type"] == "resource"
        assert m["hierarchy"] == "resource.type.name"
        assert m["language_id"] == "terraform"

    def test_multiline_block_comment(self):
        """Multi-line /* */ comment is correctly skipped."""
        handler = TerraformHandler()
        m = handler.extract_metadata(
            '/*\n * S3 bucket for data\n */\nresource "aws_s3_bucket" "data" {'
        )
        assert m["block_type"] == "resource"
        assert m["hierarchy"] == "resource.aws_s3_bucket.data"
        assert m["language_id"] == "terraform"

    # --- Edge cases ---

    def test_unrecognized_content_returns_empty(self):
        """Unrecognized content produces empty block_type and hierarchy."""
        handler = TerraformHandler()
        m = handler.extract_metadata("unknown_block {")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "terraform"

    def test_empty_content(self):
        """Empty content returns empty block_type and hierarchy."""
        handler = TerraformHandler()
        m = handler.extract_metadata("")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "terraform"

    def test_leading_newline(self):
        """Leading newline from separator split is handled."""
        handler = TerraformHandler()
        m = handler.extract_metadata('\nresource "aws_s3_bucket" "data" {')
        assert m["block_type"] == "resource"
        assert m["hierarchy"] == "resource.aws_s3_bucket.data"
        assert m["language_id"] == "terraform"

    def test_comment_with_keyword_no_block(self):
        """Comment containing block keyword does not produce false positive."""
        handler = TerraformHandler()
        m = handler.extract_metadata("# This resource was replaced\nsome_other_content")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "terraform"

    def test_value_classification(self):
        """Content with = sign produces attribute metadata."""
        handler = TerraformHandler()
        m = handler.extract_metadata("  instance_type = var.type")
        assert m["block_type"] == "attribute"
        assert m["hierarchy"] == "attribute.instance_type"
        assert m["language_id"] == "terraform"


@pytest.mark.unit
class TestTerraformProtocol:
    """Tests for TerraformHandler protocol compliance."""

    def test_has_grammar_name(self):
        handler = TerraformHandler()
        assert handler.GRAMMAR_NAME == "terraform"

    def test_has_base_language(self):
        handler = TerraformHandler()
        assert handler.BASE_LANGUAGE == "hcl"

    def test_has_path_patterns(self):
        handler = TerraformHandler()
        assert len(handler.PATH_PATTERNS) > 0
        assert "**/*.tf" in handler.PATH_PATTERNS
        assert "**/*.tfvars" in handler.PATH_PATTERNS

    def test_has_matches_method(self):
        handler = TerraformHandler()
        assert hasattr(handler, "matches")
        assert callable(handler.matches)

    def test_has_terraform_keywords(self):
        """_TERRAFORM_KEYWORDS should be a frozenset with 12 keywords."""
        handler = TerraformHandler()
        assert isinstance(handler._TERRAFORM_KEYWORDS, frozenset)
        assert len(handler._TERRAFORM_KEYWORDS) == 12
        assert "resource" in handler._TERRAFORM_KEYWORDS
        assert "data" in handler._TERRAFORM_KEYWORDS
        assert "variable" in handler._TERRAFORM_KEYWORDS
