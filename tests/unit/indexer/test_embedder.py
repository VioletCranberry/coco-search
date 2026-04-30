"""Tests for cocosearch.indexer.embedder module."""

from unittest.mock import patch, MagicMock


class TestKnownDimensions:
    """Tests for _KNOWN_DIMENSIONS map."""

    def test_nomic_embed_text(self):
        from cocosearch.indexer.embedder import _KNOWN_DIMENSIONS

        assert _KNOWN_DIMENSIONS["nomic-embed-text"] == 768

    def test_openai_small(self):
        from cocosearch.indexer.embedder import _KNOWN_DIMENSIONS

        assert _KNOWN_DIMENSIONS["text-embedding-3-small"] == 1536

    def test_openrouter_small(self):
        from cocosearch.indexer.embedder import _KNOWN_DIMENSIONS

        assert _KNOWN_DIMENSIONS["openai/text-embedding-3-small"] == 1536

    def test_openai_large(self):
        from cocosearch.indexer.embedder import _KNOWN_DIMENSIONS

        assert _KNOWN_DIMENSIONS["text-embedding-3-large"] == 3072

    def test_openrouter_large(self):
        from cocosearch.indexer.embedder import _KNOWN_DIMENSIONS

        assert _KNOWN_DIMENSIONS["openai/text-embedding-3-large"] == 3072

    def test_unknown_model_not_in_map(self):
        from cocosearch.indexer.embedder import _KNOWN_DIMENSIONS

        assert "some-unknown-model" not in _KNOWN_DIMENSIONS


class TestOutputDimensionResolution:
    """Tests for _resolve_output_dimension helper."""

    def test_known_model_returns_dimension(self):
        """Known model returns its dimension from the map."""
        from cocosearch.indexer.embedder import _resolve_output_dimension

        assert _resolve_output_dimension("openai/text-embedding-3-small") == 1536

    def test_nomic_returns_768(self):
        """Ollama default model returns 768."""
        from cocosearch.indexer.embedder import _resolve_output_dimension

        assert _resolve_output_dimension("nomic-embed-text") == 768

    def test_env_var_overrides_known_dimension(self):
        """COCOSEARCH_EMBEDDING_OUTPUT_DIMENSION env var overrides known map."""
        from cocosearch.indexer.embedder import _resolve_output_dimension

        with patch.dict("os.environ", {"COCOSEARCH_EMBEDDING_OUTPUT_DIMENSION": "512"}):
            assert _resolve_output_dimension("nomic-embed-text") == 512

    def test_unknown_model_returns_none(self):
        """Unknown model without env var returns None."""
        from cocosearch.indexer.embedder import _resolve_output_dimension

        assert _resolve_output_dimension("some-custom-model") is None

    def test_unknown_model_with_env_var(self):
        """Unknown model with env var returns dimension from env."""
        from cocosearch.indexer.embedder import _resolve_output_dimension

        with patch.dict("os.environ", {"COCOSEARCH_EMBEDDING_OUTPUT_DIMENSION": "256"}):
            assert _resolve_output_dimension("some-custom-model") == 256


