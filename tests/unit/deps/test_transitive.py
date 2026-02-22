"""Tests for transitive dependency queries (BFS tree/impact)."""

from unittest.mock import patch

from cocosearch.deps.models import DependencyEdge, DepType
from cocosearch.deps.query import get_dependency_tree, get_impact


def _edge(source, target, dep_type=DepType.IMPORT, symbol=None):
    """Create a simple DependencyEdge for testing."""
    return DependencyEdge(
        source_file=source,
        source_symbol=None,
        target_file=target,
        target_symbol=symbol,
        dep_type=dep_type,
        metadata={},
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
