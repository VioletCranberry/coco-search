"""Tests for HCL and Terraform symbol extraction."""

from cocosearch.indexer.symbols import extract_symbol_metadata


class TestHclSymbols:
    """Test HCL symbol extraction (via 'hcl' language key)."""

    def test_resource_block(self):
        """Extract resource block with two labels."""
        code = 'resource "aws_s3_bucket" "data" {\n  bucket = "my-bucket"\n}'
        result = extract_symbol_metadata(code, "hcl")

        assert result.symbol_type == "class"
        assert result.symbol_name == "aws_s3_bucket.data"
        assert result.symbol_signature == 'resource "aws_s3_bucket" "data"'

    def test_variable_block(self):
        """Extract variable block with one label."""
        code = 'variable "region" {\n  default = "us-east-1"\n}'
        result = extract_symbol_metadata(code, "hcl")

        assert result.symbol_type == "class"
        assert result.symbol_name == "region"
        assert result.symbol_signature == 'variable "region"'

    def test_data_block(self):
        """Extract data block with two labels."""
        code = 'data "aws_ami" "ubuntu" {\n  most_recent = true\n}'
        result = extract_symbol_metadata(code, "hcl")

        assert result.symbol_type == "class"
        assert result.symbol_name == "aws_ami.ubuntu"
        assert result.symbol_signature == 'data "aws_ami" "ubuntu"'

    def test_module_block(self):
        """Extract module block with one label."""
        code = 'module "vpc" {\n  source = "./modules/vpc"\n}'
        result = extract_symbol_metadata(code, "hcl")

        assert result.symbol_type == "class"
        assert result.symbol_name == "vpc"
        assert result.symbol_signature == 'module "vpc"'

    def test_locals_block(self):
        """Extract locals block (no labels, falls back to identifier)."""
        code = 'locals {\n  name = "test"\n}'
        result = extract_symbol_metadata(code, "hcl")

        assert result.symbol_type == "class"
        assert result.symbol_name == "locals"
        assert result.symbol_signature == "locals"

    def test_output_block(self):
        """Extract output block."""
        code = 'output "bucket_arn" {\n  value = aws_s3_bucket.data.arn\n}'
        result = extract_symbol_metadata(code, "hcl")

        assert result.symbol_type == "class"
        assert result.symbol_name == "bucket_arn"
        assert result.symbol_signature == 'output "bucket_arn"'

    def test_provider_block(self):
        """Extract provider block."""
        code = 'provider "aws" {\n  region = "us-east-1"\n}'
        result = extract_symbol_metadata(code, "hcl")

        assert result.symbol_type == "class"
        assert result.symbol_name == "aws"
        assert result.symbol_signature == 'provider "aws"'

    def test_tfvars_extension(self):
        """tfvars extension uses HCL extractor."""
        code = 'variable "env" {\n  default = "prod"\n}'
        result = extract_symbol_metadata(code, "tfvars")

        assert result.symbol_type == "class"
        assert result.symbol_name == "env"

    def test_nested_block_returns_outer(self):
        """Nested blocks: first (outer) block is returned."""
        code = 'resource "aws_instance" "web" {\n  provisioner "local-exec" {\n    command = "echo hello"\n  }\n}'
        result = extract_symbol_metadata(code, "hcl")

        assert result.symbol_type == "class"
        assert result.symbol_name == "aws_instance.web"

    def test_empty_input(self):
        """Empty HCL returns NULL fields."""
        result = extract_symbol_metadata("", "hcl")

        assert result.symbol_type is None
        assert result.symbol_name is None
        assert result.symbol_signature is None

    def test_comments_only(self):
        """HCL with only comments returns NULL fields."""
        code = "# This is a comment\n// Another comment\n/* Block comment */"
        result = extract_symbol_metadata(code, "hcl")

        assert result.symbol_type is None


class TestTerraformSymbols:
    """Test Terraform symbol extraction (via 'tf' language key)."""

    def test_resource_block(self):
        """Extract Terraform resource block."""
        code = (
            'resource "aws_lambda_function" "handler" {\n  function_name = "my-func"\n}'
        )
        result = extract_symbol_metadata(code, "tf")

        assert result.symbol_type == "class"
        assert result.symbol_name == "aws_lambda_function.handler"
        assert result.symbol_signature == 'resource "aws_lambda_function" "handler"'

    def test_variable_block(self):
        """Extract Terraform variable block."""
        code = 'variable "instance_type" {\n  default = "t3.micro"\n}'
        result = extract_symbol_metadata(code, "tf")

        assert result.symbol_type == "class"
        assert result.symbol_name == "instance_type"

    def test_locals_block(self):
        """Extract Terraform locals block."""
        code = 'locals {\n  env = "prod"\n}'
        result = extract_symbol_metadata(code, "tf")

        assert result.symbol_type == "class"
        assert result.symbol_name == "locals"

    def test_empty_input(self):
        """Empty Terraform returns NULL fields."""
        result = extract_symbol_metadata("", "tf")

        assert result.symbol_type is None
        assert result.symbol_name is None
        assert result.symbol_signature is None
