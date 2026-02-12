"""Tests for Bash symbol extraction."""

from cocosearch.indexer.symbols import extract_symbol_metadata


class TestBashSymbols:
    """Test Bash symbol extraction."""

    def test_posix_function(self):
        """POSIX style: name() { ... }"""
        code = "my_function() {\n    echo hello\n}"
        result = extract_symbol_metadata(code, "sh")

        assert result.symbol_type == "function"
        assert result.symbol_name == "my_function"

    def test_ksh_function(self):
        """ksh style: function name { ... }"""
        code = "function deploy {\n    echo deploying\n}"
        result = extract_symbol_metadata(code, "bash")

        assert result.symbol_type == "function"
        assert result.symbol_name == "deploy"

    def test_hybrid_function(self):
        """Hybrid style: function name() { ... }"""
        code = "function setup() {\n    echo setup\n}"
        result = extract_symbol_metadata(code, "zsh")

        assert result.symbol_type == "function"
        assert result.symbol_name == "setup"

    def test_non_function_code(self):
        """Non-function code returns None fields."""
        code = "echo hello world\nls -la"
        result = extract_symbol_metadata(code, "sh")

        assert result.symbol_type is None
        assert result.symbol_name is None

    def test_function_with_body(self):
        """Function with multiline body."""
        code = "cleanup() {\n    rm -rf /tmp/build\n    echo done\n}"
        result = extract_symbol_metadata(code, "sh")

        assert result.symbol_type == "function"
        assert result.symbol_name == "cleanup"
        assert "cleanup()" in result.symbol_signature
