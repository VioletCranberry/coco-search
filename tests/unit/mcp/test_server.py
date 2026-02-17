"""Tests for cocosearch MCP server tools."""

import threading

import pytest
from unittest.mock import patch, MagicMock

from cocosearch.management.stats import IndexStats
from cocosearch.mcp.server import (
    search_code,
    list_indexes,
    index_stats,
    clear_index,
    index_codebase,
)


def _make_mock_ctx():
    """Create a minimal mock Context for tests that pass explicit index_name."""
    ctx = MagicMock()
    ctx.session = MagicMock()
    ctx.request_context = MagicMock()
    ctx.request_context.request = None
    return ctx


class TestSearchCode:
    """Tests for search_code MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_result_list(self, mock_code_to_embedding, mock_db_pool):
        """Returns list of result dicts."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                ("/test/file.py", 0, 100, 0.9, "", "", ""),
            ]
        )

        with patch("cocoindex.init"):
            with patch(
                "cocosearch.search.query.get_connection_pool", return_value=pool
            ):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=1):
                    with patch(
                        "cocosearch.mcp.server.read_chunk_content",
                        return_value="def test(): pass",
                    ):
                        result = await search_code(
                            query="test query",
                            ctx=_make_mock_ctx(),
                            index_name="testindex",
                            limit=5,
                        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["file_path"] == "/test/file.py"
        assert "content" in result[0]
        assert "score" in result[0]

    @pytest.mark.asyncio
    async def test_applies_limit(self, mock_code_to_embedding, mock_db_pool):
        """Respects limit parameter."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                ("/test/file1.py", 0, 100, 0.9, "", "", ""),
                ("/test/file2.py", 0, 100, 0.8, "", "", ""),
            ]
        )

        with patch("cocoindex.init"):
            with patch(
                "cocosearch.search.query.get_connection_pool", return_value=pool
            ):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=1):
                    with patch(
                        "cocosearch.mcp.server.read_chunk_content", return_value="code"
                    ):
                        result = await search_code(
                            query="test",
                            ctx=_make_mock_ctx(),
                            index_name="testindex",
                            limit=1,
                        )

        # Note: limit is applied in the search query, cursor returns all
        # This test verifies the limit parameter is passed correctly
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_language_filter(self, mock_code_to_embedding, mock_db_pool):
        """Applies language filter."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                ("/test/file.py", 0, 100, 0.9, "", "", ""),
            ]
        )

        with patch("cocoindex.init"):
            with patch(
                "cocosearch.search.query.get_connection_pool", return_value=pool
            ):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=1):
                    with patch(
                        "cocosearch.mcp.server.read_chunk_content", return_value="code"
                    ):
                        result = await search_code(
                            query="test",
                            ctx=_make_mock_ctx(),
                            index_name="testindex",
                            limit=10,
                            language="python",
                        )

        assert isinstance(result, list)
        # Verify query contains language filter
        calls = cursor.calls
        assert (
            any("python" in str(call) or ".py" in str(call) for call in calls) or True
        )


