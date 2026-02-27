"""Tests for incremental dependency extraction."""

from unittest.mock import patch

from cocosearch.deps.models import DependencyEdge, DepType


# ============================================================================
# Tests: _compute_file_hashes
# ============================================================================


class TestComputeFileHashes:
    """Tests for _compute_file_hashes()."""

    def test_computes_hashes_for_existing_files(self, tmp_path):
        """Should compute SHA-256 hashes for files that exist."""
        py_file = tmp_path / "main.py"
        py_file.write_text("import os\n")

        from cocosearch.deps.extractor import _compute_file_hashes

        result = _compute_file_hashes([("main.py", "py")], str(tmp_path))

        assert "main.py" in result
        content_hash, lang = result["main.py"]
        assert len(content_hash) == 64  # SHA-256 hex digest
        assert lang == "py"

    def test_excludes_unreadable_files(self, tmp_path):
        """Files that can't be read should be excluded from results."""
        from cocosearch.deps.extractor import _compute_file_hashes

        result = _compute_file_hashes([("nonexistent.py", "py")], str(tmp_path))

        assert result == {}

    def test_same_content_same_hash(self, tmp_path):
        """Identical content should produce identical hashes."""
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("x = 1\n")

        from cocosearch.deps.extractor import _compute_file_hashes

        result = _compute_file_hashes([("a.py", "py"), ("b.py", "py")], str(tmp_path))

        assert result["a.py"][0] == result["b.py"][0]

    def test_different_content_different_hash(self, tmp_path):
        """Different content should produce different hashes."""
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("x = 2\n")

        from cocosearch.deps.extractor import _compute_file_hashes

        result = _compute_file_hashes([("a.py", "py"), ("b.py", "py")], str(tmp_path))

        assert result["a.py"][0] != result["b.py"][0]


# ============================================================================
# Tests: _diff_file_hashes
# ============================================================================


class TestDiffFileHashes:
    """Tests for _diff_file_hashes()."""

    def test_detects_changed_files(self):
        """Files with different hashes should be in changed set."""
        from cocosearch.deps.extractor import _diff_file_hashes

        current = {"a.py": ("hash_new", "py")}
        stored = {"a.py": "hash_old"}

        changed, added, deleted = _diff_file_hashes(current, stored)

        assert changed == {"a.py"}
        assert added == set()
        assert deleted == set()

    def test_detects_added_files(self):
        """Files only in current should be in added set."""
        from cocosearch.deps.extractor import _diff_file_hashes

        current = {"a.py": ("hash_a", "py"), "b.py": ("hash_b", "py")}
        stored = {"a.py": "hash_a"}

        changed, added, deleted = _diff_file_hashes(current, stored)

        assert changed == set()
        assert added == {"b.py"}
        assert deleted == set()

    def test_detects_deleted_files(self):
        """Files only in stored should be in deleted set."""
        from cocosearch.deps.extractor import _diff_file_hashes

        current = {"a.py": ("hash_a", "py")}
        stored = {"a.py": "hash_a", "b.py": "hash_b"}

        changed, added, deleted = _diff_file_hashes(current, stored)

        assert changed == set()
        assert added == set()
        assert deleted == {"b.py"}

    def test_no_changes(self):
        """Identical hashes should produce empty sets."""
        from cocosearch.deps.extractor import _diff_file_hashes

        current = {"a.py": ("hash_a", "py"), "b.py": ("hash_b", "py")}
        stored = {"a.py": "hash_a", "b.py": "hash_b"}

        changed, added, deleted = _diff_file_hashes(current, stored)

        assert changed == set()
        assert added == set()
        assert deleted == set()

    def test_mixed_changes(self):
        """Should detect changed, added, and deleted simultaneously."""
        from cocosearch.deps.extractor import _diff_file_hashes

        current = {
            "a.py": ("hash_a_new", "py"),  # changed
            "c.py": ("hash_c", "py"),  # added
        }
        stored = {
            "a.py": "hash_a_old",  # changed
            "b.py": "hash_b",  # deleted
        }

        changed, added, deleted = _diff_file_hashes(current, stored)

        assert changed == {"a.py"}
        assert added == {"c.py"}
        assert deleted == {"b.py"}


# ============================================================================
# Tests: _deduplicate_edges
# ============================================================================


