"""Tests for cocosearch.handlers.grammars.argocd module."""

import pytest

from cocosearch.handlers.grammars.argocd import ArgoCDHandler


@pytest.mark.unit
class TestArgoCDMatching:
    """Tests for ArgoCDHandler.matches()."""

    def test_matches_yaml_with_argocd_content(self):
        """Matches *.yaml with valid ArgoCD content (apiVersion + argoproj.io + kind)."""
        handler = ArgoCDHandler()
        content = "apiVersion: argoproj.io/v1alpha1\nkind: Application\nmetadata:\n  name: my-app"
        assert handler.matches("app.yaml", content) is True

    def test_matches_yml_with_argocd_content(self):
        """Matches *.yml with valid ArgoCD content."""
        handler = ArgoCDHandler()
        content = "apiVersion: argoproj.io/v1alpha1\nkind: ApplicationSet\nmetadata:\n  name: my-set"
        assert handler.matches("appset.yml", content) is True

    def test_matches_appproject(self):
        """Matches AppProject kind."""
        handler = ArgoCDHandler()
        content = "apiVersion: argoproj.io/v1alpha1\nkind: AppProject\nmetadata:\n  name: default"
        assert handler.matches("project.yaml", content) is True

    def test_rejects_missing_apiversion(self):
        """Rejects YAML without 'apiVersion:'."""
        handler = ArgoCDHandler()
        content = "kind: Application\nmetadata:\n  name: my-app"
        assert handler.matches("app.yaml", content) is False

    def test_rejects_missing_kind(self):
        """Rejects YAML without 'kind:'."""
        handler = ArgoCDHandler()
        content = "apiVersion: argoproj.io/v1alpha1\nmetadata:\n  name: my-app"
        assert handler.matches("app.yaml", content) is False

    def test_rejects_missing_argocd_marker(self):
        """Rejects YAML without 'argoproj.io/' in apiVersion."""
        handler = ArgoCDHandler()
        content = "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: web"
        assert handler.matches("deploy.yaml", content) is False

    def test_rejects_non_yaml_extension(self):
        """Rejects non-YAML file extensions."""
        handler = ArgoCDHandler()
        content = "apiVersion: argoproj.io/v1alpha1\nkind: Application"
        assert handler.matches("config.json", content) is False

    def test_rejects_content_none(self):
        """Returns False when content is None (broad path requires content)."""
        handler = ArgoCDHandler()
        assert handler.matches("app.yaml") is False

    def test_rejects_content_none_yml(self):
        """Returns False when content is None for .yml."""
        handler = ArgoCDHandler()
        assert handler.matches("app.yml", None) is False

    def test_rejects_helm_template_markers(self):
        """Rejects files containing Helm template markers."""
        handler = ArgoCDHandler()
        content = (
            "apiVersion: argoproj.io/v1alpha1\nkind: Application\n{{ .Values.name }}"
        )
        assert handler.matches("app.yaml", content) is False

    def test_rejects_helm_include(self):
        """Rejects files with {{- include markers."""
        handler = ArgoCDHandler()
        content = 'apiVersion: argoproj.io/v1alpha1\nkind: Application\n{{- include "helpers" . }}'
        assert handler.matches("app.yaml", content) is False

    def test_matches_nested_path(self):
        """Matches ArgoCD manifests in nested directories."""
        handler = ArgoCDHandler()
        content = "apiVersion: argoproj.io/v1alpha1\nkind: Application\nmetadata:\n  name: my-app"
        assert handler.matches("argocd/apps/my-app.yaml", content) is True

    def test_matches_deeply_nested_path(self):
        """Matches ArgoCD manifests in deeply nested directories."""
        handler = ArgoCDHandler()
        content = "apiVersion: argoproj.io/v1alpha1\nkind: ApplicationSet\nspec:\n  generators: []"
        assert handler.matches("infra/argocd/sets/my-set.yml", content) is True

    def test_rejects_non_yaml_nested(self):
        """Rejects non-YAML files even in nested directories."""
        handler = ArgoCDHandler()
        content = "apiVersion: argoproj.io/v1alpha1\nkind: Application"
        assert handler.matches("argocd/app.toml", content) is False

    def test_matches_multi_resource_file(self):
        """Matches multi-resource YAML files with ArgoCD content."""
        handler = ArgoCDHandler()
        content = (
            "apiVersion: argoproj.io/v1alpha1\nkind: Application\n---\n"
            "apiVersion: argoproj.io/v1alpha1\nkind: AppProject"
        )
        assert handler.matches("argocd.yaml", content) is True


