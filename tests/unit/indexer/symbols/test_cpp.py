"""Tests for C++ symbol extraction."""

from cocosearch.indexer.symbols import extract_symbol_metadata


class TestCppSymbols:
    """Test C++ symbol extraction."""

    def test_simple_function(self):
        """Extract simple C++ function."""
        code = "int process() { return 0; }"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "function"
        assert result.symbol_name == "process"
        assert result.symbol_signature == "int process()"

    def test_class_declaration(self):
        """Extract class declaration."""
        code = "class Server { int port; };"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Server"
        assert result.symbol_signature == "class Server"

    def test_struct_declaration(self):
        """Extract struct declaration."""
        code = "struct Point { int x; int y; };"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Point"
        assert result.symbol_signature == "struct Point"

    def test_namespace_declaration(self):
        """Extract namespace declaration (mapped to class)."""
        code = "namespace MyLib { }"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "class"
        assert result.symbol_name == "MyLib"
        assert result.symbol_signature == "namespace MyLib"

    def test_method_with_qualified_name(self):
        """Extract method with qualified name (ClassName::method)."""
        code = "void MyClass::myMethod() { }"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "method"
        assert result.symbol_name == "myMethod"
        assert "MyClass::myMethod" in result.symbol_signature

    def test_pointer_function(self):
        """Extract function returning pointer."""
        code = "void *allocate(size_t size) { return new char[size]; }"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "function"
        assert result.symbol_name == "allocate"

    def test_template_class(self):
        """Extract template class."""
        code = "template<typename T> class Container { };"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Container"

    def test_template_function(self):
        """Extract template function."""
        code = "template<typename T> T max(T a, T b) { return a > b ? a : b; }"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type == "function"
        assert result.symbol_name == "max"

    def test_multiple_extensions(self):
        """Test various C++ extensions."""
        code = "class Foo {};"

        result_cpp = extract_symbol_metadata(code, "cpp")
        result_cxx = extract_symbol_metadata(code, "cxx")
        result_cc = extract_symbol_metadata(code, "cc")
        result_hpp = extract_symbol_metadata(code, "hpp")

        assert result_cpp.symbol_type == "class"
        assert result_cxx.symbol_type == "class"
        assert result_cc.symbol_type == "class"
        assert result_hpp.symbol_type == "class"

    def test_empty_input(self):
        """Empty C++ returns NULL fields."""
        result = extract_symbol_metadata("", "cpp")

        assert result.symbol_type is None

    def test_no_symbols(self):
        """C++ with no symbols returns NULL fields."""
        code = "#include <iostream>\nusing namespace std;"
        result = extract_symbol_metadata(code, "cpp")

        assert result.symbol_type is None
