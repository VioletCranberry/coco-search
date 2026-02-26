"""Tests for transitive dependency queries (BFS tree/impact)."""

from unittest.mock import patch

from cocosearch.deps.models import DependencyEdge, DepType
from cocosearch.deps.query import get_dependency_tree, get_impact


def _edge(source, target, dep_type=DepType.IMPORT, symbol=None, metadata=None):
    """Create a simple DependencyEdge for testing."""
    return DependencyEdge(
        source_file=source,
        source_symbol=None,
        target_file=target,
        target_symbol=symbol,
        dep_type=dep_type,
        metadata=metadata or {},
    )


# A → B → C → D (linear chain)
_LINEAR_DEPS = {
    "a.py": [_edge("a.py", "b.py"), _edge("a.py", "x.py")],
    "b.py": [_edge("b.py", "c.py")],
    "c.py": [_edge("c.py", "d.py")],
    "d.py": [],
    "x.py": [],
}

# Same graph reversed for dependents
_LINEAR_DEPENDENTS = {
    "d.py": [_edge("c.py", "d.py")],
    "c.py": [_edge("b.py", "c.py")],
    "b.py": [_edge("a.py", "b.py")],
    "a.py": [],
    "x.py": [_edge("a.py", "x.py")],
}

# Diamond: A → B, A → C, B → D, C → D
_DIAMOND_DEPS = {
    "a.py": [_edge("a.py", "b.py"), _edge("a.py", "c.py")],
    "b.py": [_edge("b.py", "d.py")],
    "c.py": [_edge("c.py", "d.py")],
    "d.py": [],
}

# Cycle: A → B → C → A
_CYCLE_DEPS = {
    "a.py": [_edge("a.py", "b.py")],
    "b.py": [_edge("b.py", "c.py")],
    "c.py": [_edge("c.py", "a.py")],
}

# Mixed: A → B (local) + A → fmt (external, via metadata module) + A → os (external, via symbol)
_MIXED_DEPS = {
    "main.go": [
        _edge("main.go", "pkg/utils.go"),
        _edge("main.go", None, symbol="fmt", metadata={"module": "fmt"}),
        _edge(
            "main.go",
            None,
            symbol="client_golang",
            metadata={"module": "github.com/prometheus/client_golang"},
        ),
    ],
    "pkg/utils.go": [],
}

# Only external deps
_EXTERNAL_ONLY_DEPS = {
    "main.go": [
        _edge("main.go", None, symbol="fmt", metadata={"module": "fmt"}),
        _edge("main.go", None, symbol="os"),
    ],
}

# External deps with ref metadata (e.g., GitHub Actions pre-fix data)
_REF_METADATA_DEPS = {
    "workflow.yml": [
        _edge(
            "workflow.yml",
            None,
            symbol=None,
            metadata={"ref": "actions/checkout@v4"},
        ),
        _edge(
            "workflow.yml",
            None,
            symbol=None,
            metadata={"ref": "astral-sh/setup-uv@v5"},
        ),
        _edge(
            "workflow.yml",
            None,
            symbol=None,
            metadata={"module": "docker/build-push-action"},
        ),
        _edge("workflow.yml", None, symbol="bare_symbol"),
        _edge("workflow.yml", None, symbol=None),
    ],
}


def _mock_get_dependencies(graph):
    """Create a mock for get_dependencies using a predefined graph."""

    def mock_fn(index_name, file, dep_type=None, symbol=None):
        edges = graph.get(file, [])
        if dep_type:
            edges = [e for e in edges if e.dep_type == dep_type]
        return edges

    return mock_fn


def _mock_get_dependents(graph):
    """Create a mock for get_dependents using a predefined graph."""

    def mock_fn(index_name, file, dep_type=None, symbol=None):
        edges = graph.get(file, [])
        if dep_type:
            edges = [e for e in edges if e.dep_type == dep_type]
        return edges

    return mock_fn


# ============================================================================
# Tests: get_dependency_tree
# ============================================================================


