"""Tests for C symbol extraction."""

from cocosearch.indexer.symbols import extract_symbol_metadata


class TestCSymbols:
    """Test C symbol extraction."""

    def test_simple_function(self):
        """Extract simple C function."""
        code = "int process() { return 0; }"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type == "function"
        assert result.symbol_name == "process"
        assert result.symbol_signature == "int process()"

    def test_function_with_parameters(self):
        """Extract function with parameters."""
        code = "int add(int a, int b) { return a + b; }"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type == "function"
        assert result.symbol_name == "add"
        assert "int add(" in result.symbol_signature

    def test_pointer_function(self):
        """Extract function returning pointer."""
        code = "void *allocate(size_t size) { return malloc(size); }"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type == "function"
        assert result.symbol_name == "allocate"

    def test_struct_with_body(self):
        """Extract struct with body (mapped to class)."""
        code = "struct User { char *name; int age; };"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type == "class"
        assert result.symbol_name == "User"
        assert result.symbol_signature == "struct User"

    def test_struct_forward_declaration_ignored(self):
        """Forward declaration without body should be ignored."""
        code = "struct User;"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type is None
        assert result.symbol_name is None

    def test_enum_declaration(self):
        """Extract enum declaration (mapped to class)."""
        code = "enum Status { ACTIVE, INACTIVE, PENDING };"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Status"
        assert result.symbol_signature == "enum Status"

    def test_typedef_declaration(self):
        """Extract typedef (mapped to interface)."""
        code = "typedef struct User User;"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "User"
        assert result.symbol_signature == "typedef struct User User;"

    def test_function_declaration_ignored(self):
        """Function declaration without body should be ignored."""
        code = "int process();"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type is None

    def test_header_extension(self):
        """C header files (.h) use C extractor."""
        code = "int process() { return 0; }"
        result = extract_symbol_metadata(code, "h")

        assert result.symbol_type == "function"
        assert result.symbol_name == "process"

    def test_empty_input(self):
        """Empty C returns NULL fields."""
        result = extract_symbol_metadata("", "c")

        assert result.symbol_type is None

    def test_no_symbols(self):
        """C with no symbols returns NULL fields."""
        code = "#include <stdio.h>\n#define MAX 100"
        result = extract_symbol_metadata(code, "c")

        assert result.symbol_type is None
