"""Tests for cocosearch.handlers.grammars.helm_values module."""

import pytest

from cocosearch.handlers.grammars.helm_values import HelmValuesHandler


@pytest.mark.unit
class TestHelmValuesHandlerAttributes:
    """Tests for HelmValuesHandler class attributes."""

    def test_grammar_name(self):
        """GRAMMAR_NAME should be 'helm-values'."""
        handler = HelmValuesHandler()
        assert handler.GRAMMAR_NAME == "helm-values"

    def test_base_language(self):
        """BASE_LANGUAGE should be 'yaml'."""
        handler = HelmValuesHandler()
        assert handler.BASE_LANGUAGE == "yaml"

    def test_path_patterns(self):
        """PATH_PATTERNS should match values.yaml and values-*.yaml."""
        handler = HelmValuesHandler()
        assert "**/values.yaml" in handler.PATH_PATTERNS
        assert "**/values-*.yaml" in handler.PATH_PATTERNS
        assert len(handler.PATH_PATTERNS) == 2


@pytest.mark.unit
class TestHelmValuesHandlerSeparatorSpec:
    """Tests for HelmValuesHandler SEPARATOR_SPEC."""

    def test_language_name(self):
        """SEPARATOR_SPEC.language_name should be 'helm-values'."""
        handler = HelmValuesHandler()
        assert handler.SEPARATOR_SPEC.language_name == "helm-values"

    def test_has_separators(self):
        """SEPARATOR_SPEC should have a non-empty separators_regex list."""
        handler = HelmValuesHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) > 0

    def test_level1_splits_on_section_annotation(self):
        """Level 1 separator should split on ## @section."""
        handler = HelmValuesHandler()
        level1 = handler.SEPARATOR_SPEC.separators_regex[0]
        assert "@section" in level1

    def test_no_lookaheads_in_separators(self):
        """Separators must not contain lookahead or lookbehind patterns."""
        handler = HelmValuesHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep, f"Lookahead found in separator: {sep}"
            assert "(?<=" not in sep, f"Lookbehind found in separator: {sep}"
            assert "(?!" not in sep, f"Negative lookahead found: {sep}"
            assert "(?<!" not in sep, f"Negative lookbehind found: {sep}"


@pytest.mark.unit
class TestHelmValuesHandlerMatches:
    """Tests for HelmValuesHandler.matches()."""

    def test_matches_values_yaml_with_helm_keys(self):
        """Should match values.yaml with 3+ common Helm keys."""
        handler = HelmValuesHandler()
        content = (
            "replicaCount: 1\n"
            "image:\n  repository: nginx\n"
            "service:\n  type: ClusterIP\n"
            "ingress:\n  enabled: false\n"
        )
        assert handler.matches("mychart/values.yaml", content)

    def test_matches_values_override(self):
        """Should match values-*.yaml with Helm keys."""
        handler = HelmValuesHandler()
        content = (
            "replicaCount: 3\n"
            "image:\n  tag: latest\n"
            "resources:\n  limits:\n    cpu: 500m\n"
        )
        assert handler.matches("mychart/values-production.yaml", content)

    def test_no_match_too_few_keys(self):
        """Should not match values.yaml with fewer than 3 Helm keys."""
        handler = HelmValuesHandler()
        content = "replicaCount: 1\nimage:\n  tag: latest\n"
        assert not handler.matches("mychart/values.yaml", content)

    def test_no_match_non_helm_values(self):
        """Should not match values.yaml from non-Helm project."""
        handler = HelmValuesHandler()
        content = "database:\n  host: localhost\nlogging:\n  level: info\n"
        assert not handler.matches("myapp/values.yaml", content)

    def test_no_match_wrong_path(self):
        """Should not match non-values.yaml files."""
        handler = HelmValuesHandler()
        content = (
            "replicaCount: 1\nimage:\n  tag: latest\nservice:\n  type: ClusterIP\n"
        )
        assert not handler.matches("mychart/config.yaml", content)

    def test_matches_path_only_no_content(self):
        """Should match by path when content is None."""
        handler = HelmValuesHandler()
        assert handler.matches("mychart/values.yaml")

    def test_matches_nested_values(self):
        """Should match nested values.yaml."""
        handler = HelmValuesHandler()
        content = (
            "replicaCount: 1\n"
            "image:\n  tag: v1\n"
            "service:\n  port: 80\n"
            "ingress:\n  enabled: true\n"
        )
        assert handler.matches("charts/subchart/values.yaml", content)

    def test_matches_with_exactly_three_keys(self):
        """Should match when exactly 3 Helm keys are present."""
        handler = HelmValuesHandler()
        content = (
            "replicaCount: 1\n"
            "image:\n  repository: nginx\n"
            "service:\n  type: ClusterIP\n"
        )
        assert handler.matches("mychart/values.yaml", content)


@pytest.mark.unit
class TestHelmValuesHandlerExtractMetadata:
    """Tests for HelmValuesHandler.extract_metadata()."""

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

    def test_top_level_key_with_comment(self):
        """Comment before top-level key is correctly skipped."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("# Image configuration\nimage:\n  tag: v1")
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:image"

    def test_section_takes_priority_over_key(self):
        """Section annotation takes priority over key detection."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata(
            "## @section Image parameters\nimage:\n  repository: nginx"
        )
        assert m["block_type"] == "section"
        assert m["hierarchy"] == "section:Image parameters"

    def test_leading_newline(self):
        """Leading newline from separator split is handled."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("\nresources:\n  limits:\n    cpu: 100m")
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:resources"

    def test_indented_key_not_top_level(self):
        """Indented key should not be treated as top-level."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("  repository: nginx\n  tag: latest")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "helm-values"

    def test_unrecognized_content_returns_empty(self):
        """Unrecognized content produces empty metadata."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("  - name: http\n    containerPort: 8080")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "helm-values"

    def test_key_with_hyphen(self):
        """Top-level key with hyphen is correctly extracted."""
        handler = HelmValuesHandler()
        m = handler.extract_metadata("full-name-override: myapp")
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:full-name-override"