class TestGetDependencyTree:
    """Tests for get_dependency_tree() BFS."""

    def test_linear_chain_full_depth(self):
        with patch(
            "cocosearch.deps.query.get_dependencies",
            side_effect=_mock_get_dependencies(_LINEAR_DEPS),
        ):
            tree = get_dependency_tree("test", "a.py", max_depth=5)

        assert tree.file == "a.py"
        child_files = {c.file for c in tree.children}
        assert child_files == {"b.py", "x.py"}

        # b.py should have c.py as child
        b_node = next(c for c in tree.children if c.file == "b.py")
        assert len(b_node.children) == 1
        assert b_node.children[0].file == "c.py"

        # c.py should have d.py as child
        c_node = b_node.children[0]
        assert len(c_node.children) == 1
        assert c_node.children[0].file == "d.py"

    def test_depth_limit(self):
        with patch(
            "cocosearch.deps.query.get_dependencies",
            side_effect=_mock_get_dependencies(_LINEAR_DEPS),
        ):
            tree = get_dependency_tree("test", "a.py", max_depth=1)

        # Should only have direct children, no grandchildren
        assert len(tree.children) == 2
        for child in tree.children:
            assert len(child.children) == 0

    def test_diamond_no_duplicates(self):
        with patch(
            "cocosearch.deps.query.get_dependencies",
            side_effect=_mock_get_dependencies(_DIAMOND_DEPS),
        ):
            tree = get_dependency_tree("test", "a.py", max_depth=5)

        # d.py should appear only once (visited set prevents duplicates)
        all_files = _collect_files(tree)
        assert all_files.count("d.py") == 1

    def test_cycle_detection(self):
        with patch(
            "cocosearch.deps.query.get_dependencies",
            side_effect=_mock_get_dependencies(_CYCLE_DEPS),
        ):
            tree = get_dependency_tree("test", "a.py", max_depth=10)

        # Should not infinite loop; a.py is root and visited
        all_files = _collect_files(tree)
        assert all_files.count("a.py") == 1  # root only
        assert "b.py" in all_files
        assert "c.py" in all_files

    def test_empty_dependencies(self):
        with patch(
            "cocosearch.deps.query.get_dependencies",
            return_value=[],
        ):
            tree = get_dependency_tree("test", "lonely.py")

        assert tree.file == "lonely.py"
        assert tree.children == []

    def test_root_node_has_root_dep_type(self):
        with patch(
            "cocosearch.deps.query.get_dependencies",
            return_value=[],
        ):
            tree = get_dependency_tree("test", "a.py")

        assert tree.dep_type == "root"

    def test_mixed_local_and_external_deps(self):
        with patch(
            "cocosearch.deps.query.get_dependencies",
            side_effect=_mock_get_dependencies(_MIXED_DEPS),
        ):
            tree = get_dependency_tree("test", "main.go", max_depth=5)

        assert tree.file == "main.go"
        assert len(tree.children) == 3

        local = [c for c in tree.children if not c.is_external]
        external = [c for c in tree.children if c.is_external]

        assert len(local) == 1
        assert local[0].file == "pkg/utils.go"

        assert len(external) == 2
        ext_files = {c.file for c in external}
        assert "fmt" in ext_files
        assert "github.com/prometheus/client_golang" in ext_files
        for ext in external:
            assert ext.children == []

    def test_only_external_deps(self):
        with patch(
            "cocosearch.deps.query.get_dependencies",
            side_effect=_mock_get_dependencies(_EXTERNAL_ONLY_DEPS),
        ):
            tree = get_dependency_tree("test", "main.go", max_depth=5)

        assert tree.file == "main.go"
        assert len(tree.children) == 2
        for child in tree.children:
            assert child.is_external is True
            assert child.children == []

        child_files = {c.file for c in tree.children}
        assert "fmt" in child_files
        assert "os" in child_files

    def test_external_deps_use_module_metadata(self):
        with patch(
            "cocosearch.deps.query.get_dependencies",
            side_effect=_mock_get_dependencies(_MIXED_DEPS),
        ):
            tree = get_dependency_tree("test", "main.go", max_depth=5)

        # The prometheus edge has metadata.module, should use that as file label
        ext = [c for c in tree.children if c.is_external]
        prometheus = [c for c in ext if "prometheus" in c.file]
        assert len(prometheus) == 1
        assert prometheus[0].file == "github.com/prometheus/client_golang"

    def test_external_deps_fallback_to_symbol(self):
        """When no metadata.module, external dep falls back to target_symbol."""
        with patch(
            "cocosearch.deps.query.get_dependencies",
            side_effect=_mock_get_dependencies(_EXTERNAL_ONLY_DEPS),
        ):
            tree = get_dependency_tree("test", "main.go", max_depth=5)

        # "os" edge has no metadata.module, should use target_symbol
        os_nodes = [c for c in tree.children if c.file == "os"]
        assert len(os_nodes) == 1

    def test_external_deps_fallback_to_ref(self):
        """When no metadata.module but metadata.ref exists, use ref as label."""
        with patch(
            "cocosearch.deps.query.get_dependencies",
            side_effect=_mock_get_dependencies(_REF_METADATA_DEPS),
        ):
            tree = get_dependency_tree("test", "workflow.yml", max_depth=5)

        ext = [c for c in tree.children if c.is_external]
        assert len(ext) == 5
        ext_files = {c.file for c in ext}

        # module wins over ref
        assert "docker/build-push-action" in ext_files
        # ref used when no module
        assert "actions/checkout@v4" in ext_files
        assert "astral-sh/setup-uv@v5" in ext_files
        # symbol used when no module or ref
        assert "bare_symbol" in ext_files
        # unknown when nothing available
        assert "unknown" in ext_files

    def test_external_deps_distinct_nodes(self):
        """Multiple distinct external deps should not collapse into one node."""
        with patch(
            "cocosearch.deps.query.get_dependencies",
            side_effect=_mock_get_dependencies(_REF_METADATA_DEPS),
        ):
            tree = get_dependency_tree("test", "workflow.yml", max_depth=5)

        ext = [c for c in tree.children if c.is_external]
        ext_files = [c.file for c in ext]
        # All 5 are separate children (no collapsing)
        assert len(ext_files) == 5
        # 4 of 5 have unique names
        unique_named = [f for f in ext_files if f != "unknown"]
        assert len(set(unique_named)) == len(unique_named)


