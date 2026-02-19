"""Tests for cocosearch.handlers.grammars.helm_template module."""

import pytest

from cocosearch.handlers.grammars.helm_template import HelmTemplateHandler


@pytest.mark.unit
class TestHelmTemplateMatching:
    """Tests for HelmTemplateHandler.matches()."""

    def test_matches_template_yaml_with_values(self):
        """Matches templates/*.yaml with {{ .Values marker."""
        handler = HelmTemplateHandler()
        content = "apiVersion: apps/v1\nimage: {{ .Values.image }}"
        assert (
            handler.matches("charts/mychart/templates/deployment.yaml", content) is True
        )

    def test_matches_template_yaml_with_release(self):
        """Matches templates/*.yaml with {{ .Release marker."""
        handler = HelmTemplateHandler()
        content = "name: {{ .Release.Name }}-svc"
        assert handler.matches("mychart/templates/service.yaml", content) is True

    def test_matches_template_yaml_with_chart(self):
        """Matches templates/*.yaml with {{ .Chart marker."""
        handler = HelmTemplateHandler()
        content = "chart: {{ .Chart.Name }}"
        assert handler.matches("mychart/templates/notes.yaml", content) is True

    def test_matches_template_yaml_with_include(self):
        """Matches templates/*.yaml with {{ include marker."""
        handler = HelmTemplateHandler()
        content = 'labels:\n  {{ include "mychart.labels" . }}'
        assert handler.matches("mychart/templates/configmap.yaml", content) is True

    def test_matches_template_with_dash_syntax(self):
        """Matches templates/*.yaml with {{- syntax."""
        handler = HelmTemplateHandler()
        content = "image: {{- .Values.image.tag }}"
        assert handler.matches("mychart/templates/deployment.yaml", content) is True

    def test_matches_template_yaml_with_template_action(self):
        """Matches templates/*.yaml with {{ template marker."""
        handler = HelmTemplateHandler()
        content = '{{ template "mychart.fullname" . }}\napiVersion: v1'
        assert handler.matches("mychart/templates/pull-secret.yaml", content) is True

    def test_matches_template_yaml_with_define(self):
        """Matches templates/*.yaml with {{- define marker."""
        handler = HelmTemplateHandler()
        content = '{{- define "mychart.labels" }}\napp: test\n{{- end }}'
        assert handler.matches("mychart/templates/helpers.yaml", content) is True

    def test_matches_nested_template(self):
        """Matches nested templates/**/*.yaml."""
        handler = HelmTemplateHandler()
        content = "{{ .Values.service.port }}"
        assert (
            handler.matches("mychart/templates/tests/test-connection.yaml", content)
            is True
        )

    def test_matches_yml_extension(self):
        """Matches .yml extension."""
        handler = HelmTemplateHandler()
        content = "port: {{ .Values.service.port }}"
        assert handler.matches("mychart/templates/service.yml", content) is True

    def test_rejects_without_helm_markers(self):
        """Rejects templates/ YAML without Helm markers."""
        handler = HelmTemplateHandler()
        content = "apiVersion: apps/v1\nkind: Deployment\nimage: nginx"
        assert handler.matches("mychart/templates/deployment.yaml", content) is False

    def test_rejects_wrong_path(self):
        """Rejects YAML outside templates/ directory."""
        handler = HelmTemplateHandler()
        content = "image: {{ .Values.image }}"
        assert handler.matches("mychart/values.yaml", content) is False

    def test_matches_path_only_without_content(self):
        """Matches by path alone when content is None."""
        handler = HelmTemplateHandler()
        assert handler.matches("mychart/templates/deployment.yaml") is True

    def test_rejects_wrong_path_without_content(self):
        """Rejects wrong path when content is None."""
        handler = HelmTemplateHandler()
        assert handler.matches("mychart/values.yaml") is False

    def test_rejects_jinja2_template(self):
        """Rejects Jinja2 templates in templates/ dir."""
        handler = HelmTemplateHandler()
        content = "name: {{ name }}\nport: {{ port }}"
        assert handler.matches("project/templates/config.yaml", content) is False

    def test_matches_nested_path(self):
        """Matches templates/ in nested directories."""
        handler = HelmTemplateHandler()
        content = "image: {{ .Values.image }}"
        assert (
            handler.matches("org/project/charts/mychart/templates/deploy.yaml", content)
            is True
        )

    def test_matches_nested_path_without_content(self):
        """Matches nested templates/ by path alone."""
        handler = HelmTemplateHandler()
        assert handler.matches("org/charts/mychart/templates/deploy.yaml") is True

    def test_matches_deeply_nested_path(self):
        """Matches templates/ in deeply nested directory."""
        handler = HelmTemplateHandler()
        content = "{{ .Values.name }}"
        assert handler.matches("a/b/c/templates/service.yml", content) is True

    def test_matches_deeply_nested_path_without_content(self):
        """Matches deeply nested templates/ by path alone."""
        handler = HelmTemplateHandler()
        assert handler.matches("a/b/c/templates/configmap.yaml") is True


