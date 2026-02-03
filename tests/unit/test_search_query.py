"""Tests for search query graceful degradation behavior.

Tests hybrid search column detection and backward compatibility
for pre-v1.7 indexes that lack content_text column.
"""

import pytest
from unittest.mock import patch


class TestCheckColumnExists:
    """Tests for check_column_exists helper function."""

    def test_check_column_exists_detects_missing_column(self, mock_db_pool):
        """Test that check_column_exists returns False for missing columns."""
        # Mock cursor to return False (column not found)
        pool, cursor, conn = mock_db_pool(results=[(False,)])

        with patch("cocosearch.search.db.get_connection_pool", return_value=pool):
            from cocosearch.search.db import check_column_exists

            result = check_column_exists("test_table", "nonexistent_column")

        assert result is False
        cursor.assert_query_contains("information_schema.columns")

    def test_check_column_exists_detects_existing_column(self, mock_db_pool):
        """Test that check_column_exists returns True for existing columns."""
        pool, cursor, conn = mock_db_pool(results=[(True,)])

        with patch("cocosearch.search.db.get_connection_pool", return_value=pool):
            from cocosearch.search.db import check_column_exists

            result = check_column_exists("test_table", "existing_column")

        assert result is True
        cursor.assert_query_contains("information_schema.columns")

    def test_check_column_exists_passes_table_and_column_names(self, mock_db_pool):
        """Test that check_column_exists passes correct parameters to query."""
        pool, cursor, conn = mock_db_pool(results=[(True,)])

        with patch("cocosearch.search.db.get_connection_pool", return_value=pool):
            from cocosearch.search.db import check_column_exists

            check_column_exists("my_table", "my_column")

        # Verify the parameters were passed
        cursor.assert_called_with_param("my_table")
        cursor.assert_called_with_param("my_column")


class TestHybridSearchGracefulDegradation:
    """Tests for hybrid search column detection and graceful degradation."""

    def test_hybrid_warning_logged_when_content_text_missing(self, mock_db_pool):
        """Test that warning is logged when content_text column is missing."""
        import cocosearch.search.query as query_module

        # Reset module state for test isolation
        query_module._has_content_text_column = True
        query_module._hybrid_warning_emitted = False

        # Mock check_column_exists to return False (no content_text column)
        with patch.object(
            query_module, "check_column_exists", return_value=False
        ) as mock_check:
            with patch.object(query_module, "logger") as mock_logger:
                with patch.object(
                    query_module, "code_to_embedding"
                ) as mock_embedding:
                    mock_embedding.eval.return_value = [0.1] * 1024

                    # Setup mock pool for the search query
                    pool, cursor, conn = mock_db_pool(results=[])
                    with patch.object(
                        query_module, "get_connection_pool", return_value=pool
                    ):
                        with patch.object(
                            query_module,
                            "get_table_name",
                            return_value="test_table",
                        ):
                            # Execute search to trigger hybrid column check
                            query_module.search("test query", "test_index")

                # Verify check_column_exists was called
                mock_check.assert_called_once_with("test_table", "content_text")

                # Verify warning was logged
                mock_logger.warning.assert_called_once()
                warning_msg = mock_logger.warning.call_args[0][0]
                assert "hybrid search" in warning_msg.lower()
                assert "content_text" in warning_msg

        # Verify flag was set
        assert query_module._has_content_text_column is False
        assert query_module._hybrid_warning_emitted is True

    def test_hybrid_warning_logged_only_once(self, mock_db_pool):
        """Test that hybrid warning is logged only once per session."""
        import cocosearch.search.query as query_module

        # Start with warning already emitted
        query_module._has_content_text_column = False
        query_module._hybrid_warning_emitted = True

        with patch.object(
            query_module, "check_column_exists", return_value=False
        ) as mock_check:
            with patch.object(query_module, "logger") as mock_logger:
                with patch.object(
                    query_module, "code_to_embedding"
                ) as mock_embedding:
                    mock_embedding.eval.return_value = [0.1] * 1024

                    pool, cursor, conn = mock_db_pool(results=[])
                    with patch.object(
                        query_module, "get_connection_pool", return_value=pool
                    ):
                        with patch.object(
                            query_module,
                            "get_table_name",
                            return_value="test_table",
                        ):
                            # Execute search multiple times
                            query_module.search("test query", "test_index")
                            query_module.search("another query", "test_index")

                # check_column_exists should not be called when flag already set
                mock_check.assert_not_called()

                # Warning should not be logged again
                mock_logger.warning.assert_not_called()

    def test_no_warning_when_content_text_exists(self, mock_db_pool):
        """Test that no warning is logged when content_text column exists."""
        import cocosearch.search.query as query_module

        # Reset module state
        query_module._has_content_text_column = True
        query_module._hybrid_warning_emitted = False

        # Mock check_column_exists to return True (column exists)
        with patch.object(
            query_module, "check_column_exists", return_value=True
        ) as mock_check:
            with patch.object(query_module, "logger") as mock_logger:
                with patch.object(
                    query_module, "code_to_embedding"
                ) as mock_embedding:
                    mock_embedding.eval.return_value = [0.1] * 1024

                    pool, cursor, conn = mock_db_pool(results=[])
                    with patch.object(
                        query_module, "get_connection_pool", return_value=pool
                    ):
                        with patch.object(
                            query_module,
                            "get_table_name",
                            return_value="test_table",
                        ):
                            query_module.search("test query", "test_index")

                # check_column_exists should be called
                mock_check.assert_called_once()

                # No warning should be logged
                mock_logger.warning.assert_not_called()

        # Flag should remain True
        assert query_module._has_content_text_column is True
        assert query_module._hybrid_warning_emitted is False

    def test_search_continues_when_hybrid_columns_missing(self, mock_db_pool):
        """Test that search works even when content_text column is missing."""
        import cocosearch.search.query as query_module

        # Reset module state
        query_module._has_content_text_column = True
        query_module._hybrid_warning_emitted = False

        # Sample search results (without content_text - pre-v1.7 schema)
        search_results = [
            ("/path/to/file.py", 0, 100, 0.95, "function", "main", "python"),
        ]

        pool, cursor, conn = mock_db_pool(results=search_results)

        with patch.object(query_module, "check_column_exists", return_value=False):
            with patch.object(query_module, "code_to_embedding") as mock_embedding:
                mock_embedding.eval.return_value = [0.1] * 1024
                with patch.object(
                    query_module, "get_connection_pool", return_value=pool
                ):
                    with patch.object(
                        query_module, "get_table_name", return_value="test_table"
                    ):
                        # Should complete without error
                        results = query_module.search("test query", "test_index")

        # Search should return results even though hybrid column is missing
        assert len(results) == 1
        assert results[0].filename == "/path/to/file.py"
        assert results[0].score == 0.95