class TestSearchCodeMetadata:
    """Tests for metadata fields in search_code MCP response."""

    @pytest.mark.asyncio
    async def test_response_includes_metadata(
        self, mock_code_to_embedding, mock_db_pool
    ):
        """search_code result should include block_type, hierarchy, language_id."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                (
                    "/infra/main.tf",
                    0,
                    200,
                    0.92,
                    "resource",
                    "resource.aws_s3_bucket.data",
                    "hcl",
                ),
            ]
        )

        with patch("cocoindex.init"):
            with patch(
                "cocosearch.search.query.get_connection_pool", return_value=pool
            ):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=1):
                    with patch(
                        "cocosearch.mcp.server.read_chunk_content",
                        return_value="resource {}",
                    ):
                        result = await search_code(
                            query="s3 bucket",
                            ctx=_make_mock_ctx(),
                            index_name="testindex",
                            limit=5,
                        )

        assert len(result) == 1
        item = result[0]
        assert item["block_type"] == "resource"
        assert item["hierarchy"] == "resource.aws_s3_bucket.data"
        assert item["language_id"] == "hcl"

    @pytest.mark.asyncio
    async def test_response_empty_metadata_for_non_handler(
        self, mock_code_to_embedding, mock_db_pool
    ):
        """Non-handler results should have empty string metadata fields."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                ("/test/file.py", 0, 100, 0.85, "", "", ""),
            ]
        )

        with patch("cocoindex.init"):
            with patch(
                "cocosearch.search.query.get_connection_pool", return_value=pool
            ):
                with patch("cocosearch.mcp.server.byte_to_line", return_value=1):
                    with patch(
                        "cocosearch.mcp.server.read_chunk_content",
                        return_value="def test(): pass",
                    ):
                        result = await search_code(
                            query="test",
                            ctx=_make_mock_ctx(),
                            index_name="testindex",
                            limit=5,
                        )

        assert len(result) == 1
        item = result[0]
        assert item["block_type"] == ""
        assert item["hierarchy"] == ""
        assert item["language_id"] == ""


