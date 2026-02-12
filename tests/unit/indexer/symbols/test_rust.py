"""Tests for Rust symbol extraction."""

from cocosearch.indexer.symbols import extract_symbol_metadata


class TestRustSymbols:
    """Test Rust symbol extraction."""

    def test_simple_function(self):
        """Extract simple Rust function."""
        code = "fn process() -> Result<(), Error> { Ok(()) }"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "function"
        assert result.symbol_name == "process"
        assert result.symbol_signature == "fn process() -> Result<(), Error>"

    def test_function_with_parameters(self):
        """Extract function with parameters."""
        code = "fn add(a: i32, b: i32) -> i32 { a + b }"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "function"
        assert result.symbol_name == "add"
        assert "fn add(" in result.symbol_signature

    def test_public_function(self):
        """Extract public function."""
        code = "pub fn new() -> Self { Self {} }"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "function"
        assert result.symbol_name == "new"

    def test_method_in_impl_block(self):
        """Extract method from impl block."""
        code = """impl Server {
    fn start(&self) -> Result<(), Error> {
        Ok(())
    }
}"""
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "method"
        assert result.symbol_name == "Server.start"
        assert result.symbol_signature == "fn start(&self) -> Result<(), Error>"

    def test_multiple_methods_in_impl(self):
        """Verify multiple methods extracted from impl block."""
        from cocosearch.indexer.symbols import (
            _extract_symbols_with_query,
            resolve_query_file,
        )

        code = """impl Server {
    fn start(&self) {}
    fn stop(&mut self) {}
}"""
        query_text = resolve_query_file("rust")
        symbols = _extract_symbols_with_query(code, "rust", query_text)

        assert len(symbols) == 2
        assert symbols[0]["symbol_name"] == "Server.start"
        assert symbols[1]["symbol_name"] == "Server.stop"

    def test_struct_declaration(self):
        """Extract struct declaration (mapped to class)."""
        code = "struct Server { port: u16, host: String }"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Server"
        assert result.symbol_signature == "struct Server"

    def test_tuple_struct(self):
        """Extract tuple struct."""
        code = "struct Point(i32, i32);"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Point"

    def test_trait_declaration(self):
        """Extract trait declaration (mapped to interface)."""
        code = "trait Handler { fn handle(&self) -> Result<(), Error>; }"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Handler"
        assert result.symbol_signature == "trait Handler"

    def test_enum_declaration(self):
        """Extract enum declaration (mapped to class)."""
        code = "enum Status { Active, Inactive, Pending }"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Status"
        assert result.symbol_signature == "enum Status"

    def test_enum_with_data(self):
        """Extract enum with associated data."""
        code = "enum Message { Quit, Move { x: i32, y: i32 }, Write(String) }"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Message"

    def test_empty_input(self):
        """Empty Rust returns NULL fields."""
        result = extract_symbol_metadata("", "rs")

        assert result.symbol_type is None

    def test_no_symbols(self):
        """Rust with no symbols returns NULL fields."""
        code = "use std::io::Result;\nmod tests;"
        result = extract_symbol_metadata(code, "rs")

        assert result.symbol_type is None
