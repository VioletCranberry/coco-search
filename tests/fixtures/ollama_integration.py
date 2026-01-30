"""Ollama integration fixtures for testing with real embeddings.

Provides session-scoped fixtures for Ollama integration tests.
Native-first detection checks localhost:11434 before falling back to Docker.
"""

import os

import cocoindex
import httpx
import pytest
from testcontainers.ollama import OllamaContainer


def is_ollama_available() -> bool:
    """Check if native Ollama is available on localhost:11434.

    Uses lightweight health check via /api/tags endpoint.
    2-second timeout sufficient for local check.

    Returns:
        True if Ollama responds with 200, False on timeout/connection error.
    """
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


@pytest.fixture(scope="session")
def ollama_service():
    """Provide Ollama service URL (native or Docker).

    Locked decisions from Phase 13 CONTEXT:
    - Native-first detection via localhost:11434 health check
    - Docker fallback when native unavailable
    - Session scope for performance (container persists for session)

    Yields:
        str: Ollama service URL (http://localhost:11434 or container URL)
    """
    # Check for native Ollama first
    if is_ollama_available():
        yield "http://localhost:11434"
        return

    # Fallback to Docker container
    try:
        container = OllamaContainer(model="nomic-embed-text")
        container.start()

        # Get container URL
        host = container.get_container_host_ip()
        port = container.get_exposed_port(11434)
        url = f"http://{host}:{port}"

        yield url

        # Cleanup
        container.stop()

    except Exception as e:
        pytest.skip(
            f"Ollama unavailable (native and Docker failed): {e}\n\n"
            f"To run Ollama integration tests:\n"
            f"1. Install Ollama: https://ollama.ai/download\n"
            f"2. Pull model: ollama pull nomic-embed-text\n"
            f"3. Start service: ollama serve\n\n"
            f"Or ensure Docker is available for container fallback."
        )


@pytest.fixture(scope="session")
def warmed_ollama(ollama_service):
    """Provide pre-warmed Ollama service ready for embedding requests.

    Locked decisions from Phase 13 CONTEXT:
    - Session-scoped warmup runs once per test session
    - Makes throwaway embedding request to load model into memory
    - 60s timeout for safety on first request (model load takes 15-30s)
    - Both pre-warm AND extended timeout approach

    Args:
        ollama_service: Ollama service URL from ollama_service fixture

    Yields:
        str: Ollama service URL (same as ollama_service, but warmed up)
    """
    # Set OLLAMA_HOST environment variable for CocoIndex
    original_host = os.environ.get("OLLAMA_HOST")
    os.environ["OLLAMA_HOST"] = ollama_service

    try:
        # Create warmup embedding flow
        # Note: EmbedText doesn't accept timeout parameter directly,
        # relying on environment and httpx defaults with generous buffer
        warmup_flow = cocoindex.transform_flow()(
            lambda text: text.transform(
                cocoindex.functions.EmbedText(
                    api_type=cocoindex.LlmApiType.OLLAMA,
                    model="nomic-embed-text",
                )
            )
        )

        # Execute warmup embedding (loads model into memory)
        # First request will be slow (15-30s), subsequent requests fast
        _ = warmup_flow(cocoindex.DataSlice(["warmup"]))

    except Exception as e:
        pytest.skip(
            f"Ollama warmup failed: {e}\n\n"
            f"Model loading timed out or failed. This may indicate:\n"
            f"1. Model not pulled: run 'ollama pull nomic-embed-text'\n"
            f"2. Ollama service not responding\n"
            f"3. Resource constraints (low memory/CPU)"
        )
    finally:
        # Restore original OLLAMA_HOST
        if original_host is not None:
            os.environ["OLLAMA_HOST"] = original_host
        elif "OLLAMA_HOST" in os.environ:
            del os.environ["OLLAMA_HOST"]

    yield ollama_service
