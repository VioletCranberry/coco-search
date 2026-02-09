"""Unit tests for hybrid search module."""

from unittest.mock import patch

from cocosearch.search.hybrid import (
    KeywordResult,
    VectorResult,
    HybridSearchResult,
    rrf_fusion,
    execute_keyword_search,
    hybrid_search,
)


class TestRRFFusion:
    """Tests for RRF fusion algorithm."""

    def test_rrf_fusion_single_source_vector_only(self):
        """Test RRF with only vector results."""
        vector_results = [
            VectorResult("/path/file1.py", 0, 100, 0.95),
            VectorResult("/path/file2.py", 0, 100, 0.85),
        ]
        keyword_results = []

        fused = rrf_fusion(vector_results, keyword_results, k=60)

        assert len(fused) == 2
        assert fused[0].match_type == "semantic"
        assert fused[0].vector_score == 0.95
        assert fused[0].keyword_score is None
        assert fused[1].match_type == "semantic"

    def test_rrf_fusion_single_source_keyword_only(self):
        """Test RRF with only keyword results."""
        vector_results = []
        keyword_results = [
            KeywordResult("/path/file1.py", 0, 100, 0.8),
            KeywordResult("/path/file2.py", 0, 100, 0.6),
        ]

        fused = rrf_fusion(vector_results, keyword_results, k=60)

        assert len(fused) == 2
        assert fused[0].match_type == "keyword"
        assert fused[0].vector_score is None
        assert fused[0].keyword_score == 0.8
        assert fused[1].match_type == "keyword"

    def test_rrf_fusion_combined_results(self):
        """Test RRF combining both sources with no overlap."""
        vector_results = [
            VectorResult("/path/vector1.py", 0, 100, 0.95),
        ]
        keyword_results = [
            KeywordResult("/path/keyword1.py", 0, 100, 0.8),
        ]

        fused = rrf_fusion(vector_results, keyword_results, k=60)

        assert len(fused) == 2
        # Both should have same RRF score (rank 1 from their list)
        assert fused[0].combined_score == fused[1].combined_score
        # One semantic, one keyword
        match_types = {r.match_type for r in fused}
        assert match_types == {"semantic", "keyword"}

    def test_rrf_double_match_ranks_higher(self):
        """Test that results found by both methods rank higher."""
        # Same file appears in both results
        vector_results = [
            VectorResult("/path/double_match.py", 0, 100, 0.90),
            VectorResult(
                "/path/vector_only.py", 0, 100, 0.95
            ),  # Higher score but vector-only
        ]
        keyword_results = [
            KeywordResult("/path/double_match.py", 0, 100, 0.7),
            KeywordResult("/path/keyword_only.py", 0, 100, 0.85),
        ]

        fused = rrf_fusion(vector_results, keyword_results, k=60)

        # Double match should be first despite lower individual scores
        assert fused[0].filename == "/path/double_match.py"
        assert fused[0].match_type == "both"
        assert fused[0].vector_score == 0.90
        assert fused[0].keyword_score == 0.7

        # Its RRF score should be sum of both contributions
        # Rank 1 from vector (1/61) + Rank 1 from keyword (1/61) = 2/61
        expected_score = 1 / (60 + 1) + 1 / (60 + 1)
        assert abs(fused[0].combined_score - expected_score) < 0.0001

    def test_rrf_match_type_semantic_only(self):
        """Test match_type is 'semantic' for vector-only results."""
        vector_results = [
            VectorResult("/path/file.py", 0, 100, 0.9),
        ]
        keyword_results = []

        fused = rrf_fusion(vector_results, keyword_results, k=60)

        assert len(fused) == 1
        assert fused[0].match_type == "semantic"

    def test_rrf_match_type_keyword_only(self):
        """Test match_type is 'keyword' for keyword-only results."""
        vector_results = []
        keyword_results = [
            KeywordResult("/path/file.py", 0, 100, 0.8),
        ]

        fused = rrf_fusion(vector_results, keyword_results, k=60)

        assert len(fused) == 1
        assert fused[0].match_type == "keyword"

    def test_rrf_match_type_both(self):
        """Test match_type is 'both' for double-matched results."""
        vector_results = [
            VectorResult("/path/file.py", 0, 100, 0.9),
        ]
        keyword_results = [
            KeywordResult("/path/file.py", 0, 100, 0.8),
        ]

        fused = rrf_fusion(vector_results, keyword_results, k=60)

        assert len(fused) == 1
        assert fused[0].match_type == "both"
        assert fused[0].vector_score == 0.9
        assert fused[0].keyword_score == 0.8

    def test_rrf_preserves_metadata_from_vector(self):
        """Test that metadata (block_type, hierarchy, language_id) is preserved."""
        vector_results = [
            VectorResult(
                "/path/file.py",
                0,
                100,
                0.9,
                block_type="function",
                hierarchy="module.MyClass.my_method",
                language_id="python",
            ),
        ]
        keyword_results = []

        fused = rrf_fusion(vector_results, keyword_results, k=60)

        assert fused[0].block_type == "function"
        assert fused[0].hierarchy == "module.MyClass.my_method"
        assert fused[0].language_id == "python"

    def test_rrf_empty_inputs(self):
        """Test RRF with empty inputs."""
        fused = rrf_fusion([], [], k=60)
        assert fused == []

    def test_rrf_k_parameter_affects_scores(self):
        """Test that k parameter affects score calculation."""
        vector_results = [
            VectorResult("/path/file.py", 0, 100, 0.9),
        ]

        fused_k60 = rrf_fusion(vector_results, [], k=60)
        fused_k1 = rrf_fusion(vector_results, [], k=1)

        # Lower k means higher score for same rank
        assert fused_k1[0].combined_score > fused_k60[0].combined_score

    def test_rrf_tiebreak_favors_keyword(self):
        """Test that keyword matches are favored on score tie."""
        # Create two results with identical RRF scores
        vector_results = [
            VectorResult("/path/semantic.py", 0, 100, 0.9),
        ]
        keyword_results = [
            KeywordResult("/path/keyword.py", 0, 100, 0.8),
        ]

        fused = rrf_fusion(vector_results, keyword_results, k=60)

        # Both have same RRF score (1/(60+1) each)
        # Keyword should be favored
        assert fused[0].filename == "/path/keyword.py"
        assert fused[0].match_type == "keyword"


