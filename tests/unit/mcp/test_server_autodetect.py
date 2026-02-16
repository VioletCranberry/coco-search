"""Unit tests for MCP server auto-detection feature.

Tests search_code auto-detection behavior, structured error responses,
path registration in index_codebase, and metadata cleanup in clear_index.

After Plan 02, search_code is async and uses _detect_project(ctx) instead of
the old find_project_root() at module level. Auto-detect tests mock both:
  - cocosearch.mcp.project_detection._detect_project (AsyncMock)
  - cocosearch.management.context.find_project_root (for git-root walking)
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path


def _make_mock_ctx():
    """Create a minimal mock Context for autodetect tests."""
    ctx = MagicMock()
    ctx.session = MagicMock()
    ctx.request_context = MagicMock()
    ctx.request_context.request = None
    return ctx


class TestSearchCodeAutoDetect:
    """Tests for search_code auto-detection behavior."""

    @pytest.mark.asyncio
    async def test_auto_detects_from_cwd(self, mock_code_to_embedding, mock_db_pool):
        """search_code auto-detects index via _detect_project -> find_project_root."""
        from cocosearch.mcp.server import search_code

        mock_root = Path("/path/to/project")
        mock_indexes = [
            {"name": "project", "table_name": "codeindex_project__project_chunks"}
        ]

        pool, cursor, conn = mock_db_pool(
            results=[
                ("/test/file.py", 0, 100, 0.9, "", "", ""),
            ]
        )

        with patch(
            "cocosearch.mcp.project_detection._detect_project",
            new_callable=AsyncMock,
            return_value=(mock_root, "roots"),
        ):
            with patch(
                "cocosearch.management.context.find_project_root",
                return_value=(mock_root, "git"),
            ):
                with patch(
                    "cocosearch.mcp.server.resolve_index_name", return_value="project"
                ):
                    with patch(
                        "cocosearch.mcp.server.mgmt_list_indexes",
                        return_value=mock_indexes,
                    ):
                        with patch(
                            "cocosearch.mcp.server.get_index_metadata",
                            return_value=None,
                        ):
                            with patch("cocoindex.init"):
                                with patch(
                                    "cocosearch.search.query.get_connection_pool",
                                    return_value=pool,
                                ):
                                    with patch(
                                        "cocosearch.mcp.server.byte_to_line",
                                        return_value=1,
                                    ):
                                        with patch(
                                            "cocosearch.mcp.server.read_chunk_content",
                                            return_value="def test(): pass",
                                        ):
                                            result = await search_code(
                                                query="test query", ctx=_make_mock_ctx()
                                            )

        # Should return search results (header + result)
        assert isinstance(result, list)
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_returns_error_when_no_project(self):
        """search_code returns 'Index not found' when find_project_root returns None."""
        from cocosearch.mcp.server import search_code

        # _detect_project returns cwd, find_project_root finds no git root
        mock_detected = Path("/some/random/dir")

        with patch(
            "cocosearch.mcp.project_detection._detect_project",
            new_callable=AsyncMock,
            return_value=(mock_detected, "cwd"),
        ):
            with patch(
                "cocosearch.management.context.find_project_root",
                return_value=(None, None),
            ):
                with patch(
                    "cocosearch.mcp.server.resolve_index_name",
                    return_value="random_dir",
                ):
                    with patch(
                        "cocosearch.mcp.server.mgmt_list_indexes", return_value=[]
                    ):
                        result = await search_code(
                            query="test query", ctx=_make_mock_ctx()
                        )

        assert len(result) == 1
        assert result[0]["error"] == "Index not found"
        assert "not indexed" in result[0]["message"]

    @pytest.mark.asyncio
    async def test_returns_error_when_index_not_found(self):
        """search_code returns error when project exists but not indexed."""
        from cocosearch.mcp.server import search_code

        mock_root = Path("/path/to/project")

        with patch(
            "cocosearch.mcp.project_detection._detect_project",
            new_callable=AsyncMock,
            return_value=(mock_root, "roots"),
        ):
            with patch(
                "cocosearch.management.context.find_project_root",
                return_value=(mock_root, "git"),
            ):
                with patch(
                    "cocosearch.mcp.server.resolve_index_name", return_value="project"
                ):
                    with patch(
                        "cocosearch.mcp.server.mgmt_list_indexes", return_value=[]
                    ):
                        result = await search_code(
                            query="test query", ctx=_make_mock_ctx()
                        )

        assert len(result) == 1
        assert result[0]["error"] == "Index not found"
        assert "not indexed" in result[0]["message"]
        assert (
            "cocosearch index" in result[0]["message"]
            or "index_codebase" in result[0]["message"]
        )

    @pytest.mark.asyncio
    async def test_returns_collision_error(self):
        """search_code returns error on index name collision."""
        from cocosearch.mcp.server import search_code

        mock_root = Path("/path/to/new_project")
        mock_indexes = [
            {"name": "project", "table_name": "codeindex_project__project_chunks"}
        ]
        mock_metadata = {
            "index_name": "project",
            "canonical_path": "/path/to/old_project",  # Different path!
        }

        with patch(
            "cocosearch.mcp.project_detection._detect_project",
            new_callable=AsyncMock,
            return_value=(mock_root, "roots"),
        ):
            with patch(
                "cocosearch.management.context.find_project_root",
                return_value=(mock_root, "git"),
            ):
                with patch(
                    "cocosearch.mcp.server.resolve_index_name", return_value="project"
                ):
                    with patch(
                        "cocosearch.mcp.server.mgmt_list_indexes",
                        return_value=mock_indexes,
                    ):
                        with patch(
                            "cocosearch.mcp.server.get_index_metadata",
                            return_value=mock_metadata,
                        ):
                            result = await search_code(
                                query="test query", ctx=_make_mock_ctx()
                            )

        assert len(result) == 1
        assert result[0]["error"] == "Index name collision"
        assert (
            "different project" in result[0]["message"]
            or "different" in result[0]["message"].lower()
        )

    @pytest.mark.asyncio
    async def test_uses_explicit_index_name(self, mock_code_to_embedding, mock_db_pool):
        """search_code uses explicit index_name when provided -- _detect_project not called."""
        from cocosearch.mcp.server import search_code

        pool, cursor, conn = mock_db_pool(
            results=[
                ("/test/file.py", 0, 100, 0.9, "", "", ""),
            ]
        )

        with patch(
            "cocosearch.mcp.project_detection._detect_project", new_callable=AsyncMock
        ) as mock_detect:
            with patch("cocoindex.init"):
                with patch(
                    "cocosearch.search.query.get_connection_pool", return_value=pool
                ):
                    with patch("cocosearch.mcp.server.byte_to_line", return_value=1):
                        with patch(
                            "cocosearch.mcp.server.read_chunk_content",
                            return_value="code",
                        ):
                            await search_code(
                                query="test query",
                                ctx=_make_mock_ctx(),
                                index_name="explicit_index",
                            )

        # Should NOT call _detect_project when index_name is explicit
        mock_detect.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_collision_when_paths_match(
        self, mock_code_to_embedding, mock_db_pool
    ):
        """search_code proceeds when metadata path matches current path."""
        from cocosearch.mcp.server import search_code

        mock_root = Path("/path/to/project")
        mock_indexes = [
            {"name": "project", "table_name": "codeindex_project__project_chunks"}
        ]
        mock_metadata = {
            "index_name": "project",
            "canonical_path": str(mock_root.resolve()),  # Same path
        }

        pool, cursor, conn = mock_db_pool(
            results=[
                ("/test/file.py", 0, 100, 0.9, "", "", ""),
            ]
        )

        with patch(
            "cocosearch.mcp.project_detection._detect_project",
            new_callable=AsyncMock,
            return_value=(mock_root, "roots"),
        ):
            with patch(
                "cocosearch.management.context.find_project_root",
                return_value=(mock_root, "git"),
            ):
                with patch(
                    "cocosearch.mcp.server.resolve_index_name", return_value="project"
                ):
                    with patch(
                        "cocosearch.mcp.server.mgmt_list_indexes",
                        return_value=mock_indexes,
                    ):
                        with patch(
                            "cocosearch.mcp.server.get_index_metadata",
                            return_value=mock_metadata,
                        ):
                            with patch("cocoindex.init"):
                                with patch(
                                    "cocosearch.search.query.get_connection_pool",
                                    return_value=pool,
                                ):
                                    with patch(
                                        "cocosearch.mcp.server.byte_to_line",
                                        return_value=1,
                                    ):
                                        with patch(
                                            "cocosearch.mcp.server.read_chunk_content",
                                            return_value="code",
                                        ):
                                            result = await search_code(
                                                query="test query", ctx=_make_mock_ctx()
                                            )

        # Should proceed to search, not return collision error
        assert isinstance(result, list)
        # First item is search_context header when auto-detecting
        assert result[0].get("type") == "search_context"
        # If we got actual search results, no error occurred
        if len(result) > 1 and "error" not in result[1]:
            assert result[1]["file_path"] == "/test/file.py"

    @pytest.mark.asyncio
    async def test_logs_auto_detected_index(self):
        """search_code logs auto-detected index info."""
        from cocosearch.mcp.server import search_code

        mock_root = Path("/path/to/project")
        mock_indexes = [
            {"name": "project", "table_name": "codeindex_project__project_chunks"}
        ]

        with patch(
            "cocosearch.mcp.project_detection._detect_project",
            new_callable=AsyncMock,
            return_value=(mock_root, "roots"),
        ):
            with patch(
                "cocosearch.management.context.find_project_root",
                return_value=(mock_root, "git"),
            ):
                with patch(
                    "cocosearch.mcp.server.resolve_index_name", return_value="project"
                ):
                    with patch(
                        "cocosearch.mcp.server.mgmt_list_indexes",
                        return_value=mock_indexes,
                    ):
                        with patch(
                            "cocosearch.mcp.server.get_index_metadata",
                            return_value=None,
                        ):
                            with patch("cocosearch.mcp.server.logger") as mock_logger:
                                with patch("cocoindex.init"):
                                    with patch(
                                        "cocosearch.mcp.server.search", return_value=[]
                                    ):
                                        await search_code(
                                            query="test query", ctx=_make_mock_ctx()
                                        )

        # Should log auto-detection
        mock_logger.info.assert_called()
        log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("Auto-detected" in msg or "project" in msg for msg in log_messages)


class TestIndexCodebasePathRegistration:
    """Tests for path registration in index_codebase."""

    def test_registers_path_after_indexing(self, tmp_codebase):
        """index_codebase registers path-to-index mapping."""
        from cocosearch.mcp.server import index_codebase

        with patch("cocoindex.init"):
            with patch("cocosearch.mcp.server.run_index") as mock_run:
                mock_run.return_value = MagicMock(stats={})
                with patch("cocosearch.mcp.server._register_with_git") as mock_register:
                    with patch("cocosearch.mcp.server.set_index_status"):
                        with patch("cocosearch.mcp.server.ensure_metadata_table"):
                            result = index_codebase(
                                path=str(tmp_codebase), index_name="myindex"
                            )

        assert result["success"] is True
        # Called twice: once before indexing (status tracking) and once after
        assert mock_register.call_count == 2
        mock_register.assert_any_call("myindex", str(tmp_codebase))

    def test_handles_collision_during_indexing(self, tmp_codebase):
        """index_codebase logs warning on collision but doesn't fail."""
        from cocosearch.mcp.server import index_codebase

        with patch("cocoindex.init"):
            with patch("cocosearch.mcp.server.run_index") as mock_run:
                mock_run.return_value = MagicMock(stats={})
                with patch("cocosearch.mcp.server._register_with_git") as mock_register:
                    mock_register.side_effect = ValueError("Collision!")
                    with patch("cocosearch.mcp.server.ensure_metadata_table"):
                        with patch("cocosearch.mcp.server.set_index_status"):
                            with patch("cocosearch.mcp.server.logger") as mock_logger:
                                result = index_codebase(
                                    path=str(tmp_codebase), index_name="myindex"
                                )

        # Should succeed (indexing worked)
        assert result["success"] is True
        # Should log warning
        mock_logger.warning.assert_called_once()

    def test_derives_index_name_and_registers(self, tmp_codebase):
        """index_codebase derives name and registers path."""
        from cocosearch.mcp.server import index_codebase

        with patch("cocoindex.init"):
            with patch("cocosearch.mcp.server.run_index") as mock_run:
                mock_run.return_value = MagicMock(stats={})
                with patch("cocosearch.mcp.server._register_with_git") as mock_register:
                    with patch("cocosearch.mcp.server.set_index_status"):
                        with patch("cocosearch.mcp.server.ensure_metadata_table"):
                            result = index_codebase(
                                path=str(tmp_codebase), index_name=None
                            )

        assert result["success"] is True
        # Called twice: once before indexing (status tracking) and once after
        assert mock_register.call_count == 2
        call_args = mock_register.call_args[0]
        assert call_args[1] == str(tmp_codebase)


