"""Tests for cocosearch.indexer.metadata module."""

from cocosearch.indexer.metadata import (
    DevOpsMetadata,
    extract_hcl_metadata,
    extract_dockerfile_metadata,
    extract_bash_metadata,
    _strip_leading_comments,
    _HCL_COMMENT_LINE,
    _DOCKERFILE_COMMENT_LINE,
    _BASH_COMMENT_LINE,
    _LANGUAGE_DISPATCH,
    _LANGUAGE_ID_MAP,
    _EMPTY_METADATA,
)


def _dispatch(text: str, language: str) -> DevOpsMetadata:
    """Replicate dispatch logic for testing without CocoIndex runtime."""
    extractor = _LANGUAGE_DISPATCH.get(language)
    if extractor is None:
        return _EMPTY_METADATA
    metadata = extractor(text)
    return DevOpsMetadata(
        block_type=metadata.block_type,
        hierarchy=metadata.hierarchy,
        language_id=_LANGUAGE_ID_MAP[language],
    )


class TestDevOpsMetadata:
    """Tests for DevOpsMetadata dataclass."""

    def test_dataclass_fields(self):
        """DevOpsMetadata has exactly 3 fields: block_type, hierarchy, language_id."""
        import dataclasses

        fields = [f.name for f in dataclasses.fields(DevOpsMetadata)]
        assert fields == ["block_type", "hierarchy", "language_id"]

    def test_empty_metadata_constant(self):
        """_EMPTY_METADATA has all empty strings."""
        assert _EMPTY_METADATA.block_type == ""
        assert _EMPTY_METADATA.hierarchy == ""
        assert _EMPTY_METADATA.language_id == ""


class TestStripLeadingComments:
    """Tests for _strip_leading_comments helper."""

    def test_strips_hash_comments(self):
        """Text starting with '# comment\\nresource' returns text from 'resource' onward."""
        text = "# comment\nresource \"aws_s3_bucket\" \"data\" {"
        result = _strip_leading_comments(text, _HCL_COMMENT_LINE)
        assert result.startswith("resource")

    def test_strips_blank_lines(self):
        """Text starting with blank lines returns text from first non-blank line."""
        text = "\n\n\nresource \"aws_s3_bucket\" \"data\" {"
        result = _strip_leading_comments(text, _HCL_COMMENT_LINE)
        assert result.startswith("resource")

    def test_preserves_non_comment_text(self):
        """Text starting with non-comment content is returned unchanged (after lstrip)."""
        text = "resource \"aws_s3_bucket\" \"data\" {"
        result = _strip_leading_comments(text, _HCL_COMMENT_LINE)
        assert result == text

    def test_all_comments_returns_empty(self):
        """Text with only comments returns empty string."""
        text = "# comment 1\n# comment 2\n# comment 3"
        result = _strip_leading_comments(text, _HCL_COMMENT_LINE)
        assert result == ""

    def test_strips_leading_whitespace(self):
        """Text starting with whitespace then comments then content is handled."""
        text = "   \n# comment\nresource \"type\" \"name\" {"
        result = _strip_leading_comments(text, _HCL_COMMENT_LINE)
        assert result.startswith("resource")


