"""Tests for cocosearch.handlers.grammars.kubernetes module."""

import pytest

from cocosearch.handlers.grammars.kubernetes import KubernetesHandler


@pytest.mark.unit
class TestKubernetesHandlerAttributes:
    """Tests for KubernetesHandler class attributes."""

    def test_grammar_name(self):
        """GRAMMAR_NAME should be 'kubernetes'."""
        handler = KubernetesHandler()
        assert handler.GRAMMAR_NAME == "kubernetes"

    def test_base_language(self):
        """BASE_LANGUAGE should be 'yaml'."""
        handler = KubernetesHandler()
        assert handler.BASE_LANGUAGE == "yaml"

    def test_path_patterns(self):
        """PATH_PATTERNS should match YAML files broadly."""
        handler = KubernetesHandler()
        assert len(handler.PATH_PATTERNS) == 2
        assert "*.yaml" in handler.PATH_PATTERNS
        assert "*.yml" in handler.PATH_PATTERNS


@pytest.mark.unit
class TestKubernetesHandlerSeparatorSpec:
    """Tests for KubernetesHandler SEPARATOR_SPEC."""

    def test_language_name(self):
        """SEPARATOR_SPEC.language_name should be 'kubernetes'."""
        handler = KubernetesHandler()
        assert handler.SEPARATOR_SPEC.language_name == "kubernetes"

    def test_has_separators(self):
        """SEPARATOR_SPEC should have 7 separator levels."""
        handler = KubernetesHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) == 7

    def test_level1_splits_on_yaml_doc_separator(self):
        """Level 1 separator should split on YAML document separators."""
        handler = KubernetesHandler()
        level1 = handler.SEPARATOR_SPEC.separators_regex[0]
        assert "---" in level1

    def test_no_lookaheads_in_separators(self):
        """Separators must not contain lookahead or lookbehind patterns."""
        handler = KubernetesHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep, f"Lookahead found in separator: {sep}"
            assert "(?<=" not in sep, f"Lookbehind found in separator: {sep}"
            assert "(?!" not in sep, f"Negative lookahead found: {sep}"
            assert "(?<!" not in sep, f"Negative lookbehind found: {sep}"


@pytest.mark.unit
class TestKubernetesHandlerMatches:
    """Tests for KubernetesHandler.matches()."""

    def test_matches_deployment(self):
        """Should match a K8s Deployment YAML."""
        handler = KubernetesHandler()
        assert handler.matches(
            "k8s/deployment.yaml",
            "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: web",
        )

    def test_matches_service(self):
        """Should match a K8s Service YAML."""
        handler = KubernetesHandler()
        assert handler.matches(
            "manifests/service.yml",
            "apiVersion: v1\nkind: Service\nmetadata:\n  name: web-svc",
        )

    def test_matches_multi_document(self):
        """Should match multi-document K8s YAML."""
        handler = KubernetesHandler()
        content = (
            "apiVersion: v1\nkind: Service\n---\napiVersion: apps/v1\nkind: Deployment"
        )
        assert handler.matches("deploy/all.yaml", content)

    def test_no_match_when_content_is_none(self):
        """Should NOT match when content is None (broad patterns require content)."""
        handler = KubernetesHandler()
        assert not handler.matches("k8s/deployment.yaml")

    def test_no_match_generic_yaml(self):
        """Should NOT match generic YAML without apiVersion+kind."""
        handler = KubernetesHandler()
        assert not handler.matches("config.yaml", "key: value\nother: stuff")

    def test_no_match_non_yaml(self):
        """Should NOT match non-YAML files."""
        handler = KubernetesHandler()
        assert not handler.matches("main.py", "apiVersion: v1\nkind: Service")

    def test_no_match_helm_template(self):
        """Should NOT match K8s manifest with Helm template markers."""
        handler = KubernetesHandler()
        content = (
            "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n"
            "  name: {{ .Values.name }}\nspec:\n"
            "  replicas: {{ .Values.replicas }}"
        )
        assert not handler.matches("mychart/templates/deployment.yaml", content)

    def test_no_match_docker_compose(self):
        """Should NOT match Docker Compose (has services: but not apiVersion+kind)."""
        handler = KubernetesHandler()
        assert not handler.matches(
            "docker-compose.yaml",
            "services:\n  web:\n    image: nginx",
        )


@pytest.mark.unit
class TestKubernetesHandlerExtractMetadata:
    """Tests for KubernetesHandler.extract_metadata()."""

    def test_kind_deployment(self):
        """K8s Deployment kind produces correct metadata."""
        handler = KubernetesHandler()
        m = handler.extract_metadata("apiVersion: apps/v1\nkind: Deployment")
        assert m["block_type"] == "Deployment"
        assert m["hierarchy"] == "kind:Deployment"
        assert m["language_id"] == "kubernetes"

    def test_kind_service(self):
        """K8s Service kind produces correct metadata."""
        handler = KubernetesHandler()
        m = handler.extract_metadata("apiVersion: v1\nkind: Service")
        assert m["block_type"] == "Service"
        assert m["hierarchy"] == "kind:Service"

    def test_kind_configmap(self):
        """K8s ConfigMap kind produces correct metadata."""
        handler = KubernetesHandler()
        m = handler.extract_metadata("kind: ConfigMap\nmetadata:")
        assert m["block_type"] == "ConfigMap"
        assert m["hierarchy"] == "kind:ConfigMap"

    def test_top_level_section_spec(self):
        """Top-level 'spec' section produces correct metadata."""
        handler = KubernetesHandler()
        m = handler.extract_metadata("spec:\n  replicas: 3")
        assert m["block_type"] == "spec"
        assert m["hierarchy"] == "spec"

    def test_top_level_section_metadata(self):
        """Top-level 'metadata' section produces correct metadata."""
        handler = KubernetesHandler()
        m = handler.extract_metadata("metadata:\n  name: web")
        assert m["block_type"] == "metadata"
        assert m["hierarchy"] == "metadata"

    def test_top_level_section_data(self):
        """Top-level 'data' section produces correct metadata."""
        handler = KubernetesHandler()
        m = handler.extract_metadata("data:\n  key: value")
        assert m["block_type"] == "data"
        assert m["hierarchy"] == "data"

    def test_comment_before_kind(self):
        """Comment before kind is correctly skipped."""
        handler = KubernetesHandler()
        m = handler.extract_metadata("# Deployment manifest\nkind: Deployment")
        assert m["block_type"] == "Deployment"
        assert m["hierarchy"] == "kind:Deployment"

    def test_unrecognized_content_returns_empty(self):
        """Unrecognized content produces empty metadata."""
        handler = KubernetesHandler()
        m = handler.extract_metadata("    - containerPort: 8080")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "kubernetes"
