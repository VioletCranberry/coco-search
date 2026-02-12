"""Tests for grammar handler discovery, dispatch, and spec collection."""

import pytest

from cocosearch.handlers import (
    _GRAMMAR_REGISTRY,
    detect_grammar,
    get_grammar_handler,
    get_custom_languages,
    get_registered_grammars,
    extract_chunk_metadata,
)


@pytest.mark.unit
class TestGrammarRegistryDiscovery:
    """Tests for grammar handler autodiscovery."""

    def test_discover_finds_all_grammars(self):
        """_GRAMMAR_REGISTRY should have 5 grammar handlers."""
        assert len(_GRAMMAR_REGISTRY) == 6

    def test_grammar_names(self):
        """All expected grammar names should be registered."""
        names = {h.GRAMMAR_NAME for h in _GRAMMAR_REGISTRY}
        assert "github-actions" in names
        assert "gitlab-ci" in names
        assert "docker-compose" in names
        assert "helm-template" in names
        assert "helm-values" in names
        assert "kubernetes" in names

    def test_all_grammars_have_base_language(self):
        """All grammars should declare a BASE_LANGUAGE."""
        for handler in _GRAMMAR_REGISTRY:
            assert handler.BASE_LANGUAGE, (
                f"Grammar {handler.GRAMMAR_NAME} missing BASE_LANGUAGE"
            )

    def test_all_grammars_have_path_patterns(self):
        """All grammars should declare PATH_PATTERNS."""
        for handler in _GRAMMAR_REGISTRY:
            assert len(handler.PATH_PATTERNS) > 0, (
                f"Grammar {handler.GRAMMAR_NAME} missing PATH_PATTERNS"
            )

    def test_template_excluded_from_discovery(self):
        """_template.py should be excluded from grammar discovery."""
        for handler in _GRAMMAR_REGISTRY:
            assert handler.GRAMMAR_NAME != "template-grammar"


@pytest.mark.unit
class TestDetectGrammar:
    """Tests for detect_grammar() function."""

    def test_detects_github_actions(self):
        """detect_grammar should identify GitHub Actions workflows."""
        result = detect_grammar(
            ".github/workflows/ci.yml",
            "name: CI\non: push\njobs:\n  build:",
        )
        assert result == "github-actions"

    def test_detects_gitlab_ci(self):
        """detect_grammar should identify GitLab CI files."""
        result = detect_grammar(
            ".gitlab-ci.yml",
            "stages:\n  - build\nbuild:\n  script: make",
        )
        assert result == "gitlab-ci"

    def test_detects_docker_compose(self):
        """detect_grammar should identify Docker Compose files."""
        result = detect_grammar(
            "docker-compose.yml",
            "services:\n  web:\n    image: nginx",
        )
        assert result == "docker-compose"

    def test_detects_kubernetes(self):
        """detect_grammar should identify Kubernetes manifests."""
        result = detect_grammar(
            "k8s/deployment.yaml",
            "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: web",
        )
        assert result == "kubernetes"

    def test_returns_none_for_generic_yaml(self):
        """detect_grammar should return None for generic YAML."""
        result = detect_grammar("config.yml", "key: value")
        assert result is None

    def test_kubernetes_does_not_match_helm_template(self):
        """detect_grammar on a Helm template with K8s markers should return helm-template."""
        content = (
            "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n"
            "  name: {{ .Values.name }}\nspec:\n"
            "  replicas: {{ .Values.replicas }}"
        )
        result = detect_grammar("mychart/templates/deployment.yaml", content)
        assert result == "helm-template"

    def test_returns_none_for_non_yaml(self):
        """detect_grammar should return None for non-YAML files."""
        result = detect_grammar("main.py", "def hello(): pass")
        assert result is None


