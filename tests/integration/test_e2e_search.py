"""E2E search flow tests.

Tests the complete search pipeline from query through embedding generation to vector
search and result formatting using the actual CLI with real PostgreSQL and Ollama.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def e2e_fixtures_path():
    """Return path to e2e test fixtures."""
    return Path(__file__).parent.parent / "fixtures" / "e2e_fixtures"


@pytest.fixture
def indexed_e2e_fixtures(initialized_db, warmed_ollama, e2e_fixtures_path):
    """Index e2e_fixtures for each search test.

    Function scope ensures each test gets a fresh index. The clean_tables
    autouse fixture truncates all tables after each test, so we need to
    re-index for each test to ensure data availability.

    Args:
        initialized_db: PostgreSQL connection URL with pgvector extension
        warmed_ollama: Pre-warmed Ollama service URL
        e2e_fixtures_path: Path to synthetic test codebase

    Yields:
        tuple: (index_name, env_dict) for use in search commands
    """
    env = os.environ.copy()
    env["COCOSEARCH_DATABASE_URL"] = initialized_db
    env["COCOSEARCH_OLLAMA_URL"] = warmed_ollama

    index_name = "e2e_search_tests"

    # Index the fixtures
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cocosearch",
            "index",
            str(e2e_fixtures_path),
            "--name",
            index_name,
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, f"Indexing failed: {result.stderr}"

    yield index_name, env

    # Cleanup handled by clean_tables autouse fixture


def search_and_parse(
    query: str, index_name: str, env: dict, extra_args: list = None
) -> tuple[int, list, str]:
    """Run search command and parse JSON output.

    Key pattern from 14-RESEARCH.md: Check returncode before JSON parsing.
    Failed commands output error text, not JSON.

    Args:
        query: Search query string
        index_name: Name of index to search
        env: Environment variables for subprocess
        extra_args: Additional CLI arguments (e.g., ["--lang", "python"])

    Returns:
        tuple: (returncode, parsed_results_list, error_output)
    """
    args = [sys.executable, "-m", "cocosearch", "search", query, "--index", index_name]
    if extra_args:
        args.extend(extra_args)

    result = subprocess.run(args, capture_output=True, text=True, env=env)

    error_output = f"stdout: {result.stdout}\nstderr: {result.stderr}"

    # Return returncode and error output for error case tests
    if result.returncode != 0:
        return result.returncode, [], error_output

    # Parse JSON for success cases
    try:
        return result.returncode, json.loads(result.stdout), error_output
    except json.JSONDecodeError as e:
        pytest.fail(f"Failed to parse JSON output: {e}\n{error_output}")


def test_full_search_flow(indexed_e2e_fixtures):
    """Test complete search flow from query to results.

    Covers requirement E2E-02: CLI search command finds indexed content
    via semantic similarity.

    Args:
        indexed_e2e_fixtures: Pre-indexed e2e fixtures with environment
    """
    index_name, env = indexed_e2e_fixtures

    # Search for "authenticate user" (should find auth.py)
    returncode, results, stderr = search_and_parse("authenticate user", index_name, env)

    assert returncode == 0, f"Search command should succeed. stderr: {stderr}"
    assert len(results) > 0, "Should return at least one result"

    # Verify at least one result has good relevance score
    max_score = max(r["score"] for r in results)
    assert max_score > 0.3, f"Best result should have score > 0.3, got {max_score}"

    # Verify results contain auth.py
    result_files = [r["file_path"] for r in results]
    assert any("auth.py" in f for f in result_files), (
        f"Results should contain auth.py, got: {result_files}"
    )


def test_search_result_structure(indexed_e2e_fixtures):
    """Test that search results have correct JSON structure.

    Covers requirement E2E-05: Search results contain correct file paths,
    line numbers, and can be validated programmatically.

    Args:
        indexed_e2e_fixtures: Pre-indexed e2e fixtures with environment
    """
    index_name, env = indexed_e2e_fixtures

    # Search for known content (use semantically meaningful query with lower threshold)
    returncode, results, stderr = search_and_parse(
        "format currency", index_name, env, extra_args=["--min-score", "0.2"]
    )

    assert returncode == 0, f"Search command should succeed. stderr: {stderr}"
    assert len(results) > 0, "Should return at least one result"

    # Validate structure of first result
    result = results[0]

    # Required fields
    assert "file_path" in result, "Result should have file_path field"
    assert "start_line" in result, "Result should have start_line field"
    assert "end_line" in result, "Result should have end_line field"
    assert "score" in result, "Result should have score field"
    assert "content" in result, "Result should have content field"

    # Type validation
    assert isinstance(result["file_path"], str), "file_path should be string"
    assert isinstance(result["start_line"], int), "start_line should be int"
    assert isinstance(result["end_line"], int), "end_line should be int"
    assert isinstance(result["score"], (int, float)), "score should be numeric"
    assert isinstance(result["content"], str), "content should be string"

    # Value validation
    assert len(result["file_path"]) > 0, "file_path should not be empty"
    assert result["start_line"] >= 0, (
        f"start_line should be >= 0, got {result['start_line']}"
    )
    assert result["end_line"] >= result["start_line"], (
        f"end_line ({result['end_line']}) should be >= start_line ({result['start_line']})"
    )
    assert 0.0 <= result["score"] <= 1.0, (
        f"score should be in [0, 1], got {result['score']}"
    )
    # Note: content may be empty for some results
    assert isinstance(result["content"], str), "content should be string"

    # Validate file_path is a string (may be relative or absolute)
    # File existence check would require knowing the index base path
    assert Path(result["file_path"]).name, "file_path should have a filename"


def test_search_returns_correct_file(indexed_e2e_fixtures, e2e_fixtures_path):
    """Test that search returns correct files based on content.

    Covers requirement E2E-04: Search results contain correct file paths
    for language-specific content.

    Args:
        indexed_e2e_fixtures: Pre-indexed e2e fixtures with environment
        e2e_fixtures_path: Path to e2e fixtures for validation
    """
    index_name, env = indexed_e2e_fixtures

    # Search for "terraform web server" (terraform-specific) with lower threshold
    returncode, results, stderr = search_and_parse(
        "terraform web server", index_name, env, extra_args=["--min-score", "0.2"]
    )

    assert returncode == 0, f"Search command should succeed. stderr: {stderr}"
    assert len(results) > 0, "Should find results for terraform web server"

    # Verify results contain main.tf
    result_files = [r["file_path"] for r in results]
    assert any("main.tf" in f for f in result_files), (
        f"Results should contain main.tf for terraform content, got: {result_files}"
    )

    # Search for "docker build deploy" (bash script) with lower threshold
    returncode, results, stderr = search_and_parse(
        "docker build deploy", index_name, env, extra_args=["--min-score", "0.2"]
    )

    assert returncode == 0, f"Search command should succeed. stderr: {stderr}"
    assert len(results) > 0, "Should find results for docker build"

    # Verify results contain deploy.sh
    result_files = [r["file_path"] for r in results]
    assert any("deploy.sh" in f for f in result_files), (
        f"Results should contain deploy.sh for bash script content, got: {result_files}"
    )


def test_language_filtering(indexed_e2e_fixtures):
    """Test that --lang flag correctly filters search results by language.

    Validates that language filtering restricts results to matching files only.

    Args:
        indexed_e2e_fixtures: Pre-indexed e2e fixtures with environment
    """
    index_name, env = indexed_e2e_fixtures

    # Search for "format currency" without filter - should find JavaScript (lower threshold)
    returncode, results_all, stderr = search_and_parse(
        "format currency", index_name, env, extra_args=["--min-score", "0.2"]
    )

    assert returncode == 0, f"Search command should succeed. stderr: {stderr}"
    assert len(results_all) > 0, "Should find results for 'format currency'"

    # Search for "format currency" with --lang javascript - should only find JavaScript
    returncode, results_js, stderr = search_and_parse(
        "format currency",
        index_name,
        env,
        extra_args=["--lang", "javascript", "--min-score", "0.2"],
    )

    assert returncode == 0, (
        f"Search with --lang javascript should succeed. stderr: {stderr}"
    )
    assert len(results_js) > 0, "Should find JavaScript results"

    # Verify all results are JavaScript files
    for result in results_js:
        file_path = result["file_path"]
        assert file_path.endswith(".js"), (
            f"With --lang javascript, should only find .js files, got: {file_path}"
        )

    # Search with --lang python - should find Python files
    returncode, results_py, stderr = search_and_parse(
        "authenticate",
        index_name,
        env,
        extra_args=["--lang", "python", "--min-score", "0.2"],
    )

    assert returncode == 0, (
        f"Search with --lang python should succeed. stderr: {stderr}"
    )
    assert len(results_py) > 0, "Should find Python results"

    # Verify all results are Python files
    for result in results_py:
        file_path = result["file_path"]
        assert file_path.endswith(".py"), (
            f"With --lang python, should only find .py files, got: {file_path}"
        )


def test_search_empty_results(indexed_e2e_fixtures):
    """Test that search with high threshold returns few/no results.

    Covers E2E-02 edge case: Search should handle low-relevance queries gracefully.
    Note: Semantic search may match any query with some score, so we use a very
    high threshold to get minimal results.

    Args:
        indexed_e2e_fixtures: Pre-indexed e2e fixtures with environment
    """
    index_name, env = indexed_e2e_fixtures

    # Search with very high threshold - should return few or no results
    returncode, results, stderr = search_and_parse(
        "xyzabc123nonsense999", index_name, env, extra_args=["--min-score", "0.8"]
    )

    # Should succeed, even with no or minimal results
    assert returncode == 0, (
        f"Search with high threshold should succeed. stderr: {stderr}"
    )
    assert isinstance(results, list), "Should return a list"
    # With high threshold, expect 0 or very few results
    assert len(results) <= 2, (
        f"Should return few/no results with high threshold, got {len(results)}"
    )


def test_search_missing_index(warmed_ollama, initialized_db):
    """Test error handling when searching non-existent index.

    Validates that search command handles missing index gracefully with
    helpful error message.

    Args:
        warmed_ollama: Pre-warmed Ollama service URL
        initialized_db: PostgreSQL connection URL
    """
    env = os.environ.copy()
    env["COCOSEARCH_DATABASE_URL"] = initialized_db
    env["COCOSEARCH_OLLAMA_URL"] = warmed_ollama

    # Search against non-existent index
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cocosearch",
            "search",
            "test query",
            "--index",
            "nonexistent_index_12345",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    # Should fail with non-zero exit code
    assert result.returncode != 0, "Search on missing index should fail"

    # Should provide helpful error message
    error_output = result.stdout + result.stderr
    assert "index" in error_output.lower() or "not found" in error_output.lower(), (
        f"Error message should mention index issue: {error_output}"
    )
