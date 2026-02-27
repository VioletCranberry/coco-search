"""Tests for cocosearch.handlers.scala module."""

import pytest

from cocosearch.handlers.scala import ScalaHandler


@pytest.mark.unit
class TestScalaHandlerExtensions:
    """Tests for ScalaHandler EXTENSIONS."""

    def test_extensions_contains_scala(self):
        """EXTENSIONS should contain .scala."""
        handler = ScalaHandler()
        assert ".scala" in handler.EXTENSIONS


@pytest.mark.unit
class TestScalaHandlerSeparatorSpec:
    """Tests for ScalaHandler SEPARATOR_SPEC."""

    def test_language_name_is_scala(self):
        """SEPARATOR_SPEC.language_name should be 'scala'."""
        handler = ScalaHandler()
        assert handler.SEPARATOR_SPEC.language_name == "scala"

    def test_aliases_contains_sc(self):
        """SEPARATOR_SPEC.aliases should contain 'sc'."""
        handler = ScalaHandler()
        assert handler.SEPARATOR_SPEC.aliases == ["sc"]

    def test_has_separators(self):
        """SEPARATOR_SPEC should have a non-empty separators_regex list."""
        handler = ScalaHandler()
        assert len(handler.SEPARATOR_SPEC.separators_regex) > 0

    def test_no_lookaheads_in_separators(self):
        """Scala separators must not contain lookahead or lookbehind patterns."""
        handler = ScalaHandler()
        for sep in handler.SEPARATOR_SPEC.separators_regex:
            assert "(?=" not in sep, f"Lookahead found in Scala separator: {sep}"
            assert "(?<=" not in sep, f"Lookbehind found in Scala separator: {sep}"
            assert "(?!" not in sep, (
                f"Negative lookahead found in Scala separator: {sep}"
            )
            assert "(?<!" not in sep, (
                f"Negative lookbehind found in Scala separator: {sep}"
            )


@pytest.mark.unit
class TestScalaHandlerExtractMetadata:
    """Tests for ScalaHandler.extract_metadata()."""

    def test_simple_class(self):
        """Simple class definition is recognized."""
        handler = ScalaHandler()
        m = handler.extract_metadata("class MyClass {")
        assert m["block_type"] == "class"
        assert m["hierarchy"] == "class:MyClass"
        assert m["language_id"] == "scala"

    def test_case_class(self):
        """Case class definition is recognized."""
        handler = ScalaHandler()
        m = handler.extract_metadata("case class Dog(name: String)")
        assert m["block_type"] == "class"
        assert m["hierarchy"] == "class:Dog"
        assert m["language_id"] == "scala"

    def test_abstract_class(self):
        """Abstract class definition is recognized."""
        handler = ScalaHandler()
        m = handler.extract_metadata("abstract class Animal {")
        assert m["block_type"] == "class"
        assert m["hierarchy"] == "class:Animal"
        assert m["language_id"] == "scala"

    def test_trait(self):
        """Trait definition is recognized."""
        handler = ScalaHandler()
        m = handler.extract_metadata("trait Serializable {")
        assert m["block_type"] == "trait"
        assert m["hierarchy"] == "trait:Serializable"
        assert m["language_id"] == "scala"

    def test_sealed_trait(self):
        """Sealed trait definition is recognized."""
        handler = ScalaHandler()
        m = handler.extract_metadata("sealed trait Color")
        assert m["block_type"] == "trait"
        assert m["hierarchy"] == "trait:Color"
        assert m["language_id"] == "scala"

    def test_object(self):
        """Object definition is recognized."""
        handler = ScalaHandler()
        m = handler.extract_metadata("object Utils {")
        assert m["block_type"] == "object"
        assert m["hierarchy"] == "object:Utils"
        assert m["language_id"] == "scala"

    def test_case_object(self):
        """Case object definition is recognized."""
        handler = ScalaHandler()
        m = handler.extract_metadata("case object Red")
        assert m["block_type"] == "object"
        assert m["hierarchy"] == "object:Red"
        assert m["language_id"] == "scala"

    def test_def(self):
        """Method/function definition is recognized."""
        handler = ScalaHandler()
        m = handler.extract_metadata("def process(x: Int): String = {")
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:process"
        assert m["language_id"] == "scala"

    def test_override_def(self):
        """Override def is recognized."""
        handler = ScalaHandler()
        m = handler.extract_metadata("override def speak(): String =")
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:speak"
        assert m["language_id"] == "scala"

    def test_val(self):
        """Val definition is recognized."""
        handler = ScalaHandler()
        m = handler.extract_metadata("val x: Int = 42")
        assert m["block_type"] == "val"
        assert m["hierarchy"] == "val:x"
        assert m["language_id"] == "scala"

    def test_var(self):
        """Var definition is recognized."""
        handler = ScalaHandler()
        m = handler.extract_metadata("var count: Int = 0")
        assert m["block_type"] == "var"
        assert m["hierarchy"] == "var:count"
        assert m["language_id"] == "scala"

    def test_type_alias(self):
        """Type alias is recognized."""
        handler = ScalaHandler()
        m = handler.extract_metadata("type Callback = Int => Unit")
        assert m["block_type"] == "type"
        assert m["hierarchy"] == "type:Callback"
        assert m["language_id"] == "scala"

    def test_comment_before_definition(self):
        """Comment line before definition is correctly skipped."""
        handler = ScalaHandler()
        m = handler.extract_metadata("// This is a class\nclass MyClass {")
        assert m["block_type"] == "class"
        assert m["hierarchy"] == "class:MyClass"
        assert m["language_id"] == "scala"

    def test_unrecognized_content_returns_empty(self):
        """Unrecognized content produces empty block_type and hierarchy."""
        handler = ScalaHandler()
        m = handler.extract_metadata('println("hello world")')
        assert m["block_type"] == ""
        assert m["hierarchy"] == ""
        assert m["language_id"] == "scala"

    def test_leading_newline(self):
        """Leading newline from separator split is handled."""
        handler = ScalaHandler()
        m = handler.extract_metadata("\nclass MyClass {")
        assert m["block_type"] == "class"
        assert m["hierarchy"] == "class:MyClass"
        assert m["language_id"] == "scala"

    def test_doc_comment_before_definition(self):
        """Doc comment (/** ... */) lines before definition are skipped."""
        handler = ScalaHandler()
        m = handler.extract_metadata(
            "/** Process data.\n  * @param x input\n  */\ndef process(x: Int): Int = {"
        )
        assert m["block_type"] == "function"
        assert m["hierarchy"] == "function:process"
        assert m["language_id"] == "scala"
