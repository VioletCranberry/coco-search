"""Tests for cocosearch.indexer.flow module."""

import inspect

import pytest
from unittest.mock import patch, MagicMock

from cocosearch.indexer.config import IndexingConfig


class TestCreateCodeIndexFlow:
    """Tests for create_code_index_flow function."""

    def test_creates_flow_with_name(self):
        """Creates a flow with the correct name."""
        from cocosearch.indexer.flow import create_code_index_flow

        flow = create_code_index_flow(
            index_name="testindex",
            codebase_path="/test/path",
            include_patterns=["*.py"],
            exclude_patterns=[],
        )

        # Flow should have a name attribute
        assert flow is not None


class TestRunIndex:
    """Tests for run_index function."""

    @pytest.fixture(autouse=True)
    def _skip_preflight(self):
        with patch("cocosearch.indexer.flow.check_infrastructure"):
            yield

    def test_returns_update_info(self, tmp_path):
        """run_index returns object with stats attribute."""
        from cocosearch.indexer.flow import run_index

        # Create a sample file in tmp_path
        (tmp_path / "test.py").write_text("def hello(): pass")

        # Mock cocoindex.init() and Flow to avoid real DB/Ollama calls
        mock_update_info = MagicMock()
        mock_update_info.stats = {"files_added": 1}

        mock_flow = MagicMock()
        mock_flow.setup.return_value = None
        mock_flow.update.return_value = mock_update_info

        # Mock database connection and schema migration
        mock_conn = MagicMock()

        with patch("cocosearch.indexer.flow.cocoindex.init"):
            with patch(
                "cocosearch.indexer.flow.create_code_index_flow", return_value=mock_flow
            ):
                with patch(
                    "cocosearch.indexer.flow.os.getenv",
                    return_value="postgresql://localhost/test",
                ):
                    with patch(
                        "cocosearch.indexer.flow.psycopg.connect",
                        return_value=mock_conn,
                    ):
                        with patch("cocosearch.indexer.flow.ensure_symbol_columns"):
                            result = run_index(
                                index_name="testindex",
                                codebase_path=str(tmp_path),
                            )

        # Should return the update info from flow.update()
        assert result == mock_update_info
        mock_flow.setup.assert_called_once()
        mock_flow.update.assert_called_once()

    def test_respects_config(self, tmp_path):
        """Passes config to flow correctly."""
        from cocosearch.indexer.flow import run_index

        (tmp_path / "test.py").write_text("def hello(): pass")

        custom_config = IndexingConfig(
            include_patterns=["*.py", "*.js"],
            chunk_size=500,
            chunk_overlap=100,
        )

        mock_flow = MagicMock()
        mock_flow.update.return_value = MagicMock()

        mock_conn = MagicMock()

        with patch("cocosearch.indexer.flow.cocoindex.init"):
            with patch(
                "cocosearch.indexer.flow.create_code_index_flow", return_value=mock_flow
            ) as mock_create_flow:
                with patch(
                    "cocosearch.indexer.flow.os.getenv",
                    return_value="postgresql://localhost/test",
                ):
                    with patch(
                        "cocosearch.indexer.flow.psycopg.connect",
                        return_value=mock_conn,
                    ):
                        with patch("cocosearch.indexer.flow.ensure_symbol_columns"):
                            run_index(
                                index_name="testindex",
                                codebase_path=str(tmp_path),
                                config=custom_config,
                            )

        # Verify create_code_index_flow was called with config values
        call_kwargs = mock_create_flow.call_args[1]
        assert call_kwargs["include_patterns"] == ["*.py", "*.js"]
        assert call_kwargs["chunk_size"] == 500
        assert call_kwargs["chunk_overlap"] == 100

    def test_uses_default_config_when_none(self, tmp_path):
        """Uses default config when not provided."""
        from cocosearch.indexer.flow import run_index

        (tmp_path / "test.py").write_text("def hello(): pass")

        mock_flow = MagicMock()
        mock_flow.update.return_value = MagicMock()

        mock_conn = MagicMock()

        with patch("cocosearch.indexer.flow.cocoindex.init"):
            with patch(
                "cocosearch.indexer.flow.create_code_index_flow", return_value=mock_flow
            ) as mock_create_flow:
                with patch(
                    "cocosearch.indexer.flow.os.getenv",
                    return_value="postgresql://localhost/test",
                ):
                    with patch(
                        "cocosearch.indexer.flow.psycopg.connect",
                        return_value=mock_conn,
                    ):
                        with patch("cocosearch.indexer.flow.ensure_symbol_columns"):
                            run_index(
                                index_name="testindex",
                                codebase_path=str(tmp_path),
                                config=None,
                            )

        # Should use default include_patterns (has *.py)
        call_kwargs = mock_create_flow.call_args[1]
        assert "*.py" in call_kwargs["include_patterns"]
        assert call_kwargs["chunk_size"] == 1000  # default

    def test_respects_gitignore_flag_true(self, tmp_path):
        """Includes gitignore patterns when respect_gitignore=True."""
        from cocosearch.indexer.flow import run_index

        (tmp_path / "test.py").write_text("def hello(): pass")
        (tmp_path / ".gitignore").write_text("custom_ignore/\n")

        mock_flow = MagicMock()
        mock_flow.update.return_value = MagicMock()

        mock_conn = MagicMock()

        with patch("cocosearch.indexer.flow.cocoindex.init"):
            with patch(
                "cocosearch.indexer.flow.create_code_index_flow", return_value=mock_flow
            ) as mock_create_flow:
                with patch(
                    "cocosearch.indexer.flow.os.getenv",
                    return_value="postgresql://localhost/test",
                ):
                    with patch(
                        "cocosearch.indexer.flow.psycopg.connect",
                        return_value=mock_conn,
                    ):
                        with patch("cocosearch.indexer.flow.ensure_symbol_columns"):
                            run_index(
                                index_name="testindex",
                                codebase_path=str(tmp_path),
                                respect_gitignore=True,
                            )

        call_kwargs = mock_create_flow.call_args[1]
        assert "custom_ignore/" in call_kwargs["exclude_patterns"]

    def test_respects_gitignore_flag_false(self, tmp_path):
        """Excludes gitignore patterns when respect_gitignore=False."""
        from cocosearch.indexer.flow import run_index

        (tmp_path / "test.py").write_text("def hello(): pass")
        (tmp_path / ".gitignore").write_text("custom_ignore/\n")

        mock_flow = MagicMock()
        mock_flow.update.return_value = MagicMock()

        mock_conn = MagicMock()

        with patch("cocosearch.indexer.flow.cocoindex.init"):
            with patch(
                "cocosearch.indexer.flow.create_code_index_flow", return_value=mock_flow
            ) as mock_create_flow:
                with patch(
                    "cocosearch.indexer.flow.os.getenv",
                    return_value="postgresql://localhost/test",
                ):
                    with patch(
                        "cocosearch.indexer.flow.psycopg.connect",
                        return_value=mock_conn,
                    ):
                        with patch("cocosearch.indexer.flow.ensure_symbol_columns"):
                            run_index(
                                index_name="testindex",
                                codebase_path=str(tmp_path),
                                respect_gitignore=False,
                            )

        call_kwargs = mock_create_flow.call_args[1]
        assert "custom_ignore/" not in call_kwargs["exclude_patterns"]

    def test_initializes_cocoindex(self, tmp_path):
        """Calls cocoindex.init() before creating flow."""
        from cocosearch.indexer.flow import run_index

        (tmp_path / "test.py").write_text("def hello(): pass")

        mock_flow = MagicMock()
        mock_flow.update.return_value = MagicMock()

        mock_conn = MagicMock()

        with patch("cocosearch.indexer.flow.cocoindex.init") as mock_init:
            with patch(
                "cocosearch.indexer.flow.create_code_index_flow", return_value=mock_flow
            ):
                with patch(
                    "cocosearch.indexer.flow.os.getenv",
                    return_value="postgresql://localhost/test",
                ):
                    with patch(
                        "cocosearch.indexer.flow.psycopg.connect",
                        return_value=mock_conn,
                    ):
                        with patch("cocosearch.indexer.flow.ensure_symbol_columns"):
                            run_index(
                                index_name="testindex",
                                codebase_path=str(tmp_path),
                            )

        mock_init.assert_called_once()

    def test_skips_parse_tracking_when_no_changes(self, tmp_path):
        """Skips parse tracking when flow.update() reports zero changes."""
        from cocosearch.indexer.flow import run_index

        (tmp_path / "test.py").write_text("def hello(): pass")

        mock_update_info = MagicMock()
        mock_update_info.stats = {
            "files": {"num_insertions": 0, "num_deletions": 0, "num_updates": 0}
        }

        mock_flow = MagicMock()
        mock_flow.update.return_value = mock_update_info

        mock_conn = MagicMock()

        with patch("cocosearch.indexer.flow.cocoindex.init"):
            with patch(
                "cocosearch.indexer.flow.create_code_index_flow",
                return_value=mock_flow,
            ):
                with patch(
                    "cocosearch.indexer.flow.psycopg.connect",
                    return_value=mock_conn,
                ):
                    with patch("cocosearch.indexer.flow.ensure_symbol_columns"):
                        with patch(
                            "cocosearch.indexer.flow.track_parse_results"
                        ) as mock_track:
                            run_index(
                                index_name="testindex",
                                codebase_path=str(tmp_path),
                            )

        mock_track.assert_not_called()

    def test_skips_cache_invalidation_when_no_changes(self, tmp_path):
        """Skips cache invalidation when flow.update() reports zero changes."""
        from cocosearch.indexer.flow import run_index

        (tmp_path / "test.py").write_text("def hello(): pass")

        mock_update_info = MagicMock()
        mock_update_info.stats = {
            "files": {"num_insertions": 0, "num_deletions": 0, "num_updates": 0}
        }

        mock_flow = MagicMock()
        mock_flow.update.return_value = mock_update_info

        mock_conn = MagicMock()

        with patch("cocosearch.indexer.flow.cocoindex.init"):
            with patch(
                "cocosearch.indexer.flow.create_code_index_flow",
                return_value=mock_flow,
            ):
                with patch(
                    "cocosearch.indexer.flow.psycopg.connect",
                    return_value=mock_conn,
                ):
                    with patch("cocosearch.indexer.flow.ensure_symbol_columns"):
                        with patch(
                            "cocosearch.indexer.flow.invalidate_index_cache"
                        ) as mock_invalidate:
                            run_index(
                                index_name="testindex",
                                codebase_path=str(tmp_path),
                            )

        mock_invalidate.assert_not_called()

    def test_runs_both_when_changes_detected(self, tmp_path):
        """Runs parse tracking and cache invalidation when changes are detected."""
        from cocosearch.indexer.flow import run_index

        (tmp_path / "test.py").write_text("def hello(): pass")

        mock_update_info = MagicMock()
        mock_update_info.stats = {
            "files": {"num_insertions": 5, "num_deletions": 0, "num_updates": 0}
        }

        mock_flow = MagicMock()
        mock_flow.update.return_value = mock_update_info

        mock_conn = MagicMock()

        with patch("cocosearch.indexer.flow.cocoindex.init"):
            with patch(
                "cocosearch.indexer.flow.create_code_index_flow",
                return_value=mock_flow,
            ):
                with patch(
                    "cocosearch.indexer.flow.psycopg.connect",
                    return_value=mock_conn,
                ):
                    with patch("cocosearch.indexer.flow.ensure_symbol_columns"):
                        with patch(
                            "cocosearch.indexer.flow.track_parse_results"
                        ) as mock_track:
                            with patch(
                                "cocosearch.indexer.flow.invalidate_index_cache"
                            ) as mock_invalidate:
                                run_index(
                                    index_name="testindex",
                                    codebase_path=str(tmp_path),
                                )

        mock_track.assert_called_once()
        mock_invalidate.assert_called_once()

    def test_conservative_default_when_stats_unavailable(self, tmp_path):
        """Runs both when update_info has no stats attribute (conservative default)."""
        from cocosearch.indexer.flow import run_index

        (tmp_path / "test.py").write_text("def hello(): pass")

        # MagicMock with spec=object so hasattr(update_info, "stats") is False
        mock_update_info = MagicMock(spec=object)

        mock_flow = MagicMock()
        mock_flow.update.return_value = mock_update_info

        mock_conn = MagicMock()

        with patch("cocosearch.indexer.flow.cocoindex.init"):
            with patch(
                "cocosearch.indexer.flow.create_code_index_flow",
                return_value=mock_flow,
            ):
                with patch(
                    "cocosearch.indexer.flow.psycopg.connect",
                    return_value=mock_conn,
                ):
                    with patch("cocosearch.indexer.flow.ensure_symbol_columns"):
                        with patch(
                            "cocosearch.indexer.flow.track_parse_results"
                        ) as mock_track:
                            with patch(
                                "cocosearch.indexer.flow.invalidate_index_cache"
                            ) as mock_invalidate:
                                run_index(
                                    index_name="testindex",
                                    codebase_path=str(tmp_path),
                                )

        mock_track.assert_called_once()
        mock_invalidate.assert_called_once()