class TestExecuteKeywordSearch:
    """Tests for execute_keyword_search function."""

    def test_keyword_search_uses_plainto_tsquery(self, mock_db_pool):
        """Test that keyword search uses plainto_tsquery for query building."""
        pool, cursor, conn = mock_db_pool(
            results=[
                ("/path/file.py", 0, 100, 0.5),
            ]
        )

        with patch("cocosearch.search.hybrid.get_connection_pool", return_value=pool):
            with patch(
                "cocosearch.search.hybrid.check_column_exists", return_value=True
            ):
                execute_keyword_search("getUserById", "test_table")

        # Verify tsquery was used
        cursor.assert_query_contains("plainto_tsquery")
        cursor.assert_query_contains("'simple'")

    def test_keyword_search_returns_empty_when_column_missing(self, mock_db_pool):
        """Test graceful degradation when content_tsv column doesn't exist."""
        pool, cursor, conn = mock_db_pool(results=[])

        with patch("cocosearch.search.hybrid.get_connection_pool", return_value=pool):
            with patch(
                "cocosearch.search.hybrid.check_column_exists", return_value=False
            ):
                results = execute_keyword_search("test query", "test_table")

        assert results == []

    def test_keyword_search_normalizes_query(self, mock_db_pool):
        """Test that query is normalized to split identifiers."""
        pool, cursor, conn = mock_db_pool(results=[])

        with patch("cocosearch.search.hybrid.get_connection_pool", return_value=pool):
            with patch(
                "cocosearch.search.hybrid.check_column_exists", return_value=True
            ):
                execute_keyword_search("getUserById", "test_table")

        # The normalized query should include split tokens
        # Check that parameters were passed (normalized query appears twice)
        assert len(cursor.calls) > 0
        query, params = cursor.calls[0]
        # Normalized query should be in params
        assert params is not None
        # At least one param should contain "get" (from split)
        assert any("get" in str(p).lower() for p in params if isinstance(p, str))


