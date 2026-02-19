"""Tests for cocosearch.handlers.grammars.helm_values module."""

import pytest

from cocosearch.handlers.grammars.helm_values import HelmValuesHandler


@pytest.mark.unit
class TestHelmValuesMatching:
    """Tests for HelmValuesHandler.matches()."""

    def test_matches_values_yaml_with_helm_keys(self):
        """Matches values.yaml with 3+ common Helm keys."""
        handler = HelmValuesHandler()
        content = (
            "replicaCount: 1\n"
            "image:\n  repository: nginx\n"
            "service:\n  type: ClusterIP\n"
            "ingress:\n  enabled: false\n"
        )
        assert handler.matches("mychart/values.yaml", content) is True

    def test_matches_values_override(self):
        """Matches values-*.yaml with Helm keys."""
        handler = HelmValuesHandler()
        content = (
            "replicaCount: 3\n"
            "image:\n  tag: latest\n"
            "resources:\n  limits:\n    cpu: 500m\n"
        )
        assert handler.matches("mychart/values-production.yaml", content) is True

    def test_rejects_too_few_keys(self):
        """Rejects values.yaml with fewer than 3 Helm keys."""
        handler = HelmValuesHandler()
        content = "replicaCount: 1\nimage:\n  tag: latest\n"
        assert handler.matches("mychart/values.yaml", content) is False

    def test_rejects_non_helm_values(self):
        """Rejects values.yaml from non-Helm project."""
        handler = HelmValuesHandler()
        content = "database:\n  host: localhost\nlogging:\n  level: info\n"
        assert handler.matches("myapp/values.yaml", content) is False

    def test_rejects_wrong_path(self):
        """Rejects non-values.yaml files."""
        handler = HelmValuesHandler()
        content = (
            "replicaCount: 1\nimage:\n  tag: latest\nservice:\n  type: ClusterIP\n"
        )
        assert handler.matches("mychart/config.yaml", content) is False

    def test_matches_path_only_without_content(self):
        """Matches by path alone when content is None."""
        handler = HelmValuesHandler()
        assert handler.matches("mychart/values.yaml") is True

    def test_rejects_wrong_path_without_content(self):
        """Rejects wrong path when content is None."""
        handler = HelmValuesHandler()
        assert handler.matches("mychart/config.yaml") is False

    def test_matches_nested_values(self):
        """Matches nested values.yaml."""
        handler = HelmValuesHandler()
        content = (
            "replicaCount: 1\n"
            "image:\n  tag: v1\n"
            "service:\n  port: 80\n"
            "ingress:\n  enabled: true\n"
        )
        assert handler.matches("charts/subchart/values.yaml", content) is True

    def test_matches_nested_path_without_content(self):
        """Matches nested values.yaml by path alone."""
        handler = HelmValuesHandler()
        assert handler.matches("charts/subchart/values.yaml") is True

    def test_matches_deeply_nested_path(self):
        """Matches values.yaml in deeply nested directory."""
        handler = HelmValuesHandler()
        content = "replicaCount: 1\nimage:\n  tag: v1\nservice:\n  port: 80\n"
        assert (
            handler.matches("org/project/charts/mychart/values.yaml", content) is True
        )

    def test_matches_deeply_nested_path_without_content(self):
        """Matches deeply nested values.yaml by path alone."""
        handler = HelmValuesHandler()
        assert handler.matches("org/project/charts/mychart/values.yaml") is True

    def test_matches_with_exactly_three_keys(self):
        """Matches when exactly 3 Helm keys are present."""
        handler = HelmValuesHandler()
        content = (
            "replicaCount: 1\n"
            "image:\n  repository: nginx\n"
            "service:\n  type: ClusterIP\n"
        )
        assert handler.matches("mychart/values.yaml", content) is True

    def test_matches_values_override_nested(self):
        """Matches nested values-*.yaml override."""
        handler = HelmValuesHandler()
        content = (
            "replicaCount: 3\n"
            "image:\n  tag: latest\n"
            "resources:\n  limits:\n    cpu: 500m\n"
        )
        assert handler.matches("charts/subchart/values-staging.yaml", content) is True


