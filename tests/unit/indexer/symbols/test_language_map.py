"""Tests for language extension mapping."""

from cocosearch.indexer.symbols import LANGUAGE_MAP


class TestLanguageMap:
    """Test language extension mapping."""

    def test_language_map_count(self):
        """LANGUAGE_MAP contains all 34 extension mappings."""
        assert len(LANGUAGE_MAP) == 34

    def test_javascript_extensions(self):
        """JavaScript extensions map correctly."""
        assert LANGUAGE_MAP["js"] == "javascript"
        assert LANGUAGE_MAP["jsx"] == "javascript"
        assert LANGUAGE_MAP["mjs"] == "javascript"
        assert LANGUAGE_MAP["cjs"] == "javascript"

    def test_typescript_extensions(self):
        """TypeScript extensions map correctly."""
        assert LANGUAGE_MAP["ts"] == "typescript"
        assert LANGUAGE_MAP["tsx"] == "typescript"
        assert LANGUAGE_MAP["mts"] == "typescript"
        assert LANGUAGE_MAP["cts"] == "typescript"

    def test_other_extensions(self):
        """Other language extensions map correctly."""
        assert LANGUAGE_MAP["go"] == "go"
        assert LANGUAGE_MAP["rs"] == "rust"
        assert LANGUAGE_MAP["py"] == "python"
        assert LANGUAGE_MAP["python"] == "python"
        assert LANGUAGE_MAP["java"] == "java"

    def test_c_extensions(self):
        """C extensions map correctly."""
        assert LANGUAGE_MAP["c"] == "c"
        assert LANGUAGE_MAP["h"] == "c"

    def test_cpp_extensions(self):
        """C++ extensions map correctly."""
        assert LANGUAGE_MAP["cpp"] == "cpp"
        assert LANGUAGE_MAP["cxx"] == "cpp"
        assert LANGUAGE_MAP["cc"] == "cpp"
        assert LANGUAGE_MAP["hpp"] == "cpp"
        assert LANGUAGE_MAP["hxx"] == "cpp"
        assert LANGUAGE_MAP["hh"] == "cpp"

    def test_ruby_extension(self):
        """Ruby extension maps correctly."""
        assert LANGUAGE_MAP["rb"] == "ruby"

    def test_php_extension(self):
        """PHP extension maps correctly."""
        assert LANGUAGE_MAP["php"] == "php"

    def test_hcl_extensions(self):
        """HCL/Terraform extensions map correctly."""
        assert LANGUAGE_MAP["tf"] == "terraform"
        assert LANGUAGE_MAP["hcl"] == "hcl"
        assert LANGUAGE_MAP["tfvars"] == "hcl"

    def test_bash_extensions(self):
        """Bash extensions map correctly."""
        assert LANGUAGE_MAP["sh"] == "bash"
        assert LANGUAGE_MAP["bash"] == "bash"
        assert LANGUAGE_MAP["zsh"] == "bash"

    def test_scala_extension(self):
        """Scala extension maps correctly."""
        assert LANGUAGE_MAP["scala"] == "scala"

    def test_css_extensions(self):
        """CSS extensions map correctly."""
        assert LANGUAGE_MAP["css"] == "css"
        assert LANGUAGE_MAP["scss"] == "css"

    def test_unsupported_extension(self):
        """Unsupported extension returns None."""
        assert LANGUAGE_MAP.get("swift") is None
        assert LANGUAGE_MAP.get("kt") is None