class TestGetLitellmModel:
    """Tests for _get_litellm_model helper."""

    def test_ollama_default(self):
        """Ollama provider prefixes model with 'ollama/'."""
        from cocosearch.indexer.embedder import _get_litellm_model

        with patch.dict("os.environ", {}, clear=True):
            result = _get_litellm_model()
        assert result == "ollama/nomic-embed-text"

    def test_ollama_custom_model(self):
        """Ollama with custom model prefixes correctly."""
        from cocosearch.indexer.embedder import _get_litellm_model

        env = {
            "COCOSEARCH_EMBEDDING_PROVIDER": "ollama",
            "COCOSEARCH_EMBEDDING_MODEL": "mxbai-embed-large",
        }
        with patch.dict("os.environ", env, clear=True):
            result = _get_litellm_model()
        assert result == "ollama/mxbai-embed-large"

    def test_openai_default(self):
        """OpenAI provider uses model name directly."""
        from cocosearch.indexer.embedder import _get_litellm_model

        env = {"COCOSEARCH_EMBEDDING_PROVIDER": "openai"}
        with patch.dict("os.environ", env, clear=True):
            result = _get_litellm_model()
        assert result == "text-embedding-3-small"

    def test_openrouter_default(self):
        """OpenRouter provider prefixes with 'openrouter/'."""
        from cocosearch.indexer.embedder import _get_litellm_model

        env = {"COCOSEARCH_EMBEDDING_PROVIDER": "openrouter"}
        with patch.dict("os.environ", env, clear=True):
            result = _get_litellm_model()
        assert result == "openrouter/openai/text-embedding-3-small"

    def test_unknown_provider_falls_back(self):
        """Unknown provider uses default model without prefix."""
        from cocosearch.indexer.embedder import _get_litellm_model

        env = {"COCOSEARCH_EMBEDDING_PROVIDER": "custom"}
        with patch.dict("os.environ", env, clear=True):
            result = _get_litellm_model()
        assert result == "nomic-embed-text"


class TestEmbedQuery:
    """Tests for embed_query function."""

    def test_calls_litellm_embedding(self):
        """embed_query calls litellm.embedding with correct arguments."""
        from cocosearch.indexer.embedder import embed_query

        mock_response = MagicMock()
        mock_response.data = [{"embedding": [0.1, 0.2, 0.3]}]

        with patch("cocosearch.indexer.embedder.litellm") as mock_litellm:
            mock_litellm.embedding.return_value = mock_response
            with patch.dict("os.environ", {}, clear=True):
                result = embed_query("test text")

        assert result == [0.1, 0.2, 0.3]
        mock_litellm.embedding.assert_called_once()

    def test_returns_embedding_vector(self):
        """embed_query returns the embedding list from the response."""
        from cocosearch.indexer.embedder import embed_query

        expected = [0.5] * 768
        mock_response = MagicMock()
        mock_response.data = [{"embedding": expected}]

        with patch("cocosearch.indexer.embedder.litellm") as mock_litellm:
            mock_litellm.embedding.return_value = mock_response
            with patch.dict("os.environ", {}, clear=True):
                result = embed_query("hello world")

        assert result == expected