@pytest.mark.unit
class TestHelmTemplateSeparatorSpec:
    """Tests for HelmTemplateHandler.SEPARATOR_SPEC."""

    def test_language_name(self):
        """SEPARATOR_SPEC.language_name should be 'helm-template'."""
        handler = HelmTemplateHandler()
        assert handler.SEPARATOR_SPEC.language_name == "helm-template"

    def test_separator_count(self):
        """SEPARATOR_SPEC should have 9 separator levels."""
        handler = HelmTemplateHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) == 9

    def test_has_yaml_document_separator(self):
        """First separator should be YAML document separator (---)."""
        handler = HelmTemplateHandler()
        assert r"\n---" in handler.SEPARATOR_SPEC.separators_regex[0]

    def test_has_api_version_separator(self):
        """Second separator should split on apiVersion: boundaries."""
        handler = HelmTemplateHandler()
        assert "apiVersion" in handler.SEPARATOR_SPEC.separators_regex[1]

    def test_has_define_separator(self):
        """Third separator should split on Go template define blocks."""
        handler = HelmTemplateHandler()
        assert "define" in handler.SEPARATOR_SPEC.separators_regex[2]

    def test_has_top_level_key_separator(self):
        """Fourth separator should split on top-level YAML keys."""
        handler = HelmTemplateHandler()
        assert r"[a-zA-Z_]" in handler.SEPARATOR_SPEC.separators_regex[3]

    def test_has_control_flow_separator(self):
        """Fifth separator should split on Go template control flow."""
        handler = HelmTemplateHandler()
        sep = handler.SEPARATOR_SPEC.separators_regex[4]
        assert "if" in sep
        assert "range" in sep
        assert "with" in sep

    def test_has_indented_key_separator(self):
        """Sixth separator should split on 2-space indented keys."""
        handler = HelmTemplateHandler()
        assert r"\n  " in handler.SEPARATOR_SPEC.separators_regex[5]

    def test_no_lookaheads_in_separators(self):
        """Separators must not contain lookahead/lookbehind patterns."""
        handler = HelmTemplateHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep
            assert "(?<=" not in sep
            assert "(?!" not in sep
            assert "(?<!" not in sep


