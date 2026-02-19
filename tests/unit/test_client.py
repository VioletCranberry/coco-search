"""Unit tests for cocosearch.client — HTTP client for remote CocoSearch server."""

import io
import json
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

from cocosearch.client import (
    CocoSearchClient,
    CocoSearchClientError,
    CocoSearchConnectionError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def mock_urlopen_response(data, status=200):
    """Create a mock response for urlopen."""
    resp = MagicMock()
    resp.read.return_value = json.dumps(data).encode("utf-8")
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.status = status
    return resp


# ---------------------------------------------------------------------------
# TestCocoSearchClient._request
# ---------------------------------------------------------------------------


class TestRequest:
    """Tests for the low-level _request method."""

    def test_successful_get_request(self):
        """GET request returns parsed JSON."""
        client = CocoSearchClient("http://localhost:8080")
        payload = {"ok": True}

        with patch(
            "urllib.request.urlopen", return_value=mock_urlopen_response(payload)
        ) as mock_open:
            result = client._request("GET", "/api/stats")

        assert result == payload
        req = mock_open.call_args[0][0]
        assert req.full_url == "http://localhost:8080/api/stats"
        assert req.method == "GET"
        assert req.data is None

    def test_successful_post_request_with_body(self):
        """POST request sends JSON body and returns parsed response."""
        client = CocoSearchClient("http://localhost:8080/")
        body = {"query": "hello", "index_name": "myindex"}
        response_data = {"results": [], "total": 0}

        with patch(
            "urllib.request.urlopen", return_value=mock_urlopen_response(response_data)
        ) as mock_open:
            result = client._request("POST", "/api/search", body)

        assert result == response_data
        req = mock_open.call_args[0][0]
        assert req.full_url == "http://localhost:8080/api/search"
        assert req.method == "POST"
        assert json.loads(req.data.decode("utf-8")) == body
        assert req.headers["Content-type"] == "application/json"

    def test_http_error_raises_client_error_with_json_body(self):
        """HTTPError with JSON error body raises CocoSearchClientError with message."""
        client = CocoSearchClient("http://localhost:8080")
        error_body = json.dumps({"error": "Index not found"}).encode("utf-8")
        http_error = urllib.error.HTTPError(
            url="http://localhost:8080/api/stats/missing",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=io.BytesIO(error_body),
        )

        with patch("urllib.request.urlopen", side_effect=http_error):
            with pytest.raises(CocoSearchClientError, match="Index not found"):
                client._request("GET", "/api/stats/missing")

    def test_http_error_raises_client_error_with_non_json_body(self):
        """HTTPError with non-JSON body falls back to str(e)."""
        client = CocoSearchClient("http://localhost:8080")
        http_error = urllib.error.HTTPError(
            url="http://localhost:8080/api/bad",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=io.BytesIO(b"not json"),
        )

        with patch("urllib.request.urlopen", side_effect=http_error):
            with pytest.raises(CocoSearchClientError):
                client._request("GET", "/api/bad")

    def test_url_error_raises_connection_error(self):
        """URLError raises CocoSearchConnectionError."""
        client = CocoSearchClient("http://localhost:9999")
        url_error = urllib.error.URLError("Connection refused")

        with patch("urllib.request.urlopen", side_effect=url_error):
            with pytest.raises(CocoSearchConnectionError, match="Cannot connect"):
                client._request("GET", "/api/stats")

    def test_trailing_slash_stripped_from_server_url(self):
        """Server URL trailing slash is stripped to avoid double slashes."""
        client = CocoSearchClient("http://localhost:8080/")
        assert client.server_url == "http://localhost:8080"


# ---------------------------------------------------------------------------
# TestPathTranslation
# ---------------------------------------------------------------------------


class TestPathTranslation:
    """Tests for host <-> container path translation."""

    def test_translate_path_to_container(self, monkeypatch):
        """Host path is translated to container path when prefix matches."""
        monkeypatch.setenv("COCOSEARCH_PATH_PREFIX", "/home/user/GIT:/projects")
        client = CocoSearchClient("http://localhost:8080")

        result = client._translate_path_to_container("/home/user/GIT/myapp")
        assert result == "/projects/myapp"

    def test_translate_path_to_container_with_tilde(self, monkeypatch):
        """Tilde in host prefix is expanded before matching."""
        import os

        home = os.path.expanduser("~")
        monkeypatch.setenv("COCOSEARCH_PATH_PREFIX", "~/GIT:/projects")
        client = CocoSearchClient("http://localhost:8080")

        result = client._translate_path_to_container(f"{home}/GIT/myapp")
        assert result == "/projects/myapp"

    def test_translate_path_to_host(self, monkeypatch):
        """Container path is translated back to host path."""
        monkeypatch.setenv("COCOSEARCH_PATH_PREFIX", "/home/user/GIT:/projects")
        client = CocoSearchClient("http://localhost:8080")

        result = client._translate_path_to_host("/projects/myapp/src/main.py")
        assert result == "/home/user/GIT/myapp/src/main.py"

    def test_no_translation_when_prefix_empty(self, monkeypatch):
        """Path returned unchanged when COCOSEARCH_PATH_PREFIX is not set."""
        monkeypatch.delenv("COCOSEARCH_PATH_PREFIX", raising=False)
        client = CocoSearchClient("http://localhost:8080")

        path = "/home/user/GIT/myapp"
        assert client._translate_path_to_container(path) == path
        assert client._translate_path_to_host(path) == path

    def test_no_translation_when_prefix_does_not_match(self, monkeypatch):
        """Path returned unchanged when it does not start with the prefix."""
        monkeypatch.setenv("COCOSEARCH_PATH_PREFIX", "/home/user/GIT:/projects")
        client = CocoSearchClient("http://localhost:8080")

        assert client._translate_path_to_container("/other/path") == "/other/path"
        assert client._translate_path_to_host("/other/path") == "/other/path"

    def test_invalid_prefix_format_returns_path_unchanged(self, monkeypatch):
        """Prefix with wrong number of colon-separated parts returns path unchanged."""
        monkeypatch.setenv("COCOSEARCH_PATH_PREFIX", "invalid-no-colon")
        client = CocoSearchClient("http://localhost:8080")

        path = "/some/path"
        assert client._translate_path_to_container(path) == path
        assert client._translate_path_to_host(path) == path

    def test_too_many_colons_returns_path_unchanged(self, monkeypatch):
        """Prefix with more than one colon returns path unchanged."""
        monkeypatch.setenv("COCOSEARCH_PATH_PREFIX", "a:b:c")
        client = CocoSearchClient("http://localhost:8080")

        path = "/some/path"
        assert client._translate_path_to_container(path) == path
        assert client._translate_path_to_host(path) == path


# ---------------------------------------------------------------------------
# TestSearch
# ---------------------------------------------------------------------------


class TestSearch:
    """Tests for the search method."""

    def test_search_sends_correct_body(self):
        """search() POSTs to /api/search with the right payload."""
        client = CocoSearchClient("http://localhost:8080")
        response_data = {"results": [], "total": 0}

        with patch.object(client, "_request", return_value=response_data) as mock_req:
            result = client.search(
                query="hello world",
                index_name="myindex",
                limit=5,
                min_score=0.5,
                language="python",
                use_hybrid=True,
                symbol_type=["function"],
                symbol_name="main*",
                no_cache=True,
                smart_context=True,
                context_before=3,
                context_after=3,
            )

        mock_req.assert_called_once_with(
            "POST",
            "/api/search",
            {
                "query": "hello world",
                "index_name": "myindex",
                "limit": 5,
                "min_score": 0.5,
                "language": "python",
                "use_hybrid": True,
                "symbol_type": ["function"],
                "symbol_name": "main*",
                "no_cache": True,
                "smart_context": True,
                "context_before": 3,
                "context_after": 3,
            },
        )
        assert result == response_data

    def test_search_omits_optional_fields_when_none(self):
        """search() only includes fields that are set."""
        client = CocoSearchClient("http://localhost:8080")
        response_data = {"results": [], "total": 0}

        with patch.object(client, "_request", return_value=response_data) as mock_req:
            client.search(query="test", index_name="idx")

        expected_body = {
            "query": "test",
            "index_name": "idx",
            "limit": 10,
            "min_score": 0.3,
        }
        mock_req.assert_called_once_with("POST", "/api/search", expected_body)

    def test_search_translates_file_paths_to_host(self, monkeypatch):
        """search() translates file_path in results from container to host."""
        monkeypatch.setenv("COCOSEARCH_PATH_PREFIX", "/home/user/GIT:/projects")
        client = CocoSearchClient("http://localhost:8080")

        response_data = {
            "results": [
                {"file_path": "/projects/myapp/main.py", "score": 0.9},
                {"file_path": "/projects/myapp/utils.py", "score": 0.8},
            ],
            "total": 2,
        }

        with patch.object(client, "_request", return_value=response_data):
            result = client.search(query="test", index_name="idx")

        assert result["results"][0]["file_path"] == "/home/user/GIT/myapp/main.py"
        assert result["results"][1]["file_path"] == "/home/user/GIT/myapp/utils.py"


# ---------------------------------------------------------------------------
# TestIndex
# ---------------------------------------------------------------------------


class TestIndex:
    """Tests for the index method."""

    def test_index_sends_correct_body(self, monkeypatch):
        """index() POSTs to /api/index with all parameters."""
        monkeypatch.delenv("COCOSEARCH_PATH_PREFIX", raising=False)
        client = CocoSearchClient("http://localhost:8080")

        index_response = {"index_name": "myindex", "status": "indexing"}
        stats_response = {"name": "myindex", "status": "indexed", "total_chunks": 100}

        call_count = 0

        def fake_request(method, path, body=None):
            nonlocal call_count
            call_count += 1
            if method == "POST" and path == "/api/index":
                return index_response
            if method == "GET" and path == "/api/stats/myindex":
                return stats_response
            raise AssertionError(f"Unexpected request: {method} {path}")

        with (
            patch.object(client, "_request", side_effect=fake_request) as mock_req,
            patch("time.sleep"),
        ):
            result = client.index(
                project_path="/home/user/myapp",
                index_name="myindex",
                include_patterns=["*.py", "*.js"],
                exclude_patterns=["*.pyc"],
                no_gitignore=True,
                fresh=True,
            )

        # First call should be POST /api/index with the full body
        first_call_args = mock_req.call_args_list[0][0]
        assert first_call_args[0] == "POST"
        assert first_call_args[1] == "/api/index"
        body = first_call_args[2]
        assert body["project_path"] == "/home/user/myapp"
        assert body["index_name"] == "myindex"
        assert body["include_patterns"] == ["*.py", "*.js"]
        assert body["exclude_patterns"] == ["*.pyc"]
        assert body["no_gitignore"] is True
        assert body["fresh"] is True

        # Final result should be the stats response (indexing complete)
        assert result == stats_response

    def test_index_translates_project_path_to_container(self, monkeypatch):
        """index() translates the project path before sending."""
        monkeypatch.setenv("COCOSEARCH_PATH_PREFIX", "/home/user/GIT:/projects")
        client = CocoSearchClient("http://localhost:8080")

        index_response = {"index_name": "myapp", "status": "indexed"}

        with (
            patch.object(client, "_request", return_value=index_response) as mock_req,
            patch("time.sleep"),
        ):
            client.index(project_path="/home/user/GIT/myapp")

        first_call = mock_req.call_args_list[0]
        body = first_call[0][2]
        assert body["project_path"] == "/projects/myapp"

    def test_index_polls_until_indexing_complete(self, monkeypatch):
        """index() polls /api/stats/{name} until status is no longer 'indexing'."""
        monkeypatch.delenv("COCOSEARCH_PATH_PREFIX", raising=False)
        client = CocoSearchClient("http://localhost:8080")

        index_response = {"index_name": "myindex", "status": "indexing"}
        poll_responses = [
            {"name": "myindex", "status": "indexing"},
            {"name": "myindex", "status": "indexing"},
            {"name": "myindex", "status": "indexed", "total_chunks": 42},
        ]
        poll_iter = iter(poll_responses)

        def fake_request(method, path, body=None):
            if method == "POST" and path == "/api/index":
                return index_response
            if method == "GET" and path == "/api/stats/myindex":
                return next(poll_iter)
            raise AssertionError(f"Unexpected: {method} {path}")

        with (
            patch.object(client, "_request", side_effect=fake_request),
            patch("time.sleep") as mock_sleep,
        ):
            result = client.index(
                project_path="/some/path",
                index_name="myindex",
                poll_interval=1.0,
            )

        assert result["status"] == "indexed"
        assert result["total_chunks"] == 42
        # sleep called once per poll iteration (3 times: 2 indexing + 1 indexed)
        assert mock_sleep.call_count == 3

    def test_index_returns_initial_result_when_no_index_name(self, monkeypatch):
        """index() returns initial POST result if resolved_name is empty."""
        monkeypatch.delenv("COCOSEARCH_PATH_PREFIX", raising=False)
        client = CocoSearchClient("http://localhost:8080")

        # No index_name in response and no index_name passed
        index_response = {"status": "accepted"}

        with (
            patch.object(client, "_request", return_value=index_response),
            patch("time.sleep"),
        ):
            result = client.index(project_path="/some/path")

        assert result == index_response

    def test_index_stops_polling_on_client_error(self, monkeypatch):
        """index() stops polling if stats request raises an error."""
        monkeypatch.delenv("COCOSEARCH_PATH_PREFIX", raising=False)
        client = CocoSearchClient("http://localhost:8080")

        index_response = {"index_name": "myindex", "status": "indexing"}

        call_count = 0

        def fake_request(method, path, body=None):
            nonlocal call_count
            if method == "POST":
                return index_response
            call_count += 1
            raise CocoSearchClientError("Server error")

        with (
            patch.object(client, "_request", side_effect=fake_request),
            patch("time.sleep"),
        ):
            result = client.index(project_path="/some/path", index_name="myindex")

        # Returns the initial POST result since polling broke
        assert result == index_response
        assert call_count == 1


# ---------------------------------------------------------------------------
# TestStats
# ---------------------------------------------------------------------------


class TestStats:
    """Tests for the stats method."""

    def test_stats_with_index_name(self):
        """stats(index_name) calls GET /api/stats/{name}."""
        client = CocoSearchClient("http://localhost:8080")
        stats_data = {"name": "myindex", "total_chunks": 100}

        with patch.object(client, "_request", return_value=stats_data) as mock_req:
            result = client.stats("myindex")

        mock_req.assert_called_once_with("GET", "/api/stats/myindex")
        assert result == stats_data

    def test_stats_without_index_name(self):
        """stats() without index_name calls GET /api/stats."""
        client = CocoSearchClient("http://localhost:8080")
        stats_data = [{"name": "idx1"}, {"name": "idx2"}]

        with patch.object(client, "_request", return_value=stats_data) as mock_req:
            result = client.stats()

        mock_req.assert_called_once_with("GET", "/api/stats")
        assert result == stats_data


# ---------------------------------------------------------------------------
# TestListIndexes
# ---------------------------------------------------------------------------


class TestListIndexes:
    """Tests for the list_indexes method."""

    def test_list_indexes_returns_list(self):
        """list_indexes() calls GET /api/list and returns the list."""
        client = CocoSearchClient("http://localhost:8080")
        indexes = [{"name": "idx1"}, {"name": "idx2"}]

        with patch.object(client, "_request", return_value=indexes) as mock_req:
            result = client.list_indexes()

        mock_req.assert_called_once_with("GET", "/api/list")
        assert result == indexes

    def test_list_indexes_returns_empty_list_for_non_list_response(self):
        """list_indexes() returns [] if server returns a dict instead of list."""
        client = CocoSearchClient("http://localhost:8080")

        with patch.object(client, "_request", return_value={"error": "unexpected"}):
            result = client.list_indexes()

        assert result == []


# ---------------------------------------------------------------------------
# TestClear
# ---------------------------------------------------------------------------


class TestClear:
    """Tests for the clear method."""

    def test_clear_sends_post_with_index_name(self):
        """clear() POSTs to /api/delete-index with the index name."""
        client = CocoSearchClient("http://localhost:8080")
        response = {"success": True}

        with patch.object(client, "_request", return_value=response) as mock_req:
            result = client.clear("myindex")

        mock_req.assert_called_once_with(
            "POST", "/api/delete-index", {"index_name": "myindex"}
        )
        assert result == response


# ---------------------------------------------------------------------------
# TestAnalyze
# ---------------------------------------------------------------------------


class TestAnalyze:
    """Tests for the analyze method."""

    def test_analyze_sends_correct_body(self):
        """analyze() POSTs to /api/analyze with all parameters."""
        client = CocoSearchClient("http://localhost:8080")
        response = {"stages": [], "total_time_ms": 50}

        with patch.object(client, "_request", return_value=response) as mock_req:
            result = client.analyze(
                query="search query",
                index_name="myindex",
                limit=20,
                min_score=0.1,
                language="python",
                use_hybrid=True,
                symbol_type=["class"],
                symbol_name="MyClass*",
            )

        mock_req.assert_called_once_with(
            "POST",
            "/api/analyze",
            {
                "query": "search query",
                "index_name": "myindex",
                "limit": 20,
                "min_score": 0.1,
                "language": "python",
                "use_hybrid": True,
                "symbol_type": ["class"],
                "symbol_name": "MyClass*",
            },
        )
        assert result == response

    def test_analyze_omits_optional_fields_when_none(self):
        """analyze() only includes set fields."""
        client = CocoSearchClient("http://localhost:8080")

        with patch.object(client, "_request", return_value={}) as mock_req:
            client.analyze(query="test", index_name="idx")

        mock_req.assert_called_once_with(
            "POST",
            "/api/analyze",
            {
                "query": "test",
                "index_name": "idx",
                "limit": 10,
                "min_score": 0.3,
            },
        )


# ---------------------------------------------------------------------------
# TestLanguages
# ---------------------------------------------------------------------------


class TestLanguages:
    """Tests for the languages method."""

    def test_languages_returns_list(self):
        """languages() calls GET /api/languages and returns the list."""
        client = CocoSearchClient("http://localhost:8080")
        lang_data = [
            {"name": "python", "extensions": [".py"], "symbols": True, "context": True},
            {"name": "go", "extensions": [".go"], "symbols": True, "context": False},
        ]

        with patch.object(client, "_request", return_value=lang_data) as mock_req:
            result = client.languages()

        mock_req.assert_called_once_with("GET", "/api/languages")
        assert result == lang_data

    def test_languages_returns_empty_list_for_non_list_response(self):
        """languages() returns [] if server returns a non-list."""
        client = CocoSearchClient("http://localhost:8080")

        with patch.object(client, "_request", return_value={"unexpected": True}):
            result = client.languages()

        assert result == []


# ---------------------------------------------------------------------------
# TestGrammars
# ---------------------------------------------------------------------------


class TestGrammars:
    """Tests for the grammars method."""

    def test_grammars_returns_list(self):
        """grammars() calls GET /api/grammars and returns the list."""
        client = CocoSearchClient("http://localhost:8080")
        grammar_data = [
            {
                "name": "GitHub Actions",
                "base_language": "yaml",
                "path_patterns": [".github/workflows/*.yml"],
            },
            {"name": "Terraform", "base_language": "hcl", "path_patterns": ["*.tf"]},
        ]

        with patch.object(client, "_request", return_value=grammar_data) as mock_req:
            result = client.grammars()

        mock_req.assert_called_once_with("GET", "/api/grammars")
        assert result == grammar_data

    def test_grammars_returns_empty_list_for_non_list_response(self):
        """grammars() returns [] if server returns a non-list."""
        client = CocoSearchClient("http://localhost:8080")

        with patch.object(client, "_request", return_value={"unexpected": True}):
            result = client.grammars()

        assert result == []
