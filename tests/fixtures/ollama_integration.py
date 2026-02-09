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
    container = None
    try:
        container = OllamaContainer()
        container.start()

        # Check if model exists, pull only if needed
        models = container.list_models()
        model_names = [m.get("name", "") for m in models]
        if "nomic-embed-text:latest" not in model_names:
            # Pull takes ~2-3 minutes for first time
            container.pull_model("nomic-embed-text")

        # Get container URL
        host = container.get_container_host_ip()
        port = container.get_exposed_port(11434)
        url = f"http://{host}:{port}"

        yield url

    except Exception as e:
        pytest.skip(
            f"Ollama unavailable (native and Docker failed): {e}\n\n"
            f"To run Ollama integration tests:\n"
            f"1. Install Ollama: https://ollama.ai/download\n"
            f"2. Pull model: ollama pull nomic-embed-text\n"
            f"3. Start service: ollama serve\n\n"
            f"Or ensure Docker is available for container fallback."
        )
    finally:
        # Cleanup: stop container if it was started
        if container is not None:
            try:
                container.stop()
            except Exception:
                pass  # Ignore cleanup errors


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
    # Set COCOSEARCH_OLLAMA_URL environment variable
    original_url = os.environ.get("COCOSEARCH_OLLAMA_URL")
    os.environ["COCOSEARCH_OLLAMA_URL"] = ollama_service

    try:
        # Create warmup embedding flow
        # Note: EmbedText doesn't accept timeout parameter directly,
        # relying on environment and httpx defaults with generous buffer
        # Use regular function instead of lambda for proper type annotations
        def warmup_embed(text: cocoindex.DataSlice[str]) -> cocoindex.DataSlice:
            return text.transform(
                cocoindex.functions.EmbedText(
                    api_type=cocoindex.LlmApiType.OLLAMA,
                    model="nomic-embed-text",
                )
            )

        warmup_flow = cocoindex.transform_flow()(warmup_embed)

        # Execute warmup embedding (loads model into memory)
        # First request will be slow (15-30s for native, 60-90s for container with pull)
        # Container-based Ollama may timeout if model needs pulling - that's expected
        try:
            _ = warmup_flow(cocoindex.DataSlice(["warmup"]))
        except Exception as warmup_error:
            # If warmup fails, log but don't skip - tests can still proceed
            # The first test request will just be slower
            import warnings

            warnings.warn(
                f"Ollama warmup failed (first test request will be slower): {warmup_error}",
                UserWarning,
            )

    except Exception as e:
        pytest.skip(
            f"Ollama service setup failed: {e}\n\n"
            f"To run Ollama integration tests:\n"
            f"1. Install Ollama: https://ollama.ai/download\n"
            f"2. Pull model: ollama pull nomic-embed-text\n"
            f"3. Start service: ollama serve\n\n"
            f"Or ensure Docker is available for container fallback."
        )
    finally:
        # Restore original COCOSEARCH_OLLAMA_URL
        if original_url is not None:
            os.environ["COCOSEARCH_OLLAMA_URL"] = original_url
        elif "COCOSEARCH_OLLAMA_URL" in os.environ:
            del os.environ["COCOSEARCH_OLLAMA_URL"]

    yield ollama_service
