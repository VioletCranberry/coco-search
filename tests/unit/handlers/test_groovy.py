"""Tests for cocosearch.handlers.groovy module."""

import pytest

from cocosearch.handlers.groovy import GroovyHandler


@pytest.mark.unit
class TestGroovyHandlerExtensions:
    """Tests for GroovyHandler EXTENSIONS."""

    def test_extensions_contains_groovy(self):
        """EXTENSIONS should contain .groovy."""
        handler = GroovyHandler()
        assert ".groovy" in handler.EXTENSIONS

    def test_extensions_contains_gradle(self):
        """EXTENSIONS should contain .gradle."""
        handler = GroovyHandler()
        assert ".gradle" in handler.EXTENSIONS


@pytest.mark.unit
class TestGroovyHandlerSeparatorSpec:
    """Tests for GroovyHandler SEPARATOR_SPEC."""

    def test_language_name_is_groovy(self):
        """SEPARATOR_SPEC.language_name should be 'groovy'."""
        handler = GroovyHandler()
        assert handler.SEPARATOR_SPEC.language_name == "groovy"

    def test_aliases_contains_gradle(self):
        """SEPARATOR_SPEC.aliases should contain 'gradle'."""
        handler = GroovyHandler()
        assert handler.SEPARATOR_SPEC.aliases == ["gradle"]

    def test_has_separators(self):
        """SEPARATOR_SPEC should have a non-empty separators_regex list."""
        handler = GroovyHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) > 0

    def test_no_lookaheads_in_separators(self):
        """Groovy separators must not contain lookahead or lookbehind patterns."""
        handler = GroovyHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep, f"Lookahead found in Groovy separator: {sep}"
            assert "(?<=" not in sep, f"Lookbehind found in Groovy separator: {sep}"
            assert "(?!" not in sep, (
                f"Negative lookahead found in Groovy separator: {sep}"
            )
            assert "(?<!" not in sep, (
                f"Negative lookbehind found in Groovy separator: {sep}"
            )


@pytest.mark.unit
class TestGroovyHandlerExtractMetadata:
    """Tests for GroovyHandler.extract_metadata()."""

    def test_simple_class(self):
        """Simple class definition is recognized."""
        handler = GroovyHandler()
        m = handler.extract_metadata("class MyService {")
        assert m["block_type"] == "class"
        assert m["hierarchy"] == "class:MyService"
        assert m["language_id"] == "groovy"

    def test_abstract_class(self):
        """Abstract class definition is recognized."""
        handler = GroovyHandler()
        m = handler.extract_metadata("abstract class Animal {")
        assert m["block_type"] == "class"
        assert m["hierarchy"] == "class:Animal"
        assert m["language_id"] == "groovy"

    def test_public_class(self):
        """Public class definition is recognized."""
        handler = GroovyHandler()
        m = handler.extract_metadata("public class UserService {")
        assert m["block_type"] == "class"
        assert m["hierarchy"] == "class:UserService"
        assert m["language_id"] == "groovy"

    def test_interface(self):
        """Interface definition is recognized."""
        handler = GroovyHandler()
        m = handler.extract_metadata("interface Searchable {")
        assert m["block_type"] == "interface"
        assert m["hierarchy"] == "interface:Searchable"
        assert m["language_id"] == "groovy"

    def test_trait(self):
        """Trait definition is recognized."""
        handler = GroovyHandler()
        m = handler.extract_metadata("trait Cacheable {")
        assert m["block_type"] == "trait"
        assert m["hierarchy"] == "trait:Cacheable"
        assert m["language_id"] == "groovy"

    def test_enum(self):
        """Enum definition is recognized."""
        handler = GroovyHandler()
        m = handler.extract_metadata("enum Status {")
        assert m["block_type"] == "enum"
        assert m["hierarchy"] == "enum:Status"
        assert m["language_id"] == "groovy"

    def test_def(self):
        """Method/function definition with def is recognized."""
        handler = GroovyHandler()
        m = handler.extract_metadata("def processData(List items) {")
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:processData"
        assert m["language_id"] == "groovy"

    def test_static_def(self):
        """Static def is recognized."""
        handler = GroovyHandler()
        m = handler.extract_metadata("static def getInstance() {")
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:getInstance"
        assert m["language_id"] == "groovy"

    def test_private_def(self):
        """Private def is recognized."""
        handler = GroovyHandler()
        m = handler.extract_metadata("private def helper(String input) {")
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:helper"
        assert m["language_id"] == "groovy"

    def test_comment_before_definition(self):
        """Comment line before definition is correctly skipped."""
        handler = GroovyHandler()
        m = handler.extract_metadata("// This is a class\nclass MyClass {")
        assert m["block_type"] == "class"
        assert m["hierarchy"] == "class:MyClass"
        assert m["language_id"] == "groovy"

    def test_doc_comment_before_definition(self):
        """Doc comment (/** ... */) lines before definition are skipped."""
        handler = GroovyHandler()
        m = handler.extract_metadata(
            "/** Process data.\n  * @param items input\n  */\ndef process(List items) {"
        )
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:process"
        assert m["language_id"] == "groovy"

    def test_unrecognized_content_returns_empty(self):
        """Unrecognized content produces empty block_type and hierarchy."""
        handler = GroovyHandler()
        m = handler.extract_metadata('println "hello world"')
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "groovy"

    def test_leading_newline(self):
        """Leading newline from separator split is handled."""
        handler = GroovyHandler()
        m = handler.extract_metadata("\nclass MyClass {")
        assert m["block_type"] == "class"
        assert m["hierarchy"] == "class:MyClass"
        assert m["language_id"] == "groovy"
