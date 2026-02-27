"""Tests for cocosearch.deps.extractor module."""

from unittest.mock import patch

from cocosearch.deps.models import DepType

# ============================================================================
# Tests: get_indexed_files
# ============================================================================


class TestGetIndexedFiles:
    """Tests for get_indexed_files()."""

    def test_returns_correct_tuples(self, mock_db_pool):
        """Should return (filename, language_id) tuples from the DB query."""
        pool, cursor, conn = mock_db_pool(
            results=[
                ("src/main.py", "py"),
                ("src/utils.go", "go"),
                ("README.md", "md"),
            ]
        )

        with (
            patch(
                "cocosearch.deps.extractor.get_connection_pool",
                return_value=pool,
            ),
            patch(
                "cocosearch.deps.extractor.get_table_name",
                return_value="codeindex_test__test_chunks",
            ),
        ):
            from cocosearch.deps.extractor import get_indexed_files

            result = get_indexed_files("test")

        assert result == [
            ("src/main.py", "py"),
            ("src/utils.go", "go"),
            ("README.md", "md"),
        ]

    def test_query_contains_distinct_filename_language_id(self, mock_db_pool):
        """Query should use SELECT DISTINCT with filename and language_id."""
        pool, cursor, conn = mock_db_pool(results=[])

        with (
            patch(
                "cocosearch.deps.extractor.get_connection_pool",
                return_value=pool,
            ),
            patch(
                "cocosearch.deps.extractor.get_table_name",
                return_value="codeindex_test__test_chunks",
            ),
        ):
            from cocosearch.deps.extractor import get_indexed_files

            get_indexed_files("test")

        cursor.assert_query_contains("DISTINCT")
        cursor.assert_query_contains("filename")
        cursor.assert_query_contains("language_id")

    def test_query_filters_null_language_id(self, mock_db_pool):
        """Query should filter out rows where language_id IS NOT NULL."""
        pool, cursor, conn = mock_db_pool(results=[])

        with (
            patch(
                "cocosearch.deps.extractor.get_connection_pool",
                return_value=pool,
            ),
            patch(
                "cocosearch.deps.extractor.get_table_name",
                return_value="codeindex_test__test_chunks",
            ),
        ):
            from cocosearch.deps.extractor import get_indexed_files

            get_indexed_files("test")

        cursor.assert_query_contains("language_id IS NOT NULL")


# ============================================================================
# Tests: extract_dependencies
# ============================================================================


class TestExtractDependencies:
    """Tests for extract_dependencies()."""

    def test_extracts_and_stores_edges_from_python_file(self, mock_db_pool, tmp_path):
        """Should extract edges from a real Python file and store them."""
        # Create a real Python file with imports
        py_file = tmp_path / "src" / "main.py"
        py_file.parent.mkdir(parents=True)
        py_file.write_text("import os\nfrom sys import argv\n")

        pool, cursor, conn = mock_db_pool()

        indexed_files = [("src/main.py", "py")]

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch(
                "cocosearch.deps.extractor.drop_deps_table",
            ) as mock_drop,
            patch(
                "cocosearch.deps.extractor.create_deps_table",
            ) as mock_create,
            patch(
                "cocosearch.deps.extractor.insert_edges",
            ) as mock_insert,
        ):
            from cocosearch.deps.extractor import extract_dependencies

            stats = extract_dependencies("test", str(tmp_path))

        # Should drop and recreate the table
        mock_drop.assert_called_once_with("test")
        mock_create.assert_called_once_with("test")

        # Should have inserted edges
        mock_insert.assert_called_once()
        call_args = mock_insert.call_args
        assert call_args[0][0] == "test"  # index_name
        edges = call_args[0][1]
        assert len(edges) == 2  # import os + from sys import argv

        # All edges should have source_file set
        for edge in edges:
            assert edge.source_file == "src/main.py"
            assert edge.dep_type == DepType.IMPORT

        # Stats
        assert stats["files_processed"] == 1
        assert stats["files_skipped"] == 0
        assert stats["edges_found"] == 2
        assert stats["errors"] == 0

    def test_skips_files_without_registered_extractor(self, mock_db_pool, tmp_path):
        """Files with no registered extractor should be skipped."""
        # Create a CSS file (no extractor for "css")
        css_file = tmp_path / "styles.css"
        css_file.write_text("body { color: red; }")

        indexed_files = [("styles.css", "css")]

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch(
                "cocosearch.deps.extractor.drop_deps_table",
            ),
            patch(
                "cocosearch.deps.extractor.create_deps_table",
            ),
            patch(
                "cocosearch.deps.extractor.insert_edges",
            ) as mock_insert,
        ):
            from cocosearch.deps.extractor import extract_dependencies

            stats = extract_dependencies("test", str(tmp_path))

        assert stats["files_processed"] == 0
        assert stats["files_skipped"] == 1
        assert stats["edges_found"] == 0
        assert stats["errors"] == 0

        # insert_edges should be called with empty list
        mock_insert.assert_called_once_with("test", [])

    def test_handles_missing_file_gracefully(self, mock_db_pool, tmp_path):
        """Missing file should increment errors, not crash."""
        # Don't create the file — it's "missing"
        indexed_files = [("nonexistent.py", "py")]

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch(
                "cocosearch.deps.extractor.drop_deps_table",
            ),
            patch(
                "cocosearch.deps.extractor.create_deps_table",
            ),
            patch(
                "cocosearch.deps.extractor.insert_edges",
            ) as mock_insert,
        ):
            from cocosearch.deps.extractor import extract_dependencies

            stats = extract_dependencies("test", str(tmp_path))

        assert stats["files_processed"] == 0
        assert stats["files_skipped"] == 0
        assert stats["edges_found"] == 0
        assert stats["errors"] == 1

        # insert_edges should be called with empty list (no edges from missing file)
        mock_insert.assert_called_once_with("test", [])

    def test_mixed_files_correct_stats(self, mock_db_pool, tmp_path):
        """Mix of valid, skipped, and missing files should produce correct stats."""
        # Create a valid Python file
        py_file = tmp_path / "app.py"
        py_file.write_text("import json\n")

        indexed_files = [
            ("app.py", "py"),  # valid
            ("styles.css", "css"),  # no extractor -> skipped
            ("missing.py", "py"),  # missing -> error
        ]

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch(
                "cocosearch.deps.extractor.drop_deps_table",
            ),
            patch(
                "cocosearch.deps.extractor.create_deps_table",
            ),
            patch(
                "cocosearch.deps.extractor.insert_edges",
            ),
        ):
            from cocosearch.deps.extractor import extract_dependencies

            stats = extract_dependencies("test", str(tmp_path))

        assert stats["files_processed"] == 1
        assert stats["files_skipped"] == 1
        assert stats["edges_found"] == 1  # import json
        assert stats["errors"] == 1

    def test_sets_source_file_on_edges(self, mock_db_pool, tmp_path):
        """Orchestrator should set source_file on each returned edge."""
        py_file = tmp_path / "lib.py"
        py_file.write_text("from os.path import join\n")

        indexed_files = [("lib.py", "py")]

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch(
                "cocosearch.deps.extractor.drop_deps_table",
            ),
            patch(
                "cocosearch.deps.extractor.create_deps_table",
            ),
            patch(
                "cocosearch.deps.extractor.insert_edges",
            ) as mock_insert,
        ):
            from cocosearch.deps.extractor import extract_dependencies

            extract_dependencies("test", str(tmp_path))

        edges = mock_insert.call_args[0][1]
        assert len(edges) == 1
        assert edges[0].source_file == "lib.py"