class TestExtractHclMetadata:
    """Tests for HCL metadata extraction."""

    def test_resource_two_labels(self):
        """resource with two labels produces correct block_type and hierarchy."""
        m = extract_hcl_metadata('resource "aws_s3_bucket" "data" {')
        assert m.block_type == "resource"
        assert m.hierarchy == "resource.aws_s3_bucket.data"
        assert m.language_id == "hcl"

    def test_data_two_labels(self):
        """data with two labels produces correct hierarchy."""
        m = extract_hcl_metadata('data "aws_iam_policy" "admin" {')
        assert m.block_type == "data"
        assert m.hierarchy == "data.aws_iam_policy.admin"

    def test_module_one_label(self):
        """module with one label produces correct hierarchy."""
        m = extract_hcl_metadata('module "vpc" {')
        assert m.block_type == "module"
        assert m.hierarchy == "module.vpc"

    def test_variable_one_label(self):
        """variable with one label produces correct hierarchy."""
        m = extract_hcl_metadata('variable "name" {')
        assert m.block_type == "variable"
        assert m.hierarchy == "variable.name"

    def test_output_one_label(self):
        """output with one label produces correct hierarchy."""
        m = extract_hcl_metadata('output "id" {')
        assert m.block_type == "output"
        assert m.hierarchy == "output.id"

    def test_provider_one_label(self):
        """provider with one label produces correct hierarchy."""
        m = extract_hcl_metadata('provider "aws" {')
        assert m.block_type == "provider"
        assert m.hierarchy == "provider.aws"

    def test_check_one_label(self):
        """check with one label produces correct hierarchy."""
        m = extract_hcl_metadata('check "health" {')
        assert m.block_type == "check"
        assert m.hierarchy == "check.health"

    def test_terraform_no_labels(self):
        """terraform with no labels produces block_type-only hierarchy."""
        m = extract_hcl_metadata("terraform {")
        assert m.block_type == "terraform"
        assert m.hierarchy == "terraform"

    def test_locals_no_labels(self):
        """locals with no labels produces block_type-only hierarchy."""
        m = extract_hcl_metadata("locals {")
        assert m.block_type == "locals"
        assert m.hierarchy == "locals"

    def test_import_no_labels(self):
        """import with no labels produces block_type-only hierarchy."""
        m = extract_hcl_metadata("import {")
        assert m.block_type == "import"
        assert m.hierarchy == "import"

    def test_moved_no_labels(self):
        """moved with no labels produces block_type-only hierarchy."""
        m = extract_hcl_metadata("moved {")
        assert m.block_type == "moved"
        assert m.hierarchy == "moved"

    def test_removed_no_labels(self):
        """removed with no labels produces block_type-only hierarchy."""
        m = extract_hcl_metadata("removed {")
        assert m.block_type == "removed"
        assert m.hierarchy == "removed"

    def test_comment_before_block(self):
        """Comment line before block keyword is correctly skipped."""
        m = extract_hcl_metadata('# This resource\nresource "aws_s3_bucket" "data" {')
        assert m.block_type == "resource"
        assert m.hierarchy == "resource.aws_s3_bucket.data"

    def test_comment_with_keyword_no_block(self):
        """Comment containing block keyword does not produce false positive."""
        m = extract_hcl_metadata("# This resource was replaced\nsome_other_content")
        assert m.block_type == ""
        assert m.hierarchy == ""
        assert m.language_id == "hcl"

    def test_leading_newline(self):
        """Leading newline from separator split is handled."""
        m = extract_hcl_metadata('\nresource "aws_s3_bucket" "data" {')
        assert m.block_type == "resource"
        assert m.hierarchy == "resource.aws_s3_bucket.data"

    def test_unrecognized_content(self):
        """Unrecognized content produces empty block_type and hierarchy."""
        m = extract_hcl_metadata("unknown_block {")
        assert m.block_type == ""
        assert m.hierarchy == ""
        assert m.language_id == "hcl"

    def test_hcl_inline_comment(self):
        """HCL // comment before block is correctly skipped."""
        m = extract_hcl_metadata('// resource declaration\nresource "type" "name" {')
        assert m.block_type == "resource"

    def test_hcl_block_comment(self):
        """HCL /* block comment */ before block is correctly skipped."""
        m = extract_hcl_metadata('/* block comment */\nresource "type" "name" {')
        assert m.block_type == "resource"


class TestExtractDockerfileMetadata:
    """Tests for Dockerfile metadata extraction."""

    def test_from_with_as(self):
        """FROM with AS clause produces stage hierarchy."""
        m = extract_dockerfile_metadata("FROM golang:1.21 AS builder")
        assert m.block_type == "FROM"
        assert m.hierarchy == "stage:builder"
        assert m.language_id == "dockerfile"

    def test_from_without_as(self):
        """FROM without AS clause produces image hierarchy."""
        m = extract_dockerfile_metadata("FROM ubuntu:22.04")
        assert m.block_type == "FROM"
        assert m.hierarchy == "image:ubuntu:22.04"

    def test_from_with_platform(self):
        """FROM with --platform flag and AS clause produces stage hierarchy."""
        m = extract_dockerfile_metadata(
            "FROM --platform=linux/amd64 golang:1.21 AS builder"
        )
        assert m.hierarchy == "stage:builder"

    def test_from_scratch(self):
        """FROM scratch produces image:scratch hierarchy."""
        m = extract_dockerfile_metadata("FROM scratch")
        assert m.block_type == "FROM"
        assert m.hierarchy == "image:scratch"

    def test_run_instruction(self):
        """RUN instruction produces empty hierarchy."""
        m = extract_dockerfile_metadata("RUN apt-get update")
        assert m.block_type == "RUN"
        assert m.hierarchy == ""

    def test_copy_instruction(self):
        """COPY instruction produces empty hierarchy."""
        m = extract_dockerfile_metadata("COPY . /app")
        assert m.block_type == "COPY"
        assert m.hierarchy == ""

    def test_env_instruction(self):
        """ENV instruction produces empty hierarchy."""
        m = extract_dockerfile_metadata("ENV NODE_ENV=production")
        assert m.block_type == "ENV"
        assert m.hierarchy == ""

    def test_comment_before_instruction(self):
        """Comment line before instruction is correctly skipped."""
        m = extract_dockerfile_metadata("# install deps\nRUN apt-get install")
        assert m.block_type == "RUN"

    def test_leading_newline(self):
        """Leading newline from separator split is handled."""
        m = extract_dockerfile_metadata("\nFROM golang:1.21 AS builder")
        assert m.block_type == "FROM"
        assert m.hierarchy == "stage:builder"

    def test_unrecognized_content(self):
        """Unrecognized content produces empty block_type and hierarchy."""
        m = extract_dockerfile_metadata('echo "not a dockerfile instruction"')
        assert m.block_type == ""
        assert m.hierarchy == ""
        assert m.language_id == "dockerfile"


