"""Tests for cocosearch.handlers.grammars.kubernetes module."""

import pytest

from cocosearch.handlers.grammars.kubernetes import KubernetesHandler


@pytest.mark.unit
class TestKubernetesMatching:
    """Tests for KubernetesHandler.matches()."""

    def test_matches_yaml_with_k8s_content(self):
        """Matches *.yaml with valid K8s content (apiVersion + kind)."""
        handler = KubernetesHandler()
        content = "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: web"
        assert handler.matches("deployment.yaml", content) is True

    def test_matches_yml_with_k8s_content(self):
        """Matches *.yml with valid K8s content."""
        handler = KubernetesHandler()
        content = "apiVersion: v1\nkind: Service\nmetadata:\n  name: api"
        assert handler.matches("service.yml", content) is True

    def test_rejects_missing_apiversion(self):
        """Rejects YAML without 'apiVersion:'."""
        handler = KubernetesHandler()
        content = "kind: Deployment\nmetadata:\n  name: web"
        assert handler.matches("deploy.yaml", content) is False

    def test_rejects_missing_kind(self):
        """Rejects YAML without 'kind:'."""
        handler = KubernetesHandler()
        content = "apiVersion: apps/v1\nmetadata:\n  name: web"
        assert handler.matches("deploy.yaml", content) is False

    def test_rejects_non_yaml_extension(self):
        """Rejects non-YAML file extensions."""
        handler = KubernetesHandler()
        content = "apiVersion: apps/v1\nkind: Deployment"
        assert handler.matches("config.json", content) is False

    def test_rejects_content_none(self):
        """Returns False when content is None (broad path requires content)."""
        handler = KubernetesHandler()
        assert handler.matches("deployment.yaml") is False

    def test_rejects_content_none_yml(self):
        """Returns False when content is None for .yml."""
        handler = KubernetesHandler()
        assert handler.matches("service.yml", None) is False

    def test_rejects_helm_template_markers(self):
        """Rejects files containing Helm template markers."""
        handler = KubernetesHandler()
        content = "apiVersion: apps/v1\nkind: Deployment\n{{ .Values.name }}"
        assert handler.matches("deploy.yaml", content) is False

    def test_rejects_helm_include(self):
        """Rejects files with {{- include markers."""
        handler = KubernetesHandler()
        content = 'apiVersion: v1\nkind: ConfigMap\n{{- include "helpers" . }}'
        assert handler.matches("configmap.yaml", content) is False

    def test_matches_nested_path(self):
        """Matches K8s manifests in nested directories."""
        handler = KubernetesHandler()
        content = "apiVersion: v1\nkind: ConfigMap\ndata:\n  key: val"
        assert handler.matches("k8s/base/configmap.yaml", content) is True

    def test_matches_deeply_nested_path(self):
        """Matches K8s manifests in deeply nested directories."""
        handler = KubernetesHandler()
        content = "apiVersion: apps/v1\nkind: Deployment\nspec:\n  replicas: 3"
        assert handler.matches("infra/k8s/prod/deploy.yml", content) is True

    def test_rejects_non_yaml_nested(self):
        """Rejects non-YAML files even in nested directories."""
        handler = KubernetesHandler()
        content = "apiVersion: apps/v1\nkind: Deployment"
        assert handler.matches("k8s/deploy.toml", content) is False

    def test_matches_configmap(self):
        """Matches ConfigMap manifest."""
        handler = KubernetesHandler()
        content = "apiVersion: v1\nkind: ConfigMap\ndata:\n  app.conf: |\n    key=val"
        assert handler.matches("cm.yaml", content) is True

    def test_matches_multi_resource_file(self):
        """Matches multi-resource YAML files."""
        handler = KubernetesHandler()
        content = (
            "apiVersion: v1\nkind: Service\n---\napiVersion: apps/v1\nkind: Deployment"
        )
        assert handler.matches("app.yaml", content) is True