class TestClearIndexMetadataCleanup:
    """Tests for metadata cleanup in clear_index."""

    def test_clears_metadata_via_mgmt_layer(self, mock_db_pool):
        """clear_index delegates to management layer which handles metadata."""
        from cocosearch.mcp.server import clear_index

        pool, cursor, conn = mock_db_pool(results=[(True,)])

        with patch("cocosearch.mcp.server.mgmt_clear_index") as mock_clear:
            mock_clear.return_value = {"success": True, "message": "Deleted"}
            result = clear_index(index_name="myindex")

        assert result["success"] is True
        mock_clear.assert_called_once_with("myindex")

    def test_returns_error_on_failure(self):
        """clear_index returns error dict on failure."""
        from cocosearch.mcp.server import clear_index

        with patch("cocosearch.mcp.server.mgmt_clear_index") as mock_clear:
            mock_clear.side_effect = ValueError("Index not found")
            result = clear_index(index_name="nonexistent")

        assert result["success"] is False
        assert "error" in result


class TestAutoDetectErrorResponses:
    """Tests for structured error response format."""

    @pytest.mark.asyncio
    async def test_no_project_error_format(self):
        """When find_project_root returns None, error has correct structure."""
        from cocosearch.mcp.server import search_code

        mock_detected = Path("/some/dir")

        with patch(
            "cocosearch.mcp.project_detection._detect_project",
            new_callable=AsyncMock,
            return_value=(mock_detected, "cwd"),
        ):
            with patch(
                "cocosearch.management.context.find_project_root",
                return_value=(None, None),
            ):
                with patch(
                    "cocosearch.mcp.server.resolve_index_name", return_value="some_dir"
                ):
                    with patch(
                        "cocosearch.mcp.server.mgmt_list_indexes", return_value=[]
                    ):
                        result = await search_code(query="test", ctx=_make_mock_ctx())

        assert len(result) == 1
        error_response = result[0]
        assert "error" in error_response
        assert "message" in error_response
        assert "results" in error_response
        assert error_response["results"] == []

    @pytest.mark.asyncio
    async def test_index_not_found_error_has_suggestions(self):
        """Index not found error includes CLI and MCP suggestions."""
        from cocosearch.mcp.server import search_code

        mock_root = Path("/path/to/project")

        with patch(
            "cocosearch.mcp.project_detection._detect_project",
            new_callable=AsyncMock,
            return_value=(mock_root, "roots"),
        ):
            with patch(
                "cocosearch.management.context.find_project_root",
                return_value=(mock_root, "git"),
            ):
                with patch(
                    "cocosearch.mcp.server.resolve_index_name", return_value="project"
                ):
                    with patch(
                        "cocosearch.mcp.server.mgmt_list_indexes", return_value=[]
                    ):
                        result = await search_code(query="test", ctx=_make_mock_ctx())

        error_response = result[0]
        message = error_response["message"]

        # Should include both CLI and MCP suggestions
        assert "cocosearch index" in message or "CLI" in message
        assert "index_codebase" in message or "MCP" in message

    @pytest.mark.asyncio
    async def test_collision_error_has_resolution_guidance(self):
        """Collision error includes resolution guidance."""
        from cocosearch.mcp.server import search_code

        mock_root = Path("/path/to/new_project")
        mock_indexes = [
            {"name": "project", "table_name": "codeindex_project__project_chunks"}
        ]
        mock_metadata = {
            "index_name": "project",
            "canonical_path": "/path/to/old_project",
        }

        with patch(
            "cocosearch.mcp.project_detection._detect_project",
            new_callable=AsyncMock,
            return_value=(mock_root, "roots"),
        ):
            with patch(
                "cocosearch.management.context.find_project_root",
                return_value=(mock_root, "git"),
            ):
                with patch(
                    "cocosearch.mcp.server.resolve_index_name", return_value="project"
                ):
                    with patch(
                        "cocosearch.mcp.server.mgmt_list_indexes",
                        return_value=mock_indexes,
                    ):
                        with patch(
                            "cocosearch.mcp.server.get_index_metadata",
                            return_value=mock_metadata,
                        ):
                            result = await search_code(
                                query="test", ctx=_make_mock_ctx()
                            )

        error_response = result[0]
        message = error_response["message"]

        # Should include resolution guidance
        assert (
            "cocosearch.yaml" in message
            or "indexName" in message
            or "index_name" in message
        )