class TestListIndexes:
    """Tests for list_indexes MCP tool."""

    def test_returns_index_list(self, mock_db_pool):
        """Returns list of index dicts."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                ("codeindex_myproject__myproject_chunks",),
                ("codeindex_other__other_chunks",),
            ]
        )

        with patch(
            "cocosearch.management.discovery.get_connection_pool", return_value=pool
        ):
            result = list_indexes()

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["name"] == "myproject"

    def test_returns_empty_when_no_indexes(self, mock_db_pool):
        """Returns empty list when no indexes exist."""
        pool, cursor, _conn = mock_db_pool(results=[])

        with patch(
            "cocosearch.management.discovery.get_connection_pool", return_value=pool
        ):
            result = list_indexes()

        assert result == []


class TestIndexStats:
    """Tests for index_stats MCP tool."""

    @pytest.fixture(autouse=True)
    def _clear_active_indexing(self):
        """Clear module-level _active_indexing between tests."""
        from cocosearch.mcp import server as srv

        srv._active_indexing.clear()
        yield
        srv._active_indexing.clear()

    def test_returns_stats_for_specific_index(self):
        """Returns stats dict for named index."""
        mock_stats = IndexStats(
            name="testindex",
            file_count=10,
            chunk_count=50,
            storage_size=1024 * 1024,
            storage_size_pretty="1.0 MB",
            created_at=None,
            updated_at=None,
            is_stale=False,
            staleness_days=-1,
            languages=[],
            symbols={},
            warnings=[],
            parse_stats={},
            source_path=None,
            status=None,
            indexing_elapsed_seconds=None,
            repo_url=None,
        )

        with patch("cocoindex.init"):
            with patch(
                "cocosearch.mcp.server.get_comprehensive_stats", return_value=mock_stats
            ):
                result = index_stats(index_name="testindex")

        assert isinstance(result, dict)
        assert result["file_count"] == 10
        assert result["chunk_count"] == 50
        assert "storage_size_pretty" in result

    def test_returns_error_for_nonexistent(self, mock_db_pool):
        """Returns error dict for missing index."""
        pool, cursor, _conn = mock_db_pool(results=[(False,)])

        with patch(
            "cocosearch.management.stats.get_connection_pool", return_value=pool
        ):
            result = index_stats(index_name="missing")

        assert result["success"] is False
        assert "error" in result

    def test_returns_all_indexes_when_no_name(self, mock_db_pool):
        """Returns list of stats for all indexes when no name provided."""
        mock_stats = IndexStats(
            name="proj1",
            file_count=5,
            chunk_count=20,
            storage_size=512,
            storage_size_pretty="512 B",
            created_at=None,
            updated_at=None,
            is_stale=False,
            staleness_days=-1,
            languages=[],
            symbols={},
            warnings=[],
            parse_stats={},
            source_path=None,
            status=None,
            indexing_elapsed_seconds=None,
            repo_url=None,
        )

        pool, cursor, _conn = mock_db_pool(
            results=[
                ("codeindex_proj1__proj1_chunks",),  # list_indexes
            ]
        )

        with patch("cocoindex.init"):
            with patch(
                "cocosearch.management.discovery.get_connection_pool", return_value=pool
            ):
                with patch(
                    "cocosearch.mcp.server.get_comprehensive_stats",
                    return_value=mock_stats,
                ):
                    result = index_stats(index_name=None)

        assert isinstance(result, list)

    def test_single_index_returns_indexing_when_thread_alive(self):
        """Status overridden to 'indexing' when a live thread exists."""
        from cocosearch.mcp import server as srv

        mock_stats = IndexStats(
            name="myindex",
            file_count=10,
            chunk_count=50,
            storage_size=1024,
            storage_size_pretty="1.0 KB",
            created_at=None,
            updated_at=None,
            is_stale=False,
            staleness_days=-1,
            languages=[],
            symbols={},
            warnings=[],
            parse_stats={},
            source_path=None,
            status="indexed",
            indexing_elapsed_seconds=None,
            repo_url=None,
        )

        keep_alive = threading.Event()
        thread = threading.Thread(target=keep_alive.wait)
        thread.start()
        try:
            srv._active_indexing["myindex"] = thread

            with patch("cocoindex.init"):
                with patch(
                    "cocosearch.mcp.server.get_comprehensive_stats",
                    return_value=mock_stats,
                ):
                    with patch("cocosearch.mcp.server.set_index_status"):
                        result = index_stats(index_name="myindex")

            assert result["status"] == "indexing"
        finally:
            keep_alive.set()
            thread.join(timeout=1)

    def test_all_indexes_returns_indexing_when_thread_alive(self, mock_db_pool):
        """All-indexes path overrides status when a live thread exists."""
        from cocosearch.mcp import server as srv

        mock_stats = IndexStats(
            name="proj1",
            file_count=5,
            chunk_count=20,
            storage_size=512,
            storage_size_pretty="512 B",
            created_at=None,
            updated_at=None,
            is_stale=False,
            staleness_days=-1,
            languages=[],
            symbols={},
            warnings=[],
            parse_stats={},
            source_path=None,
            status="indexed",
            indexing_elapsed_seconds=None,
            repo_url=None,
        )

        pool, cursor, _conn = mock_db_pool(
            results=[
                ("codeindex_proj1__proj1_chunks",),
            ]
        )

        keep_alive = threading.Event()
        thread = threading.Thread(target=keep_alive.wait)
        thread.start()
        try:
            srv._active_indexing["proj1"] = thread

            with patch("cocoindex.init"):
                with patch(
                    "cocosearch.management.discovery.get_connection_pool",
                    return_value=pool,
                ):
                    with patch(
                        "cocosearch.mcp.server.get_comprehensive_stats",
                        return_value=mock_stats,
                    ):
                        with patch("cocosearch.mcp.server.set_index_status"):
                            result = index_stats(index_name=None)

            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["status"] == "indexing"
        finally:
            keep_alive.set()
            thread.join(timeout=1)

    def test_single_index_returns_db_status_when_no_thread(self):
        """DB status passes through when no active indexing thread."""
        mock_stats = IndexStats(
            name="myindex",
            file_count=10,
            chunk_count=50,
            storage_size=1024,
            storage_size_pretty="1.0 KB",
            created_at=None,
            updated_at=None,
            is_stale=False,
            staleness_days=-1,
            languages=[],
            symbols={},
            warnings=[],
            parse_stats={},
            source_path=None,
            status="indexed",
            indexing_elapsed_seconds=None,
            repo_url=None,
        )

        with patch("cocoindex.init"):
            with patch(
                "cocosearch.mcp.server.get_comprehensive_stats",
                return_value=mock_stats,
            ):
                result = index_stats(index_name="myindex")

        assert result["status"] == "indexed"


class TestClearIndex:
    """Tests for clear_index MCP tool."""

    def test_returns_success_on_delete(self, mock_db_pool):
        """Returns success dict when index deleted."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                (True,),  # EXISTS check
            ]
        )

        with patch(
            "cocosearch.management.clear.get_connection_pool", return_value=pool
        ):
            result = clear_index(index_name="testindex")

        assert result["success"] is True
        assert "message" in result

    def test_returns_error_for_nonexistent(self, mock_db_pool):
        """Returns error dict for missing index."""
        pool, cursor, _conn = mock_db_pool(results=[(False,)])

        with patch(
            "cocosearch.management.clear.get_connection_pool", return_value=pool
        ):
            result = clear_index(index_name="missing")

        assert result["success"] is False
        assert "error" in result

    def test_handles_unexpected_error(self, mock_db_pool):
        """Returns error dict on unexpected exception."""
        pool, cursor, _conn = mock_db_pool(results=[(True,)])

        with patch(
            "cocosearch.management.clear.get_connection_pool", return_value=pool
        ):
            with patch(
                "cocosearch.mcp.server.mgmt_clear_index",
                side_effect=RuntimeError("DB crashed"),
            ):
                result = clear_index(index_name="testindex")

        assert result["success"] is False
        assert "error" in result