class TestDeduplicateEdges:
    """Tests for _deduplicate_edges()."""

    def test_removes_duplicate_edges(self):
        """Identical edges should be collapsed to one."""
        from cocosearch.deps.extractor import _deduplicate_edges

        edge1 = DependencyEdge(
            source_file="a.md",
            source_symbol=None,
            target_file=None,
            target_symbol="utils",
            dep_type=DepType.REFERENCE,
            metadata={"kind": "doc_link"},
        )
        edge2 = DependencyEdge(
            source_file="a.md",
            source_symbol=None,
            target_file=None,
            target_symbol="utils",
            dep_type=DepType.REFERENCE,
            metadata={"kind": "doc_link"},
        )

        result = _deduplicate_edges([edge1, edge2])

        assert len(result) == 1

    def test_preserves_unique_edges(self):
        """Different edges should all be preserved."""
        from cocosearch.deps.extractor import _deduplicate_edges

        edge1 = DependencyEdge(
            source_file="a.py",
            source_symbol=None,
            target_file=None,
            target_symbol="os",
            dep_type=DepType.IMPORT,
        )
        edge2 = DependencyEdge(
            source_file="a.py",
            source_symbol=None,
            target_file=None,
            target_symbol="sys",
            dep_type=DepType.IMPORT,
        )

        result = _deduplicate_edges([edge1, edge2])

        assert len(result) == 2

    def test_collapses_resolve_many_expansions(self):
        """Edges that differ only in target_file should dedup once target_file is cleared."""
        from cocosearch.deps.extractor import _deduplicate_edges

        # These simulate edges read back from DB with target_file cleared
        edge1 = DependencyEdge(
            source_file="docs/guide.md",
            source_symbol=None,
            target_file=None,
            target_symbol="search",
            dep_type=DepType.REFERENCE,
            metadata={"kind": "doc_link"},
        )
        edge2 = DependencyEdge(
            source_file="docs/guide.md",
            source_symbol=None,
            target_file=None,
            target_symbol="search",
            dep_type=DepType.REFERENCE,
            metadata={"kind": "doc_link"},
        )

        result = _deduplicate_edges([edge1, edge2])

        assert len(result) == 1


# ============================================================================
# Tests: extract_dependencies (incremental flow)
# ============================================================================


