"""Unit tests for cocosearch indexer flow.

Tests the CocoIndex flow definition for code indexing,
focusing on the content_text field for hybrid search (v1.7).
"""

import inspect

from cocosearch.indexer.flow import create_code_index_flow


class TestFlowContentText:
    """Tests for content_text field in indexing flow."""

    def test_flow_source_code_contains_content_text_collection(self):
        """Verify flow definition collects content_text for hybrid search.

        This inspects the source code of create_code_index_flow to confirm
        the content_text field is passed to code_embeddings.collect().

        Note: We inspect source rather than run the flow because:
        - Flow execution requires CocoIndex runtime + database
        - The field existence in collect() determines schema creation
        - This is a static analysis test for the flow definition
        """
        source = inspect.getsource(create_code_index_flow)

        # Verify content_text is collected
        assert "content_text=" in source, (
            "Flow should collect content_text field for keyword search"
        )

        # Verify it receives chunk text (not transformed)
        assert 'content_text=chunk["text"]' in source, (
            "content_text should receive raw chunk text"
        )

    def test_flow_has_hybrid_search_documentation(self):
        """Verify flow documents content_text purpose for maintainability."""
        source = inspect.getsource(create_code_index_flow)

        # Check for hybrid search comment (any case)
        has_hybrid_comment = (
            "hybrid search" in source.lower() or
            "keyword search" in source.lower() or
            "bm25" in source.lower()
        )

        assert has_hybrid_comment, (
            "Flow should document content_text purpose for hybrid/keyword search"
        )

    def test_flow_collects_all_required_fields(self):
        """Verify flow collects all fields needed for search functionality."""
        source = inspect.getsource(create_code_index_flow)

        # Required fields for semantic + keyword hybrid search
        required_fields = [
            "filename=",      # File identification
            "location=",      # Chunk location within file
            "embedding=",     # Vector for semantic search
            "content_text=",  # Text for keyword search (v1.7)
            "block_type=",    # DevOps metadata
            "hierarchy=",     # DevOps metadata
            "language_id=",   # Language classification
        ]

        for field in required_fields:
            assert field in source, f"Flow should collect {field.rstrip('=')} field"
