"""Tests for cocosearch.handlers.grammars.helm_template module."""

import pytest

from cocosearch.handlers.grammars.helm_template import HelmTemplateHandler


@pytest.mark.unit
class TestHelmTemplateHandlerAttributes:
    """Tests for HelmTemplateHandler class attributes."""

    def test_grammar_name(self):
        """GRAMMAR_NAME should be 'helm-template'."""
        handler = HelmTemplateHandler()
        assert handler.GRAMMAR_NAME == "helm-template"

    def test_base_language(self):
        """BASE_LANGUAGE should be 'gotmpl'."""
        handler = HelmTemplateHandler()
        assert handler.BASE_LANGUAGE == "gotmpl"

    def test_path_patterns(self):
        """PATH_PATTERNS should match templates/ directory."""
        handler = HelmTemplateHandler()
        assert len(handler.PATH_PATTERNS) == 4
        assert "**/templates/*.yaml" in handler.PATH_PATTERNS
        assert "**/templates/**/*.yaml" in handler.PATH_PATTERNS
        assert "**/templates/*.yml" in handler.PATH_PATTERNS
        assert "**/templates/**/*.yml" in handler.PATH_PATTERNS


@pytest.mark.unit
class TestHelmTemplateHandlerSeparatorSpec:
    """Tests for HelmTemplateHandler SEPARATOR_SPEC."""

    def test_language_name(self):
        """SEPARATOR_SPEC.language_name should be 'helm-template'."""
        handler = HelmTemplateHandler()
        assert handler.SEPARATOR_SPEC.language_name == "helm-template"

    def test_has_separators(self):
        """SEPARATOR_SPEC should have a non-empty separators_regex list."""
        handler = HelmTemplateHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) > 0

    def test_level1_splits_on_yaml_doc_separator(self):
        """Level 1 separator should split on YAML document separators."""
        handler = HelmTemplateHandler()
        level1 = handler.SEPARATOR_SPEC.separators_regex[0]
        assert "---" in level1

    def test_no_lookaheads_in_separators(self):
        """Separators must not contain lookahead or lookbehind patterns."""
        handler = HelmTemplateHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep, f"Lookahead found in separator: {sep}"
            assert "(?<=" not in sep, f"Lookbehind found in separator: {sep}"
            assert "(?!" not in sep, f"Negative lookahead found: {sep}"
            assert "(?<!" not in sep, f"Negative lookbehind found: {sep}"


@pytest.mark.unit
class TestHelmTemplateHandlerMatches:
    """Tests for HelmTemplateHandler.matches()."""

    def test_matches_template_yaml_with_values(self):
        """Should match templates/*.yaml with {{ .Values marker."""
        handler = HelmTemplateHandler()
        assert handler.matches(
            "charts/mychart/templates/deployment.yaml",
            "apiVersion: apps/v1\nimage: {{ .Values.image }}",
        )

    def test_matches_template_yaml_with_release(self):
        """Should match templates/*.yaml with {{ .Release marker."""
        handler = HelmTemplateHandler()
        assert handler.matches(
            "mychart/templates/service.yaml",
            "name: {{ .Release.Name }}-svc",
        )

    def test_matches_template_yaml_with_chart(self):
        """Should match templates/*.yaml with {{ .Chart marker."""
        handler = HelmTemplateHandler()
        assert handler.matches(
            "mychart/templates/notes.yaml",
            "chart: {{ .Chart.Name }}",
        )

    def test_matches_template_yaml_with_include(self):
        """Should match templates/*.yaml with {{ include marker."""
        handler = HelmTemplateHandler()
        assert handler.matches(
            "mychart/templates/configmap.yaml",
            'labels:\n  {{ include "mychart.labels" . }}',
        )

    def test_matches_template_with_dash_syntax(self):
        """Should match templates/*.yaml with {{- syntax."""
        handler = HelmTemplateHandler()
        assert handler.matches(
            "mychart/templates/deployment.yaml",
            "image: {{- .Values.image.tag }}",
        )

    def test_matches_nested_template(self):
        """Should match nested templates/**/*.yaml."""
        handler = HelmTemplateHandler()
        assert handler.matches(
            "mychart/templates/tests/test-connection.yaml",
            "{{ .Values.service.port }}",
        )

    def test_matches_yml_extension(self):
        """Should match .yml extension."""
        handler = HelmTemplateHandler()
        assert handler.matches(
            "mychart/templates/service.yml",
            "port: {{ .Values.service.port }}",
        )

    def test_no_match_without_helm_markers(self):
        """Should not match templates/ YAML without Helm markers."""
        handler = HelmTemplateHandler()
        assert not handler.matches(
            "mychart/templates/deployment.yaml",
            "apiVersion: apps/v1\nkind: Deployment\nimage: nginx",
        )

    def test_no_match_wrong_path(self):
        """Should not match YAML outside templates/ directory."""
        handler = HelmTemplateHandler()
        assert not handler.matches(
            "mychart/values.yaml",
            "image: {{ .Values.image }}",
        )

    def test_matches_path_only_no_content(self):
        """Should match by path when content is None."""
        handler = HelmTemplateHandler()
        assert handler.matches("mychart/templates/deployment.yaml")

    def test_no_match_jinja2_template(self):
        """Should not match Jinja2 templates in templates/ dir."""
        handler = HelmTemplateHandler()
        assert not handler.matches(
            "project/templates/config.yaml",
            "name: {{ name }}\nport: {{ port }}",
        )


