#!/usr/bin/env python3
"""Verify Phase 1 infrastructure setup.

This script checks that all Phase 1 foundation components are properly
configured and working together:
- PostgreSQL with pgvector extension enabled
- Ollama serving nomic-embed-text with 768-dimensional embeddings
- Python dependencies (cocoindex, psycopg, pgvector) installed

Run with: uv run python scripts/verify_setup.py
Exit code: 0 if all checks pass, 1 if any fail
"""

import json
import subprocess
import sys
import urllib.request


def check_postgres() -> bool:
    """Verify PostgreSQL is running with pgvector extension enabled.

    Uses docker exec to query the pg_extension catalog table.
    Returns True if pgvector extension is found with a version number.
    """
    try:
        result = subprocess.run(
            [
                "docker", "exec", "cocosearch-db",
                "psql", "-U", "cocoindex", "-d", "cocoindex", "-t", "-c",
                "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
            ],
            capture_output=True,
            text=True,
            check=True
        )
        version = result.stdout.strip()
        if version:
            print(f"[OK] PostgreSQL with pgvector {version}")
            return True
        else:
            print("[FAIL] pgvector extension not enabled")
            return False
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] PostgreSQL check failed: {e}")
        return False
    except FileNotFoundError:
        print("[FAIL] Docker not found - is Docker installed and running?")
        return False


def check_ollama() -> bool:
    """Verify Ollama is running with nomic-embed-text model.

    Checks two things:
    1. Ollama is running and nomic-embed-text model is available
    2. The model returns exactly 768-dimensional embeddings

    Returns True only if both conditions are met.
    """
    try:
        # Check Ollama is running and model is available
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=10) as resp:
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            if any("nomic-embed-text" in m for m in models):
                print("[OK] Ollama running with nomic-embed-text")
            else:
                print(f"[FAIL] nomic-embed-text not found. Available: {models}")
                return False

        # Verify embedding dimensions (must be exactly 768)
        req = urllib.request.Request(
            "http://localhost:11434/api/embed",
            data=json.dumps({"model": "nomic-embed-text", "input": "test code search"}).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            dims = len(data["embeddings"][0])
            if dims == 768:
                print(f"[OK] nomic-embed-text returns {dims} dimensions")
                return True
            else:
                print(f"[FAIL] Expected 768 dimensions, got {dims}")
                return False
    except urllib.error.URLError as e:
        print(f"[FAIL] Ollama check failed - is Ollama running? Error: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Ollama check failed: {e}")
        return False


def check_python_deps() -> bool:
    """Verify Python dependencies are installed.

    Imports the core dependencies and reports the cocoindex version.
    Returns True if all imports succeed.
    """
    try:
        import cocoindex
        import psycopg  # noqa: F401
        import pgvector  # noqa: F401
        print(f"[OK] Python dependencies installed (cocoindex {cocoindex.__version__})")
        return True
    except ImportError as e:
        print(f"[FAIL] Missing Python dependency: {e}")
        return False


def main() -> int:
    """Run all verification checks.

    Returns:
        0 if all checks pass
        1 if any check fails
    """
    print("=== Phase 1 Foundation Verification ===\n")

    results = [
        check_postgres(),
        check_ollama(),
        check_python_deps(),
    ]

    print()
    if all(results):
        print("All checks passed! Foundation is ready.")
        return 0
    else:
        print("Some checks failed. See above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