class TestHybridSearch:
    """Tests for hybrid_search function."""

    def test_hybrid_search_returns_semantic_only_when_no_keywords(self, mock_db_pool):
        """Test fallback to semantic-only when keyword search returns nothing."""
        vector_results = [
            ("/path/file.py", 0, 100, 0.9, "function", "main", "python"),
        ]
        pool, cursor, conn = mock_db_pool(results=vector_results)

        with patch("cocosearch.search.hybrid.get_connection_pool", return_value=pool):
            with patch("cocosearch.search.db.get_connection_pool", return_value=pool):
                with patch(
                    "cocosearch.search.hybrid.get_table_name", return_value="test_table"
                ):
                    with patch(
                        "cocosearch.search.hybrid.check_column_exists",
                        return_value=False,
                    ):
                        with patch(
                            "cocosearch.search.hybrid.code_to_embedding"
                        ) as mock_embed:
                            mock_embed.eval.return_value = [0.1] * 1024
                            results = hybrid_search("test query", "test_index")

        assert len(results) == 1
        assert results[0].match_type == "semantic"
        assert results[0].vector_score == 0.9
        assert results[0].keyword_score is None

    def test_hybrid_search_fuses_when_both_available(self, mock_db_pool):
        """Test that hybrid search fuses results when both are available."""
        # Setup mock to return different results for vector and keyword queries
        call_count = [0]
        vector_results = [
            ("/path/vector.py", 0, 100, 0.9, "function", "main", "python"),
        ]
        keyword_results = [
            ("/path/keyword.py", 0, 100, 0.5),
        ]

        def mock_fetchall():
            call_count[0] += 1
            if call_count[0] == 1:
                return vector_results
            return keyword_results

        pool, cursor, conn = mock_db_pool(results=[])
        cursor.fetchall = mock_fetchall

        with patch("cocosearch.search.hybrid.get_connection_pool", return_value=pool):
            with patch("cocosearch.search.db.get_connection_pool", return_value=pool):
                with patch(
                    "cocosearch.search.hybrid.get_table_name", return_value="test_table"
                ):
                    with patch(
                        "cocosearch.search.hybrid.check_column_exists",
                        return_value=True,
                    ):
                        with patch(
                            "cocosearch.search.hybrid.code_to_embedding"
                        ) as mock_embed:
                            mock_embed.eval.return_value = [0.1] * 1024
                            results = hybrid_search("getUserById", "test_index")

        # Should have results from both sources
        assert len(results) >= 1

    def test_hybrid_search_respects_limit(self, mock_db_pool):
        """Test that hybrid search respects the limit parameter."""
        # Create many results
        vector_results = [
            (f"/path/file{i}.py", i * 100, (i + 1) * 100, 0.9 - i * 0.05, "", "", "")
            for i in range(20)
        ]
        pool, cursor, conn = mock_db_pool(results=vector_results)

        with patch("cocosearch.search.hybrid.get_connection_pool", return_value=pool):
            with patch("cocosearch.search.db.get_connection_pool", return_value=pool):
                with patch(
                    "cocosearch.search.hybrid.get_table_name", return_value="test_table"
                ):
                    with patch(
                        "cocosearch.search.hybrid.check_column_exists",
                        return_value=False,
                    ):
                        with patch(
                            "cocosearch.search.hybrid.code_to_embedding"
                        ) as mock_embed:
                            mock_embed.eval.return_value = [0.1] * 1024
                            results = hybrid_search("test", "test_index", limit=5)

        assert len(results) <= 5


class TestHybridSearchResult:
    """Tests for HybridSearchResult dataclass."""

    def test_hybrid_result_has_all_fields(self):
        """Test that HybridSearchResult has all required fields."""
        result = HybridSearchResult(
            filename="/path/file.py",
            start_byte=0,
            end_byte=100,
            combined_score=0.5,
            match_type="both",
            vector_score=0.9,
            keyword_score=0.4,
            block_type="function",
            hierarchy="module.func",
            language_id="python",
        )

        assert result.filename == "/path/file.py"
        assert result.start_byte == 0
        assert result.end_byte == 100
        assert result.combined_score == 0.5
        assert result.match_type == "both"
        assert result.vector_score == 0.9
        assert result.keyword_score == 0.4
        assert result.block_type == "function"
        assert result.hierarchy == "module.func"
        assert result.language_id == "python"

    def test_hybrid_result_optional_scores(self):
        """Test that vector_score and keyword_score can be None."""
        result = HybridSearchResult(
            filename="/path/file.py",
            start_byte=0,
            end_byte=100,
            combined_score=0.5,
            match_type="semantic",
            vector_score=0.9,
            keyword_score=None,
        )

        assert result.vector_score == 0.9
        assert result.keyword_score is None