@pytest.mark.unit
class TestHelmValuesSeparatorSpec:
    """Tests for HelmValuesHandler.SEPARATOR_SPEC."""

    def test_language_name(self):
        """SEPARATOR_SPEC.language_name should be 'helm-values'."""
        handler = HelmValuesHandler()
        assert handler.SEPARATOR_SPEC.language_name == "helm-values"

    def test_separator_count(self):
        """SEPARATOR_SPEC should have 8 separator levels."""
        handler = HelmValuesHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) == 8

    def test_has_section_annotation_separator(self):
        """First separator should split on ## @section annotations."""
        handler = HelmValuesHandler()
        assert "@section" in handler.SEPARATOR_SPEC.separators_regex[0]

    def test_has_comment_section_separator(self):
        """Second separator should split on ## comment headers."""
        handler = HelmValuesHandler()
        assert r"\n## " in handler.SEPARATOR_SPEC.separators_regex[1]

    def test_has_top_level_key_separator(self):
        """Third separator should split on top-level YAML keys."""
        handler = HelmValuesHandler()
        assert r"[a-zA-Z_]" in handler.SEPARATOR_SPEC.separators_regex[2]

    def test_has_second_level_key_separator(self):
        """Fourth separator should split on 2-space indented keys."""
        handler = HelmValuesHandler()
        assert r"\n  " in handler.SEPARATOR_SPEC.separators_regex[3]

    def test_has_third_level_key_separator(self):
        """Fifth separator should split on 4-space indented keys."""
        handler = HelmValuesHandler()
        assert r"\n    " in handler.SEPARATOR_SPEC.separators_regex[4]

    def test_no_lookaheads_in_separators(self):
        """Separators must not contain lookahead/lookbehind patterns."""
        handler = HelmValuesHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep
            assert "(?<=" not in sep
            assert "(?!" not in sep
            assert "(?<!" not in sep


