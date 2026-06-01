"""Unit tests for the optional query-rewrite controller."""

from unittest.mock import MagicMock, patch

import pytest

from cocosearch.search import controller


@pytest.fixture(autouse=True)
def _clean_controller_env(monkeypatch):
    """Start each test with controller env vars cleared."""
    for var in (
        "COCOSEARCH_CONTROLLER_ENABLED",
        "COCOSEARCH_CONTROLLER_PROVIDER",
        "COCOSEARCH_CONTROLLER_MODEL",
        "COCOSEARCH_CONTROLLER_BASE_URL",
        "COCOSEARCH_CONTROLLER_API_KEY",
        "COCOSEARCH_CONTROLLER_TIMEOUT",
        "COCOSEARCH_OLLAMA_URL",
    ):
        monkeypatch.delenv(var, raising=False)


def _mock_completion(content: str) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


class TestRewriteDisabled:
    def test_disabled_is_noop(self, monkeypatch):
        """When disabled (default), returns the original query and does not call the model."""
        with patch.object(controller, "litellm") as mock_litellm:
            result = controller.rewrite_query("how does login work")
        assert result == ("how does login work", False)
        mock_litellm.completion.assert_not_called()

    def test_enabled_flag_false_value(self, monkeypatch):
        """COCOSEARCH_CONTROLLER_ENABLED=false keeps it disabled."""
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_ENABLED", "false")
        assert controller._controller_enabled() is False


class TestRewriteEnabled:
    def test_valid_rewrite(self, monkeypatch):
        """A valid single-line rewrite is returned with was_rewritten=True."""
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_ENABLED", "true")
        with patch.object(controller, "litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_completion(
                "authentication session credential login user"
            )
            result = controller.rewrite_query("how does login work")
        assert result == ("authentication session credential login user", True)
        mock_litellm.completion.assert_called_once()

    def test_identical_output_not_marked_rewritten(self, monkeypatch):
        """If the model returns the same query, was_rewritten is False."""
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_ENABLED", "true")
        with patch.object(controller, "litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_completion("login")
            result = controller.rewrite_query("login")
        assert result == ("login", False)


class TestRewriteFallback:
    @pytest.fixture(autouse=True)
    def _enable(self, monkeypatch):
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_ENABLED", "true")

    def test_exception_falls_back(self):
        """Any exception from the model falls back to the original query."""
        with patch.object(controller, "litellm") as mock_litellm:
            mock_litellm.completion.side_effect = RuntimeError("network down")
            result = controller.rewrite_query("how does login work")
        assert result == ("how does login work", False)

    def test_empty_output_falls_back(self):
        with patch.object(controller, "litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_completion("   ")
            result = controller.rewrite_query("login")
        assert result == ("login", False)

    def test_none_content_falls_back(self):
        with patch.object(controller, "litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_completion(None)
            result = controller.rewrite_query("login")
        assert result == ("login", False)

    def test_multiline_output_falls_back(self):
        """Multiline output keeps only the first line; here line 1 is the query."""
        with patch.object(controller, "litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_completion(
                "auth login session\nextra explanation line"
            )
            result = controller.rewrite_query("login")
        # First line is taken as the rewrite.
        assert result == ("auth login session", True)

    def test_runaway_length_falls_back(self):
        """Absurdly long output is rejected."""
        long = "x " * 500
        with patch.object(controller, "litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_completion(long)
            result = controller.rewrite_query("login")
        assert result == ("login", False)

    def test_quotes_and_backticks_stripped(self):
        with patch.object(controller, "litellm") as mock_litellm:
            mock_litellm.completion.return_value = _mock_completion(
                '"auth login session token"'
            )
            result = controller.rewrite_query("login")
        assert result == ("auth login session token", True)


class TestModelAndKwargs:
    def test_ollama_model_string(self, monkeypatch):
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_PROVIDER", "ollama")
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_MODEL", "qwen2.5:3b")
        assert controller._get_litellm_model() == "ollama/qwen2.5:3b"

    def test_openrouter_model_string(self, monkeypatch):
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_PROVIDER", "openrouter")
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_MODEL", "openai/gpt-4o-mini")
        assert controller._get_litellm_model() == "openrouter/openai/gpt-4o-mini"

    def test_openai_model_string_raw(self, monkeypatch):
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_PROVIDER", "openai")
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_MODEL", "gpt-4o-mini")
        assert controller._get_litellm_model() == "gpt-4o-mini"

    def test_kwargs_base_url_and_key(self, monkeypatch):
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_PROVIDER", "openrouter")
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_BASE_URL", "http://localhost:9999")
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_API_KEY", "sk-test")
        kwargs = controller._get_litellm_kwargs()
        assert kwargs["api_base"] == "http://localhost:9999"
        assert kwargs["api_key"] == "sk-test"

    def test_kwargs_reuses_embedding_key_when_provider_matches(self, monkeypatch):
        """No controller key + same provider as embedding → reuse embedding key."""
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_PROVIDER", "openrouter")
        monkeypatch.setenv("COCOSEARCH_EMBEDDING_PROVIDER", "openrouter")
        monkeypatch.setenv("COCOSEARCH_EMBEDDING_API_KEY", "sk-embed")
        kwargs = controller._get_litellm_kwargs()
        assert kwargs["api_key"] == "sk-embed"

    def test_kwargs_does_not_reuse_key_when_provider_differs(self, monkeypatch):
        """Embedding key is NOT reused when providers differ."""
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_PROVIDER", "openrouter")
        monkeypatch.setenv("COCOSEARCH_EMBEDDING_PROVIDER", "openai")
        monkeypatch.setenv("COCOSEARCH_EMBEDDING_API_KEY", "sk-embed")
        kwargs = controller._get_litellm_kwargs()
        assert "api_key" not in kwargs

    def test_kwargs_controller_key_takes_precedence(self, monkeypatch):
        """An explicit controller key is used over the embedding key."""
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_PROVIDER", "openrouter")
        monkeypatch.setenv("COCOSEARCH_EMBEDDING_PROVIDER", "openrouter")
        monkeypatch.setenv("COCOSEARCH_EMBEDDING_API_KEY", "sk-embed")
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_API_KEY", "sk-controller")
        kwargs = controller._get_litellm_kwargs()
        assert kwargs["api_key"] == "sk-controller"

    def test_kwargs_ollama_falls_back_to_ollama_url(self, monkeypatch):
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_PROVIDER", "ollama")
        monkeypatch.setenv("COCOSEARCH_OLLAMA_URL", "http://ollama:11434")
        kwargs = controller._get_litellm_kwargs()
        assert kwargs["api_base"] == "http://ollama:11434"

    def test_timeout_default_and_override(self, monkeypatch):
        assert controller._timeout() == 5.0
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_TIMEOUT", "2.5")
        assert controller._timeout() == 2.5
        monkeypatch.setenv("COCOSEARCH_CONTROLLER_TIMEOUT", "not-a-number")
        assert controller._timeout() == 5.0
