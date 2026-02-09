"""Tests for cocosearch.indexer.preflight module."""

import urllib.error

import psycopg
import pytest
from unittest.mock import patch, MagicMock


from cocosearch.indexer.preflight import check_infrastructure


class TestCheckInfrastructure:
    """Tests for check_infrastructure."""

    def test_success_when_both_reachable(self):
        """No exception when both PostgreSQL and Ollama are reachable."""
        mock_conn = MagicMock()
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect", return_value=mock_conn
        ):
            with patch("cocosearch.indexer.preflight.urllib.request.urlopen"):
                check_infrastructure("postgresql://localhost/test", None)

    def test_postgres_unreachable_raises_connection_error(self):
        """Raises ConnectionError when PostgreSQL is unreachable."""
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect",
            side_effect=psycopg.OperationalError("connection refused"),
        ):
            with pytest.raises(ConnectionError, match="PostgreSQL is not reachable"):
                check_infrastructure("postgresql://user:pass@localhost:5432/db", None)

    def test_postgres_error_includes_host(self):
        """ConnectionError message includes the host:port from the URL."""
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect",
            side_effect=psycopg.OperationalError("connection refused"),
        ):
            with pytest.raises(ConnectionError, match="localhost:5432"):
                check_infrastructure("postgresql://user:pass@localhost:5432/db", None)

    def test_ollama_unreachable_raises_connection_error(self):
        """Raises ConnectionError when Ollama is unreachable."""
        mock_conn = MagicMock()
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect", return_value=mock_conn
        ):
            with patch(
                "cocosearch.indexer.preflight.urllib.request.urlopen",
                side_effect=urllib.error.URLError("connection refused"),
            ):
                with pytest.raises(ConnectionError, match="Ollama is not reachable"):
                    check_infrastructure("postgresql://localhost/test", None)

    def test_ollama_error_includes_url(self):
        """ConnectionError message includes the Ollama URL attempted."""
        mock_conn = MagicMock()
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect", return_value=mock_conn
        ):
            with patch(
                "cocosearch.indexer.preflight.urllib.request.urlopen",
                side_effect=urllib.error.URLError("connection refused"),
            ):
                with pytest.raises(ConnectionError, match="http://myhost:9999"):
                    check_infrastructure(
                        "postgresql://localhost/test", "http://myhost:9999"
                    )

    def test_uses_default_ollama_url_when_none(self):
        """Uses default Ollama URL (localhost:11434) when None is passed."""
        mock_conn = MagicMock()
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect", return_value=mock_conn
        ):
            with patch(
                "cocosearch.indexer.preflight.urllib.request.urlopen"
            ) as mock_urlopen:
                check_infrastructure("postgresql://localhost/test", None)
                mock_urlopen.assert_called_once_with(
                    "http://localhost:11434", timeout=3
                )

    def test_postgres_checked_before_ollama(self):
        """PostgreSQL is checked first; Ollama check is skipped if PG fails."""
        with patch(
            "cocosearch.indexer.preflight.psycopg.connect",
            side_effect=psycopg.OperationalError("connection refused"),
        ):
            with patch(
                "cocosearch.indexer.preflight.urllib.request.urlopen"
            ) as mock_urlopen:
                with pytest.raises(ConnectionError, match="PostgreSQL"):
                    check_infrastructure("postgresql://localhost/test", None)
                mock_urlopen.assert_not_called()