@pytest.mark.unit
class TestGetGrammarHandler:
    """Tests for get_grammar_handler() function."""

    def test_get_github_actions(self):
        """get_grammar_handler returns handler for 'github-actions'."""
        handler = get_grammar_handler("github-actions")
        assert handler is not None
        assert handler.GRAMMAR_NAME == "github-actions"

    def test_get_gitlab_ci(self):
        """get_grammar_handler returns handler for 'gitlab-ci'."""
        handler = get_grammar_handler("gitlab-ci")
        assert handler is not None
        assert handler.GRAMMAR_NAME == "gitlab-ci"

    def test_get_docker_compose(self):
        """get_grammar_handler returns handler for 'docker-compose'."""
        handler = get_grammar_handler("docker-compose")
        assert handler is not None
        assert handler.GRAMMAR_NAME == "docker-compose"

    def test_get_helm_template(self):
        """get_grammar_handler returns handler for 'helm-template'."""
        handler = get_grammar_handler("helm-template")
        assert handler is not None
        assert handler.GRAMMAR_NAME == "helm-template"

    def test_get_helm_values(self):
        """get_grammar_handler returns handler for 'helm-values'."""
        handler = get_grammar_handler("helm-values")
        assert handler is not None
        assert handler.GRAMMAR_NAME == "helm-values"

    def test_get_kubernetes(self):
        """get_grammar_handler returns handler for 'kubernetes'."""
        handler = get_grammar_handler("kubernetes")
        assert handler is not None
        assert handler.GRAMMAR_NAME == "kubernetes"

    def test_returns_none_for_unknown(self):
        """get_grammar_handler returns None for unknown grammar."""
        assert get_grammar_handler("unknown-grammar") is None


@pytest.mark.unit
class TestGetCustomLanguagesWithGrammars:
    """Tests for get_custom_languages() including grammar specs."""

    def test_returns_eleven_specs(self):
        """get_custom_languages() should return 11 specs (5 language + 6 grammar)."""
        specs = get_custom_languages()
        assert len(specs) == 11

    def test_includes_grammar_specs(self):
        """get_custom_languages() should include grammar language names."""
        specs = get_custom_languages()
        language_names = {spec.language_name for spec in specs}
        assert "github-actions" in language_names
        assert "gitlab-ci" in language_names
        assert "docker-compose" in language_names
        assert "helm-template" in language_names
        assert "helm-values" in language_names
        assert "kubernetes" in language_names

    def test_still_includes_language_specs(self):
        """get_custom_languages() should still include language handler specs."""
        specs = get_custom_languages()
        language_names = {spec.language_name for spec in specs}
        assert "hcl" in language_names
        assert "dockerfile" in language_names
        assert "bash" in language_names
        assert "gotmpl" in language_names

    def test_no_duplicate_specs(self):
        """get_custom_languages() should not return duplicate specs."""
        specs = get_custom_languages()
        spec_ids = [id(spec) for spec in specs]
        assert len(spec_ids) == len(set(spec_ids))


@pytest.mark.unit
class TestGetRegisteredGrammars:
    """Tests for get_registered_grammars() function."""

    def test_returns_list(self):
        """get_registered_grammars() should return a list."""
        grammars = get_registered_grammars()
        assert isinstance(grammars, list)

    def test_returns_five_grammars(self):
        """get_registered_grammars() should return 5 grammars."""
        grammars = get_registered_grammars()
        assert len(grammars) == 6


@pytest.mark.unit
class TestExtractChunkMetadataGrammarDispatch:
    """Tests for extract_chunk_metadata() grammar dispatch."""

    def test_dispatches_to_github_actions(self):
        """extract_chunk_metadata dispatches to GitHub Actions handler."""
        text = "build:\n    runs-on: ubuntu-latest"
        result = extract_chunk_metadata(text, "github-actions")
        assert result.language_id == "github-actions"
        assert result.block_type == "job"
        assert result.hierarchy == "job:build"

    def test_dispatches_to_gitlab_ci(self):
        """extract_chunk_metadata dispatches to GitLab CI handler."""
        text = "build:\n  stage: build\n  script: make"
        result = extract_chunk_metadata(text, "gitlab-ci")
        assert result.language_id == "gitlab-ci"
        assert result.block_type == "job"

    def test_dispatches_to_docker_compose(self):
        """extract_chunk_metadata dispatches to Docker Compose handler."""
        text = "  web:\n    image: nginx"
        result = extract_chunk_metadata(text, "docker-compose")
        assert result.language_id == "docker-compose"
        assert result.block_type == "service"

    def test_dispatches_to_kubernetes(self):
        """extract_chunk_metadata dispatches to Kubernetes handler."""
        text = "apiVersion: apps/v1\nkind: Deployment"
        result = extract_chunk_metadata(text, "kubernetes")
        assert result.language_id == "kubernetes"
        assert result.block_type == "Deployment"
        assert result.hierarchy == "kind:Deployment"

    def test_still_dispatches_to_language_handler(self):
        """extract_chunk_metadata still works for language handlers."""
        text = 'resource "aws_s3_bucket" "data" {'
        result = extract_chunk_metadata(text, "tf")
        assert result.language_id == "hcl"
        assert result.block_type == "resource"
