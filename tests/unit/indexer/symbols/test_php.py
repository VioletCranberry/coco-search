"""Tests for PHP symbol extraction."""

from cocosearch.indexer.symbols import extract_symbol_metadata


class TestPhpSymbols:
    """Test PHP symbol extraction."""

    def test_simple_function(self):
        """Extract simple PHP function."""
        code = "<?php function process() { return true; }"
        result = extract_symbol_metadata(code, "php")

        assert result.symbol_type == "function"
        assert result.symbol_name == "process"
        assert result.symbol_signature == "function process()"

    def test_simple_class(self):
        """Extract simple PHP class."""
        code = "<?php class User {}"
        result = extract_symbol_metadata(code, "php")

        assert result.symbol_type == "class"
        assert result.symbol_name == "User"
        assert result.symbol_signature == "class User"

    def test_interface_declaration(self):
        """Extract interface declaration."""
        code = "<?php interface Repository { public function save(); }"
        result = extract_symbol_metadata(code, "php")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Repository"
        assert result.symbol_signature == "interface Repository"

    def test_trait_declaration(self):
        """Extract trait declaration (mapped to interface)."""
        code = "<?php trait Timestamps { }"
        result = extract_symbol_metadata(code, "php")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Timestamps"
        assert result.symbol_signature == "trait Timestamps"

    def test_method_in_class(self):
        """Extract method from class."""
        code = """<?php
class UserService {
    public function findById($id) {
        return null;
    }
}"""
        result = extract_symbol_metadata(code, "php")

        # First symbol is the class
        assert result.symbol_type == "class"
        assert result.symbol_name == "UserService"

    def test_method_with_parameters(self):
        """Extract method with parameters."""
        code = """<?php
class Calculator {
    public function add($x, $y) {
        return $x + $y;
    }
}"""
        result = extract_symbol_metadata(code, "php")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Calculator"

    def test_empty_input(self):
        """Empty PHP returns NULL fields."""
        result = extract_symbol_metadata("", "php")

        assert result.symbol_type is None