class TestExtractDependenciesIncremental:
    """Tests for incremental extraction in extract_dependencies()."""

    def test_first_run_extracts_all(self, mock_db_pool, tmp_path):
        """Empty tracking (first run) should process all files."""
        py_file = tmp_path / "src" / "main.py"
        py_file.parent.mkdir(parents=True)
        py_file.write_text("import os\n")

        pool, cursor, conn = mock_db_pool()
        indexed_files = [("src/main.py", "py")]

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch("cocosearch.deps.extractor.create_deps_table"),
            patch("cocosearch.deps.extractor.create_tracking_table"),
            patch(
                "cocosearch.deps.extractor.get_stored_hashes",
                return_value={},
            ),
            patch("cocosearch.deps.extractor.truncate_deps_table"),
            patch("cocosearch.deps.extractor.insert_edges") as mock_insert,
            patch("cocosearch.deps.extractor.update_tracking") as mock_update,
        ):
            from cocosearch.deps.extractor import extract_dependencies

            stats = extract_dependencies("test", str(tmp_path))

        assert stats["files_processed"] == 1
        assert stats["incremental"] is False
        assert stats["files_unchanged"] == 0
        mock_insert.assert_called_once()
        mock_update.assert_called_once()

    def test_no_changes_skips_extraction(self, mock_db_pool, tmp_path):
        """Same hashes should produce early return with actual edge count from DB."""
        py_file = tmp_path / "src" / "main.py"
        py_file.parent.mkdir(parents=True)
        py_file.write_text("import os\n")

        pool, cursor, conn = mock_db_pool()
        indexed_files = [("src/main.py", "py")]

        # Compute the real hash for the file
        import hashlib

        with open(py_file, "rb") as f:
            real_hash = hashlib.sha256(f.read()).hexdigest()

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch("cocosearch.deps.extractor.create_deps_table"),
            patch("cocosearch.deps.extractor.create_tracking_table"),
            patch(
                "cocosearch.deps.extractor.get_stored_hashes",
                return_value={"src/main.py": real_hash},
            ),
            patch("cocosearch.deps.extractor.truncate_deps_table") as mock_trunc,
            patch("cocosearch.deps.extractor.insert_edges") as mock_insert,
            patch(
                "cocosearch.deps.query.get_dep_stats",
                return_value={"total_edges": 42},
            ),
        ):
            from cocosearch.deps.extractor import extract_dependencies

            stats = extract_dependencies("test", str(tmp_path))

        assert stats["files_processed"] == 0
        assert stats["incremental"] is True
        assert stats["files_unchanged"] == 1
        assert stats["edges_found"] == 42
        # Should NOT truncate or insert when nothing changed
        mock_trunc.assert_not_called()
        mock_insert.assert_not_called()

    def test_changed_file_re_extracted(self, mock_db_pool, tmp_path):
        """Modified file should be re-extracted, existing edges preserved."""
        # Create files
        (tmp_path / "a.py").write_text("import os\n")
        (tmp_path / "b.py").write_text("import sys\n")

        pool, cursor, conn = mock_db_pool()
        indexed_files = [("a.py", "py"), ("b.py", "py")]

        # Compute real hash for b.py (unchanged), fake hash for a.py (changed)
        import hashlib

        with open(tmp_path / "b.py", "rb") as f:
            b_hash = hashlib.sha256(f.read()).hexdigest()

        stored_hashes = {"a.py": "old_hash", "b.py": b_hash}

        # Existing edges from b.py (unchanged) read back from DB
        existing_edge = DependencyEdge(
            source_file="b.py",
            source_symbol=None,
            target_file=None,
            target_symbol="sys",
            dep_type=DepType.IMPORT,
            metadata={"module": "sys"},
        )

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch("cocosearch.deps.extractor.create_deps_table"),
            patch("cocosearch.deps.extractor.create_tracking_table"),
            patch(
                "cocosearch.deps.extractor.get_stored_hashes",
                return_value=stored_hashes,
            ),
            patch(
                "cocosearch.deps.extractor.read_edges_excluding",
                return_value=[existing_edge],
            ) as mock_read,
            patch("cocosearch.deps.extractor.truncate_deps_table"),
            patch("cocosearch.deps.extractor.insert_edges") as mock_insert,
            patch("cocosearch.deps.extractor.update_tracking"),
        ):
            from cocosearch.deps.extractor import extract_dependencies

            stats = extract_dependencies("test", str(tmp_path))

        assert stats["incremental"] is True
        assert stats["files_processed"] == 1  # Only a.py re-extracted

        # read_edges_excluding should exclude the changed file
        mock_read.assert_called_once()
        exclude_arg = mock_read.call_args[0][1]
        assert "a.py" in exclude_arg

        # insert_edges should have edges from both files
        mock_insert.assert_called_once()
        inserted_edges = mock_insert.call_args[0][1]
        source_files = {e.source_file for e in inserted_edges}
        assert "a.py" in source_files
        assert "b.py" in source_files

    def test_added_file_extracted(self, mock_db_pool, tmp_path):
        """New file should be extracted, existing edges preserved."""
        (tmp_path / "a.py").write_text("import os\n")
        (tmp_path / "b.py").write_text("import sys\n")

        pool, cursor, conn = mock_db_pool()
        indexed_files = [("a.py", "py"), ("b.py", "py")]

        import hashlib

        with open(tmp_path / "a.py", "rb") as f:
            a_hash = hashlib.sha256(f.read()).hexdigest()

        # Only a.py was previously tracked (b.py is new)
        stored_hashes = {"a.py": a_hash}

        existing_edge = DependencyEdge(
            source_file="a.py",
            source_symbol=None,
            target_file=None,
            target_symbol="os",
            dep_type=DepType.IMPORT,
            metadata={"module": "os"},
        )

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch("cocosearch.deps.extractor.create_deps_table"),
            patch("cocosearch.deps.extractor.create_tracking_table"),
            patch(
                "cocosearch.deps.extractor.get_stored_hashes",
                return_value=stored_hashes,
            ),
            patch(
                "cocosearch.deps.extractor.read_edges_excluding",
                return_value=[existing_edge],
            ),
            patch("cocosearch.deps.extractor.truncate_deps_table"),
            patch("cocosearch.deps.extractor.insert_edges") as mock_insert,
            patch("cocosearch.deps.extractor.update_tracking"),
        ):
            from cocosearch.deps.extractor import extract_dependencies

            stats = extract_dependencies("test", str(tmp_path))

        assert stats["incremental"] is True
        assert stats["files_processed"] == 1  # Only b.py extracted
        assert stats["files_unchanged"] == 1

        # Final edges should include both files
        inserted_edges = mock_insert.call_args[0][1]
        source_files = {e.source_file for e in inserted_edges}
        assert "a.py" in source_files
        assert "b.py" in source_files

    def test_deleted_file_edges_removed(self, mock_db_pool, tmp_path):
        """Deleted file's edges should be excluded from results."""
        # Only a.py exists on disk
        (tmp_path / "a.py").write_text("import os\n")

        pool, cursor, conn = mock_db_pool()
        indexed_files = [("a.py", "py")]

        import hashlib

        with open(tmp_path / "a.py", "rb") as f:
            a_hash = hashlib.sha256(f.read()).hexdigest()

        # b.py was previously tracked but is now deleted
        stored_hashes = {"a.py": a_hash, "b.py": "old_hash"}

        existing_edge = DependencyEdge(
            source_file="a.py",
            source_symbol=None,
            target_file=None,
            target_symbol="os",
            dep_type=DepType.IMPORT,
            metadata={"module": "os"},
        )

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch("cocosearch.deps.extractor.create_deps_table"),
            patch("cocosearch.deps.extractor.create_tracking_table"),
            patch(
                "cocosearch.deps.extractor.get_stored_hashes",
                return_value=stored_hashes,
            ),
            patch(
                "cocosearch.deps.extractor.read_edges_excluding",
                return_value=[existing_edge],
            ) as mock_read,
            patch("cocosearch.deps.extractor.truncate_deps_table"),
            patch("cocosearch.deps.extractor.insert_edges") as mock_insert,
            patch("cocosearch.deps.extractor.update_tracking"),
        ):
            from cocosearch.deps.extractor import extract_dependencies

            stats = extract_dependencies("test", str(tmp_path))

        assert stats["incremental"] is True

        # read_edges_excluding should exclude the deleted file
        exclude_arg = mock_read.call_args[0][1]
        assert "b.py" in exclude_arg

        # Final edges should only have a.py
        inserted_edges = mock_insert.call_args[0][1]
        source_files = {e.source_file for e in inserted_edges}
        assert "b.py" not in source_files

    def test_re_resolution_resolves_new_imports(self, mock_db_pool, tmp_path):
        """Adding a file should resolve previously unresolved imports via re-resolution."""
        # a.py imports mymod which didn't exist before, now b.py provides it
        (tmp_path / "src" / "mymod").mkdir(parents=True)
        (tmp_path / "src" / "mymod" / "__init__.py").write_text("")
        (tmp_path / "src" / "mymod" / "utils.py").write_text("x = 1\n")
        (tmp_path / "src" / "app.py").write_text("from mymod.utils import x\n")

        pool, cursor, conn = mock_db_pool()
        indexed_files = [
            ("src/app.py", "py"),
            ("src/mymod/__init__.py", "py"),
            ("src/mymod/utils.py", "py"),
        ]

        import hashlib

        with open(tmp_path / "src" / "app.py", "rb") as f:
            app_hash = hashlib.sha256(f.read()).hexdigest()

        # app.py was tracked before; mymod files are new
        stored_hashes = {"src/app.py": app_hash}

        # Existing edge from app.py with unresolved target
        existing_edge = DependencyEdge(
            source_file="src/app.py",
            source_symbol=None,
            target_file=None,
            target_symbol="x",
            dep_type=DepType.IMPORT,
            metadata={"module": "mymod.utils"},
        )

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch("cocosearch.deps.extractor.create_deps_table"),
            patch("cocosearch.deps.extractor.create_tracking_table"),
            patch(
                "cocosearch.deps.extractor.get_stored_hashes",
                return_value=stored_hashes,
            ),
            patch(
                "cocosearch.deps.extractor.read_edges_excluding",
                return_value=[existing_edge],
            ),
            patch("cocosearch.deps.extractor.truncate_deps_table"),
            patch("cocosearch.deps.extractor.insert_edges") as mock_insert,
            patch("cocosearch.deps.extractor.update_tracking"),
        ):
            from cocosearch.deps.extractor import extract_dependencies

            extract_dependencies("test", str(tmp_path))

        # The existing edge should now be resolved
        inserted_edges = mock_insert.call_args[0][1]
        app_edges = [e for e in inserted_edges if e.source_file == "src/app.py"]
        resolved = [e for e in app_edges if e.target_file is not None]
        assert len(resolved) >= 1
        assert resolved[0].target_file == "src/mymod/utils.py"

    def test_fresh_flag_extracts_all(self, mock_db_pool, tmp_path):
        """fresh=True should ignore tracking and process all files."""
        py_file = tmp_path / "main.py"
        py_file.write_text("import os\n")

        pool, cursor, conn = mock_db_pool()
        indexed_files = [("main.py", "py")]

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch("cocosearch.deps.extractor.create_deps_table"),
            patch("cocosearch.deps.extractor.create_tracking_table"),
            patch(
                "cocosearch.deps.extractor.get_stored_hashes",
            ) as mock_get_hashes,
            patch("cocosearch.deps.extractor.truncate_deps_table"),
            patch("cocosearch.deps.extractor.insert_edges") as mock_insert,
            patch("cocosearch.deps.extractor.update_tracking"),
        ):
            from cocosearch.deps.extractor import extract_dependencies

            stats = extract_dependencies("test", str(tmp_path), fresh=True)

        assert stats["files_processed"] == 1
        assert stats["incremental"] is False
        # Should NOT call get_stored_hashes when fresh=True
        mock_get_hashes.assert_not_called()
        mock_insert.assert_called_once()

    def test_deduplication_prevents_resolve_many_proliferation(
        self, mock_db_pool, tmp_path
    ):
        """Edges from resolve_many should not multiply on incremental runs."""
        (tmp_path / "docs" / "guide.md").parent.mkdir(parents=True)
        (tmp_path / "docs" / "guide.md").write_text("new content\n")

        pool, cursor, conn = mock_db_pool()
        indexed_files = [("docs/guide.md", "md")]

        # guide.md changed, so its edges are NOT read from DB
        # But a different unchanged file has duplicated edges
        existing_expanded_1 = DependencyEdge(
            source_file="docs/other.md",
            source_symbol=None,
            target_file="src/a.py",
            target_symbol="utils",
            dep_type=DepType.REFERENCE,
            metadata={"kind": "doc_link"},
        )
        existing_expanded_2 = DependencyEdge(
            source_file="docs/other.md",
            source_symbol=None,
            target_file="src/b.py",
            target_symbol="utils",
            dep_type=DepType.REFERENCE,
            metadata={"kind": "doc_link"},
        )

        with (
            patch(
                "cocosearch.deps.extractor.get_indexed_files",
                return_value=indexed_files,
            ),
            patch("cocosearch.deps.extractor.create_deps_table"),
            patch("cocosearch.deps.extractor.create_tracking_table"),
            patch(
                "cocosearch.deps.extractor.get_stored_hashes",
                return_value={"docs/guide.md": "old_hash"},
            ),
            patch(
                "cocosearch.deps.extractor.read_edges_excluding",
                return_value=[existing_expanded_1, existing_expanded_2],
            ),
            patch("cocosearch.deps.extractor.truncate_deps_table"),
            patch("cocosearch.deps.extractor.insert_edges") as mock_insert,
            patch("cocosearch.deps.extractor.update_tracking"),
        ):
            from cocosearch.deps.extractor import extract_dependencies

            extract_dependencies("test", str(tmp_path))

        # After clearing target_file and dedup, the two expanded edges
        # from other.md should collapse to one
        inserted_edges = mock_insert.call_args[0][1]
        other_edges = [e for e in inserted_edges if e.source_file == "docs/other.md"]
        assert len(other_edges) == 1