@pytest.mark.unit
class TestKubernetesSeparatorSpec:
    """Tests for KubernetesHandler.SEPARATOR_SPEC."""

    def test_language_name(self):
        """SEPARATOR_SPEC.language_name should be 'kubernetes'."""
        handler = KubernetesHandler()
        assert handler.SEPARATOR_SPEC.language_name == "kubernetes"

    def test_separator_count(self):
        """SEPARATOR_SPEC should have 7 separator levels."""
        handler = KubernetesHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) == 7

    def test_has_yaml_document_separator(self):
        """First separator should be YAML document separator (---)."""
        handler = KubernetesHandler()
        assert r"\n---" in handler.SEPARATOR_SPEC.separators_regex[0]

    def test_has_apiversion_separator(self):
        """Second separator should split on apiVersion boundaries."""
        handler = KubernetesHandler()
        assert "apiVersion" in handler.SEPARATOR_SPEC.separators_regex[1]

    def test_has_top_level_key_separator(self):
        """Third separator should split on top-level keys."""
        handler = KubernetesHandler()
        assert r"[a-zA-Z_]" in handler.SEPARATOR_SPEC.separators_regex[2]

    def test_has_second_level_key_separator(self):
        """Fourth separator should split on 2-space indented keys."""
        handler = KubernetesHandler()
        assert r"\n  " in handler.SEPARATOR_SPEC.separators_regex[3]

    def test_has_blank_line_separator(self):
        """Fifth separator should split on blank lines."""
        handler = KubernetesHandler()
        assert r"\n\n" in handler.SEPARATOR_SPEC.separators_regex[4]

    def test_no_lookaheads_in_separators(self):
        """Separators must not contain lookahead/lookbehind patterns."""
        handler = KubernetesHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep
            assert "(?<=" not in sep
            assert "(?!" not in sep
            assert "(?<!" not in sep