# ============================================================================
# Tests: get_impact
# ============================================================================


class TestGetImpact:
    """Tests for get_impact() reverse BFS."""

    def test_linear_impact(self):
        with patch(
            "cocosearch.deps.query.get_dependents",
            side_effect=_mock_get_dependents(_LINEAR_DEPENDENTS),
        ):
            tree = get_impact("test", "d.py", max_depth=5)

        assert tree.file == "d.py"
        assert len(tree.children) == 1
        assert tree.children[0].file == "c.py"

        c_node = tree.children[0]
        assert len(c_node.children) == 1
        assert c_node.children[0].file == "b.py"

    def test_depth_limit(self):
        with patch(
            "cocosearch.deps.query.get_dependents",
            side_effect=_mock_get_dependents(_LINEAR_DEPENDENTS),
        ):
            tree = get_impact("test", "d.py", max_depth=1)

        assert len(tree.children) == 1
        assert tree.children[0].children == []

    def test_empty_impact(self):
        with patch(
            "cocosearch.deps.query.get_dependents",
            return_value=[],
        ):
            tree = get_impact("test", "leaf.py")

        assert tree.file == "leaf.py"
        assert tree.children == []


# ============================================================================
# Helpers
# ============================================================================


def _collect_files(tree, files=None):
    """Collect all file names in a tree (including root)."""
    if files is None:
        files = []
    files.append(tree.file)
    for child in tree.children:
        _collect_files(child, files)
    return files
