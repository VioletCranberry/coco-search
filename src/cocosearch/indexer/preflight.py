"""Infrastructure preflight checks for indexing.

Verifies PostgreSQL and Ollama are reachable before starting
the indexing pipeline, providing clear error messages on failure.
"""

import urllib.request
import urllib.error

import psycopg

DEFAULT_OLLAMA_URL = "http://localhost:11434"


def check_infrastructure(db_url: str, ollama_url: str | None) -> None:
    """Check PostgreSQL and Ollama are reachable. Raises ConnectionError if not."""
    _check_postgres(db_url)
    _check_ollama(ollama_url or DEFAULT_OLLAMA_URL)


def _check_postgres(db_url: str) -> None:
    try:
        with psycopg.connect(db_url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
    except psycopg.OperationalError as e:
        raise ConnectionError(
            f"PostgreSQL is not reachable at {db_url.split('@')[-1].split('/')[0]}. "
            f"Start it with: docker compose up -d\n"
            f"Details: {e}"
        ) from e


def _check_ollama(ollama_url: str) -> None:
    try:
        urllib.request.urlopen(ollama_url, timeout=3)  # noqa: S310
    except (urllib.error.URLError, OSError) as e:
        raise ConnectionError(
            f"Ollama is not reachable at {ollama_url}. "
            f"Start it with: docker compose up -d\n"
            f"Details: {e}"
        ) from e
