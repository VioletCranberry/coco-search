"""Tests for Dockerfile symbol extraction."""

from cocosearch.indexer.symbols import extract_symbol_metadata


class TestDockerfileSymbols:
    """Test Dockerfile symbol extraction."""

    def test_from_with_as_produces_class(self):
        """FROM with AS clause extracts build stage as class symbol."""
        code = "FROM golang:1.21 AS builder\nRUN go build -o app .\n"
        result = extract_symbol_metadata(code, "dockerfile")

        assert result.symbol_type == "class"
        assert result.symbol_name == "builder"
        assert "FROM" in result.symbol_signature

    def test_arg_with_default_produces_variable(self):
        """ARG with default value extracts variable symbol."""
        code = "ARG VERSION=dev\n"
        result = extract_symbol_metadata(code, "dockerfile")

        # "variable" maps to "function" via default in _map_symbol_type
        assert result.symbol_type == "function"
        assert result.symbol_name == "VERSION"

    def test_arg_without_default(self):
        """ARG without default value extracts variable symbol."""
        code = "ARG COMMIT_SHA\n"
        result = extract_symbol_metadata(code, "dockerfile")

        assert result.symbol_type == "function"
        assert result.symbol_name == "COMMIT_SHA"

    def test_from_without_as_returns_none(self):
        """FROM without AS clause produces no named symbol."""
        code = "FROM ubuntu:22.04\nRUN apt-get update\n"
        result = extract_symbol_metadata(code, "dockerfile")

        assert result.symbol_type is None
        assert result.symbol_name is None

    def test_run_instruction_returns_none(self):
        """RUN instruction produces no symbol."""
        code = "RUN apt-get update && apt-get install -y curl\n"
        result = extract_symbol_metadata(code, "dockerfile")

        assert result.symbol_type is None
        assert result.symbol_name is None

    def test_empty_input_returns_none(self):
        """Empty input returns NULL fields."""
        result = extract_symbol_metadata("", "dockerfile")

        assert result.symbol_type is None
        assert result.symbol_name is None
        assert result.symbol_signature is None

    def test_extension_mapping(self):
        """'dockerfile' key in LANGUAGE_MAP resolves to 'dockerfile'."""
        from cocosearch.indexer.symbols import LANGUAGE_MAP

        assert LANGUAGE_MAP["dockerfile"] == "dockerfile"

    def test_multistage_first_stage(self):
        """First FROM AS in multi-stage returns stage name."""
        code = "FROM node:18 AS deps\nRUN npm ci\n"
        result = extract_symbol_metadata(code, "dockerfile")

        assert result.symbol_type == "class"
        assert result.symbol_name == "deps"

    def test_from_with_platform_and_as(self):
        """FROM with --platform and AS extracts stage name."""
        code = "FROM --platform=linux/amd64 golang:1.21 AS builder\n"
        result = extract_symbol_metadata(code, "dockerfile")

        assert result.symbol_type == "class"
        assert result.symbol_name == "builder"
