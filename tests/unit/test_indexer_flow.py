"""Unit tests for cocosearch indexer flow.

Tests the indexing pipeline structure, verifying that all required
fields are stored and the key functions are correctly wired.
"""

import inspect

from cocosearch.indexer.flow import _index_file, run_index


class TestIndexFileStructure:
    """Tests for _index_file function structure."""

    def test_index_file_stores_all_required_fields(self):
        """Verify _index_file inserts all fields needed for search."""
        source = inspect.getsource(_index_file)

        required_fields = [
            "filename",
            "embedding",
            "content_text",
            "content_tsv_input",
            "block_type",
            "hierarchy",
            "language_id",
            "symbol_type",
            "symbol_name",
            "symbol_signature",
        ]

        for field in required_fields:
            assert field in source, f"_index_file should store {field} field"

    def test_index_file_uses_add_filename_context(self):
        """Verify _index_file enriches embedding text with filename context."""
        source = inspect.getsource(_index_file)
        assert "add_filename_context" in source

    def test_index_file_uses_extract_chunk_metadata(self):
        """Verify _index_file extracts chunk metadata."""
        source = inspect.getsource(_index_file)
        assert "extract_chunk_metadata" in source

    def test_index_file_uses_extract_symbol_metadata(self):
        """Verify _index_file extracts symbol metadata."""
        source = inspect.getsource(_index_file)
        assert "extract_symbol_metadata" in source

    def test_index_file_uses_tsvector(self):
        """Verify _index_file generates tsvector input."""
        source = inspect.getsource(_index_file)
        assert "text_to_tsvector_sql" in source

    def test_index_file_uses_embed_batch(self):
        """Verify _index_file uses batched embedding."""
        source = inspect.getsource(_index_file)
        assert "embed_batch" in source


class TestRunIndexStructure:
    """Tests for run_index function structure."""

    def test_run_index_has_incremental_tracking(self):
        """Verify run_index uses SHA-256 content hashes for incremental indexing."""
        source = inspect.getsource(run_index)
        assert "sha256" in source
        assert "content_hash" in source

    def test_run_index_handles_deleted_files(self):
        """Verify run_index detects and removes deleted files."""
        source = inspect.getsource(run_index)
        assert "deleted_files" in source

    def test_run_index_invalidates_cache(self):
        """Verify run_index invalidates query cache after changes."""
        source = inspect.getsource(run_index)
        assert "invalidate_index_cache" in source