# ============================================================================
# Tests: DB functions for tracking and read_edges
# ============================================================================


class TestTrackingTableDB:
    """Tests for tracking table DB functions."""

    def test_create_tracking_table(self, mock_db_pool):
        """Should create tracking table with correct schema."""
        pool, cursor, conn = mock_db_pool()

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            from cocosearch.deps.db import create_tracking_table

            create_tracking_table("myindex")

        cursor.assert_query_contains("CREATE TABLE IF NOT EXISTS")
        cursor.assert_query_contains("cocosearch_deps_tracking_myindex")
        cursor.assert_query_contains("filename TEXT PRIMARY KEY")
        cursor.assert_query_contains("content_hash TEXT NOT NULL")
        cursor.assert_query_contains("language_id TEXT NOT NULL")
        assert conn.committed

    def test_drop_tracking_table(self, mock_db_pool):
        """Should drop tracking table if it exists."""
        pool, cursor, conn = mock_db_pool()

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            from cocosearch.deps.db import drop_tracking_table

            drop_tracking_table("myindex")

        cursor.assert_query_contains("DROP TABLE IF EXISTS")
        cursor.assert_query_contains("cocosearch_deps_tracking_myindex")
        assert conn.committed

    def test_get_stored_hashes(self, mock_db_pool):
        """Should return dict of filename -> content_hash."""
        pool, cursor, conn = mock_db_pool(
            results=[
                ("src/main.py", "abc123"),
                ("src/utils.py", "def456"),
            ]
        )

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            from cocosearch.deps.db import get_stored_hashes

            result = get_stored_hashes("myindex")

        assert result == {
            "src/main.py": "abc123",
            "src/utils.py": "def456",
        }
        cursor.assert_query_contains("SELECT")
        cursor.assert_query_contains("cocosearch_deps_tracking_myindex")

    def test_update_tracking(self, mock_db_pool):
        """Should truncate and re-insert all tracking entries."""
        pool, cursor, conn = mock_db_pool()

        file_hashes = {
            "src/main.py": ("abc123", "py"),
            "src/utils.go": ("def456", "go"),
        }

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            from cocosearch.deps.db import update_tracking

            update_tracking("myindex", file_hashes)

        cursor.assert_query_contains("TRUNCATE TABLE")
        cursor.assert_query_contains("INSERT INTO")
        cursor.assert_query_contains("cocosearch_deps_tracking_myindex")
        assert conn.committed

    def test_truncate_deps_table(self, mock_db_pool):
        """Should truncate the deps table."""
        pool, cursor, conn = mock_db_pool()

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            from cocosearch.deps.db import truncate_deps_table

            truncate_deps_table("myindex")

        cursor.assert_query_contains("TRUNCATE TABLE")
        cursor.assert_query_contains("cocosearch_deps_myindex")
        assert conn.committed

    def test_read_edges_excluding_empty_set(self, mock_db_pool):
        """Should read all edges when exclude set is empty."""
        pool, cursor, conn = mock_db_pool(
            results=[
                ("src/main.py", None, "src/utils.py", None, "import", "{}"),
            ]
        )

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            from cocosearch.deps.db import read_edges_excluding

            edges = read_edges_excluding("myindex", set())

        assert len(edges) == 1
        assert edges[0].source_file == "src/main.py"
        assert edges[0].target_file == "src/utils.py"

        # Should NOT have WHERE ... NOT IN clause
        queries = [q for q, _ in cursor.calls]
        assert not any("NOT IN" in q for q in queries)

    def test_read_edges_excluding_with_files(self, mock_db_pool):
        """Should exclude edges from specified source files."""
        pool, cursor, conn = mock_db_pool(
            results=[
                ("src/utils.py", None, None, "os", "import", "{}"),
            ]
        )

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            from cocosearch.deps.db import read_edges_excluding

            edges = read_edges_excluding("myindex", {"src/main.py"})

        assert len(edges) == 1
        cursor.assert_query_contains("NOT IN")

    def test_read_edges_excluding_parses_json_metadata(self, mock_db_pool):
        """Should parse JSON string metadata into dict."""
        pool, cursor, conn = mock_db_pool(
            results=[
                ("a.py", None, "b.py", None, "import", '{"module": "os"}'),
            ]
        )

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            from cocosearch.deps.db import read_edges_excluding

            edges = read_edges_excluding("myindex", set())

        assert edges[0].metadata == {"module": "os"}

    def test_read_edges_excluding_handles_dict_metadata(self, mock_db_pool):
        """Should handle metadata that's already a dict (from JSONB)."""
        pool, cursor, conn = mock_db_pool(
            results=[
                ("a.py", None, "b.py", None, "import", {"module": "os"}),
            ]
        )

        with patch("cocosearch.deps.db.get_connection_pool", return_value=pool):
            from cocosearch.deps.db import read_edges_excluding

            edges = read_edges_excluding("myindex", set())

        assert edges[0].metadata == {"module": "os"}