@pytest.mark.unit
class TestHelmTemplateHandlerExtractMetadata:
    """Tests for HelmTemplateHandler.extract_metadata()."""

    def test_kind_deployment(self):
        """K8s Deployment kind produces correct metadata."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("apiVersion: apps/v1\nkind: Deployment")
        assert m["block_type"] == "Deployment"
        assert m["hierarchy"] == "kind:Deployment"
        assert m["language_id"] == "helm-template"

    def test_kind_service(self):
        """K8s Service kind produces correct metadata."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("apiVersion: v1\nkind: Service")
        assert m["block_type"] == "Service"
        assert m["hierarchy"] == "kind:Service"

    def test_kind_configmap(self):
        """K8s ConfigMap kind produces correct metadata."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("kind: ConfigMap\nmetadata:")
        assert m["block_type"] == "ConfigMap"
        assert m["hierarchy"] == "kind:ConfigMap"

    def test_if_control_flow(self):
        """Go template if block produces control flow metadata."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("{{- if .Values.ingress.enabled }}")
        assert m["block_type"] == "if"
        assert m["hierarchy"] == "if"
        assert m["language_id"] == "helm-template"

    def test_range_control_flow(self):
        """Go template range block produces control flow metadata."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("{{- range .Values.hosts }}")
        assert m["block_type"] == "range"
        assert m["hierarchy"] == "range"

    def test_with_control_flow(self):
        """Go template with block produces control flow metadata."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("{{ with .Values.resources }}")
        assert m["block_type"] == "with"
        assert m["hierarchy"] == "with"

    def test_comment_before_kind(self):
        """Comment before kind is correctly skipped."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("# Deployment manifest\nkind: Deployment")
        assert m["block_type"] == "Deployment"
        assert m["hierarchy"] == "kind:Deployment"

    def test_leading_newline(self):
        """Leading newline from separator split is handled."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("\nkind: StatefulSet")
        assert m["block_type"] == "StatefulSet"
        assert m["hierarchy"] == "kind:StatefulSet"

    def test_unrecognized_content_returns_empty(self):
        """Unrecognized content produces empty metadata."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("  replicas: 3\n  selector:")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "helm-template"

    def test_kind_takes_priority_over_control_flow(self):
        """Kind detection takes priority over control flow detection."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("kind: Deployment\n{{- if .Values.enabled }}")
        assert m["block_type"] == "Deployment"
        assert m["hierarchy"] == "kind:Deployment"