class TestHybridSearchModes:
    """Tests for hybrid search mode selection (auto/explicit/disabled)."""

    def test_search_auto_hybrid_triggered_by_camelcase(self, mock_db_pool):
        """Test that camelCase queries auto-trigger hybrid search."""
        import cocosearch.search.query as query_module

        # Reset module state
        query_module._has_content_text_column = True
        query_module._hybrid_warning_emitted = False

        # Mock hybrid search results
        from cocosearch.search.hybrid import HybridSearchResult

        mock_hybrid_results = [
            HybridSearchResult(
                filename="/path/to/file.py",
                start_byte=0,
                end_byte=100,
                combined_score=0.9,
                match_type="both",
                vector_score=0.85,
                keyword_score=0.75,
                block_type="function",
                hierarchy="main.getUserById",
                language_id="python",
            )
        ]

        with patch.object(query_module, "check_column_exists", return_value=True):
            with patch.object(
                query_module, "execute_hybrid_search", return_value=mock_hybrid_results
            ) as mock_hybrid:
                with patch.object(
                    query_module, "get_connection_pool"
                ):
                    with patch.object(
                        query_module, "get_table_name", return_value="test_table"
                    ):
                        # camelCase query should trigger hybrid search
                        results = query_module.search("getUserById", "test_index")

                # Hybrid search should have been called (with filter params)
                mock_hybrid.assert_called_once_with(
                    "getUserById",
                    "test_index",
                    10,
                    symbol_type=None,
                    symbol_name=None,
                    language_filter=None,
                )

        # Results should have match_type from hybrid search
        assert len(results) == 1
        assert results[0].match_type == "both"
        assert results[0].vector_score == 0.85
        assert results[0].keyword_score == 0.75

    def test_search_auto_hybrid_triggered_by_snake_case(self, mock_db_pool):
        """Test that snake_case queries auto-trigger hybrid search."""
        import cocosearch.search.query as query_module

        # Reset module state
        query_module._has_content_text_column = True
        query_module._hybrid_warning_emitted = False

        from cocosearch.search.hybrid import HybridSearchResult

        mock_hybrid_results = [
            HybridSearchResult(
                filename="/path/to/file.py",
                start_byte=0,
                end_byte=100,
                combined_score=0.88,
                match_type="keyword",
                vector_score=None,
                keyword_score=0.88,
                block_type="function",
                hierarchy="main.get_user_by_id",
                language_id="python",
            )
        ]

        with patch.object(query_module, "check_column_exists", return_value=True):
            with patch.object(
                query_module, "execute_hybrid_search", return_value=mock_hybrid_results
            ) as mock_hybrid:
                with patch.object(query_module, "get_connection_pool"):
                    with patch.object(
                        query_module, "get_table_name", return_value="test_table"
                    ):
                        # snake_case query should trigger hybrid search
                        results = query_module.search("get_user_by_id", "test_index")

                mock_hybrid.assert_called_once()

        assert len(results) == 1
        assert results[0].match_type == "keyword"

    def test_search_explicit_hybrid_mode(self, mock_db_pool):
        """Test that use_hybrid=True forces hybrid search even for plain queries."""
        import cocosearch.search.query as query_module

        # Reset module state
        query_module._has_content_text_column = True
        query_module._hybrid_warning_emitted = False

        from cocosearch.search.hybrid import HybridSearchResult

        mock_hybrid_results = [
            HybridSearchResult(
                filename="/path/to/file.py",
                start_byte=0,
                end_byte=100,
                combined_score=0.75,
                match_type="semantic",
                vector_score=0.75,
                keyword_score=None,
            )
        ]

        with patch.object(query_module, "check_column_exists", return_value=True):
            with patch.object(
                query_module, "execute_hybrid_search", return_value=mock_hybrid_results
            ) as mock_hybrid:
                with patch.object(query_module, "get_connection_pool"):
                    with patch.object(
                        query_module, "get_table_name", return_value="test_table"
                    ):
                        # Plain query with use_hybrid=True should still use hybrid
                        results = query_module.search(
                            "database connection", "test_index", use_hybrid=True
                        )

                mock_hybrid.assert_called_once()

        assert len(results) == 1
        assert results[0].match_type == "semantic"

    def test_search_vector_only_when_hybrid_false(self, mock_db_pool):
        """Test that use_hybrid=False forces vector-only search even for identifiers."""
        import cocosearch.search.query as query_module

        # Reset module state
        query_module._has_content_text_column = True
        query_module._hybrid_warning_emitted = False

        # Mock vector search results
        vector_results = [
            ("/path/to/file.py", 0, 100, 0.85, "function", "main", "python"),
        ]

        pool, cursor, conn = mock_db_pool(results=vector_results)

        with patch.object(query_module, "check_column_exists", return_value=True):
            with patch.object(
                query_module, "execute_hybrid_search"
            ) as mock_hybrid:
                with patch.object(query_module, "code_to_embedding") as mock_embedding:
                    mock_embedding.eval.return_value = [0.1] * 1024
                    with patch.object(
                        query_module, "get_connection_pool", return_value=pool
                    ):
                        with patch.object(
                            query_module, "get_table_name", return_value="test_table"
                        ):
                            # camelCase query with use_hybrid=False should NOT use hybrid
                            results = query_module.search(
                                "getUserById", "test_index", use_hybrid=False
                            )

                # Hybrid search should NOT have been called
                mock_hybrid.assert_not_called()

        # Results should NOT have match_type (vector-only)
        assert len(results) == 1
        assert results[0].match_type == ""  # Empty for vector-only
        assert results[0].vector_score is None
        assert results[0].keyword_score is None

    def test_search_fallback_when_no_hybrid_columns(self, mock_db_pool):
        """Test that hybrid search falls back to vector-only when columns missing."""
        import cocosearch.search.query as query_module

        # Reset module state
        query_module._has_content_text_column = True
        query_module._hybrid_warning_emitted = False

        # Vector search results
        vector_results = [
            ("/path/to/file.py", 0, 100, 0.85, "function", "main", "python"),
        ]

        pool, cursor, conn = mock_db_pool(results=vector_results)

        with patch.object(query_module, "check_column_exists", return_value=False):
            with patch.object(
                query_module, "execute_hybrid_search"
            ) as mock_hybrid:
                with patch.object(query_module, "code_to_embedding") as mock_embedding:
                    mock_embedding.eval.return_value = [0.1] * 1024
                    with patch.object(
                        query_module, "get_connection_pool", return_value=pool
                    ):
                        with patch.object(
                            query_module, "get_table_name", return_value="test_table"
                        ):
                            # Request hybrid but column missing - should fallback
                            results = query_module.search(
                                "getUserById", "test_index", use_hybrid=True
                            )

                # Hybrid search should NOT be called (column missing)
                mock_hybrid.assert_not_called()

        # Should still return results (from vector-only)
        assert len(results) == 1
        assert results[0].score == 0.85

    def test_search_auto_mode_uses_vector_for_plain_query(self, mock_db_pool):
        """Test that plain English queries use vector-only search in auto mode."""
        import cocosearch.search.query as query_module

        # Reset module state
        query_module._has_content_text_column = True
        query_module._hybrid_warning_emitted = False

        # Vector search results
        vector_results = [
            ("/path/to/file.py", 0, 100, 0.75, "function", "main", "python"),
        ]

        pool, cursor, conn = mock_db_pool(results=vector_results)

        with patch.object(query_module, "check_column_exists", return_value=True):
            with patch.object(
                query_module, "execute_hybrid_search"
            ) as mock_hybrid:
                with patch.object(query_module, "code_to_embedding") as mock_embedding:
                    mock_embedding.eval.return_value = [0.1] * 1024
                    with patch.object(
                        query_module, "get_connection_pool", return_value=pool
                    ):
                        with patch.object(
                            query_module, "get_table_name", return_value="test_table"
                        ):
                            # Plain English query in auto mode should use vector-only
                            results = query_module.search(
                                "find database connection code", "test_index"
                            )

                # Hybrid search should NOT be called for plain query
                mock_hybrid.assert_not_called()

        assert len(results) == 1