class TestExtractBashMetadata:
    """Tests for Bash metadata extraction."""

    def test_posix_function(self):
        """POSIX function syntax 'name() {' is recognized."""
        m = extract_bash_metadata("deploy_app() {")
        assert m.block_type == "function"
        assert m.hierarchy == "function:deploy_app"
        assert m.language_id == "bash"

    def test_ksh_function(self):
        """ksh function syntax 'function name {' is recognized."""
        m = extract_bash_metadata("function deploy_app {")
        assert m.block_type == "function"
        assert m.hierarchy == "function:deploy_app"

    def test_hybrid_function(self):
        """Hybrid function syntax 'function name() {' is recognized."""
        m = extract_bash_metadata("function deploy_app() {")
        assert m.block_type == "function"
        assert m.hierarchy == "function:deploy_app"

    def test_function_with_underscores(self):
        """Function name with underscores is correctly extracted."""
        m = extract_bash_metadata("my_long_func_name() {")
        assert m.hierarchy == "function:my_long_func_name"

    def test_comment_before_function(self):
        """Comment line before function definition is correctly skipped."""
        m = extract_bash_metadata("# Deploy the app\ndeploy_app() {")
        assert m.block_type == "function"

    def test_non_function_chunk(self):
        """Non-function content produces empty block_type and hierarchy."""
        m = extract_bash_metadata('echo "hello world"')
        assert m.block_type == ""
        assert m.hierarchy == ""
        assert m.language_id == "bash"

    def test_if_block(self):
        """if block is not a function."""
        m = extract_bash_metadata("if [ -f /etc/hosts ]; then")
        assert m.block_type == ""
        assert m.hierarchy == ""

    def test_leading_newline(self):
        """Leading newline from separator split is handled."""
        m = extract_bash_metadata("\nfunction deploy_app {")
        assert m.block_type == "function"
        assert m.hierarchy == "function:deploy_app"


class TestLanguageDispatchMaps:
    """Tests for dispatch maps and language ID normalization."""

    def test_hcl_aliases_dispatch(self):
        """HCL aliases hcl, tf, tfvars all present in dispatch map."""
        for lang in ("hcl", "tf", "tfvars"):
            assert lang in _LANGUAGE_DISPATCH, f"{lang} missing from dispatch"

    def test_dockerfile_dispatch(self):
        """dockerfile present in dispatch map."""
        assert "dockerfile" in _LANGUAGE_DISPATCH

    def test_bash_aliases_dispatch(self):
        """Bash aliases sh, bash, zsh, shell all present in dispatch map."""
        for lang in ("sh", "bash", "zsh", "shell"):
            assert lang in _LANGUAGE_DISPATCH, f"{lang} missing from dispatch"

    def test_language_id_normalization(self):
        """Aliases map to canonical language IDs."""
        assert _LANGUAGE_ID_MAP["tf"] == "hcl"
        assert _LANGUAGE_ID_MAP["tfvars"] == "hcl"
        assert _LANGUAGE_ID_MAP["sh"] == "bash"
        assert _LANGUAGE_ID_MAP["zsh"] == "bash"
        assert _LANGUAGE_ID_MAP["shell"] == "bash"

    def test_unknown_language_not_in_dispatch(self):
        """Non-DevOps languages are not in dispatch map."""
        for lang in ("py", "js", ""):
            assert lang not in _LANGUAGE_DISPATCH


class TestExtractDevopsMetadataDispatch:
    """Tests for dispatch logic using _dispatch helper (avoids CocoIndex runtime)."""

    def test_python_file_returns_empty_strings(self):
        """Non-DevOps language returns all empty strings."""
        m = _dispatch("def foo():\n    pass", "py")
        assert m.block_type == ""
        assert m.hierarchy == ""
        assert m.language_id == ""

    def test_empty_language_returns_empty_strings(self):
        """Empty language string returns all empty strings."""
        m = _dispatch("some text", "")
        assert m.block_type == ""
        assert m.hierarchy == ""
        assert m.language_id == ""

    def test_hcl_via_tf_alias(self):
        """tf alias routes to HCL extraction with normalized language_id."""
        m = _dispatch('resource "aws_s3_bucket" "data" {', "tf")
        assert m.block_type == "resource"
        assert m.hierarchy == "resource.aws_s3_bucket.data"
        assert m.language_id == "hcl"

    def test_bash_via_sh_alias(self):
        """sh alias routes to Bash extraction with normalized language_id."""
        m = _dispatch("deploy_app() {", "sh")
        assert m.block_type == "function"
        assert m.hierarchy == "function:deploy_app"
        assert m.language_id == "bash"

    def test_devops_file_always_has_language_id(self):
        """DevOps file with unrecognized content still returns language_id."""
        m = _dispatch("some random content", "hcl")
        assert m.block_type == ""
        assert m.hierarchy == ""
        assert m.language_id == "hcl"
