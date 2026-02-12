"""Tests for Go symbol extraction."""

from cocosearch.indexer.symbols import extract_symbol_metadata


class TestGoSymbols:
    """Test Go symbol extraction."""

    def test_simple_function(self):
        """Extract simple Go function."""
        code = "func Process() error { return nil }"
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type == "function"
        assert result.symbol_name == "Process"
        assert result.symbol_signature == "func Process() error"

    def test_function_with_parameters(self):
        """Extract function with parameters."""
        code = "func Add(a, b int) int { return a + b }"
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type == "function"
        assert result.symbol_name == "Add"
        assert "func Add(" in result.symbol_signature

    def test_method_with_pointer_receiver(self):
        """Extract method with pointer receiver."""
        code = "func (s *Server) Start() error { return nil }"
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type == "method"
        assert result.symbol_name == "Server.Start"
        assert result.symbol_signature == "func (s *Server) Start() error"

    def test_method_with_value_receiver(self):
        """Extract method with value receiver."""
        code = "func (c Config) GetPort() int { return c.Port }"
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type == "method"
        assert result.symbol_name == "Config.GetPort"

    def test_struct_declaration(self):
        """Extract struct declaration (mapped to class)."""
        code = "type Server struct { port int; host string }"
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Server"
        assert result.symbol_signature == "type Server struct"

    def test_interface_declaration(self):
        """Extract interface declaration."""
        code = "type Handler interface { Handle(ctx Context) error }"
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Handler"
        assert result.symbol_signature == "type Handler interface"

    def test_empty_interface(self):
        """Extract empty interface (any)."""
        code = "type Any interface{}"
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Any"

    def test_multiple_receiver_forms(self):
        """Test various receiver syntax forms."""
        code1 = "func (srv *HTTPServer) Listen() {}"
        result1 = extract_symbol_metadata(code1, "go")
        assert result1.symbol_name == "HTTPServer.Listen"

    def test_empty_input(self):
        """Empty Go returns NULL fields."""
        result = extract_symbol_metadata("", "go")

        assert result.symbol_type is None

    def test_no_symbols(self):
        """Go with no symbols returns NULL fields."""
        code = 'package main\n\nimport "fmt"'
        result = extract_symbol_metadata(code, "go")

        assert result.symbol_type is None
