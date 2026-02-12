"""Tests for Scala symbol extraction."""

from cocosearch.indexer.symbols import extract_symbol_metadata


class TestScalaSymbols:
    """Test Scala symbol extraction."""

    def test_simple_class(self):
        """Extract simple Scala class."""
        code = "class MyClass {\n  val x = 1\n}"
        result = extract_symbol_metadata(code, "scala")

        assert result.symbol_type == "class"
        assert result.symbol_name == "MyClass"
        assert "class MyClass" in result.symbol_signature

    def test_case_class(self):
        """Extract case class."""
        code = "case class Dog(name: String, age: Int)"
        result = extract_symbol_metadata(code, "scala")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Dog"

    def test_abstract_class(self):
        """Extract abstract class."""
        code = "abstract class Animal {\n  def speak(): String\n}"
        result = extract_symbol_metadata(code, "scala")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Animal"

    def test_trait_definition(self):
        """Extract trait definition (mapped to interface)."""
        code = "trait Serializable {\n  def serialize(): String\n}"
        result = extract_symbol_metadata(code, "scala")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Serializable"
        assert "trait Serializable" in result.symbol_signature

    def test_sealed_trait(self):
        """Extract sealed trait."""
        code = "sealed trait Color"
        result = extract_symbol_metadata(code, "scala")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Color"

    def test_object_definition(self):
        """Extract object definition (mapped to class)."""
        code = "object Utils {\n  def helper(): Unit = {}\n}"
        result = extract_symbol_metadata(code, "scala")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Utils"
        assert "object Utils" in result.symbol_signature

    def test_case_object(self):
        """Extract case object."""
        code = "case object Red"
        result = extract_symbol_metadata(code, "scala")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Red"

    def test_method_in_class(self):
        """Extract method from class with qualified name."""
        from cocosearch.indexer.symbols import (
            _extract_symbols_with_query,
            resolve_query_file,
        )

        code = "class Calculator {\n  def add(x: Int, y: Int): Int = x + y\n}"
        query_text = resolve_query_file("scala")
        symbols = _extract_symbols_with_query(code, "scala", query_text)

        method_symbols = [s for s in symbols if s["symbol_type"] == "method"]
        assert len(method_symbols) >= 1
        assert method_symbols[0]["symbol_name"] == "Calculator.add"

    def test_method_in_trait(self):
        """Extract method from trait with qualified name."""
        from cocosearch.indexer.symbols import (
            _extract_symbols_with_query,
            resolve_query_file,
        )

        code = "trait Handler {\n  def handle(input: String): Unit\n}"
        query_text = resolve_query_file("scala")
        symbols = _extract_symbols_with_query(code, "scala", query_text)

        method_symbols = [s for s in symbols if s["symbol_type"] == "method"]
        assert len(method_symbols) >= 1
        assert method_symbols[0]["symbol_name"] == "Handler.handle"

    def test_method_in_object(self):
        """Extract method from object with qualified name."""
        from cocosearch.indexer.symbols import (
            _extract_symbols_with_query,
            resolve_query_file,
        )

        code = "object Utils {\n  def helper(): Unit = {}\n}"
        query_text = resolve_query_file("scala")
        symbols = _extract_symbols_with_query(code, "scala", query_text)

        method_symbols = [s for s in symbols if s["symbol_type"] == "method"]
        assert len(method_symbols) >= 1
        assert method_symbols[0]["symbol_name"] == "Utils.helper"

    def test_top_level_function(self):
        """Extract top-level function (not in class/trait/object)."""
        code = "def process(x: Int): String = x.toString"
        result = extract_symbol_metadata(code, "scala")

        assert result.symbol_type == "function"
        assert result.symbol_name == "process"

    def test_type_alias(self):
        """Extract type alias (mapped to interface)."""
        code = "type Callback = Int => Unit"
        result = extract_symbol_metadata(code, "scala")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Callback"

    def test_multiple_symbols_returns_first(self):
        """Multiple symbols in chunk returns first one."""
        code = "class Foo {\n  val x = 1\n}\n\nclass Bar {\n  val y = 2\n}"
        result = extract_symbol_metadata(code, "scala")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Foo"

    def test_empty_input(self):
        """Empty Scala returns NULL fields."""
        result = extract_symbol_metadata("", "scala")

        assert result.symbol_type is None
        assert result.symbol_name is None
        assert result.symbol_signature is None

    def test_no_symbols(self):
        """Scala with no symbols returns NULL fields."""
        code = "import scala.collection.mutable\npackage com.example"
        result = extract_symbol_metadata(code, "scala")

        assert result.symbol_type is None

    def test_generic_class(self):
        """Extract generic class with type parameters."""
        code = "class Container[T](value: T) {\n  def get: T = value\n}"
        result = extract_symbol_metadata(code, "scala")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Container"