@pytest.mark.unit
class TestArgoCDSeparatorSpec:
    """Tests for ArgoCDHandler.SEPARATOR_SPEC."""

    def test_language_name(self):
        """SEPARATOR_SPEC.language_name should be 'argocd'."""
        handler = ArgoCDHandler()
        assert handler.SEPARATOR_SPEC._config.language_name == "argocd"

    def test_separator_count(self):
        """SEPARATOR_SPEC should have 7 separator levels."""
        handler = ArgoCDHandler()
        assert len(handler.SEPARATOR_SPEC._config.separators_regex) == 7

    def test_has_yaml_document_separator(self):
        """First separator should be YAML document separator (---)."""
        handler = ArgoCDHandler()
        assert r"\n---" in handler.SEPARATOR_SPEC._config.separators_regex[0]

    def test_has_apiversion_separator(self):
        """Second separator should split on apiVersion boundaries."""
        handler = ArgoCDHandler()
        assert "apiVersion" in handler.SEPARATOR_SPEC._config.separators_regex[1]

    def test_has_top_level_key_separator(self):
        """Third separator should split on top-level keys."""
        handler = ArgoCDHandler()
        assert r"[a-zA-Z_]" in handler.SEPARATOR_SPEC._config.separators_regex[2]

    def test_has_second_level_key_separator(self):
        """Fourth separator should split on 2-space indented keys."""
        handler = ArgoCDHandler()
        assert r"\n  " in handler.SEPARATOR_SPEC._config.separators_regex[3]

    def test_has_blank_line_separator(self):
        """Fifth separator should split on blank lines."""
        handler = ArgoCDHandler()
        assert r"\n\n" in handler.SEPARATOR_SPEC._config.separators_regex[4]

    def test_no_lookaheads_in_separators(self):
        """Separators must not contain lookahead/lookbehind patterns."""
        handler = ArgoCDHandler()
        for sep in handler.SEPARATOR_SPEC._config.separators_regex:
            assert "(?=" not in sep
            assert "(?<=" not in sep
            assert "(?!" not in sep
            assert "(?<!" not in sep


@pytest.mark.unit
class TestArgoCDExtractMetadata:
    """Tests for ArgoCDHandler.extract_metadata()."""

    # --- Kind detection ---

    def test_kind_application(self):
        """Kind 'Application' detected correctly."""
        handler = ArgoCDHandler()
        text = "kind: Application\nmetadata:\n  name: my-app"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "Application"
        assert m["hierarchy"] == "kind:Application"
        assert m["language_id"] == "argocd"

    def test_kind_applicationset(self):
        """Kind 'ApplicationSet' detected correctly."""
        handler = ArgoCDHandler()
        text = "kind: ApplicationSet"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "ApplicationSet"
        assert m["hierarchy"] == "kind:ApplicationSet"

    def test_kind_appproject(self):
        """Kind 'AppProject' detected correctly."""
        handler = ArgoCDHandler()
        text = "kind: AppProject\nmetadata:\n  name: default"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "AppProject"
        assert m["hierarchy"] == "kind:AppProject"

    # --- Section key detection (2-space indented) ---

    def test_section_key_source(self):
        """2-space indented 'source:' detected as section-key."""
        handler = ArgoCDHandler()
        text = "  source:\n    repoURL: https://github.com/example/repo"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "section-key"
        assert m["hierarchy"] == "section-key:source"
        assert m["language_id"] == "argocd"

    def test_section_key_destination(self):
        """2-space indented 'destination:' detected as section-key."""
        handler = ArgoCDHandler()
        text = "  destination:\n    server: https://kubernetes.default.svc"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "section-key"
        assert m["hierarchy"] == "section-key:destination"

    def test_section_key_syncpolicy(self):
        """2-space indented 'syncPolicy:' detected as section-key."""
        handler = ArgoCDHandler()
        text = "  syncPolicy:\n    automated:\n      prune: true"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "section-key"
        assert m["hierarchy"] == "section-key:syncPolicy"

    def test_section_key_generators(self):
        """2-space indented 'generators:' detected as section-key."""
        handler = ArgoCDHandler()
        text = "  generators:\n    - clusters: {}"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "section-key"
        assert m["hierarchy"] == "section-key:generators"

    # --- Nested key detection (4+ space indented) ---

    def test_nested_key_repourl(self):
        """4-space indented 'repoURL:' detected as nested-key."""
        handler = ArgoCDHandler()
        text = "    repoURL: https://github.com/example/repo"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:repoURL"
        assert m["language_id"] == "argocd"

    def test_nested_key_targetrevision(self):
        """4-space indented 'targetRevision:' detected as nested-key."""
        handler = ArgoCDHandler()
        text = "    targetRevision: HEAD"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:targetRevision"

    def test_nested_key_server(self):
        """4-space indented 'server:' detected as nested-key."""
        handler = ArgoCDHandler()
        text = "    server: https://kubernetes.default.svc"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:server"

    def test_deeply_nested_key(self):
        """6-space indented key still detected as nested-key."""
        handler = ArgoCDHandler()
        text = "      prune: true"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:prune"

    # --- List item detection ---

    def test_list_item_name(self):
        """YAML list item '- name: my-app' detected as list-item."""
        handler = ArgoCDHandler()
        text = "- name: my-app\n  namespace: default"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:name"
        assert m["language_id"] == "argocd"

    def test_list_item_indented(self):
        """Indented YAML list item detected as list-item."""
        handler = ArgoCDHandler()
        text = "    - name: cluster-generator\n      clusters: {}"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:name"

    # --- Top-level key detection ---

    def test_top_level_metadata(self):
        """Top-level 'metadata:' key is identified."""
        handler = ArgoCDHandler()
        text = "metadata:\n  name: my-app\n  namespace: argocd"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "metadata"
        assert m["hierarchy"] == "metadata"
        assert m["language_id"] == "argocd"

    def test_top_level_spec(self):
        """Top-level 'spec:' key is identified."""
        handler = ArgoCDHandler()
        text = "spec:\n  source:\n    repoURL: https://example.com"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "spec"
        assert m["hierarchy"] == "spec"

    def test_top_level_operation(self):
        """Top-level 'operation:' key is identified."""
        handler = ArgoCDHandler()
        text = "operation:\n  sync:\n    revision: abc123"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "operation"
        assert m["hierarchy"] == "operation"

    def test_top_level_status(self):
        """Top-level 'status:' key is identified."""
        handler = ArgoCDHandler()
        text = "status:\n  sync:\n    status: Synced"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "status"
        assert m["hierarchy"] == "status"

    # --- Document separator detection ---

    def test_document_separator(self):
        """Chunk with --- detected as document."""
        handler = ArgoCDHandler()
        text = "---"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "document"
        assert m["hierarchy"] == "document"
        assert m["language_id"] == "argocd"

    def test_document_separator_with_whitespace(self):
        """Chunk containing --- among whitespace detected as document."""
        handler = ArgoCDHandler()
        text = "\n---\n"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "document"
        assert m["hierarchy"] == "document"

    # --- Value continuation detection ---

    def test_value_continuation(self):
        """Chunk with content but no recognizable key detected as value."""
        handler = ArgoCDHandler()
        text = "    some deeply indented content"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "value"
        assert m["hierarchy"] == "value"
        assert m["language_id"] == "argocd"

    # --- Comment handling ---

    def test_comment_before_kind(self):
        """Comment before kind is correctly skipped."""
        handler = ArgoCDHandler()
        text = "# ArgoCD Application\nkind: Application"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "Application"
        assert m["hierarchy"] == "kind:Application"
        assert m["language_id"] == "argocd"

    def test_comment_before_section_key(self):
        """Comment before section key is correctly skipped."""
        handler = ArgoCDHandler()
        text = "# Source config\n  source:\n    repoURL: https://example.com"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "section-key"
        assert m["hierarchy"] == "section-key:source"

    def test_comment_before_top_level(self):
        """Comment before top-level key is correctly skipped."""
        handler = ArgoCDHandler()
        text = "# Resource metadata\nmetadata:\n  name: my-app"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "metadata"
        assert m["hierarchy"] == "metadata"

    def test_multiple_comments_before_content(self):
        """Multiple comment lines before content are correctly skipped."""
        handler = ArgoCDHandler()
        text = "# Line 1\n# Line 2\nspec:\n  source:"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "spec"
        assert m["hierarchy"] == "spec"

    # --- Empty / whitespace ---

    def test_empty_content(self):
        """Empty content returns empty block_type."""
        handler = ArgoCDHandler()
        m = handler.extract_metadata("")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "argocd"

    def test_whitespace_only(self):
        """Whitespace-only content returns empty block_type."""
        handler = ArgoCDHandler()
        m = handler.extract_metadata("   \n   \n")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""

    def test_comment_only(self):
        """Comment-only content returns empty block_type."""
        handler = ArgoCDHandler()
        m = handler.extract_metadata("# just a comment\n# another comment")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""


