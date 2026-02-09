"""E2E indexing flow tests.

Tests the complete indexing pipeline from file discovery through embedding
generation to vector storage using the actual CLI with real PostgreSQL and Ollama.
"""

import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest


@pytest.fixture
def e2e_fixtures_path():
    """Return path to e2e test fixtures."""
    return Path(__file__).parent.parent / "fixtures" / "e2e_fixtures"


def run_cocosearch(args: list[str], env: dict) -> subprocess.CompletedProcess:
    """Run cocosearch CLI with given arguments.

    Args:
        args: CLI arguments (e.g., ["index", "/path/to/codebase"])
        env: Environment variables to pass to subprocess

    Returns:
        CompletedProcess with returncode, stdout, stderr
    """
    return subprocess.run(
        [sys.executable, "-m", "cocosearch"] + args,
        capture_output=True,
        text=True,
        env=env,
    )


def test_full_indexing_flow(initialized_db, warmed_ollama, e2e_fixtures_path):
    """Test complete indexing flow from CLI invocation to database storage.

    Covers requirements:
    - E2E-01: CLI index command indexes files into PostgreSQL with real embeddings
    - E2E-03: Indexed files can be retrieved from database with correct metadata

    Args:
        initialized_db: PostgreSQL connection URL with pgvector extension
        warmed_ollama: Pre-warmed Ollama service URL
        e2e_fixtures_path: Path to synthetic test codebase
    """
    # Prepare environment for CLI
    env = os.environ.copy()
    env["COCOSEARCH_DATABASE_URL"] = initialized_db
    env["COCOSEARCH_OLLAMA_URL"] = warmed_ollama

    # Debug: print environment
    print("\n=== Environment ===")
    print(f"COCOSEARCH_DATABASE_URL: {env['COCOSEARCH_DATABASE_URL']}")
    print(f"COCOSEARCH_OLLAMA_URL: {env['COCOSEARCH_OLLAMA_URL']}")

    # Index the test codebase
    index_name = "test_full_indexing_flow"
    result = run_cocosearch(
        ["index", str(e2e_fixtures_path), "-n", index_name],
        env=env,
    )

    # Verify CLI succeeded
    assert result.returncode == 0, (
        f"Indexing failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )

    # Debug: print CLI output
    print(f"\n=== CLI STDOUT ===\n{result.stdout}")
    print(f"\n=== CLI STDERR ===\n{result.stderr}")

    # Verify data in database
    with psycopg.connect(initialized_db) as conn:
        with conn.cursor() as cur:
            # Check files table
            cur.execute(f"SELECT COUNT(*) FROM cocoindex_{index_name}_files")
            file_count = cur.fetchone()[0]

            # Should have indexed 5 files (auth.py, main.tf, Dockerfile, deploy.sh, utils.js)
            # Note: __init__.py might be excluded by default patterns
            assert file_count >= 5, f"Expected >= 5 files, got {file_count}"

            # Check chunks table
            cur.execute(f"SELECT COUNT(*) FROM cocoindex_{index_name}_chunks")
            chunk_count = cur.fetchone()[0]

            # Should have at least one chunk per file
            assert chunk_count >= 5, f"Expected >= 5 chunks, got {chunk_count}"

            # Verify embeddings exist (vector is not null)
            cur.execute(
                f"SELECT COUNT(*) FROM cocoindex_{index_name}_chunks WHERE embedding IS NOT NULL"
            )
            embedded_count = cur.fetchone()[0]

            assert embedded_count == chunk_count, "All chunks should have embeddings"

            # Verify file metadata is correct
            cur.execute(
                f"""
                SELECT file_path, language FROM cocoindex_{index_name}_files
                WHERE file_path LIKE '%auth.py'
                """
            )
            auth_file = cur.fetchone()

            assert auth_file is not None, "auth.py should be indexed"
            assert auth_file[1] == "python", (
                f"auth.py language should be python, got {auth_file[1]}"
            )


def test_incremental_indexing(initialized_db, warmed_ollama, tmp_path):
    """Test that incremental indexing only processes changed files.

    Args:
        initialized_db: PostgreSQL connection URL with pgvector extension
        warmed_ollama: Pre-warmed Ollama service URL
        tmp_path: Temporary directory for test codebase
    """
    # Create temporary codebase
    codebase = tmp_path / "codebase"
    codebase.mkdir()

    file1 = codebase / "file1.py"
    file2 = codebase / "file2.py"

    file1.write_text("def foo():\n    return 'original'\n")
    file2.write_text("def bar():\n    return 'stable'\n")

    # Prepare environment
    env = os.environ.copy()
    env["COCOSEARCH_DATABASE_URL"] = initialized_db
    env["COCOSEARCH_OLLAMA_URL"] = warmed_ollama

    index_name = "test_incremental_indexing"

    # Initial indexing
    result = run_cocosearch(
        ["index", str(codebase), "-n", index_name],
        env=env,
    )

    assert result.returncode == 0, f"Initial indexing failed: {result.stderr}"

    # Record initial state
    with psycopg.connect(initialized_db) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM cocoindex_{index_name}_chunks")
            initial_chunk_count = cur.fetchone()[0]

    # Modify one file
    file1.write_text("def foo():\n    return 'modified'\n")

    # Re-index
    result = run_cocosearch(
        ["index", str(codebase), "-n", index_name],
        env=env,
    )

    assert result.returncode == 0, f"Incremental indexing failed: {result.stderr}"

    # Verify database state
    with psycopg.connect(initialized_db) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM cocoindex_{index_name}_chunks")
            final_chunk_count = cur.fetchone()[0]

            # Should have same or similar number of chunks (incremental update)
            # The exact count may vary slightly based on chunking
            assert final_chunk_count >= initial_chunk_count - 2, (
                "Incremental indexing should maintain similar chunk count"
            )


def test_index_nonexistent_path(initialized_db, warmed_ollama):
    """Test error handling when indexing a nonexistent path.

    Args:
        initialized_db: PostgreSQL connection URL with pgvector extension
        warmed_ollama: Pre-warmed Ollama service URL
    """
    env = os.environ.copy()
    env["COCOSEARCH_DATABASE_URL"] = initialized_db
    env["COCOSEARCH_OLLAMA_URL"] = warmed_ollama

    # Try to index nonexistent path
    result = run_cocosearch(
        ["index", "/nonexistent/path/that/should/not/exist"],
        env=env,
    )

    # Should fail with non-zero exit code
    assert result.returncode != 0, "Should fail when path doesn't exist"

    # Should provide helpful error message
    error_output = result.stdout + result.stderr
    assert (
        "does not exist" in error_output.lower()
        or "not a directory" in error_output.lower()
    ), f"Error message should mention path issue: {error_output}"