# ============================================================================
# Tests: extract_dependencies integration with module resolution
# ============================================================================


class TestExtractDependenciesModuleResolution:
    """Tests verifying module resolution runs during extract_dependencies()."""

    def test_resolves_internal_imports(self, mock_db_pool, tmp_path):
        """Internal imports should get target_file populated."""
        # Create two Python files where one imports the other
        (tmp_path / "src" / "mypackage").mkdir(parents=True)
        (tmp_path / "src" / "mypackage" / "__init__.py").write_text("")
        (tmp_path / "src" / "mypackage" / "models.py").write_text("class User: pass\n")
        (tmp_path / "src" / "mypackage" / "cli.py").write_text(
            "from mypackage.models import User\n"
        )

        indexed_files = [
            ("src/mypackage/__init__.py", "py"),
            ("src/mypackage/models.py", "py"),
            ("src/mypackage/cli.py", "py"),
        ]

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch(
                "cocosearch.deps.extractor.drop_deps_table",
            ),
            patch(
                "cocosearch.deps.extractor.create_deps_table",
            ),
            patch(
                "cocosearch.deps.extractor.insert_edges",
            ) as mock_insert,
        ):
            from cocosearch.deps.extractor import extract_dependencies

            extract_dependencies("test", str(tmp_path))

        edges = mock_insert.call_args[0][1]

        # Find the edge for "from mypackage.models import User"
        model_edges = [
            e for e in edges if e.metadata.get("module") == "mypackage.models"
        ]
        assert len(model_edges) == 1
        assert model_edges[0].target_file == "src/mypackage/models.py"

    def test_external_imports_stay_none(self, mock_db_pool, tmp_path):
        """External imports should keep target_file=None."""
        py_file = tmp_path / "app.py"
        py_file.write_text("import numpy\n")

        indexed_files = [("app.py", "py")]

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch(
                "cocosearch.deps.extractor.drop_deps_table",
            ),
            patch(
                "cocosearch.deps.extractor.create_deps_table",
            ),
            patch(
                "cocosearch.deps.extractor.insert_edges",
            ) as mock_insert,
        ):
            from cocosearch.deps.extractor import extract_dependencies

            extract_dependencies("test", str(tmp_path))

        edges = mock_insert.call_args[0][1]
        assert len(edges) == 1
        assert edges[0].target_file is None  # numpy is external

    def test_directory_reference_expands_to_all_files(self, mock_db_pool, tmp_path):
        """Markdown directory references should create edges to all files in the dir."""
        # Create a doc file referencing a directory
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "guide.md").write_text(
            "See [the search module](../src/search/) for details.\n"
        )

        # Create multiple files in the referenced directory
        (tmp_path / "src" / "search").mkdir(parents=True)
        (tmp_path / "src" / "search" / "engine.py").write_text("class Engine: pass\n")
        (tmp_path / "src" / "search" / "cache.py").write_text("class Cache: pass\n")

        indexed_files = [
            ("docs/guide.md", "md"),
            ("src/search/engine.py", "py"),
            ("src/search/cache.py", "py"),
        ]

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch(
                "cocosearch.deps.extractor.drop_deps_table",
            ),
            patch(
                "cocosearch.deps.extractor.create_deps_table",
            ),
            patch(
                "cocosearch.deps.extractor.insert_edges",
            ) as mock_insert,
        ):
            from cocosearch.deps.extractor import extract_dependencies

            extract_dependencies("test", str(tmp_path))

        edges = mock_insert.call_args[0][1]

        # Find edges from the doc file with doc_link kind
        doc_edges = [
            e
            for e in edges
            if e.source_file == "docs/guide.md" and e.metadata.get("kind") == "doc_link"
        ]
        target_files = {e.target_file for e in doc_edges}
        assert target_files == {"src/search/engine.py", "src/search/cache.py"}