@pytest.mark.unit
class TestKubernetesExtractMetadata:
    """Tests for KubernetesHandler.extract_metadata()."""

    # --- Kind detection ---

    def test_kind_deployment(self):
        """Kind 'Deployment' detected correctly."""
        handler = KubernetesHandler()
        text = "kind: Deployment\nmetadata:\n  name: web"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "Deployment"
        assert m["hierarchy"] == "kind:Deployment"
        assert m["language_id"] == "kubernetes"

    def test_kind_service(self):
        """Kind 'Service' detected correctly."""
        handler = KubernetesHandler()
        text = "kind: Service"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "Service"
        assert m["hierarchy"] == "kind:Service"

    def test_kind_configmap(self):
        """Kind 'ConfigMap' detected correctly."""
        handler = KubernetesHandler()
        text = "kind: ConfigMap\ndata:\n  key: value"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "ConfigMap"
        assert m["hierarchy"] == "kind:ConfigMap"

    def test_kind_statefulset(self):
        """Kind 'StatefulSet' detected correctly."""
        handler = KubernetesHandler()
        text = "kind: StatefulSet\nspec:\n  serviceName: web"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "StatefulSet"
        assert m["hierarchy"] == "kind:StatefulSet"

    def test_kind_namespace(self):
        """Kind 'Namespace' detected correctly."""
        handler = KubernetesHandler()
        text = "kind: Namespace\nmetadata:\n  name: prod"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "Namespace"
        assert m["hierarchy"] == "kind:Namespace"

    def test_kind_ingress(self):
        """Kind 'Ingress' detected correctly."""
        handler = KubernetesHandler()
        text = "kind: Ingress\nspec:\n  rules:"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "Ingress"
        assert m["hierarchy"] == "kind:Ingress"

    def test_kind_secret(self):
        """Kind 'Secret' detected correctly."""
        handler = KubernetesHandler()
        text = "kind: Secret\ntype: Opaque\ndata:\n  password: cGFzcw=="
        m = handler.extract_metadata(text)
        assert m["block_type"] == "Secret"
        assert m["hierarchy"] == "kind:Secret"

    def test_kind_clusterrole(self):
        """Kind 'ClusterRole' detected correctly."""
        handler = KubernetesHandler()
        text = "kind: ClusterRole\nrules:\n- apiGroups: ['']"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "ClusterRole"
        assert m["hierarchy"] == "kind:ClusterRole"

    # --- Section key detection (2-space indented) ---

    def test_section_key_containers(self):
        """2-space indented 'containers:' detected as section-key."""
        handler = KubernetesHandler()
        text = "  containers:\n    - name: web"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "section-key"
        assert m["hierarchy"] == "section-key:containers"
        assert m["language_id"] == "kubernetes"

    def test_section_key_ports(self):
        """2-space indented 'ports:' detected as section-key."""
        handler = KubernetesHandler()
        text = "  ports:\n    - port: 80"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "section-key"
        assert m["hierarchy"] == "section-key:ports"

    def test_section_key_volumes(self):
        """2-space indented 'volumes:' detected as section-key."""
        handler = KubernetesHandler()
        text = "  volumes:\n    - name: data"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "section-key"
        assert m["hierarchy"] == "section-key:volumes"

    def test_section_key_replicas(self):
        """2-space indented 'replicas:' detected as section-key."""
        handler = KubernetesHandler()
        text = "  replicas: 3"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "section-key"
        assert m["hierarchy"] == "section-key:replicas"

    def test_section_key_selector(self):
        """2-space indented 'selector:' detected as section-key."""
        handler = KubernetesHandler()
        text = "  selector:\n    matchLabels:\n      app: web"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "section-key"
        assert m["hierarchy"] == "section-key:selector"

    # --- Nested key detection (4+ space indented) ---

    def test_nested_key_image(self):
        """4-space indented 'image:' detected as nested-key."""
        handler = KubernetesHandler()
        text = "    image: nginx:latest"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:image"
        assert m["language_id"] == "kubernetes"

    def test_nested_key_container_port(self):
        """4-space indented 'containerPort:' detected as nested-key."""
        handler = KubernetesHandler()
        text = "    containerPort: 8080"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:containerPort"

    def test_nested_key_match_labels(self):
        """4-space indented 'matchLabels:' detected as nested-key."""
        handler = KubernetesHandler()
        text = "    matchLabels:\n      app: web"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:matchLabels"

    def test_deeply_nested_key(self):
        """6-space indented key still detected as nested-key."""
        handler = KubernetesHandler()
        text = "      protocol: TCP"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:protocol"

    def test_nested_key_resources(self):
        """4-space indented 'resources:' detected as nested-key."""
        handler = KubernetesHandler()
        text = "    resources:\n      limits:\n        cpu: 500m"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:resources"

    # --- List item detection ---

    def test_list_item_name(self):
        """YAML list item '- name: web' detected as list-item."""
        handler = KubernetesHandler()
        text = "- name: web\n  image: nginx"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:name"
        assert m["language_id"] == "kubernetes"

    def test_list_item_indented(self):
        """Indented YAML list item detected as list-item."""
        handler = KubernetesHandler()
        text = "    - name: sidecar\n      image: envoy"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:name"

    def test_list_item_port(self):
        """List item with 'port:' detected as list-item."""
        handler = KubernetesHandler()
        text = "- port: 80\n  targetPort: 8080"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:port"

    # --- Top-level key detection ---

    def test_top_level_metadata(self):
        """Top-level 'metadata:' key is identified."""
        handler = KubernetesHandler()
        text = "metadata:\n  name: web\n  namespace: default"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "metadata"
        assert m["hierarchy"] == "metadata"
        assert m["language_id"] == "kubernetes"

    def test_top_level_spec(self):
        """Top-level 'spec:' key is identified."""
        handler = KubernetesHandler()
        text = "spec:\n  replicas: 3"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "spec"
        assert m["hierarchy"] == "spec"

    def test_top_level_data(self):
        """Top-level 'data:' key is identified."""
        handler = KubernetesHandler()
        text = "data:\n  config.yaml: |"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "data"
        assert m["hierarchy"] == "data"

    def test_top_level_status(self):
        """Top-level 'status:' key is identified."""
        handler = KubernetesHandler()
        text = "status:\n  availableReplicas: 3"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "status"
        assert m["hierarchy"] == "status"

    def test_top_level_type(self):
        """Top-level 'type:' key is identified."""
        handler = KubernetesHandler()
        text = "type: ClusterIP"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "type"
        assert m["hierarchy"] == "type"

    # --- Document separator detection ---

    def test_document_separator(self):
        """Chunk with --- detected as document."""
        handler = KubernetesHandler()
        text = "---"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "document"
        assert m["hierarchy"] == "document"
        assert m["language_id"] == "kubernetes"

    def test_document_separator_with_whitespace(self):
        """Chunk containing --- among whitespace detected as document."""
        handler = KubernetesHandler()
        text = "\n---\n"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "document"
        assert m["hierarchy"] == "document"

    # --- Value continuation detection ---

    def test_value_continuation(self):
        """Chunk with content but no recognizable key detected as value."""
        handler = KubernetesHandler()
        text = "    some deeply indented content"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "value"
        assert m["hierarchy"] == "value"
        assert m["language_id"] == "kubernetes"

    # --- Comment handling ---

    def test_comment_before_kind(self):
        """Comment before kind is correctly skipped."""
        handler = KubernetesHandler()
        text = "# Deployment resource\nkind: Deployment"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "Deployment"
        assert m["hierarchy"] == "kind:Deployment"
        assert m["language_id"] == "kubernetes"

    def test_comment_before_section_key(self):
        """Comment before section key is correctly skipped."""
        handler = KubernetesHandler()
        text = "# Container spec\n  containers:\n    - name: web"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "section-key"
        assert m["hierarchy"] == "section-key:containers"

    def test_comment_before_top_level(self):
        """Comment before top-level key is correctly skipped."""
        handler = KubernetesHandler()
        text = "# Resource metadata\nmetadata:\n  name: web"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "metadata"
        assert m["hierarchy"] == "metadata"

    def test_multiple_comments_before_content(self):
        """Multiple comment lines before content are correctly skipped."""
        handler = KubernetesHandler()
        text = "# Line 1\n# Line 2\nspec:\n  replicas: 1"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "spec"
        assert m["hierarchy"] == "spec"

    # --- Indentation precision ---

    def test_two_space_is_section_key_not_top_level(self):
        """2-space indented key is section-key, not top-level."""
        handler = KubernetesHandler()
        text = "  containers:\n    - name: web"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "section-key"
        assert m["hierarchy"] == "section-key:containers"

    def test_four_space_is_nested_not_section_key(self):
        """4-space indented key is nested-key, not section-key."""
        handler = KubernetesHandler()
        text = "    image: nginx:latest"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:image"

    def test_zero_space_is_top_level_not_section_key(self):
        """0-space key is top-level, not section-key."""
        handler = KubernetesHandler()
        text = "metadata:\n  name: web"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "metadata"
        assert m["hierarchy"] == "metadata"

    # --- Empty / whitespace ---

    def test_empty_content(self):
        """Empty content returns empty block_type."""
        handler = KubernetesHandler()
        m = handler.extract_metadata("")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "kubernetes"

    def test_whitespace_only(self):
        """Whitespace-only content returns empty block_type."""
        handler = KubernetesHandler()
        m = handler.extract_metadata("   \n   \n")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""

    def test_comment_only(self):
        """Comment-only content returns empty block_type."""
        handler = KubernetesHandler()
        m = handler.extract_metadata("# just a comment\n# another comment")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""

    def test_indentation_preserved_through_strip_comments(self):
        """_strip_comments preserves indentation (does not lstrip all whitespace)."""
        handler = KubernetesHandler()
        text = "# comment\n  containers:\n    - name: web"
        m = handler.extract_metadata(text)
        # Should be section-key, NOT top-level (proving indentation preserved)
        assert m["block_type"] == "section-key"
        assert m["hierarchy"] == "section-key:containers"


