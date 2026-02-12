"""Tests for JavaScript symbol extraction."""

from cocosearch.indexer.symbols import extract_symbol_metadata


class TestJavaScriptSymbols:
    """Test JavaScript symbol extraction."""

    def test_simple_function(self):
        """Extract simple function declaration."""
        code = "function fetchUser() { return null; }"
        result = extract_symbol_metadata(code, "js")

        assert result.symbol_type == "function"
        assert result.symbol_name == "fetchUser"
        assert result.symbol_signature == "function fetchUser()"

    def test_function_with_parameters(self):
        """Extract function with parameters."""
        code = "function add(a, b) { return a + b; }"
        result = extract_symbol_metadata(code, "js")

        assert result.symbol_type == "function"
        assert result.symbol_name == "add"
        assert result.symbol_signature == "function add(a, b)"

    def test_arrow_function_with_parens(self):
        """Extract named arrow function with parentheses."""
        code = "const fetchData = (url) => { return fetch(url); }"
        result = extract_symbol_metadata(code, "js")

        assert result.symbol_type == "function"
        assert result.symbol_name == "fetchData"
        assert result.symbol_signature == "const fetchData = (url) =>"

    def test_arrow_function_multiple_params(self):
        """Extract arrow function with multiple parameters."""
        code = "const multiply = (x, y) => x * y;"
        result = extract_symbol_metadata(code, "js")

        assert result.symbol_type == "function"
        assert result.symbol_name == "multiply"

    def test_class_declaration(self):
        """Extract class declaration."""
        code = "class UserService { }"
        result = extract_symbol_metadata(code, "js")

        assert result.symbol_type == "class"
        assert result.symbol_name == "UserService"
        assert result.symbol_signature == "class UserService"

    def test_class_with_method(self):
        """Extract class with method (class is first symbol)."""
        code = """class UserService {
    fetchUser(id) {
        return this.users[id];
    }
}"""
        result = extract_symbol_metadata(code, "js")

        # First symbol is the class
        assert result.symbol_type == "class"
        assert result.symbol_name == "UserService"

    def test_method_definition(self):
        """Verify method is extracted with qualified name when class not first."""
        from cocosearch.indexer.symbols import (
            _extract_symbols_with_query,
            resolve_query_file,
        )

        code = """class UserService {
    fetchUser(id) {
        return this.users[id];
    }
}"""
        query_text = resolve_query_file("javascript")
        symbols = _extract_symbols_with_query(code, "javascript", query_text)

        assert len(symbols) == 2
        assert symbols[0]["symbol_type"] == "class"
        assert symbols[1]["symbol_type"] == "method"
        assert symbols[1]["symbol_name"] == "UserService.fetchUser"
        assert "fetchUser(id)" in symbols[1]["symbol_signature"]

    def test_jsx_extension(self):
        """JSX files use JavaScript extractor."""
        code = "function Button() { return <button />; }"
        result = extract_symbol_metadata(code, "jsx")

        assert result.symbol_type == "function"
        assert result.symbol_name == "Button"

    def test_empty_input(self):
        """Empty JavaScript returns NULL fields."""
        result = extract_symbol_metadata("", "js")

        assert result.symbol_type is None
        assert result.symbol_name is None
        assert result.symbol_signature is None

    def test_no_symbols(self):
        """JavaScript with no symbols returns NULL fields."""
        code = "const x = 42; console.log(x);"
        result = extract_symbol_metadata(code, "js")

        assert result.symbol_type is None