@pytest.mark.unit
class TestHelmValuesExtractMetadata:
    """Tests for HelmValuesHandler.extract_metadata()."""

    # --- Section annotation detection ---

    def test_section_annotation(self):
        """## @section annotation produces section metadata."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("## @section Global parameters\nglobal:")
        assert m["block_type"] == "section"
        assert m["hierarchy"] == "section:Global parameters"
        assert m["language_id"] == "helm-values"

    def test_section_with_longer_name(self):
        """## @section with multi-word name extracts full name."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata(
            "## @section Common resource parameters\nresources:"
        )
        assert m["block_type"] == "section"
        assert m["hierarchy"] == "section:Common resource parameters"

    def test_section_takes_priority_over_key(self):
        """Section annotation takes priority over key detection."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata(
            "## @section Image parameters\nimage:\n  repository: nginx"
        )
        assert m["block_type"] == "section"
        assert m["hierarchy"] == "section:Image parameters"

    # --- Top-level key detection ---

    def test_top_level_key_image(self):
        """Top-level key 'image:' produces key metadata."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("image:\n  repository: nginx\n  tag: latest")
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:image"
        assert m["language_id"] == "helm-values"

    def test_top_level_key_service(self):
        """Top-level key 'service:' produces key metadata."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("service:\n  type: ClusterIP\n  port: 80")
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:service"

    def test_top_level_key_with_hyphen(self):
        """Top-level key with hyphen is correctly extracted."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("full-name-override: myapp")
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:full-name-override"

    # --- Nested key detection ---

    def test_nested_key_recognized(self):
        """Indented key should be recognized as nested-key."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("  repository: nginx\n  tag: latest")
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:repository"
        assert m["language_id"] == "helm-values"

    def test_nested_key_deep_indent(self):
        """Deeply indented key should be recognized as nested-key."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata(
            "      endpoint: ${env:MY_POD_IP}:4317\n      auth:"
        )
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:endpoint"

    # --- List item detection ---

    def test_list_item_recognized(self):
        """YAML list item with key should be recognized."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("  - name: http\n    containerPort: 8080")
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:name"
        assert m["language_id"] == "helm-values"

    def test_list_item_no_indent(self):
        """YAML list item at root level should be recognized."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("- name: myvolume\n  emptyDir: {}")
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:name"

    # --- Document separator detection ---

    def test_document_separator(self):
        """Chunk with --- detected as document."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("---\n")
        assert m["block_type"] == "document"
        assert m["hierarchy"] == "document"
        assert m["language_id"] == "helm-values"

    def test_document_separator_with_whitespace(self):
        """Chunk containing --- among whitespace detected as document."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("\n---\n")
        assert m["block_type"] == "document"
        assert m["hierarchy"] == "document"

    # --- Value continuation detection ---

    def test_value_continuation(self):
        """Chunk with content but no recognizable key detected as value."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata(' ""\nfullnameOverride: ""')
        assert m["block_type"] == "value"
        assert m["hierarchy"] == "value"
        assert m["language_id"] == "helm-values"

    def test_value_continuation_empty_object(self):
        """Empty object value continuation should be recognized."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata(" {}\nsecurityContext:")
        assert m["block_type"] == "value"
        assert m["hierarchy"] == "value"

    # --- Comment handling ---

    def test_comment_before_top_level_key(self):
        """Comment before top-level key is correctly skipped."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("# Image configuration\nimage:\n  tag: v1")
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:image"
        assert m["language_id"] == "helm-values"

    def test_comment_before_nested_key(self):
        """Comment before indented key should be stripped."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata(
            "  # Configures the collector\n  receivers:\n    otlp:"
        )
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:receivers"

    def test_comment_before_section(self):
        """Comment before section annotation is still detected."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata(
            "# This section covers global params\n## @section Global parameters"
        )
        assert m["block_type"] == "section"
        assert m["hierarchy"] == "section:Global parameters"

    def test_leading_newline(self):
        """Leading newline from separator split is handled."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("\nresources:\n  limits:\n    cpu: 100m")
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:resources"

    # --- Empty / whitespace ---

    def test_empty_content(self):
        """Empty content returns empty block_type."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "helm-values"

    def test_whitespace_only(self):
        """Whitespace-only content returns empty block_type."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("   \n   \n")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""

    def test_unrecognized_content(self):
        """Unrecognized content without key returns value."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("  some random indented text")
        assert m["block_type"] == "value"
        assert m["hierarchy"] == "value"
        assert m["language_id"] == "helm-values"

    # --- Indentation precision ---

    def test_top_level_is_key_not_nested(self):
        """Top-level key is key, not nested-key."""
        handler = HelmValuesHandler()
        text = "image:\n  repository: nginx"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:image"

    def test_two_space_is_nested_not_top_level(self):
        """2-space indented key is nested-key, not key."""
        handler = HelmValuesHandler()
        text = "  repository: nginx\n  tag: latest"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:repository"

    def test_four_space_is_nested(self):
        """4-space indented key is still nested-key."""
        handler = HelmValuesHandler()
        text = "    cpu: 100m\n    memory: 128Mi"
        m = handler.extract_metadata(text)
        assert m["block_type"] == "nested-key"
        assert m["hierarchy"] == "nested-key:cpu"


@pytest.mark.unit
class TestHelmValuesProtocol:
    """Tests for HelmValuesHandler protocol compliance."""

    def test_has_grammar_name(self):
        handler = HelmValuesHandler()
        assert handler.GRAMMAR_NAME == "helm-values"

    def test_has_base_language(self):
        handler = HelmValuesHandler()
        assert handler.BASE_LANGUAGE == "yaml"

    def test_has_path_patterns(self):
        handler = HelmValuesHandler()
        assert len(handler.PATH_PATTERNS) > 0

    def test_path_patterns_match_expected(self):
        """PATH_PATTERNS should match values.yaml and values-*.yaml."""
        handler = HelmValuesHandler()
        assert "**/values.yaml" in handler.PATH_PATTERNS
        assert "**/values-*.yaml" in handler.PATH_PATTERNS
        assert len(handler.PATH_PATTERNS) == 2