@pytest.mark.unit
class TestKubernetesProtocol:
    """Tests for KubernetesHandler protocol compliance."""

    def test_has_grammar_name(self):
        handler = KubernetesHandler()
        assert handler.GRAMMAR_NAME == "kubernetes"

    def test_has_base_language(self):
        handler = KubernetesHandler()
        assert handler.BASE_LANGUAGE == "yaml"

    def test_has_path_patterns(self):
        handler = KubernetesHandler()
        assert len(handler.PATH_PATTERNS) > 0

    def test_has_top_level_keys(self):
        """_TOP_LEVEL_KEYS should be a frozenset with expected keywords."""
        handler = KubernetesHandler()
        assert isinstance(handler._TOP_LEVEL_KEYS, frozenset)
        assert "apiVersion" in handler._TOP_LEVEL_KEYS
        assert "kind" in handler._TOP_LEVEL_KEYS
        assert "metadata" in handler._TOP_LEVEL_KEYS
        assert "spec" in handler._TOP_LEVEL_KEYS
        assert "data" in handler._TOP_LEVEL_KEYS

    def test_has_item_re(self):
        """_ITEM_RE should be a compiled regex for 2-space indented keys."""
        handler = KubernetesHandler()
        assert hasattr(handler, "_ITEM_RE")
        match = handler._ITEM_RE.match("  containers:")
        assert match is not None
        assert match.group(1) == "containers"
