"""Tests for hybrid search definition boost functionality."""

from cocosearch.search.hybrid import (
    HybridSearchResult,
    apply_definition_boost,
)


class TestApplyDefinitionBoost:
    """Tests for apply_definition_boost function."""

    def test_empty_results(self, mocker):
        """Empty results list returns empty."""
        result = apply_definition_boost([], "test_index")
        assert result == []

    def test_multiplies_definition_score(self, mocker):
        """Definition chunks (symbol_type set) get 2x score boost."""
        mocker.patch(
            "cocosearch.search.hybrid.check_symbol_columns_exist",
            return_value=True,
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
                symbol_type="function",
            )
        ]

        boosted = apply_definition_boost(results, "test_index")
        assert boosted[0].combined_score == 1.0  # 0.5 * 2.0

    def test_non_definition_unchanged(self, mocker):
        """Non-definition chunks (symbol_type=None) keep original score."""
        mocker.patch(
            "cocosearch.search.hybrid.check_symbol_columns_exist",
            return_value=True,
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
            "cocosearch.search.hybrid.check_symbol_columns_exist",
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
                symbol_type="function",
            )
        ]

        boosted = apply_definition_boost(results, "test_index")
        assert boosted[0].combined_score == 0.5  # Unchanged

    def test_resorts_after_boost(self, mocker):
        """Results are re-sorted after boost application."""
        mocker.patch(
            "cocosearch.search.hybrid.check_symbol_columns_exist",
            return_value=True,
        )

        results = [
            # First: non-definition with higher initial score
            HybridSearchResult(
                filename="test.py",
                start_byte=0,
                end_byte=50,
                combined_score=0.6,
                match_type="semantic",
                vector_score=0.6,
                keyword_score=None,
            ),
            # Second: definition with lower initial score
            HybridSearchResult(
                filename="test.py",
                start_byte=50,
                end_byte=100,
                combined_score=0.4,
                match_type="semantic",
                vector_score=0.4,
                keyword_score=None,
                symbol_type="function",
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
            "cocosearch.search.hybrid.check_symbol_columns_exist",
            return_value=True,
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
                symbol_type="class",
            )
        ]

        # Use 3x boost
        boosted = apply_definition_boost(results, "test_index", boost_multiplier=3.0)
        assert boosted[0].combined_score == 1.5  # 0.5 * 3.0

    def test_preserves_all_fields(self, mocker):
        """All HybridSearchResult fields are preserved after boost."""
        mocker.patch(
            "cocosearch.search.hybrid.check_symbol_columns_exist",
            return_value=True,
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
                symbol_type="method",
                symbol_name="Foo.bar",
                symbol_signature="def bar(self, x: int) -> str",
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
        assert result.symbol_type == "method"
        assert result.symbol_name == "Foo.bar"
        assert result.symbol_signature == "def bar(self, x: int) -> str"
