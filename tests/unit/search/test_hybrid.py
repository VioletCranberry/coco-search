"""Tests for hybrid search definition boost functionality."""

from cocosearch.search.hybrid import (
    HybridSearchResult,
    _is_definition_chunk,
    apply_definition_boost,
)


class TestIsDefinitionChunk:
    """Tests for _is_definition_chunk heuristic."""

    def test_python_def(self):
        """Python def detected as definition."""
        assert _is_definition_chunk("def foo():\n    pass") is True

    def test_python_class(self):
        """Python class detected as definition."""
        assert _is_definition_chunk("class Foo:\n    pass") is True

    def test_python_async_def(self):
        """Python async def detected as definition."""
        assert _is_definition_chunk("async def fetch():\n    pass") is True

    def test_js_function(self):
        """JavaScript function detected as definition."""
        assert _is_definition_chunk("function fetchUser() {}") is True

    def test_js_const(self):
        """JavaScript const detected as definition."""
        assert _is_definition_chunk("const handler = () => {}") is True

    def test_js_let(self):
        """JavaScript let detected as definition."""
        assert _is_definition_chunk("let counter = 0") is True

    def test_js_var(self):
        """JavaScript var detected as definition."""
        assert _is_definition_chunk("var name = 'test'") is True

    def test_ts_interface(self):
        """TypeScript interface detected as definition."""
        assert _is_definition_chunk("interface User {\n  name: string\n}") is True

    def test_ts_type(self):
        """TypeScript type alias detected as definition."""
        assert _is_definition_chunk("type Status = 'active' | 'inactive'") is True

    def test_go_func(self):
        """Go func detected as definition."""
        assert _is_definition_chunk("func main() {\n}") is True

    def test_go_type(self):
        """Go type detected as definition."""
        assert _is_definition_chunk("type User struct {\n}") is True

    def test_rust_fn(self):
        """Rust fn detected as definition."""
        assert _is_definition_chunk("fn process() -> Result<()>") is True

    def test_rust_struct(self):
        """Rust struct detected as definition."""
        assert _is_definition_chunk("struct Config {\n    name: String\n}") is True

    def test_rust_trait(self):
        """Rust trait detected as definition."""
        assert _is_definition_chunk("trait Handler {\n}") is True

    def test_rust_enum(self):
        """Rust enum detected as definition."""
        assert _is_definition_chunk("enum Status {\n    Active\n}") is True

    def test_rust_impl(self):
        """Rust impl detected as definition."""
        assert _is_definition_chunk("impl User {\n}") is True

    def test_with_leading_whitespace(self):
        """Indented definition detected (lstrip handles indent)."""
        assert _is_definition_chunk("    def indented():\n        pass") is True
        assert _is_definition_chunk("\t\tclass Tabbed:\n\t\tpass") is True

    def test_not_definition_assignment(self):
        """Variable assignment not detected as definition."""
        assert _is_definition_chunk("x = foo()") is False

    def test_not_definition_comment(self):
        """Comment not detected as definition."""
        assert _is_definition_chunk("// comment") is False
        assert _is_definition_chunk("# comment") is False

    def test_not_definition_return(self):
        """Return statement not detected as definition."""
        assert _is_definition_chunk("return result") is False

    def test_not_definition_import(self):
        """Import statement not detected as definition."""
        assert _is_definition_chunk("import foo") is False
        assert _is_definition_chunk("from bar import baz") is False

    def test_not_definition_call(self):
        """Function call not detected as definition."""
        assert _is_definition_chunk("process()") is False
        assert _is_definition_chunk("foo.bar()") is False

    def test_empty_string(self):
        """Empty string not detected as definition."""
        assert _is_definition_chunk("") is False

    def test_whitespace_only(self):
        """Whitespace-only not detected as definition."""
        assert _is_definition_chunk("   \n\t  ") is False