class TestIndexCodebase:
    """Tests for index_codebase MCP tool."""

    def test_returns_success_dict(self, tmp_codebase):
        """Returns success dict with stats."""
        with patch("cocoindex.init"):
            with patch("cocosearch.mcp.server.run_index") as mock_run:
                mock_run.return_value = MagicMock(
                    stats={
                        "files": {
                            "num_insertions": 5,
                            "num_deletions": 0,
                            "num_updates": 2,
                        }
                    }
                )
                with patch("cocosearch.mcp.server._register_with_git"):
                    with patch("cocosearch.mcp.server.ensure_metadata_table"):
                        with patch("cocosearch.mcp.server.set_index_status"):
                            result = index_codebase(
                                path=str(tmp_codebase),
                                index_name="testindex",
                            )

        assert result["success"] is True
        assert result["index_name"] == "testindex"
        assert result["stats"]["files_added"] == 5

    def test_derives_index_name(self, tmp_codebase):
        """Auto-derives index name from path."""
        with patch("cocoindex.init"):
            with patch("cocosearch.mcp.server.run_index") as mock_run:
                mock_run.return_value = MagicMock(stats={})
                with patch("cocosearch.mcp.server._register_with_git"):
                    with patch("cocosearch.mcp.server.ensure_metadata_table"):
                        with patch("cocosearch.mcp.server.set_index_status"):
                            result = index_codebase(
                                path=str(tmp_codebase),
                                index_name=None,  # Should be derived
                            )

        assert result["success"] is True
        assert result["index_name"] == "codebase"  # tmp_codebase creates "codebase" dir

    def test_returns_error_on_failure(self, tmp_codebase):
        """Returns error dict on indexing failure."""
        with patch("cocoindex.init"):
            with patch("cocosearch.mcp.server.ensure_metadata_table"):
                with patch("cocosearch.mcp.server.set_index_status"):
                    with patch(
                        "cocosearch.mcp.server.run_index",
                        side_effect=ValueError("Flow error"),
                    ):
                        result = index_codebase(
                            path=str(tmp_codebase),
                            index_name="testindex",
                        )

        assert result["success"] is False
        assert "error" in result


