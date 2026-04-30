"""Tests for cocosearch.indexer.flow module."""

import pytest
from unittest.mock import patch, MagicMock


class TestGetTableName:
    """Tests for get_table_name function."""

    def test_returns_expected_format(self):
        """Table name follows codeindex_{name}__{name}_chunks convention."""
        from cocosearch.indexer.flow import get_table_name

        assert get_table_name("myindex") == "codeindex_myindex__myindex_chunks"

    def test_different_index_name(self):
        """Each index gets its own table."""
        from cocosearch.indexer.flow import get_table_name

        assert get_table_name("other") == "codeindex_other__other_chunks"


class TestRunIndex:
    """Tests for run_index function."""

    @pytest.fixture(autouse=True)
    def _skip_preflight(self):
        with patch("cocosearch.indexer.flow.check_infrastructure"):
            yield

    @pytest.fixture
    def _mock_db(self):
        """Mock psycopg.connect and register_vector for all tests."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (None,)
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("cocosearch.indexer.flow.psycopg.connect", return_value=mock_conn):
            with patch("cocosearch.indexer.flow.register_vector"):
                yield mock_conn, mock_cursor

    def test_returns_stats_dict(self, tmp_path, _mock_db):
        """run_index returns dict with files_indexed, files_deleted, chunks_total."""
        from cocosearch.indexer.flow import run_index

        (tmp_path / "test.py").write_text("def hello(): pass")

        with patch("cocosearch.indexer.flow.embed_query", return_value=[0.1] * 768):
            with patch(
                "cocosearch.management.metadata.get_index_metadata", return_value=None
            ):
                with patch("cocosearch.indexer.flow.invalidate_index_cache"):
                    with patch("cocosearch.indexer.flow.track_parse_results"):
                        result = run_index(
                            index_name="testindex",
                            codebase_path=str(tmp_path),
                        )

        assert "files_indexed" in result
        assert "files_deleted" in result
        assert "chunks_total" in result

    def test_uses_default_config_when_none(self, tmp_path, _mock_db):
        """Uses default IndexingConfig when not provided."""
        from cocosearch.indexer.flow import run_index

        (tmp_path / "test.py").write_text("def hello(): pass")

        with patch("cocosearch.indexer.flow.embed_query", return_value=[0.1] * 768):
            with patch(
                "cocosearch.management.metadata.get_index_metadata", return_value=None
            ):
                with patch("cocosearch.indexer.flow.invalidate_index_cache"):
                    with patch("cocosearch.indexer.flow.track_parse_results"):
                        result = run_index(
                            index_name="testindex",
                            codebase_path=str(tmp_path),
                            config=None,
                        )

        assert result["files_indexed"] >= 0

    def test_skips_parse_tracking_when_no_changes(self, tmp_path, _mock_db):
        """Skips parse tracking when no file changes detected."""
        from cocosearch.indexer.flow import run_index

        mock_conn, mock_cursor = _mock_db
        mock_cursor.fetchall.return_value = [("test.py", "abc123")]

        (tmp_path / "test.py").write_text("def hello(): pass")

        with patch(
            "cocosearch.management.metadata.get_index_metadata", return_value=None
        ):
            with patch("cocosearch.indexer.flow.hashlib") as mock_hashlib:
                mock_hash = MagicMock()
                mock_hash.hexdigest.return_value = "abc123"
                mock_hashlib.sha256.return_value = mock_hash
                with patch("cocosearch.indexer.flow.track_parse_results") as mock_track:
                    with patch(
                        "cocosearch.indexer.flow.invalidate_index_cache"
                    ) as mock_invalidate:
                        result = run_index(
                            index_name="testindex",
                            codebase_path=str(tmp_path),
                        )

        assert result["files_indexed"] == 0
        mock_track.assert_not_called()
        mock_invalidate.assert_not_called()

    def test_stop_event_cancels_indexing(self, tmp_path, _mock_db):
        """run_index stops processing files when stop_event is set."""
        import threading

        from cocosearch.indexer.flow import run_index

        for i in range(10):
            (tmp_path / f"file{i}.py").write_text(f"x = {i}")

        stop_event = threading.Event()

        call_count = 0

        def counting_embed(text):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                stop_event.set()
            return [0.1] * 768

        with patch("cocosearch.indexer.flow.embed_query", side_effect=counting_embed):
            with patch(
                "cocosearch.management.metadata.get_index_metadata", return_value=None
            ):
                with patch("cocosearch.indexer.flow.invalidate_index_cache"):
                    with patch("cocosearch.indexer.flow.track_parse_results"):
                        result = run_index(
                            index_name="testindex",
                            codebase_path=str(tmp_path),
                            stop_event=stop_event,
                        )

        assert result["files_indexed"] < 10


class TestCustomLanguageIntegration:
    """Tests for custom language integration in flow module."""

    def test_handler_custom_languages_importable(self):
        """HANDLER_CUSTOM_LANGUAGES is importable from handlers module."""
        from cocosearch.handlers import get_custom_languages

        HANDLER_CUSTOM_LANGUAGES = get_custom_languages()
        assert isinstance(HANDLER_CUSTOM_LANGUAGES, list)
        assert len(HANDLER_CUSTOM_LANGUAGES) == 15

    def test_extract_language_importable(self):
        """extract_language is importable from embedder module."""
        from cocosearch.indexer.embedder import extract_language

        assert callable(extract_language)

    def test_flow_module_imports_custom_languages(self):
        """flow module successfully imports get_custom_languages from handlers."""
        import cocosearch.indexer.flow as flow_module

        assert hasattr(flow_module, "get_custom_languages")

    def test_flow_module_imports_extract_language(self):
        """flow module successfully imports extract_language."""
        import cocosearch.indexer.flow as flow_module

        assert hasattr(flow_module, "extract_language")


class TestMetadataIntegration:
    """Tests for metadata extraction integration in flow module."""

    def test_extract_chunk_metadata_importable_from_flow(self):
        """flow module successfully imports extract_chunk_metadata."""
        import cocosearch.indexer.flow as flow_module

        assert hasattr(flow_module, "extract_chunk_metadata")

    def test_extract_chunk_metadata_returns_chunk_metadata(self):
        """extract_chunk_metadata is a callable that returns ChunkMetadata."""
        from cocosearch.handlers import extract_chunk_metadata, ChunkMetadata

        assert callable(extract_chunk_metadata)
        result = extract_chunk_metadata("some text", "py")
        assert isinstance(result, ChunkMetadata)
        assert hasattr(result, "block_type")
        assert hasattr(result, "hierarchy")
        assert hasattr(result, "language_id")


class TestFilenameContextIntegration:
    """Tests for filename context integration in flow module."""

    def test_add_filename_context_importable_from_flow(self):
        """flow module successfully imports add_filename_context."""
        import cocosearch.indexer.flow as flow_module

        assert hasattr(flow_module, "add_filename_context")


class TestSymbolIntegration:
    """Tests for symbol extraction integration in flow module."""

    def test_extract_symbol_metadata_importable_from_flow(self):
        """flow module successfully imports extract_symbol_metadata."""
        import cocosearch.indexer.flow as flow_module

        assert hasattr(flow_module, "extract_symbol_metadata")

    def test_ensure_symbol_columns_importable_from_flow(self):
        """flow module successfully imports ensure_symbol_columns."""
        import cocosearch.indexer.flow as flow_module

        assert hasattr(flow_module, "ensure_symbol_columns")