class TestApplyDefinitionBoost:
    """Tests for apply_definition_boost function."""

    def test_empty_results(self, mocker):
        """Empty results list returns empty."""
        result = apply_definition_boost([], "test_index")
        assert result == []

    def test_multiplies_definition_score(self, mocker):
        """Definition chunks get 2x score boost."""
        # Patch at source locations (local imports in apply_definition_boost)
        mocker.patch(
            "cocosearch.search.db.check_symbol_columns_exist",
            return_value=True,
        )
        mocker.patch(
            "cocosearch.search.utils.read_chunk_content",
            return_value="def foo():\n    pass",
        )

        results = [
            HybridSearchResult(
                filename="test.py",
                start_byte=0,
                end_byte=100,
                combined_score=0.5,
                match_type="both",
                vector_score=0.6,
                keyword_score=0.4,
            )
        ]

        boosted = apply_definition_boost(results, "test_index")
        assert boosted[0].combined_score == 1.0  # 0.5 * 2.0

    def test_non_definition_unchanged(self, mocker):
        """Non-definition chunks keep original score."""
        mocker.patch(
            "cocosearch.search.db.check_symbol_columns_exist",
            return_value=True,
        )
        mocker.patch(
            "cocosearch.search.utils.read_chunk_content",
            return_value="x = foo()",  # Not a definition
        )

        results = [
            HybridSearchResult(
                filename="test.py",
                start_byte=0,
                end_byte=100,
                combined_score=0.5,
                match_type="semantic",
                vector_score=0.5,
                keyword_score=None,
            )
        ]

        boosted = apply_definition_boost(results, "test_index")
        assert boosted[0].combined_score == 0.5  # Unchanged

    def test_skips_pre_v17_index(self, mocker):
        """Boost skipped when symbol columns don't exist."""
        mocker.patch(
            "cocosearch.search.db.check_symbol_columns_exist",
            return_value=False,
        )

        results = [
            HybridSearchResult(
                filename="test.py",
                start_byte=0,
                end_byte=100,
                combined_score=0.5,
                match_type="both",
                vector_score=0.6,
                keyword_score=0.4,
            )
        ]

        boosted = apply_definition_boost(results, "test_index")
        assert boosted[0].combined_score == 0.5  # Unchanged

    def test_resorts_after_boost(self, mocker):
        """Results are re-sorted after boost application."""
        mocker.patch(
            "cocosearch.search.db.check_symbol_columns_exist",
            return_value=True,
        )

        # First result: non-definition with higher initial score
        # Second result: definition with lower initial score
        def mock_read_chunk(filename, start_byte, end_byte):
            if start_byte == 0:
                return "x = foo()"  # Not definition
            else:
                return "def bar():"  # Definition

        mocker.patch(
            "cocosearch.search.utils.read_chunk_content",
            side_effect=mock_read_chunk,
        )

        results = [
            HybridSearchResult(
                filename="test.py",
                start_byte=0,
                end_byte=50,
                combined_score=0.6,
                match_type="semantic",
                vector_score=0.6,
                keyword_score=None,
            ),
            HybridSearchResult(
                filename="test.py",
                start_byte=50,
                end_byte=100,
                combined_score=0.4,
                match_type="semantic",
                vector_score=0.4,
                keyword_score=None,
            ),
        ]

        boosted = apply_definition_boost(results, "test_index")

        # Definition (0.4 * 2.0 = 0.8) should now be first
        assert boosted[0].combined_score == 0.8
        assert boosted[0].start_byte == 50  # The definition chunk
        # Non-definition (0.6) should now be second
        assert boosted[1].combined_score == 0.6
        assert boosted[1].start_byte == 0  # The non-definition chunk

    def test_custom_boost_multiplier(self, mocker):
        """Custom boost multiplier is applied."""
        mocker.patch(
            "cocosearch.search.db.check_symbol_columns_exist",
            return_value=True,
        )
        mocker.patch(
            "cocosearch.search.utils.read_chunk_content",
            return_value="class Foo:",
        )

        results = [
            HybridSearchResult(
                filename="test.py",
                start_byte=0,
                end_byte=100,
                combined_score=0.5,
                match_type="semantic",
                vector_score=0.5,
                keyword_score=None,
            )
        ]

        # Use 3x boost
        boosted = apply_definition_boost(results, "test_index", boost_multiplier=3.0)
        assert boosted[0].combined_score == 1.5  # 0.5 * 3.0

    def test_handles_read_error_gracefully(self, mocker):
        """Read errors don't boost (graceful degradation)."""
        mocker.patch(
            "cocosearch.search.db.check_symbol_columns_exist",
            return_value=True,
        )
        # Simulate file read error
        mocker.patch(
            "cocosearch.search.utils.read_chunk_content",
            side_effect=Exception("File not found"),
        )

        results = [
            HybridSearchResult(
                filename="test.py",
                start_byte=0,
                end_byte=100,
                combined_score=0.5,
                match_type="semantic",
                vector_score=0.5,
                keyword_score=None,
            )
        ]

        boosted = apply_definition_boost(results, "test_index")
        # Score unchanged due to read error
        assert boosted[0].combined_score == 0.5

    def test_preserves_all_fields(self, mocker):
        """All HybridSearchResult fields are preserved after boost."""
        mocker.patch(
            "cocosearch.search.db.check_symbol_columns_exist",
            return_value=True,
        )
        mocker.patch(
            "cocosearch.search.utils.read_chunk_content",
            return_value="def foo():",
        )

        results = [
            HybridSearchResult(
                filename="path/to/file.py",
                start_byte=100,
                end_byte=200,
                combined_score=0.5,
                match_type="both",
                vector_score=0.6,
                keyword_score=0.4,
                block_type="function",
                hierarchy="module.Foo.bar",
                language_id="python",
            )
        ]

        boosted = apply_definition_boost(results, "test_index")
        result = boosted[0]

        assert result.filename == "path/to/file.py"
        assert result.start_byte == 100
        assert result.end_byte == 200
        assert result.combined_score == 1.0  # Boosted
        assert result.match_type == "both"
        assert result.vector_score == 0.6
        assert result.keyword_score == 0.4
        assert result.block_type == "function"
        assert result.hierarchy == "module.Foo.bar"
        assert result.language_id == "python"