class TestCustomLanguageIntegration:
    """Tests for custom language integration in flow module."""

    def test_handler_custom_languages_importable(self):
        """HANDLER_CUSTOM_LANGUAGES is importable from handlers module."""
        from cocosearch.handlers import get_custom_languages

        HANDLER_CUSTOM_LANGUAGES = get_custom_languages()
        assert isinstance(HANDLER_CUSTOM_LANGUAGES, list)
        assert len(HANDLER_CUSTOM_LANGUAGES) == 13

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

    def test_create_code_index_flow_with_custom_languages(self):
        """create_code_index_flow creates flow without errors."""
        from cocosearch.indexer.flow import create_code_index_flow

        flow = create_code_index_flow(
            index_name="test_custom_lang",
            codebase_path="/test/path",
            include_patterns=["*.py", "*.tf", "Dockerfile"],
            exclude_patterns=[],
        )

        assert flow is not None


class TestMetadataIntegration:
    """Tests for metadata extraction integration in flow module."""

    def test_extract_chunk_metadata_importable_from_flow(self):
        """flow module successfully imports extract_chunk_metadata."""
        import cocosearch.indexer.flow as flow_module

        assert hasattr(flow_module, "extract_chunk_metadata")

    def test_extract_chunk_metadata_is_cocoindex_op(self):
        """extract_chunk_metadata is a callable that returns ChunkMetadata."""
        from cocosearch.handlers import extract_chunk_metadata, ChunkMetadata

        assert callable(extract_chunk_metadata)
        # Verify the function works and returns ChunkMetadata with expected fields
        result = extract_chunk_metadata("some text", "py")
        assert isinstance(result, ChunkMetadata)
        assert hasattr(result, "block_type")
        assert hasattr(result, "hierarchy")
        assert hasattr(result, "language_id")

    def test_flow_source_has_metadata_import(self):
        """flow module source contains the handlers import statement."""
        import cocosearch.indexer.flow as flow_module

        source = inspect.getsource(flow_module)
        assert "from cocosearch.handlers import" in source
        assert "extract_chunk_metadata" in source

    def test_flow_source_has_metadata_transform(self):
        """flow module source contains the metadata transform call."""
        import cocosearch.indexer.flow as flow_module

        source = inspect.getsource(flow_module)
        assert 'chunk["metadata"]' in source
        assert "extract_chunk_metadata" in source
        assert 'language=file["extension"]' in source

    def test_flow_source_collects_metadata_fields(self):
        """flow module source collects all three metadata fields via bracket notation."""
        import cocosearch.indexer.flow as flow_module

        source = inspect.getsource(flow_module)
        assert 'block_type=chunk["metadata"]["block_type"]' in source
        assert 'hierarchy=chunk["metadata"]["hierarchy"]' in source
        assert 'language_id=chunk["metadata"]["language_id"]' in source

    def test_flow_source_preserves_primary_keys(self):
        """flow module source preserves primary keys as ["filename", "location"]."""
        import cocosearch.indexer.flow as flow_module

        source = inspect.getsource(flow_module)
        assert 'primary_key_fields=["filename", "location"]' in source

    def test_create_code_index_flow_with_metadata_succeeds(self):
        """create_code_index_flow builds flow without errors after metadata wiring."""
        from cocosearch.indexer.flow import create_code_index_flow

        flow = create_code_index_flow(
            index_name="test_metadata",
            codebase_path="/test/path",
            include_patterns=["*.py", "*.tf", "Dockerfile"],
            exclude_patterns=[],
        )

        assert flow is not None


