"""Tests for TypeScript symbol extraction."""

from cocosearch.indexer.symbols import extract_symbol_metadata


class TestTypeScriptSymbols:
    """Test TypeScript symbol extraction."""

    def test_function_declaration(self):
        """Extract TypeScript function declaration."""
        code = "function fetchUser(id: number): User { return null; }"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "function"
        assert result.symbol_name == "fetchUser"
        assert "function fetchUser" in result.symbol_signature

    def test_arrow_function_typed(self):
        """Extract typed arrow function."""
        code = "const fetchData = (url: string): Promise<Data> => fetch(url);"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "function"
        assert result.symbol_name == "fetchData"

    def test_interface_declaration(self):
        """Extract interface declaration."""
        code = "interface User { name: string; age: number; }"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "User"
        assert result.symbol_signature == "interface User"

    def test_interface_extends(self):
        """Extract interface that extends another."""
        code = "interface Admin extends User { role: string; }"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Admin"

    def test_type_alias_simple(self):
        """Extract simple type alias (mapped to interface)."""
        code = "type UserID = string;"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "UserID"
        assert result.symbol_signature == "type UserID = string;"

    def test_type_alias_union(self):
        """Extract union type alias."""
        code = "type Status = 'active' | 'inactive' | 'pending';"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Status"

    def test_type_alias_object(self):
        """Extract object type alias."""
        code = "type UserConfig = { theme: string; language: string; };"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "UserConfig"

    def test_class_declaration(self):
        """Extract TypeScript class."""
        code = "class UserService { private users: User[] = []; }"
        result = extract_symbol_metadata(code, "ts")

        assert result.symbol_type == "class"
        assert result.symbol_name == "UserService"

    def test_tsx_extension(self):
        """TSX files use TypeScript extractor."""
        code = "interface Props { title: string; }"
        result = extract_symbol_metadata(code, "tsx")

        assert result.symbol_type == "interface"
        assert result.symbol_name == "Props"

    def test_empty_input(self):
        """Empty TypeScript returns NULL fields."""
        result = extract_symbol_metadata("", "ts")

        assert result.symbol_type is None
