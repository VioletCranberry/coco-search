"""Tests for cocosearch.config.env_validation module."""

import os
from unittest.mock import patch

from cocosearch.config.env_validation import (
    DEFAULT_DATABASE_URL,
    get_database_url,
    validate_required_env_vars,
)


class TestGetDatabaseUrl:
    """Tests for get_database_url function."""

    def test_returns_default_when_no_env_var(self):
        """Should return default URL when COCOSEARCH_DATABASE_URL not set."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_database_url()
        assert result == DEFAULT_DATABASE_URL
        assert "cocosearch:cocosearch" in result

    def test_returns_env_var_when_set(self):
        """Should return env var value when COCOSEARCH_DATABASE_URL is set."""
        custom_url = "postgresql://custom:pass@host:5432/mydb"
        with patch.dict(os.environ, {"COCOSEARCH_DATABASE_URL": custom_url}, clear=True):
            result = get_database_url()
        assert result == custom_url

    def test_bridges_to_cocoindex_env_var(self):
        """Should set COCOINDEX_DATABASE_URL when not already set."""
        with patch.dict(os.environ, {}, clear=True):
            url = get_database_url()
            assert os.environ.get("COCOINDEX_DATABASE_URL") == url

    def test_does_not_override_existing_cocoindex_var(self):
        """Should not override COCOINDEX_DATABASE_URL if already set."""
        existing = "postgresql://other:pass@host:5432/other"
        with patch.dict(os.environ, {"COCOINDEX_DATABASE_URL": existing}, clear=True):
            get_database_url()
            assert os.environ["COCOINDEX_DATABASE_URL"] == existing


class TestValidateRequiredEnvVars:
    """Tests for validate_required_env_vars after default addition."""

    def test_no_errors_without_database_url(self):
        """Should return no errors when DATABASE_URL is not set (has default)."""
        with patch.dict(os.environ, {}, clear=True):
            errors = validate_required_env_vars()
        assert len(errors) == 0

    def test_no_errors_with_database_url(self):
        """Should return no errors when DATABASE_URL is set."""
        with patch.dict(os.environ, {"COCOSEARCH_DATABASE_URL": "postgresql://x:x@localhost/db"}, clear=True):
            errors = validate_required_env_vars()
        assert len(errors) == 0