@pytest.mark.unit
class TestHelmTemplateExtractMetadata:
    """Tests for HelmTemplateHandler.extract_metadata()."""

    # --- Go template define detection ---

    def test_define_block(self):
        """Go template define block extracts template name."""
        handler = HelmTemplateHandler()
        text = '{{- define "mychart.fullname" -}}\n{{ .Release.Name }}\n{{- end }}'
        m = handler.extract_metadata(text)
        assert m["block_type"] == "define"
        assert m["hierarchy"] == "define:mychart.fullname"
        assert m["language_id"] == "helm-template"

    def test_define_block_without_dash(self):
        """Go template define without dash trim extracts name."""
        handler = HelmTemplateHandler()
        text = '{{ define "mychart.labels" }}\napp: test\n{{ end }}'
        m = handler.extract_metadata(text)
        assert m["block_type"] == "define"
        assert m["hierarchy"] == "define:mychart.labels"

    def test_define_takes_priority_over_kind(self):
        """Define detection takes priority over kind detection."""
        handler = HelmTemplateHandler()
        text = '{{- define "mychart.deployment" }}\nkind: Deployment\n{{- end }}'
        m = handler.extract_metadata(text)
        assert m["block_type"] == "define"
        assert m["hierarchy"] == "define:mychart.deployment"

    # --- K8s kind detection ---

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

    def test_kind_takes_priority_over_control_flow(self):
        """Kind detection takes priority over control flow detection."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("kind: Deployment\n{{- if .Values.enabled }}")
        assert m["block_type"] == "Deployment"
        assert m["hierarchy"] == "kind:Deployment"

    # --- Go template control flow detection ---

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

    # --- 2-space indented key detection ---

    def test_key_containers(self):
        """2-space indented 'containers:' detected as key."""
        handler = HelmTemplateHandler()
        text = "  containers:\n    - name: {{ .Chart.Name }}"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:containers"
        assert m["language_id"] == "helm-template"

    def test_key_template(self):
        """2-space indented 'template:' detected as key."""
        handler = HelmTemplateHandler()
        text = "  template:\n    metadata:"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:template"

    def test_key_replicas(self):
        """2-space indented 'replicas:' detected as key."""
        handler = HelmTemplateHandler()
        text = "  replicas: {{ .Values.replicaCount }}"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:replicas"

    # --- Nested key detection (4+ space indented) ---

    def test_nested_key_ports(self):
        """4-space indented 'ports:' detected as nested-key."""
        handler = HelmTemplateHandler()
        text = "    ports:\n      - containerPort: 80"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:ports"
        assert m["language_id"] == "helm-template"

    def test_nested_key_env(self):
        """4-space indented 'env:' detected as nested-key."""
        handler = HelmTemplateHandler()
        text = "    env:\n      - name: DB_HOST"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:env"

    def test_deeply_nested_key(self):
        """6-space indented key still detected as nested-key."""
        handler = HelmTemplateHandler()
        text = "      limits:\n        cpu: 100m"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:limits"

    # --- List item detection ---

    def test_list_item_key(self):
        """YAML list item with key detected as list-item."""
        handler = HelmTemplateHandler()
        text = "- name: {{ .Chart.Name }}"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:name"
        assert m["language_id"] == "helm-template"

    def test_list_item_indented(self):
        """Indented YAML list item with key detected as list-item."""
        handler = HelmTemplateHandler()
        text = "      - containerPort: 80\n        protocol: TCP"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:containerPort"

    # --- Top-level key detection ---

    def test_top_level_metadata(self):
        """Top-level 'metadata:' key is identified."""
        handler = HelmTemplateHandler()
        text = 'metadata:\n  name: {{ include "mychart.fullname" . }}'
        m = handler.extract_metadata(text)
        assert m["block_type"] == "metadata"
        assert m["hierarchy"] == "metadata"
        assert m["language_id"] == "helm-template"

    def test_top_level_spec(self):
        """Top-level 'spec:' key is identified."""
        handler = HelmTemplateHandler()
        text = "spec:\n  replicas: 3"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "spec"
        assert m["hierarchy"] == "spec"

    def test_top_level_data(self):
        """Top-level 'data:' key is identified."""
        handler = HelmTemplateHandler()
        text = "data:\n  config.yaml: |"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "data"
        assert m["hierarchy"] == "data"

    # --- Document separator detection ---

    def test_document_separator(self):
        """Chunk with --- detected as document."""
        handler = HelmTemplateHandler()
        text = "---"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "document"
        assert m["hierarchy"] == "document"
        assert m["language_id"] == "helm-template"

    def test_document_separator_with_whitespace(self):
        """Chunk containing --- among whitespace detected as document."""
        handler = HelmTemplateHandler()
        text = "\n---\n"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "document"
        assert m["hierarchy"] == "document"

    # --- Value continuation detection ---

    def test_value_continuation(self):
        """Chunk with content but no recognizable key detected as value."""
        handler = HelmTemplateHandler()
        text = "    some deeply indented content"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "value"
        assert m["hierarchy"] == "value"
        assert m["language_id"] == "helm-template"

    # --- Comment handling ---

    def test_comment_before_kind(self):
        """Comment before kind is correctly skipped."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("# Deployment manifest\nkind: Deployment")
        assert m["block_type"] == "Deployment"
        assert m["hierarchy"] == "kind:Deployment"
        assert m["language_id"] == "helm-template"

    def test_comment_before_define(self):
        """Comment before define block is correctly skipped."""
        handler = HelmTemplateHandler()
        text = '# Helper template\n{{- define "mychart.name" -}}\ntest\n{{- end }}'
        m = handler.extract_metadata(text)
        assert m["block_type"] == "define"
        assert m["hierarchy"] == "define:mychart.name"

    def test_comment_before_top_level(self):
        """Comment before top-level key is correctly skipped."""
        handler = HelmTemplateHandler()
        text = "# Resource spec\nspec:\n  replicas: 3"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "spec"
        assert m["hierarchy"] == "spec"

    def test_leading_newline(self):
        """Leading newline from separator split is handled."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("\nkind: StatefulSet")
        assert m["block_type"] == "StatefulSet"
        assert m["hierarchy"] == "kind:StatefulSet"

    # --- Empty / whitespace ---

    def test_empty_content(self):
        """Empty content returns empty block_type."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "helm-template"

    def test_whitespace_only(self):
        """Whitespace-only content returns empty block_type."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("   \n   \n")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""

    def test_unrecognized_content(self):
        """Unrecognized content without key returns value."""
        handler = HelmTemplateHandler()
        m = handler.extract_metadata("  some random indented text")
        assert m["block_type"] == "value"
        assert m["hierarchy"] == "value"
        assert m["language_id"] == "helm-template"

    # --- Indentation precision ---

    def test_two_space_is_key_not_top_level(self):
        """2-space indented key is key, not top-level."""
        handler = HelmTemplateHandler()
        text = "  containers:\n    - name: app"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:containers"

    def test_four_space_is_nested_not_key(self):
        """4-space indented key is nested-key, not key."""
        handler = HelmTemplateHandler()
        text = "    ports:\n      - containerPort: 80"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:ports"


@pytest.mark.unit
class TestHelmTemplateProtocol:
    """Tests for HelmTemplateHandler protocol compliance."""

    def test_has_grammar_name(self):
        handler = HelmTemplateHandler()
        assert handler.GRAMMAR_NAME == "helm-template"

    def test_has_base_language(self):
        handler = HelmTemplateHandler()
        assert handler.BASE_LANGUAGE == "gotmpl"

    def test_has_path_patterns(self):
        handler = HelmTemplateHandler()
        assert len(handler.PATH_PATTERNS) > 0
