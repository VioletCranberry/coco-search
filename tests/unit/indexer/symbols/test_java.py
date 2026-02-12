"""Tests for Java symbol extraction."""

from cocosearch.indexer.symbols import extract_symbol_metadata


class TestJavaSymbols:
    """Test Java symbol extraction."""

    def test_simple_class(self):
        """Extract simple Java class."""
        code = "class User { }"
        result = extract_symbol_metadata(code, "java")

        assert result.symbol_type == "class"
        assert result.symbol_name == "User"
        assert result.symbol_signature == "class User"

    def test_interface_declaration(self):
        """Extract interface declaration."""
        code = "interface Repository { void save(); }"
        result = extract_symbol_metadata(code, "java")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Repository"
        assert result.symbol_signature == "interface Repository"

    def test_enum_declaration(self):
        """Extract enum declaration (mapped to class)."""
        code = "enum Status { ACTIVE, INACTIVE, PENDING }"
        result = extract_symbol_metadata(code, "java")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Status"
        assert result.symbol_signature == "enum Status"

    def test_method_in_class(self):
        """Extract method from class."""
        code = """class UserService {
    public User findById(int id) {
        return null;
    }
}"""
        result = extract_symbol_metadata(code, "java")

        # First symbol is the class
        assert result.symbol_type == "class"
        assert result.symbol_name == "UserService"

    def test_constructor(self):
        """Extract constructor (mapped to method)."""
        code = """class User {
    public User(String name) {
        this.name = name;
    }
}"""
        result = extract_symbol_metadata(code, "java")

        assert result.symbol_type == "class"
        assert result.symbol_name == "User"

    def test_empty_input(self):
        """Empty Java returns NULL fields."""
        result = extract_symbol_metadata("", "java")

        assert result.symbol_type is None
