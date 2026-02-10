"""Tests for cocosearch.indexer.embedder module."""


class TestCodeToEmbedding:
    """Tests for code_to_embedding function.

    These tests use the mock_code_to_embedding fixture which patches the
    embedding function to return deterministic vectors without calling Ollama.
    """

    def test_generates_embedding_vector(self, mock_code_to_embedding):
        """Returns a list of floats."""
        result = mock_code_to_embedding.eval("def hello(): pass")

        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)

    def test_embedding_has_correct_dimensions(self, mock_code_to_embedding):
        """Returns 768-dimensional vector (nomic-embed-text default)."""
        result = mock_code_to_embedding.eval("def hello(): pass")

        assert len(result) == 768

    def test_different_inputs_different_embeddings(self, mock_code_to_embedding):
        """Different code produces different vectors."""
        embedding1 = mock_code_to_embedding.eval("def hello(): pass")
        embedding2 = mock_code_to_embedding.eval("def world(): return 42")

        # Embeddings should be different for different inputs
        assert embedding1 != embedding2

    def test_same_input_same_embedding(self, mock_code_to_embedding):
        """Same input produces same embedding (deterministic)."""
        code = "def example(): return True"
        embedding1 = mock_code_to_embedding.eval(code)
        embedding2 = mock_code_to_embedding.eval(code)

        assert embedding1 == embedding2

    def test_embedding_values_in_valid_range(self, mock_code_to_embedding):
        """Embedding values are in [-1, 1] range."""
        result = mock_code_to_embedding.eval("some code content")

        for value in result:
            assert -1 <= value <= 1


class TestExtractExtension:
    """Tests for extract_extension function.

    The extract_extension function is decorated with @cocoindex.op.function()
    but can still be called directly for testing.
    """

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
    """Tests for extract_language function.

    The extract_language function checks grammar handlers first (path + content),
    then filename patterns (for extensionless files like Dockerfile),
    then falls back to extension-based detection.
    """

    def test_hcl_tf_extension(self):
        """Routes .tf files by extension."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("main.tf", "resource {}") == "tf"

    def test_hcl_tfvars_extension(self):
        """Routes .tfvars files by extension."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("variables.tfvars", "var = 1") == "tfvars"

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
        """Routes .tf from full path."""
        from cocosearch.indexer.embedder import extract_language

        assert extract_language("/infra/main.tf", "resource {}") == "tf"

    # Grammar-aware routing tests

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
        # Even though .yaml extension would return "yaml", grammar wins
        result = extract_language(".github/workflows/deploy.yaml", content)
        assert result == "github-actions"