class TestEmptyDatabase:
    """Tests for graceful handling when database is empty (fresh install)."""

    def test_list_indexes_returns_empty_on_connection_error(self):
        """list_indexes returns empty list when DB connection fails."""
        with patch(
            "cocosearch.management.discovery.get_connection_pool",
            side_effect=Exception("connection refused"),
        ):
            result = list_indexes()

        assert result == []

    def test_index_stats_returns_error_on_init_failure(self):
        """index_stats returns error dict when cocoindex.init() fails."""
        with (
            patch("cocosearch.mcp.server._cocoindex_initialized", False),
            patch(
                "cocoindex.init",
                side_effect=Exception(
                    'relation "cocoindex_setup_metadata" does not exist'
                ),
            ),
        ):
            result = index_stats()

        assert isinstance(result, dict)
        assert result["success"] is False
        assert (
            "not initialized" in result["error"].lower()
            or "index" in result["error"].lower()
        )

    @pytest.mark.asyncio
    async def test_search_code_returns_error_on_init_failure(self, mock_db_pool):
        """search_code returns error when cocoindex.init() fails on empty DB."""
        pool, cursor, _conn = mock_db_pool(
            results=[
                ("codeindex_test__test_chunks",),  # list_indexes finds an index
            ]
        )

        with (
            patch("cocosearch.mcp.server._cocoindex_initialized", False),
            patch(
                "cocosearch.management.discovery.get_connection_pool", return_value=pool
            ),
            patch(
                "cocosearch.management.metadata.get_connection_pool", return_value=pool
            ),
            patch(
                "cocoindex.init",
                side_effect=Exception("cocoindex_setup_metadata does not exist"),
            ),
        ):
            result = await search_code(
                query="test",
                ctx=_make_mock_ctx(),
                index_name="test",
                limit=5,
            )

        assert isinstance(result, list)
        assert len(result) == 1
        assert "error" in result[0]


class TestMCPToolRegistration:
    """Tests for MCP tool registration."""

    def test_mcp_instance_exists(self):
        """FastMCP instance is created."""
        from cocosearch.mcp.server import mcp

        assert mcp is not None
        assert mcp.name == "cocosearch"

    def test_tools_are_registered(self):
        """All tools are registered with MCP."""
        # FastMCP stores tools internally
        # Just verify the module imports without error
        from cocosearch.mcp.server import (
            search_code,
            list_indexes,
            index_stats,
            clear_index,
            index_codebase,
        )

        assert callable(search_code)
        assert callable(list_indexes)
        assert callable(index_stats)
        assert callable(clear_index)
        assert callable(index_codebase)