class TestEmbedQueryAddress:
    """Tests for address resolution in embed_query."""

    def test_ollama_falls_back_to_ollama_url(self):
        """Ollama provider uses COCOSEARCH_OLLAMA_URL when no base URL set."""
        env = {
            "COCOSEARCH_EMBEDDING_PROVIDER": "ollama",
            "COCOSEARCH_EMBEDDING_MODEL": "nomic-embed-text",
            "COCOSEARCH_OLLAMA_URL": "http://ollama:11434",
        }
        with patch.dict("os.environ", env, clear=False):
            import os

            provider = os.environ.get("COCOSEARCH_EMBEDDING_PROVIDER", "ollama")
            address = os.environ.get("COCOSEARCH_EMBEDDING_BASE_URL")
            if address is None and provider == "ollama":
                address = os.environ.get("COCOSEARCH_OLLAMA_URL")
            assert address == "http://ollama:11434"

    def test_base_url_overrides_ollama_url(self):
        """COCOSEARCH_EMBEDDING_BASE_URL overrides COCOSEARCH_OLLAMA_URL for ollama."""
        env = {
            "COCOSEARCH_EMBEDDING_PROVIDER": "ollama",
            "COCOSEARCH_OLLAMA_URL": "http://ollama:11434",
            "COCOSEARCH_EMBEDDING_BASE_URL": "http://custom:9999",
        }
        with patch.dict("os.environ", env, clear=False):
            import os

            provider = os.environ.get("COCOSEARCH_EMBEDDING_PROVIDER", "ollama")
            address = os.environ.get("COCOSEARCH_EMBEDDING_BASE_URL")
            if address is None and provider == "ollama":
                address = os.environ.get("COCOSEARCH_OLLAMA_URL")
            assert address == "http://custom:9999"

    def test_openai_with_base_url_passes_address(self):
        """OpenAI provider with base URL resolves address."""
        env = {
            "COCOSEARCH_EMBEDDING_PROVIDER": "openai",
            "COCOSEARCH_EMBEDDING_BASE_URL": "http://localhost:8080",
        }
        with patch.dict("os.environ", env, clear=False):
            import os

            provider = os.environ.get("COCOSEARCH_EMBEDDING_PROVIDER", "ollama")
            address = os.environ.get("COCOSEARCH_EMBEDDING_BASE_URL")
            if address is None and provider == "ollama":
                address = os.environ.get("COCOSEARCH_OLLAMA_URL")
            assert address == "http://localhost:8080"

    def test_openai_without_base_url_omits_address(self):
        """OpenAI provider without base URL has no address."""
        env = {
            "COCOSEARCH_EMBEDDING_PROVIDER": "openai",
        }
        with patch.dict("os.environ", env, clear=False):
            import os

            os.environ.pop("COCOSEARCH_EMBEDDING_BASE_URL", None)
            provider = os.environ.get("COCOSEARCH_EMBEDDING_PROVIDER", "ollama")
            address = os.environ.get("COCOSEARCH_EMBEDDING_BASE_URL")
            if address is None and provider == "ollama":
                address = os.environ.get("COCOSEARCH_OLLAMA_URL")
            assert address is None

    def test_api_key_passed_for_any_provider(self):
        """API key is passed regardless of provider when set."""
        env = {
            "COCOSEARCH_EMBEDDING_PROVIDER": "ollama",
            "COCOSEARCH_EMBEDDING_API_KEY": "sk-test",
        }
        with patch.dict("os.environ", env, clear=False):
            import os

            api_key = os.environ.get("COCOSEARCH_EMBEDDING_API_KEY")
            assert api_key == "sk-test"


class TestAddFilenameContext:
    """Tests for add_filename_context function."""

    def test_prepends_filename(self):
        """Prepends 'File: <filename>' to text."""
        from cocosearch.indexer.embedder import add_filename_context

        result = add_filename_context("name: Deploy", ".github/workflows/release.yaml")
        assert result == "File: .github/workflows/release.yaml\nname: Deploy"

    def test_preserves_text(self):
        """Original text appears in full after the filename line."""
        from cocosearch.indexer.embedder import add_filename_context

        text = "def hello():\n    pass"
        result = add_filename_context(text, "src/main.py")
        assert result.endswith(text)

    def test_empty_filename_returns_original(self):
        """Returns original text when filename is empty."""
        from cocosearch.indexer.embedder import add_filename_context

        text = "some code"
        assert add_filename_context(text, "") == text

    def test_deep_path(self):
        """Handles deeply nested file paths."""
        from cocosearch.indexer.embedder import add_filename_context

        result = add_filename_context("x", "a/b/c/d/e.py")
        assert result.startswith("File: a/b/c/d/e.py\n")


class TestExtractExtension:
    """Tests for extract_extension function."""

    def test_extracts_python_extension(self):
        """Extracts .py extension correctly."""
        from cocosearch.indexer.embedder import extract_extension

        result = extract_extension("test.py")
        assert result == "py"

    def test_extracts_from_path(self):
        """Extracts extension from full path."""
        from cocosearch.indexer.embedder import extract_extension

        result = extract_extension("/path/to/file.js")
        assert result == "js"

    def test_returns_empty_for_no_extension(self):
        """Returns empty string for files without extension."""
        from cocosearch.indexer.embedder import extract_extension

        result = extract_extension("Makefile")
        assert result == ""

    def test_handles_multiple_dots(self):
        """Handles filenames with multiple dots."""
        from cocosearch.indexer.embedder import extract_extension

        result = extract_extension("file.test.spec.ts")
        assert result == "ts"


