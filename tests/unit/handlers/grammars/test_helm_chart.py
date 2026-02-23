"""Tests for cocosearch.handlers.grammars.helm_chart module."""

from cocosearch.handlers.grammars.helm_chart import HelmChartHandler


# ============================================================================
# Tests: Path and content matching
# ============================================================================


class TestHelmChartMatching:
    """Tests for HelmChartHandler.matches()."""

    def test_matches_chart_yaml_with_markers(self):
        """Matches Chart.yaml with apiVersion and name markers."""
        handler = HelmChartHandler()
        content = "apiVersion: v2\nname: mychart\nversion: 0.1.0\n"
        assert handler.matches("mychart/Chart.yaml", content) is True

    def test_matches_chart_yml(self):
        """Matches Chart.yml variant."""
        handler = HelmChartHandler()
        content = "apiVersion: v2\nname: mychart\n"
        assert handler.matches("mychart/Chart.yml", content) is True

    def test_matches_nested_path(self):
        """Matches Chart.yaml in nested directory."""
        handler = HelmChartHandler()
        content = "apiVersion: v2\nname: subchart\n"
        assert handler.matches("charts/subchart/Chart.yaml", content) is True

    def test_matches_deeply_nested_path(self):
        """Matches Chart.yaml in deeply nested directory."""
        handler = HelmChartHandler()
        content = "apiVersion: v2\nname: deep\n"
        assert handler.matches("org/project/charts/deep/Chart.yaml", content) is True

    def test_matches_path_only_without_content(self):
        """Matches by path alone when content is None."""
        handler = HelmChartHandler()
        assert handler.matches("mychart/Chart.yaml") is True

    def test_rejects_missing_api_version(self):
        """Rejects Chart.yaml without apiVersion."""
        handler = HelmChartHandler()
        content = "name: mychart\nversion: 0.1.0\n"
        assert handler.matches("mychart/Chart.yaml", content) is False

    def test_rejects_missing_name(self):
        """Rejects Chart.yaml without name."""
        handler = HelmChartHandler()
        content = "apiVersion: v2\nversion: 0.1.0\n"
        assert handler.matches("mychart/Chart.yaml", content) is False

    def test_rejects_wrong_path(self):
        """Rejects non-Chart.yaml files."""
        handler = HelmChartHandler()
        content = "apiVersion: v2\nname: mychart\n"
        assert handler.matches("mychart/values.yaml", content) is False

    def test_rejects_wrong_path_without_content(self):
        """Rejects wrong path when content is None."""
        handler = HelmChartHandler()
        assert handler.matches("mychart/values.yaml") is False


# ============================================================================
# Tests: Separator spec
# ============================================================================


class TestHelmChartSeparatorSpec:
    """Tests for HelmChartHandler.SEPARATOR_SPEC."""

    def test_language_name(self):
        """SEPARATOR_SPEC.language_name should be 'helm-chart'."""
        handler = HelmChartHandler()
        assert handler.SEPARATOR_SPEC.language_name == "helm-chart"

    def test_separator_count(self):
        """SEPARATOR_SPEC should have 7 separator levels."""
        handler = HelmChartHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) == 7

    def test_no_lookaheads_in_separators(self):
        """Separators must not contain lookahead/lookbehind patterns."""
        handler = HelmChartHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep
            assert "(?<=" not in sep
            assert "(?!" not in sep
            assert "(?<!" not in sep


# ============================================================================
# Tests: Metadata extraction
# ============================================================================


class TestHelmChartExtractMetadata:
    """Tests for HelmChartHandler.extract_metadata()."""

    def test_dependency_item(self):
        """Dependency list item produces dependency metadata."""
        handler = HelmChartHandler()
        m = handler.extract_metadata("- name: postgresql\n  version: 12.0.0")
        assert m["block_type"] == "dependency"
        assert m["hierarchy"] == "dependency:postgresql"
        assert m["language_id"] == "helm-chart"

    def test_dependency_item_indented(self):
        """Indented dependency list item is recognized."""
        handler = HelmChartHandler()
        m = handler.extract_metadata("  - name: redis\n    version: 17.0.0")
        assert m["block_type"] == "dependency"
        assert m["hierarchy"] == "dependency:redis"

    def test_top_level_key_name(self):
        """Top-level key 'name:' produces key metadata."""
        handler = HelmChartHandler()
        m = handler.extract_metadata("name: mychart")
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:name"
        assert m["language_id"] == "helm-chart"

    def test_top_level_key_api_version(self):
        """Top-level key 'apiVersion:' produces key metadata."""
        handler = HelmChartHandler()
        m = handler.extract_metadata("apiVersion: v2")
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:apiVersion"

    def test_top_level_key_dependencies(self):
        """Top-level key 'dependencies:' produces key metadata."""
        handler = HelmChartHandler()
        m = handler.extract_metadata("dependencies:")
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:dependencies"

    def test_list_item_without_name(self):
        """List item with a non-name key produces list-item metadata."""
        handler = HelmChartHandler()
        m = handler.extract_metadata("- repository: https://example.com")
        assert m["block_type"] == "list-item"
        assert m["hierarchy"] == "list-item:repository"

    def test_document_separator(self):
        """Chunk with --- detected as document."""
        handler = HelmChartHandler()
        m = handler.extract_metadata("---\n")
        assert m["block_type"] == "document"
        assert m["hierarchy"] == "document"

    def test_empty_content(self):
        """Empty content returns empty block_type."""
        handler = HelmChartHandler()
        m = handler.extract_metadata("")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "helm-chart"

    def test_comment_before_key(self):
        """Comment before top-level key is correctly skipped."""
        handler = HelmChartHandler()
        m = handler.extract_metadata("# Chart metadata\nname: mychart")
        assert m["block_type"] == "key"
        assert m["hierarchy"] == "key:name"


# ============================================================================
# Tests: Protocol compliance
# ============================================================================


class TestHelmChartProtocol:
    """Tests for HelmChartHandler protocol compliance."""

    def test_grammar_name(self):
        handler = HelmChartHandler()
        assert handler.GRAMMAR_NAME == "helm-chart"

    def test_base_language(self):
        handler = HelmChartHandler()
        assert handler.BASE_LANGUAGE == "yaml"

    def test_path_patterns(self):
        handler = HelmChartHandler()
        assert "**/Chart.yaml" in handler.PATH_PATTERNS
        assert "**/Chart.yml" in handler.PATH_PATTERNS
        assert len(handler.PATH_PATTERNS) == 2