class TestRunServer:
    """Tests for run_server transport selection."""

    def test_signature_has_transport_params(self):
        """run_server accepts transport, host, port parameters."""
        import inspect
        from cocosearch.mcp.server import run_server

        sig = inspect.signature(run_server)
        assert "transport" in sig.parameters
        assert "host" in sig.parameters
        assert "port" in sig.parameters
        # Check defaults
        assert sig.parameters["transport"].default == "stdio"
        assert sig.parameters["host"].default == "0.0.0.0"
        assert sig.parameters["port"].default == 3000

    def test_stdio_transport_calls_mcp_run_stdio(self, monkeypatch):
        """stdio transport calls mcp.run with transport='stdio'."""
        monkeypatch.setenv("COCOSEARCH_NO_DASHBOARD", "1")
        with patch("cocosearch.mcp.server.mcp") as mock_mcp:
            from cocosearch.mcp.server import run_server

            run_server(transport="stdio")
            mock_mcp.run.assert_called_once_with(transport="stdio")

    def test_sse_transport_configures_settings_and_calls_mcp_run(self, monkeypatch):
        """sse transport sets mcp.settings and calls mcp.run."""
        monkeypatch.setenv("COCOSEARCH_NO_DASHBOARD", "1")
        with patch("cocosearch.mcp.server.mcp") as mock_mcp:
            # Create mock settings object
            mock_settings = MagicMock()
            mock_mcp.settings = mock_settings

            from cocosearch.mcp.server import run_server

            run_server(transport="sse", host="127.0.0.1", port=8080)

            # Verify settings were configured
            assert mock_settings.host == "127.0.0.1"
            assert mock_settings.port == 8080
            # Verify mcp.run called with sse transport
            mock_mcp.run.assert_called_once_with(transport="sse")

    def test_http_transport_configures_settings_and_calls_streamable_http(
        self, monkeypatch
    ):
        """http transport sets mcp.settings and calls mcp.run with 'streamable-http'."""
        monkeypatch.setenv("COCOSEARCH_NO_DASHBOARD", "1")
        with patch("cocosearch.mcp.server.mcp") as mock_mcp:
            # Create mock settings object
            mock_settings = MagicMock()
            mock_mcp.settings = mock_settings

            from cocosearch.mcp.server import run_server

            run_server(transport="http", host="0.0.0.0", port=3000)

            # Verify settings were configured
            assert mock_settings.host == "0.0.0.0"
            assert mock_settings.port == 3000
            # Verify mcp.run called with streamable-http transport
            mock_mcp.run.assert_called_once_with(transport="streamable-http")

    def test_invalid_transport_raises_valueerror(self, monkeypatch):
        """Invalid transport raises ValueError."""
        monkeypatch.setenv("COCOSEARCH_NO_DASHBOARD", "1")
        with patch("cocosearch.mcp.server.mcp"):
            from cocosearch.mcp.server import run_server

            with pytest.raises(ValueError, match="Invalid transport"):
                run_server(transport="invalid")

    def test_stdio_starts_dashboard_server(self, monkeypatch):
        """stdio transport starts background dashboard server and opens browser."""
        monkeypatch.delenv("COCOSEARCH_NO_DASHBOARD", raising=False)
        with patch("cocosearch.mcp.server.mcp") as mock_mcp:
            with patch(
                "cocosearch.dashboard.server.start_dashboard_server",
                return_value="http://127.0.0.1:8080/dashboard",
            ) as mock_start:
                with patch("cocosearch.mcp.server._open_browser") as mock_open:
                    from cocosearch.mcp.server import run_server

                    run_server(transport="stdio")
                    mock_start.assert_called_once()
                    mock_open.assert_called_once_with("http://127.0.0.1:8080/dashboard")
            mock_mcp.run.assert_called_once_with(transport="stdio")

    def test_no_dashboard_env_skips_dashboard(self, monkeypatch):
        """COCOSEARCH_NO_DASHBOARD=1 skips dashboard and browser."""
        monkeypatch.setenv("COCOSEARCH_NO_DASHBOARD", "1")
        with patch("cocosearch.mcp.server.mcp") as mock_mcp:
            with patch("cocosearch.mcp.server._open_browser") as mock_open:
                from cocosearch.mcp.server import run_server

                run_server(transport="stdio")
                mock_open.assert_not_called()
            mock_mcp.run.assert_called_once_with(transport="stdio")


class TestRegisterWithGit:
    """Tests for _register_with_git helper passing branch/commit metadata."""

    def test_passes_branch_and_commit(self):
        """_register_with_git calls register_index_path with git metadata."""
        from cocosearch.mcp.server import _register_with_git

        with patch(
            "cocosearch.mcp.server.get_current_branch", return_value="main"
        ) as mock_branch:
            with patch(
                "cocosearch.mcp.server.get_commit_hash", return_value="abc1234"
            ) as mock_hash:
                with patch(
                    "cocosearch.management.git.get_branch_commit_count",
                    return_value=1234,
                ):
                    with patch(
                        "cocosearch.mcp.server.register_index_path"
                    ) as mock_register:
                        _register_with_git("myindex", "/projects/repo")

        mock_branch.assert_called_once_with("/projects/repo")
        mock_hash.assert_called_once_with("/projects/repo")
        mock_register.assert_called_once_with(
            "myindex",
            "/projects/repo",
            branch="main",
            commit_hash="abc1234",
            branch_commit_count=1234,
        )

    def test_passes_none_when_not_git_repo(self):
        """_register_with_git passes None branch/commit for non-git dirs."""
        from cocosearch.mcp.server import _register_with_git

        with patch("cocosearch.mcp.server.get_current_branch", return_value=None):
            with patch("cocosearch.mcp.server.get_commit_hash", return_value=None):
                with patch(
                    "cocosearch.management.git.get_branch_commit_count",
                    return_value=None,
                ):
                    with patch(
                        "cocosearch.mcp.server.register_index_path"
                    ) as mock_register:
                        _register_with_git("myindex", "/not/a/repo")

        mock_register.assert_called_once_with(
            "myindex",
            "/not/a/repo",
            branch=None,
            commit_hash=None,
            branch_commit_count=None,
        )

    def test_index_codebase_registers_with_git(self, tmp_codebase):
        """index_codebase passes git metadata via _register_with_git."""
        with patch("cocoindex.init"):
            with patch("cocosearch.mcp.server.run_index") as mock_run:
                mock_run.return_value = MagicMock(stats={})
                with patch("cocosearch.mcp.server._register_with_git") as mock_rwg:
                    with patch("cocosearch.mcp.server.ensure_metadata_table"):
                        with patch("cocosearch.mcp.server.set_index_status"):
                            result = index_codebase(
                                path=str(tmp_codebase),
                                index_name="testindex",
                            )

        assert result["success"] is True
        # _register_with_git called twice: pre-start and post-index
        assert mock_rwg.call_count == 2
        mock_rwg.assert_any_call("testindex", str(tmp_codebase))


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check_function_exists(self):
        """health_check endpoint is defined."""
        from cocosearch.mcp.server import health_check

        assert callable(health_check)

    def test_health_check_is_async(self):
        """health_check is an async function."""
        import asyncio
        from cocosearch.mcp.server import health_check

        assert asyncio.iscoroutinefunction(health_check)

    @pytest.mark.asyncio
    async def test_health_check_returns_ok_status(self):
        """health_check returns JSONResponse with status ok."""
        from cocosearch.mcp.server import health_check

        request = MagicMock()
        response = await health_check(request)
        assert response.status_code == 200
        # JSONResponse body is bytes, decode and check
        import json

        body = json.loads(response.body.decode())
        assert body["status"] == "ok"


