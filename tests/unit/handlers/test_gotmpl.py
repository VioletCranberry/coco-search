"""Tests for cocosearch.handlers.gotmpl module."""

import pytest

from cocosearch.handlers.gotmpl import GoTmplHandler


@pytest.mark.unit
class TestGoTmplHandlerExtensions:
    """Tests for GoTmplHandler EXTENSIONS."""

    def test_extensions_contains_tpl_gotmpl(self):
        """EXTENSIONS should contain .tpl and .gotmpl."""
        handler = GoTmplHandler()
        assert ".tpl" in handler.EXTENSIONS
        assert ".gotmpl" in handler.EXTENSIONS
        assert len(handler.EXTENSIONS) == 2


@pytest.mark.unit
class TestGoTmplHandlerSeparatorSpec:
    """Tests for GoTmplHandler SEPARATOR_SPEC."""

    def test_language_name_is_gotmpl(self):
        """SEPARATOR_SPEC.language_name should be 'gotmpl'."""
        handler = GoTmplHandler()
        assert handler.SEPARATOR_SPEC.language_name == "gotmpl"

    def test_aliases_contains_tpl(self):
        """SEPARATOR_SPEC.aliases should contain tpl."""
        handler = GoTmplHandler()
        assert handler.SEPARATOR_SPEC.aliases == ["tpl"]

    def test_has_separators(self):
        """SEPARATOR_SPEC should have a non-empty separators_regex list."""
        handler = GoTmplHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) > 0

    def test_level1_splits_on_define(self):
        """Level 1 separator should split on template define blocks."""
        handler = GoTmplHandler()
        level1 = handler.SEPARATOR_SPEC.separators_regex[0]
        assert "define" in level1

    def test_no_lookaheads_in_separators(self):
        """Separators must not contain lookahead or lookbehind patterns."""
        handler = GoTmplHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep, f"Lookahead found in separator: {sep}"
            assert "(?<=" not in sep, f"Lookbehind found in separator: {sep}"
            assert "(?!" not in sep, f"Negative lookahead found in separator: {sep}"
            assert "(?<!" not in sep, (
                f"Negative lookbehind found in separator: {sep}"
            )


@pytest.mark.unit
class TestGoTmplHandlerExtractMetadata:
    """Tests for GoTmplHandler.extract_metadata()."""

    def test_define_with_dash_whitespace(self):
        """{{- define "name" -}} produces correct metadata."""
        handler = GoTmplHandler()
        m = handler.extract_metadata('{{- define "mychart.labels" -}}')
        assert m["block_type"] == "define"
        assert m["hierarchy"] == "define:mychart.labels"
        assert m["language_id"] == "gotmpl"

    def test_define_without_dashes(self):
        """{{define "name"}} produces correct metadata."""
        handler = GoTmplHandler()
        m = handler.extract_metadata('{{define "mychart.fullname"}}')
        assert m["block_type"] == "define"
        assert m["hierarchy"] == "define:mychart.fullname"
        assert m["language_id"] == "gotmpl"

    def test_define_with_body(self):
        """Define block with body content extracts name correctly."""
        handler = GoTmplHandler()
        text = '{{- define "mychart.selectorLabels" -}}\napp: {{ .Values.app }}\n{{- end }}'
        m = handler.extract_metadata(text)
        assert m["block_type"] == "define"
        assert m["hierarchy"] == "define:mychart.selectorLabels"

    def test_define_with_leading_comment(self):
        """Comment before define block is correctly skipped."""
        handler = GoTmplHandler()
        text = '{{/* Helper template */}}\n{{- define "mychart.name" -}}'
        m = handler.extract_metadata(text)
        assert m["block_type"] == "define"
        assert m["hierarchy"] == "define:mychart.name"

    def test_define_with_leading_newline(self):
        """Leading newline from separator split is handled."""
        handler = GoTmplHandler()
        m = handler.extract_metadata('\n{{- define "mychart.labels" -}}')
        assert m["block_type"] == "define"
        assert m["hierarchy"] == "define:mychart.labels"

    def test_unrecognized_content_returns_empty(self):
        """Unrecognized content produces empty block_type and hierarchy."""
        handler = GoTmplHandler()
        m = handler.extract_metadata("{{ .Values.image.repository }}")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "gotmpl"

    def test_plain_text_returns_empty(self):
        """Plain text without Go template syntax returns empty metadata."""
        handler = GoTmplHandler()
        m = handler.extract_metadata("just some text content")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "gotmpl"

    def test_range_block_returns_empty(self):
        """Range block (not define) returns empty metadata."""
        handler = GoTmplHandler()
        m = handler.extract_metadata("{{- range .Values.items }}")
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "gotmpl"

    def test_define_with_dotted_name(self):
        """Define with multi-dotted name extracts full name."""
        handler = GoTmplHandler()
        m = handler.extract_metadata('{{- define "mylib.chart.v1.labels" -}}')
        assert m["hierarchy"] == "define:mylib.chart.v1.labels"