class TestExtractLanguage:
    """Tests for extract_language function."""

    def test_hcl_tf_extension(self):
        """Routes .tf files via Terraform grammar handler."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("main.tf", "resource {}") == "terraform"

    def test_hcl_tfvars_extension(self):
        """Routes .tfvars files via Terraform grammar handler."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("variables.tfvars", "var = 1") == "terraform"

    def test_hcl_hcl_extension(self):
        """Routes .hcl files by extension."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("config.hcl", "block {}") == "hcl"

    def test_dockerfile_exact(self):
        """Routes Dockerfile by filename pattern."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("Dockerfile", "FROM ubuntu") == "dockerfile"

    def test_dockerfile_dev_variant(self):
        """Routes Dockerfile.dev by filename prefix."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("Dockerfile.dev", "FROM node") == "dockerfile"

    def test_dockerfile_production_variant(self):
        """Routes Dockerfile.production by filename prefix."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("Dockerfile.production", "FROM python") == "dockerfile"

    def test_containerfile_exact_match(self):
        """Routes Containerfile by exact filename match."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("Containerfile", "FROM alpine") == "dockerfile"

    def test_shell_sh_extension(self):
        """Routes .sh files by extension."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("deploy.sh", "#!/bin/bash") == "sh"

    def test_shell_bash_extension(self):
        """Routes .bash files by extension."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("build.bash", "#!/bin/bash") == "bash"

    def test_non_handler_python(self):
        """Routes .py files by extension (non-handler, unchanged)."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("test.py", "def hello(): pass") == "py"

    def test_non_handler_javascript(self):
        """Routes .js files by extension (non-handler, unchanged)."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("app.js", "const x = 1") == "js"

    def test_extensionless_non_dockerfile(self):
        """Returns empty string for extensionless non-Dockerfile files."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("Makefile", "all: build") == ""

    def test_full_path_dockerfile(self):
        """Routes Dockerfile from full path."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("/path/to/Dockerfile", "FROM ubuntu") == "dockerfile"

    def test_full_path_dockerfile_variant(self):
        """Routes Dockerfile.dev from full path."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("/path/to/Dockerfile.dev", "FROM node") == "dockerfile"

    def test_full_path_hcl(self):
        """Routes .tf from full path via Terraform grammar handler."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("/infra/main.tf", "resource {}") == "terraform"

    def test_github_actions_grammar(self):
        """Routes GitHub Actions workflow via grammar detection."""
        from cocosearch.indexer.embedder import extract_language

        content = "name: CI\non: push\njobs:\n  build:"
        assert extract_language(".github/workflows/ci.yml", content) == "github-actions"

    def test_gitlab_ci_grammar(self):
        """Routes GitLab CI via grammar detection."""
        from cocosearch.indexer.embedder import extract_language

        content = "stages:\n  - build\nbuild:\n  script: make"
        assert extract_language(".gitlab-ci.yml", content) == "gitlab-ci"

    def test_docker_compose_grammar(self):
        """Routes Docker Compose via grammar detection."""
        from cocosearch.indexer.embedder import extract_language

        content = "services:\n  web:\n    image: nginx"
        assert extract_language("docker-compose.yml", content) == "docker-compose"

    def test_generic_yaml_no_grammar(self):
        """Generic YAML falls through to extension-based routing."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("config.yml", "key: value") == "yml"

    def test_grammar_priority_over_extension(self):
        """Grammar detection takes priority over extension-based routing."""
        from cocosearch.indexer.embedder import extract_language

        content = "name: Deploy\non: push\njobs:\n  deploy:"
        result = extract_language(".github/workflows/deploy.yaml", content)
        assert result == "github-actions"
