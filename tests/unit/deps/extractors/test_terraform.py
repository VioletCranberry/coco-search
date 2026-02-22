"""Tests for cocosearch.deps.extractors.terraform module."""

from cocosearch.deps.extractors.terraform import TerraformExtractor
from cocosearch.deps.models import DepType


def _extract(content: str, file_path: str = "main.tf"):
    extractor = TerraformExtractor()
    return extractor.extract(file_path, content)


class TestModuleSources:
    """Tests for module source extraction."""

    def test_local_module_source(self):
        content = '''\
module "vpc" {
  source = "./modules/vpc"
}
'''
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "module_source"
        assert edges[0].metadata["value"] == "./modules/vpc"
        assert edges[0].target_file == "modules/vpc"
        assert edges[0].source_symbol == "vpc"
        assert edges[0].dep_type == DepType.REFERENCE

    def test_parent_relative_module(self):
        content = '''\
module "shared" {
  source = "../shared/modules/db"
}
'''
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["value"] == "../shared/modules/db"
        assert edges[0].target_file == "../shared/modules/db"  # local, kept as-is

    def test_registry_module_source(self):
        content = '''\
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.0.0"
}
'''
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].target_file is None  # external

    def test_multiple_modules(self):
        content = '''\
module "vpc" {
  source = "./modules/vpc"
}

module "rds" {
  source = "./modules/rds"
}
'''
        edges = _extract(content)
        assert len(edges) == 2
        values = {e.metadata["value"] for e in edges}
        assert "./modules/vpc" in values
        assert "./modules/rds" in values


    def test_module_with_nested_braces(self):
        content = '''\
module "vpc" {
  source = "./modules/vpc"

  tags = {
    Name        = "my-vpc"
    Environment = "prod"
  }

  cidr_blocks = ["10.0.0.0/16"]
}
'''
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["value"] == "./modules/vpc"
        assert edges[0].target_file == "modules/vpc"

    def test_module_with_source_after_nested_block(self):
        content = '''\
module "rds" {
  tags = {
    Name = "my-db"
  }

  source = "./modules/rds"
  engine = "postgres"
}
'''
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["value"] == "./modules/rds"


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_file(self):
        assert _extract("") == []

    def test_no_modules(self):
        content = '''\
resource "aws_instance" "web" {
  ami           = "ami-12345"
  instance_type = "t2.micro"
}
'''
        assert _extract(content) == []

    def test_languages_set(self):
        extractor = TerraformExtractor()
        assert extractor.LANGUAGES == {"terraform"}