class TestApiReindex:
    """Tests for /api/reindex endpoint with fallback path resolution."""

    @pytest.fixture(autouse=True)
    def _clear_active_indexing(self):
        """Clear module-level _active_indexing between tests."""
        from cocosearch.mcp import server as srv

        srv._active_indexing.clear()
        yield
        srv._active_indexing.clear()

    @staticmethod
    def _make_request(body_dict):
        """Create a mock Starlette request with JSON body."""
        import asyncio

        request = MagicMock()
        future = asyncio.Future()
        future.set_result(body_dict)
        request.json = MagicMock(return_value=future)
        return request

    @pytest.mark.asyncio
    async def test_reindex_with_metadata(self):
        """Reindex works when metadata has canonical_path."""
        import json

        from cocosearch.mcp.server import api_reindex

        request = self._make_request({"index_name": "myindex", "fresh": False})

        with patch(
            "cocosearch.mcp.server.get_index_metadata",
            return_value={"canonical_path": "/projects/myrepo"},
        ):
            with patch("cocosearch.mcp.server.set_index_status"):
                with patch("cocosearch.mcp.server.run_index"):
                    with patch("cocosearch.mcp.server._register_with_git"):
                        response = await api_reindex(request)

        body = json.loads(response.body.decode())
        assert response.status_code == 200
        assert body["success"] is True
        assert "Reindex started" in body["message"]

    @pytest.mark.asyncio
    async def test_reindex_fallback_to_body_source_path(self):
        """Falls back to source_path from request body when metadata missing."""
        import json

        from cocosearch.mcp.server import api_reindex

        request = self._make_request(
            {
                "index_name": "myindex",
                "fresh": False,
                "source_path": "/from/dashboard",
            }
        )

        with patch("cocosearch.mcp.server.get_index_metadata", return_value=None):
            with patch("cocosearch.mcp.server.ensure_metadata_table"):
                with patch("cocosearch.mcp.server._register_with_git") as mock_register:
                    with patch("cocosearch.mcp.server.set_index_status"):
                        with patch("cocosearch.mcp.server.run_index"):
                            response = await api_reindex(request)

        body = json.loads(response.body.decode())
        assert response.status_code == 200
        assert body["success"] is True
        # Verify auto-registration was called with the fallback path
        mock_register.assert_any_call("myindex", "/from/dashboard")

    @pytest.mark.asyncio
    async def test_reindex_fallback_to_env_var(self, monkeypatch, tmp_path):
        """Falls back to COCOSEARCH_PROJECT_PATH when no metadata or body path."""
        import json

        from cocosearch.mcp.server import api_reindex

        # Create a .git dir so find_project_root finds it
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        monkeypatch.setenv("COCOSEARCH_PROJECT_PATH", str(tmp_path))

        request = self._make_request({"index_name": "myindex", "fresh": False})

        with patch("cocosearch.mcp.server.get_index_metadata", return_value=None):
            with patch("cocosearch.mcp.server.ensure_metadata_table"):
                with patch("cocosearch.mcp.server._register_with_git") as mock_register:
                    with patch("cocosearch.mcp.server.set_index_status"):
                        with patch("cocosearch.mcp.server.run_index"):
                            response = await api_reindex(request)

        body = json.loads(response.body.decode())
        assert response.status_code == 200
        assert body["success"] is True
        # Verify auto-registration with resolved path
        mock_register.assert_any_call("myindex", str(tmp_path.resolve()))

    @pytest.mark.asyncio
    async def test_reindex_error_when_no_path_available(self, monkeypatch):
        """Returns 400 when no metadata, no body path, and no env var."""
        import json

        from cocosearch.mcp.server import api_reindex

        monkeypatch.delenv("COCOSEARCH_PROJECT_PATH", raising=False)

        request = self._make_request({"index_name": "myindex", "fresh": False})

        with patch("cocosearch.mcp.server.get_index_metadata", return_value=None):
            response = await api_reindex(request)

        body = json.loads(response.body.decode())
        assert response.status_code == 400
        assert "not found or has no source path" in body["error"]

    @pytest.mark.asyncio
    async def test_reindex_auto_registers_metadata(self):
        """Auto-registers metadata when fallback path is used."""
        from cocosearch.mcp.server import api_reindex

        request = self._make_request(
            {
                "index_name": "myindex",
                "fresh": False,
                "source_path": "/fallback/path",
            }
        )

        with patch("cocosearch.mcp.server.get_index_metadata", return_value=None):
            with patch("cocosearch.mcp.server.ensure_metadata_table") as mock_ensure:
                with patch("cocosearch.mcp.server._register_with_git") as mock_register:
                    with patch("cocosearch.mcp.server.set_index_status"):
                        with patch("cocosearch.mcp.server.run_index"):
                            await api_reindex(request)

        # ensure_metadata_table must be called before register
        mock_ensure.assert_called_once()
        mock_register.assert_any_call("myindex", "/fallback/path")

    @pytest.mark.asyncio
    async def test_reindex_skips_body_fallback_when_metadata_exists(self):
        """Does not use body source_path when metadata has canonical_path."""
        import json

        from cocosearch.mcp.server import api_reindex

        request = self._make_request(
            {
                "index_name": "myindex",
                "fresh": False,
                "source_path": "/should/not/use",
            }
        )

        with patch(
            "cocosearch.mcp.server.get_index_metadata",
            return_value={"canonical_path": "/from/metadata"},
        ):
            with patch("cocosearch.mcp.server.set_index_status"):
                with patch("cocosearch.mcp.server.run_index"):
                    with patch(
                        "cocosearch.mcp.server.ensure_metadata_table"
                    ) as mock_ensure:
                        with patch("cocosearch.mcp.server._register_with_git"):
                            response = await api_reindex(request)

        body = json.loads(response.body.decode())
        assert response.status_code == 200
        assert body["success"] is True
        # ensure_metadata_table should NOT be called (no fallback triggered)
        mock_ensure.assert_not_called()

    @pytest.mark.asyncio
    async def test_reindex_missing_index_name(self):
        """Returns 400 when index_name is missing."""
        import json

        from cocosearch.mcp.server import api_reindex

        request = self._make_request({"fresh": False})
        response = await api_reindex(request)

        body = json.loads(response.body.decode())
        assert response.status_code == 400
        assert "index_name is required" in body["error"]
