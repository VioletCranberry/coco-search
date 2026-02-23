"""Tests for cocosearch.deps.extractors.terraform module."""

from cocosearch.deps.extractors.terraform import TerraformExtractor
from cocosearch.deps.models import DepType


def _extract(content: str, file_path: str = "main.tf"):
    extractor = TerraformExtractor()
    return extractor.extract(file_path, content)


class TestModuleSources:
    """Tests for module source extraction."""

    def test_local_module_source(self):
        content = """\
module "vpc" {
  source = "./modules/vpc"
}
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "module_source"
        assert edges[0].metadata["value"] == "./modules/vpc"
        assert edges[0].target_file == "modules/vpc"
        assert edges[0].source_symbol == "vpc"
        assert edges[0].dep_type == DepType.REFERENCE

    def test_parent_relative_module(self):
        content = """\
module "shared" {
  source = "../shared/modules/db"
}
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["value"] == "../shared/modules/db"
        assert edges[0].target_file == "../shared/modules/db"  # local, kept as-is

    def test_registry_module_with_version(self):
        content = """\
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.0.0"
}
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].target_file is None  # external
        assert edges[0].metadata["version"] == "5.0.0"

    def test_local_module_no_version(self):
        content = """\
module "vpc" {
  source = "./modules/vpc"
}
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert "version" not in edges[0].metadata

    def test_multiple_modules(self):
        content = """\
module "vpc" {
  source = "./modules/vpc"
}

module "rds" {
  source = "./modules/rds"
}
"""
        edges = _extract(content)
        assert len(edges) == 2
        values = {e.metadata["value"] for e in edges}
        assert "./modules/vpc" in values
        assert "./modules/rds" in values

    def test_module_with_nested_braces(self):
        content = """\
module "vpc" {
  source = "./modules/vpc"

  tags = {
    Name        = "my-vpc"
    Environment = "prod"
  }

  cidr_blocks = ["10.0.0.0/16"]
}
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["value"] == "./modules/vpc"
        assert edges[0].target_file == "modules/vpc"

    def test_module_with_source_after_nested_block(self):
        content = """\
module "rds" {
  tags = {
    Name = "my-db"
  }

  source = "./modules/rds"
  engine = "postgres"
}
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["value"] == "./modules/rds"


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_file(self):
        assert _extract("") == []

    def test_no_modules(self):
        content = """\
resource "aws_instance" "web" {
  ami           = "ami-12345"
  instance_type = "t2.micro"
}
"""
        assert _extract(content) == []

    def test_languages_set(self):
        extractor = TerraformExtractor()
        assert extractor.LANGUAGES == {"terraform"}


class TestRequiredProviders:
    """Tests for required_providers extraction."""

    def test_single_provider(self):
        content = """\
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "provider"
        assert edges[0].metadata["source"] == "hashicorp/aws"
        assert edges[0].metadata["version"] == "~> 5.0"
        assert edges[0].source_symbol == "aws"
        assert edges[0].target_file is None
        assert edges[0].dep_type == DepType.REFERENCE

    def test_multiple_providers(self):
        content = """\
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    google = {
      source  = "hashicorp/google"
      version = ">= 4.0"
    }
    random = "hashicorp/random"
  }
}
"""
        edges = _extract(content)
        assert len(edges) == 3
        names = {e.source_symbol for e in edges}
        assert names == {"aws", "google", "random"}

    def test_provider_without_version(self):
        content = """\
terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["source"] == "hashicorp/aws"
        assert "version" not in edges[0].metadata

    def test_provider_shorthand(self):
        content = """\
terraform {
  required_providers {
    random = "hashicorp/random"
  }
}
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "provider"
        assert edges[0].metadata["source"] == "hashicorp/random"
        assert edges[0].source_symbol == "random"

    def test_terraform_block_without_required_providers(self):
        content = """\
terraform {
  required_version = ">= 1.0"
}
"""
        edges = _extract(content)
        assert len(edges) == 0

    def test_empty_required_providers(self):
        content = """\
terraform {
  required_providers {
  }
}
"""
        edges = _extract(content)
        assert len(edges) == 0


class TestRemoteState:
    """Tests for terraform_remote_state extraction."""

    def test_s3_remote_state(self):
        content = """\
data "terraform_remote_state" "vpc" {
  backend = "s3"
  config = {
    bucket = "my-bucket"
    key    = "vpc/terraform.tfstate"
    region = "us-east-1"
  }
}
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "remote_state"
        assert edges[0].metadata["name"] == "vpc"
        assert edges[0].metadata["backend"] == "s3"
        assert edges[0].metadata["key"] == "vpc/terraform.tfstate"
        assert edges[0].source_symbol == "vpc"
        assert edges[0].target_file is None
        assert edges[0].dep_type == DepType.REFERENCE

    def test_remote_state_without_key(self):
        content = """\
data "terraform_remote_state" "network" {
  backend = "consul"
}
"""
        edges = _extract(content)
        assert len(edges) == 1
        assert edges[0].metadata["backend"] == "consul"
        assert "key" not in edges[0].metadata

    def test_multiple_remote_states(self):
        content = """\
data "terraform_remote_state" "vpc" {
  backend = "s3"
  config = {
    key = "vpc/terraform.tfstate"
  }
}

data "terraform_remote_state" "dns" {
  backend = "s3"
  config = {
    key = "dns/terraform.tfstate"
  }
}
"""
        edges = _extract(content)
        assert len(edges) == 2
        names = {e.metadata["name"] for e in edges}
        assert names == {"vpc", "dns"}

    def test_regular_data_source_ignored(self):
        content = """\
data "aws_vpc" "main" {
  default = true
}
"""
        edges = _extract(content)
        assert len(edges) == 0


class TestVariableFiles:
    """Tests for .tfvars file association."""

    def test_tfvars_creates_variable_file_edge(self):
        content = 'region = "us-east-1"'
        edges = _extract(content, file_path="terraform.tfvars")
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "variable_file"
        assert edges[0].metadata["filename"] == "terraform.tfvars"
        assert edges[0].target_file == "."
        assert edges[0].dep_type == DepType.REFERENCE

    def test_auto_tfvars_creates_variable_file_edge(self):
        content = 'environment = "prod"'
        edges = _extract(content, file_path="envs/prod.auto.tfvars")
        assert len(edges) == 1
        assert edges[0].metadata["kind"] == "variable_file"
        assert edges[0].metadata["filename"] == "prod.auto.tfvars"
        assert edges[0].target_file == "envs"

    def test_tf_file_no_variable_file_edge(self):
        content = """\
variable "region" {
  default = "us-east-1"
}
"""
        edges = _extract(content, file_path="variables.tf")
        assert len(edges) == 0
