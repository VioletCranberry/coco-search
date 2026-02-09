"""E2E DevOps file validation tests.

Tests that Terraform, Dockerfile, and Bash files index correctly with proper
chunking, metadata extraction, and language filtering (E2E-06).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def e2e_fixtures_path():
    """Return path to e2e test fixtures."""
    return Path(__file__).parent.parent / "fixtures" / "e2e_fixtures"


@pytest.fixture(scope="module")
def indexed_devops_fixtures(initialized_db, warmed_ollama, e2e_fixtures_path):
    """Index e2e_fixtures once for all DevOps tests.

    Module-scoped fixture reduces test runtime by indexing once and reusing
    across all DevOps validation tests.

    Args:
        initialized_db: PostgreSQL connection URL with pgvector extension
        warmed_ollama: Pre-warmed Ollama service URL
        e2e_fixtures_path: Path to e2e test fixtures

    Yields:
        tuple: (index_name, env_dict) for search tests
    """
    env = os.environ.copy()
    env["COCOSEARCH_DATABASE_URL"] = initialized_db
    env["COCOSEARCH_OLLAMA_URL"] = warmed_ollama

    index_name = "e2e_devops_tests"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cocosearch",
            "index",
            str(e2e_fixtures_path),
            "-n",
            index_name,
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, f"Indexing failed: {result.stderr}"

    yield index_name, env


def run_search(
    query: str, env: dict, index_name: str, lang: str | None = None
) -> subprocess.CompletedProcess:
    """Run cocosearch search with given query and optional language filter.

    Args:
        query: Search query text
        env: Environment variables to pass to subprocess
        index_name: Index name to search
        lang: Optional language filter (e.g., "terraform", "bash")

    Returns:
        CompletedProcess with returncode, stdout, stderr
    """
    args = [sys.executable, "-m", "cocosearch", "search", query, "-n", index_name]

    if lang:
        args.extend(["--lang", lang])

    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        env=env,
    )


def test_terraform_indexing(indexed_devops_fixtures):
    """Test that Terraform files index correctly with HCL chunking (E2E-06).

    Verifies:
    - main.tf is indexed and searchable
    - --lang terraform filter finds HCL files
    - --lang hcl alias also works
    - Terraform-specific content is found

    Args:
        indexed_devops_fixtures: Module-scoped indexed fixtures
    """
    index_name, env = indexed_devops_fixtures

    # Search for Terraform-specific resource declaration
    result = run_search("aws_instance", env, index_name, lang="terraform")

    assert result.returncode == 0, f"Search failed: {result.stderr}"

    # Parse JSON output
    output = json.loads(result.stdout)
    results = output.get("results", [])

    # Should find main.tf containing aws_instance resource
    assert len(results) > 0, "Should find Terraform content"

    file_paths = [r["file_path"] for r in results]
    assert any("main.tf" in path for path in file_paths), (
        f"Should find main.tf in results: {file_paths}"
    )

    # Test HCL alias
    result_hcl = run_search("aws_instance", env, index_name, lang="hcl")
    assert result_hcl.returncode == 0, (
        f"Search with --lang hcl failed: {result_hcl.stderr}"
    )

    output_hcl = json.loads(result_hcl.stdout)
    results_hcl = output_hcl.get("results", [])

    # HCL alias should find same files as terraform
    assert len(results_hcl) > 0, "HCL alias should find Terraform content"


def test_dockerfile_indexing(indexed_devops_fixtures):
    """Test that Dockerfile indexes correctly with Dockerfile chunking (E2E-06).

    Verifies:
    - Dockerfile is indexed and searchable
    - --lang dockerfile filter works
    - Dockerfile-specific content is found

    Args:
        indexed_devops_fixtures: Module-scoped indexed fixtures
    """
    index_name, env = indexed_devops_fixtures

    # Search for Dockerfile-specific instruction
    result = run_search("FROM python", env, index_name, lang="dockerfile")

    assert result.returncode == 0, f"Search failed: {result.stderr}"

    # Parse JSON output
    output = json.loads(result.stdout)
    results = output.get("results", [])

    # Should find Dockerfile containing FROM python
    assert len(results) > 0, "Should find Dockerfile content"

    file_paths = [r["file_path"] for r in results]
    assert any("Dockerfile" in path for path in file_paths), (
        f"Should find Dockerfile in results: {file_paths}"
    )


def test_bash_indexing(indexed_devops_fixtures):
    """Test that Bash scripts index correctly with shell chunking (E2E-06).

    Verifies:
    - deploy.sh is indexed and searchable
    - --lang bash filter finds shell scripts
    - --lang shell alias also works
    - Bash-specific content is found

    Args:
        indexed_devops_fixtures: Module-scoped indexed fixtures
    """
    index_name, env = indexed_devops_fixtures

    # Search for Bash-specific command (docker build appears in deploy.sh)
    result = run_search("docker build", env, index_name, lang="bash")

    assert result.returncode == 0, f"Search failed: {result.stderr}"

    # Parse JSON output
    output = json.loads(result.stdout)
    results = output.get("results", [])

    # Should find deploy.sh containing docker build
    assert len(results) > 0, "Should find Bash content"

    file_paths = [r["file_path"] for r in results]
    assert any("deploy.sh" in path for path in file_paths), (
        f"Should find deploy.sh in results: {file_paths}"
    )

    # Test shell alias
    result_shell = run_search("docker build", env, index_name, lang="shell")
    assert result_shell.returncode == 0, (
        f"Search with --lang shell failed: {result_shell.stderr}"
    )

    output_shell = json.loads(result_shell.stdout)
    results_shell = output_shell.get("results", [])

    # Shell alias should find same files as bash
    assert len(results_shell) > 0, "Shell alias should find Bash content"


def test_devops_language_aliases(indexed_devops_fixtures):
    """Test that DevOps language aliases resolve correctly (E2E-06).

    Verifies short aliases work as expected:
    - tf -> terraform
    - docker -> dockerfile
    - sh -> bash

    Args:
        indexed_devops_fixtures: Module-scoped indexed fixtures
    """
    index_name, env = indexed_devops_fixtures

    # Test tf alias (should find main.tf)
    result_tf = run_search("aws_instance", env, index_name, lang="tf")
    assert result_tf.returncode == 0, (
        f"Search with --lang tf failed: {result_tf.stderr}"
    )

    output_tf = json.loads(result_tf.stdout)
    results_tf = output_tf.get("results", [])
    assert len(results_tf) > 0, "tf alias should find Terraform content"

    # Test docker alias (should find Dockerfile)
    result_docker = run_search("FROM python", env, index_name, lang="docker")
    assert result_docker.returncode == 0, (
        f"Search with --lang docker failed: {result_docker.stderr}"
    )

    output_docker = json.loads(result_docker.stdout)
    results_docker = output_docker.get("results", [])
    assert len(results_docker) > 0, "docker alias should find Dockerfile content"

    # Test sh alias (should find shell scripts)
    result_sh = run_search("docker build", env, index_name, lang="sh")
    assert result_sh.returncode == 0, (
        f"Search with --lang sh failed: {result_sh.stderr}"
    )

    output_sh = json.loads(result_sh.stdout)
    results_sh = output_sh.get("results", [])
    assert len(results_sh) > 0, "sh alias should find Bash content"


def test_devops_metadata_presence(indexed_devops_fixtures):
    """Test that DevOps files have correct metadata in search results (E2E-06).

    Verifies metadata pipeline preserves language and file information:
    - Language field is present and correct
    - File paths are accurate
    - Content is properly chunked

    Args:
        indexed_devops_fixtures: Module-scoped indexed fixtures
    """
    index_name, env = indexed_devops_fixtures

    # Search for Terraform content and check metadata
    result_tf = run_search("aws_instance", env, index_name, lang="terraform")
    assert result_tf.returncode == 0, f"Terraform search failed: {result_tf.stderr}"

    output_tf = json.loads(result_tf.stdout)
    results_tf = output_tf.get("results", [])
    assert len(results_tf) > 0, "Should have Terraform results"

    # Check that results have required metadata fields
    for result in results_tf:
        assert "file_path" in result, "Result should have file_path"
        assert "language" in result, "Result should have language field"
        assert "chunk" in result, "Result should have chunk content"

        # Language should be hcl for Terraform files
        if "main.tf" in result["file_path"]:
            assert result["language"] == "hcl", (
                f"main.tf should have language=hcl, got {result['language']}"
            )

    # Search for Dockerfile and check metadata
    result_docker = run_search("FROM python", env, index_name, lang="dockerfile")
    assert result_docker.returncode == 0, (
        f"Dockerfile search failed: {result_docker.stderr}"
    )

    output_docker = json.loads(result_docker.stdout)
    results_docker = output_docker.get("results", [])
    assert len(results_docker) > 0, "Should have Dockerfile results"

    # Check Dockerfile metadata
    for result in results_docker:
        if "Dockerfile" in result["file_path"]:
            assert result["language"] == "dockerfile", (
                f"Dockerfile should have language=dockerfile, got {result['language']}"
            )

    # Search for Bash and check metadata
    result_bash = run_search("docker build", env, index_name, lang="bash")
    assert result_bash.returncode == 0, f"Bash search failed: {result_bash.stderr}"

    output_bash = json.loads(result_bash.stdout)
    results_bash = output_bash.get("results", [])
    assert len(results_bash) > 0, "Should have Bash results"

    # Check Bash metadata
    for result in results_bash:
        if "deploy.sh" in result["file_path"]:
            assert result["language"] == "bash", (
                f"deploy.sh should have language=bash, got {result['language']}"
            )


def test_devops_vs_regular_filtering(indexed_devops_fixtures):
    """Test that language filtering correctly separates DevOps from regular files (E2E-06).

    Verifies language filter accuracy:
    - Generic search may return mixed results
    - Python filter excludes DevOps files
    - Terraform filter excludes Python files

    Args:
        indexed_devops_fixtures: Module-scoped indexed fixtures
    """
    index_name, env = indexed_devops_fixtures

    # Search for generic term that might appear in multiple file types
    # "app" appears in both auth.py and Dockerfile
    result_unfiltered = run_search("app", env, index_name)
    assert result_unfiltered.returncode == 0, (
        f"Unfiltered search failed: {result_unfiltered.stderr}"
    )

    output_unfiltered = json.loads(result_unfiltered.stdout)
    results_unfiltered = output_unfiltered.get("results", [])

    # Get unique languages from unfiltered results
    set(r["language"] for r in results_unfiltered)

    # Search with Python filter - should only return Python files
    result_python = run_search("app", env, index_name, lang="python")
    assert result_python.returncode == 0, (
        f"Python search failed: {result_python.stderr}"
    )

    output_python = json.loads(result_python.stdout)
    results_python = output_python.get("results", [])

    if len(results_python) > 0:
        # All results should be Python
        languages_python = set(r["language"] for r in results_python)
        assert languages_python == {"python"}, (
            f"Python filter should only return python files, got {languages_python}"
        )

    # Search with Terraform filter - should only return Terraform files
    result_terraform = run_search("production", env, index_name, lang="terraform")
    assert result_terraform.returncode == 0, (
        f"Terraform search failed: {result_terraform.stderr}"
    )

    output_terraform = json.loads(result_terraform.stdout)
    results_terraform = output_terraform.get("results", [])

    if len(results_terraform) > 0:
        # All results should be HCL/Terraform
        languages_terraform = set(r["language"] for r in results_terraform)
        assert languages_terraform == {"hcl"}, (
            f"Terraform filter should only return hcl files, got {languages_terraform}"
        )