@pytest.mark.unit
class TestArgoCDProtocol:
    """Tests for ArgoCDHandler protocol compliance."""

    def test_has_grammar_name(self):
        handler = ArgoCDHandler()
        assert handler.GRAMMAR_NAME == "argocd"

    def test_has_base_language(self):
        handler = ArgoCDHandler()
        assert handler.BASE_LANGUAGE == "yaml"

    def test_has_path_patterns(self):
        handler = ArgoCDHandler()
        assert len(handler.PATH_PATTERNS) > 0

    def test_has_top_level_keys(self):
        """_TOP_LEVEL_KEYS should be a frozenset with expected keywords."""
        handler = ArgoCDHandler()
        assert isinstance(handler._TOP_LEVEL_KEYS, frozenset)
        assert "apiVersion" in handler._TOP_LEVEL_KEYS
        assert "kind" in handler._TOP_LEVEL_KEYS
        assert "metadata" in handler._TOP_LEVEL_KEYS
        assert "spec" in handler._TOP_LEVEL_KEYS
        assert "operation" in handler._TOP_LEVEL_KEYS
        assert "status" in handler._TOP_LEVEL_KEYS

    def test_has_argocd_kinds(self):
        """_ARGOCD_KINDS should contain ArgoCD CRD kinds."""
        handler = ArgoCDHandler()
        assert isinstance(handler._ARGOCD_KINDS, frozenset)
        assert "Application" in handler._ARGOCD_KINDS
        assert "ApplicationSet" in handler._ARGOCD_KINDS
        assert "AppProject" in handler._ARGOCD_KINDS