class TestFilenameContextIntegration:
    """Tests for filename context integration in flow module."""

    def test_add_filename_context_importable_from_flow(self):
        """flow module successfully imports add_filename_context."""
        import cocosearch.indexer.flow as flow_module

        assert hasattr(flow_module, "add_filename_context")

    def test_flow_source_has_embedding_text(self):
        """flow module source creates intermediate embedding_text with filename context."""
        import cocosearch.indexer.flow as flow_module

        source = inspect.getsource(flow_module)
        assert 'chunk["embedding_text"]' in source
        assert "add_filename_context" in source
        assert 'filename=file["filename"]' in source

    def test_flow_source_uses_embedding_text_for_embedding(self):
        """flow module source generates embedding from embedding_text, not raw text."""
        import cocosearch.indexer.flow as flow_module

        source = inspect.getsource(flow_module)
        assert 'chunk["embedding_text"].call(code_to_embedding)' in source

    def test_flow_source_passes_filename_to_tsvector(self):
        """flow module source passes filename to text_to_tsvector_sql."""
        import cocosearch.indexer.flow as flow_module

        source = inspect.getsource(flow_module)
        assert "text_to_tsvector_sql, filename=file[" in source

    def test_flow_source_preserves_raw_content_text(self):
        """flow module source keeps content_text as raw chunk text (no filename prefix)."""
        import cocosearch.indexer.flow as flow_module

        source = inspect.getsource(flow_module)
        assert 'content_text=chunk["text"]' in source

    def test_create_code_index_flow_with_filename_context_succeeds(self):
        """create_code_index_flow builds flow without errors after filename wiring."""
        from cocosearch.indexer.flow import create_code_index_flow

        flow = create_code_index_flow(
            index_name="test_filename_ctx",
            codebase_path="/test/path",
            include_patterns=["*.py", "*.yaml"],
            exclude_patterns=[],
        )

        assert flow is not None


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

    def test_flow_source_has_symbol_import(self):
        """flow module source contains the symbols import statement."""
        import cocosearch.indexer.flow as flow_module

        source = inspect.getsource(flow_module)
        assert "from cocosearch.indexer.symbols import" in source
        assert "extract_symbol_metadata" in source

    def test_flow_source_has_schema_migration_import(self):
        """flow module source contains the schema migration import."""
        import cocosearch.indexer.flow as flow_module

        source = inspect.getsource(flow_module)
        assert "from cocosearch.indexer.schema_migration import" in source
        assert "ensure_symbol_columns" in source

    def test_flow_source_has_symbol_transform(self):
        """flow module source contains the symbol metadata transform call."""
        import cocosearch.indexer.flow as flow_module

        source = inspect.getsource(flow_module)
        assert 'chunk["symbol_metadata"]' in source
        assert "extract_symbol_metadata" in source
        assert 'language=file["extension"]' in source

    def test_flow_source_collects_symbol_fields(self):
        """flow module source collects all three symbol fields via bracket notation."""
        import cocosearch.indexer.flow as flow_module

        source = inspect.getsource(flow_module)
        assert 'symbol_type=chunk["symbol_metadata"]["symbol_type"]' in source
        assert 'symbol_name=chunk["symbol_metadata"]["symbol_name"]' in source
        assert 'symbol_signature=chunk["symbol_metadata"]["symbol_signature"]' in source

    def test_flow_source_calls_ensure_symbol_columns(self):
        """flow module source calls ensure_symbol_columns after setup."""
        import cocosearch.indexer.flow as flow_module

        source = inspect.getsource(flow_module)
        # Should call ensure_symbol_columns in run_index
        assert "ensure_symbol_columns(conn, table_name)" in source

    def test_create_code_index_flow_with_symbols_succeeds(self):
        """create_code_index_flow builds flow without errors after symbol wiring."""
        from cocosearch.indexer.flow import create_code_index_flow

        flow = create_code_index_flow(
            index_name="test_symbols",
            codebase_path="/test/path",
            include_patterns=["*.py", "*.js"],
            exclude_patterns=[],
        )

        assert flow is not None
