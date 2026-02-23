"""Tests for cocosearch.deps.models module."""

import pytest

from cocosearch.deps.models import (
    DepType,
    DependencyEdge,
    DependencyTree,
    get_deps_table_name,
)
from cocosearch.exceptions import IndexValidationError


@pytest.mark.unit
class TestDepType:
    """Tests for DepType string constants."""

    def test_import_value(self):
        """DepType.IMPORT should be 'import'."""
        assert DepType.IMPORT == "import"

    def test_call_value(self):
        """DepType.CALL should be 'call'."""
        assert DepType.CALL == "call"

    def test_reference_value(self):
        """DepType.REFERENCE should be 'reference'."""
        assert DepType.REFERENCE == "reference"

    def test_values_are_strings(self):
        """All DepType values should be plain strings."""
        assert isinstance(DepType.IMPORT, str)
        assert isinstance(DepType.CALL, str)
        assert isinstance(DepType.REFERENCE, str)


@pytest.mark.unit
class TestDependencyEdge:
    """Tests for DependencyEdge dataclass."""

    def test_import_edge(self):
        """Create an import dependency edge."""
        edge = DependencyEdge(
            source_file="src/main.py",
            source_symbol="main",
            target_file="src/utils.py",
            target_symbol="helper",
            dep_type=DepType.IMPORT,
        )
        assert edge.source_file == "src/main.py"
        assert edge.source_symbol == "main"
        assert edge.target_file == "src/utils.py"
        assert edge.target_symbol == "helper"
        assert edge.dep_type == "import"
        assert edge.metadata == {}

    def test_call_edge(self):
        """Create a call dependency edge."""
        edge = DependencyEdge(
            source_file="src/main.py",
            source_symbol="run",
            target_file="src/db.py",
            target_symbol="connect",
            dep_type=DepType.CALL,
        )
        assert edge.dep_type == "call"

    def test_reference_edge(self):
        """Create a reference dependency edge."""
        edge = DependencyEdge(
            source_file="src/main.py",
            source_symbol=None,
            target_file="src/config.py",
            target_symbol="DEFAULT_TIMEOUT",
            dep_type=DepType.REFERENCE,
        )
        assert edge.dep_type == "reference"
        assert edge.source_symbol is None

    def test_external_dependency_null_target_file(self):
        """External dependency has None target_file."""
        edge = DependencyEdge(
            source_file="src/main.py",
            source_symbol=None,
            target_file=None,
            target_symbol="requests",
            dep_type=DepType.IMPORT,
        )
        assert edge.target_file is None
        assert edge.target_symbol == "requests"

    def test_both_symbols_none(self):
        """Edge with no symbol information (file-level dependency)."""
        edge = DependencyEdge(
            source_file="src/main.py",
            source_symbol=None,
            target_file="src/utils.py",
            target_symbol=None,
            dep_type=DepType.IMPORT,
        )
        assert edge.source_symbol is None
        assert edge.target_symbol is None

    def test_metadata_default_empty_dict(self):
        """Metadata should default to an empty dict."""
        edge = DependencyEdge(
            source_file="src/main.py",
            source_symbol=None,
            target_file=None,
            target_symbol=None,
            dep_type=DepType.IMPORT,
        )
        assert edge.metadata == {}

    def test_metadata_custom_values(self):
        """Metadata can carry custom key-value pairs."""
        edge = DependencyEdge(
            source_file="src/main.py",
            source_symbol=None,
            target_file=None,
            target_symbol="os",
            dep_type=DepType.IMPORT,
            metadata={"line": 5, "alias": "operating_system"},
        )
        assert edge.metadata["line"] == 5
        assert edge.metadata["alias"] == "operating_system"

    def test_metadata_isolation_between_instances(self):
        """Each edge instance should have its own metadata dict."""
        edge1 = DependencyEdge(
            source_file="a.py",
            source_symbol=None,
            target_file=None,
            target_symbol=None,
            dep_type=DepType.IMPORT,
        )
        edge2 = DependencyEdge(
            source_file="b.py",
            source_symbol=None,
            target_file=None,
            target_symbol=None,
            dep_type=DepType.IMPORT,
        )
        edge1.metadata["key"] = "value"
        assert "key" not in edge2.metadata


