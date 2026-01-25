"""Tests for cocosearch.indexer.embedder module."""

import pytest


class TestCodeToEmbedding:
    """Tests for code_to_embedding function.

    These tests use the mock_code_to_embedding fixture which patches the
    embedding function to return deterministic vectors without calling Ollama.
    """

    def test_generates_embedding_vector(self, mock_code_to_embedding):
        """Returns a list of floats."""
        result = mock_code_to_embedding.eval("def hello(): pass")

        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)

    def test_embedding_has_correct_dimensions(self, mock_code_to_embedding):
        """Returns 768-dimensional vector (nomic-embed-text default)."""
        result = mock_code_to_embedding.eval("def hello(): pass")

        assert len(result) == 768

    def test_different_inputs_different_embeddings(self, mock_code_to_embedding):
        """Different code produces different vectors."""
        embedding1 = mock_code_to_embedding.eval("def hello(): pass")
        embedding2 = mock_code_to_embedding.eval("def world(): return 42")

        # Embeddings should be different for different inputs
        assert embedding1 != embedding2

    def test_same_input_same_embedding(self, mock_code_to_embedding):
        """Same input produces same embedding (deterministic)."""
        code = "def example(): return True"
        embedding1 = mock_code_to_embedding.eval(code)
        embedding2 = mock_code_to_embedding.eval(code)

        assert embedding1 == embedding2

    def test_embedding_values_in_valid_range(self, mock_code_to_embedding):
        """Embedding values are in [-1, 1] range."""
        result = mock_code_to_embedding.eval("some code content")

        for value in result:
            assert -1 <= value <= 1


class TestExtractExtension:
    """Tests for extract_extension function.

    The extract_extension function is decorated with @cocoindex.op.function()
    but can still be called directly for testing.
    """

    def test_extracts_python_extension(self):
        """Extracts .py extension correctly."""
        from cocosearch.indexer.embedder import extract_extension

        result = extract_extension("test.py")
        assert result == "py"

    def test_extracts_from_path(self):
        """Extracts extension from full path."""
        from cocosearch.indexer.embedder import extract_extension

        result = extract_extension("/path/to/file.js")
        assert result == "js"

    def test_returns_empty_for_no_extension(self):
        """Returns empty string for files without extension."""
        from cocosearch.indexer.embedder import extract_extension

        result = extract_extension("Makefile")
        assert result == ""

    def test_handles_multiple_dots(self):
        """Handles filenames with multiple dots."""
        from cocosearch.indexer.embedder import extract_extension

        result = extract_extension("file.test.spec.ts")
        assert result == "ts"
