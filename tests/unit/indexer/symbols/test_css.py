"""Tests for CSS symbol extraction."""

from cocosearch.indexer.symbols import extract_symbol_metadata


class TestCSSSymbols:
    """Test CSS symbol extraction."""

    def test_class_selector(self):
        """Class selector: .header { ... }"""
        code = ".header {\n    color: red;\n}"
        result = extract_symbol_metadata(code, "css")

        assert result.symbol_type == "class"
        assert result.symbol_name == "header"
        assert ".header" in result.symbol_signature

    def test_id_selector(self):
        """ID selector: #main { ... }"""
        code = "#main {\n    display: flex;\n}"
        result = extract_symbol_metadata(code, "css")

        assert result.symbol_type == "class"
        assert result.symbol_name == "main"
        assert "#main" in result.symbol_signature

    def test_element_selector(self):
        """Element selector: body { ... }"""
        code = "body {\n    margin: 0;\n}"
        result = extract_symbol_metadata(code, "css")

        assert result.symbol_type == "class"
        assert result.symbol_name == "body"
        assert "body" in result.symbol_signature

    def test_keyframes(self):
        """@keyframes animation."""
        code = (
            "@keyframes fadeIn {\n    from { opacity: 0; }\n    to { opacity: 1; }\n}"
        )
        result = extract_symbol_metadata(code, "css")

        assert result.symbol_type == "function"
        assert result.symbol_name == "fadeIn"
        assert "@keyframes fadeIn" in result.symbol_signature

    def test_media_query(self):
        """@media query."""
        code = "@media (max-width: 768px) {\n    .mobile { display: block; }\n}"
        result = extract_symbol_metadata(code, "css")

        assert result.symbol_type == "class"
        assert "max-width" in result.symbol_name
        assert "@media" in result.symbol_signature

    def test_scss_extension(self):
        """SCSS files use CSS grammar via scss extension."""
        code = ".container {\n    padding: 10px;\n}"
        result = extract_symbol_metadata(code, "scss")

        assert result.symbol_type == "class"
        assert result.symbol_name == "container"

    def test_non_symbol_css(self):
        """Property declarations alone return None fields."""
        code = "color: red;\nfont-size: 14px;"
        result = extract_symbol_metadata(code, "css")

        assert result.symbol_type is None
        assert result.symbol_name is None
