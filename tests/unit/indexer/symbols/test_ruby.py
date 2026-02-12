"""Tests for Ruby symbol extraction."""

from cocosearch.indexer.symbols import extract_symbol_metadata


class TestRubySymbols:
    """Test Ruby symbol extraction."""

    def test_simple_class(self):
        """Extract simple Ruby class."""
        code = "class User\nend"
        result = extract_symbol_metadata(code, "rb")

        assert result.symbol_type == "class"
        assert result.symbol_name == "User"
        assert result.symbol_signature == "class User"

    def test_module_declaration(self):
        """Extract module declaration (mapped to class)."""
        code = "module Authentication\nend"
        result = extract_symbol_metadata(code, "rb")

        assert result.symbol_type == "class"
        assert result.symbol_name == "Authentication"
        assert result.symbol_signature == "module Authentication"

    def test_instance_method(self):
        """Extract instance method from class."""
        code = """class User
  def save
    puts "saving"
  end
end"""
        result = extract_symbol_metadata(code, "rb")

        # First symbol is the class
        assert result.symbol_type == "class"
        assert result.symbol_name == "User"

    def test_singleton_method(self):
        """Extract singleton (class) method."""
        code = """class User
  def self.find(id)
    puts id
  end
end"""
        result = extract_symbol_metadata(code, "rb")

        assert result.symbol_type == "class"
        assert result.symbol_name == "User"

    def test_empty_input(self):
        """Empty Ruby returns NULL fields."""
        result = extract_symbol_metadata("", "rb")

        assert result.symbol_type is None