@pytest.mark.unit
class TestDependencyTree:
    """Tests for DependencyTree dataclass."""

    def test_leaf_node(self):
        """A leaf node has no children."""
        leaf = DependencyTree(
            file="src/utils.py",
            symbol="helper",
            dep_type=DepType.IMPORT,
        )
        assert leaf.file == "src/utils.py"
        assert leaf.symbol == "helper"
        assert leaf.dep_type == "import"
        assert leaf.children == []

    def test_leaf_node_no_symbol(self):
        """A leaf node with no symbol."""
        leaf = DependencyTree(
            file="src/utils.py",
            symbol=None,
            dep_type=DepType.IMPORT,
        )
        assert leaf.symbol is None

    def test_nested_tree(self):
        """A tree with nested children."""
        child1 = DependencyTree(
            file="src/db.py",
            symbol="connect",
            dep_type=DepType.CALL,
        )
        child2 = DependencyTree(
            file="src/config.py",
            symbol="load",
            dep_type=DepType.IMPORT,
        )
        root = DependencyTree(
            file="src/main.py",
            symbol="main",
            dep_type=DepType.REFERENCE,
            children=[child1, child2],
        )
        assert len(root.children) == 2
        assert root.children[0].file == "src/db.py"
        assert root.children[0].dep_type == "call"
        assert root.children[1].file == "src/config.py"
        assert root.children[1].dep_type == "import"

    def test_deeply_nested_tree(self):
        """A tree with multiple levels of nesting."""
        grandchild = DependencyTree(
            file="src/logger.py",
            symbol="setup",
            dep_type=DepType.CALL,
        )
        child = DependencyTree(
            file="src/db.py",
            symbol="init",
            dep_type=DepType.CALL,
            children=[grandchild],
        )
        root = DependencyTree(
            file="src/main.py",
            symbol="main",
            dep_type=DepType.REFERENCE,
            children=[child],
        )
        assert root.children[0].children[0].file == "src/logger.py"
        assert root.children[0].children[0].symbol == "setup"

    def test_children_isolation_between_instances(self):
        """Each tree instance should have its own children list."""
        tree1 = DependencyTree(file="a.py", symbol=None, dep_type=DepType.IMPORT)
        tree2 = DependencyTree(file="b.py", symbol=None, dep_type=DepType.IMPORT)
        tree1.children.append(
            DependencyTree(file="c.py", symbol=None, dep_type=DepType.CALL)
        )
        assert len(tree2.children) == 0

    def test_is_external_default_false(self):
        """is_external defaults to False."""
        tree = DependencyTree(file="a.py", symbol=None, dep_type=DepType.IMPORT)
        assert tree.is_external is False

    def test_is_external_set_true(self):
        """is_external can be set to True."""
        tree = DependencyTree(
            file="fmt", symbol="fmt", dep_type=DepType.IMPORT, is_external=True
        )
        assert tree.is_external is True

    def test_to_dict_omits_is_external_when_false(self):
        """to_dict() should not include is_external when False."""
        tree = DependencyTree(file="a.py", symbol=None, dep_type=DepType.IMPORT)
        d = tree.to_dict()
        assert "is_external" not in d

    def test_to_dict_includes_is_external_when_true(self):
        """to_dict() should include is_external when True."""
        tree = DependencyTree(
            file="fmt", symbol="fmt", dep_type=DepType.IMPORT, is_external=True
        )
        d = tree.to_dict()
        assert d["is_external"] is True

    def test_to_dict_nested_with_external_child(self):
        """to_dict() correctly serializes a tree with an external child."""
        ext_child = DependencyTree(
            file="fmt", symbol="fmt", dep_type=DepType.IMPORT, is_external=True
        )
        local_child = DependencyTree(
            file="src/utils.py", symbol=None, dep_type=DepType.IMPORT
        )
        root = DependencyTree(
            file="src/main.py",
            symbol=None,
            dep_type="root",
            children=[local_child, ext_child],
        )
        d = root.to_dict()
        assert "is_external" not in d
        assert "is_external" not in d["children"][0]
        assert d["children"][1]["is_external"] is True


@pytest.mark.unit
class TestGetDepsTableName:
    """Tests for get_deps_table_name()."""

    def test_valid_name(self):
        """Valid index name produces correct table name."""
        assert get_deps_table_name("myindex") == "cocosearch_deps_myindex"

    def test_valid_name_with_underscores(self):
        """Index name with underscores is accepted."""
        assert get_deps_table_name("my_index_2") == "cocosearch_deps_my_index_2"

    def test_empty_name_raises(self):
        """Empty index name raises IndexValidationError."""
        with pytest.raises(IndexValidationError):
            get_deps_table_name("")

    def test_invalid_name_with_special_chars_raises(self):
        """Index name with special characters raises IndexValidationError."""
        with pytest.raises(IndexValidationError):
            get_deps_table_name("my-index")

    def test_invalid_name_with_sql_injection_raises(self):
        """Index name with SQL injection attempt raises IndexValidationError."""
        with pytest.raises(IndexValidationError):
            get_deps_table_name("'; DROP TABLE users; --")
