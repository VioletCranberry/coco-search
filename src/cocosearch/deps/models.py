"""Data models for the dependency graph framework.

Defines the core types used to represent dependency relationships
between code symbols: edges (pairwise relationships), trees
(recursive dependency chains), and table naming conventions.
"""

from dataclasses import dataclass, field

from cocosearch.validation import validate_index_name


class DepType:
    """String constants for dependency types."""

    IMPORT = "import"
    CALL = "call"
    REFERENCE = "reference"


@dataclass
class DependencyEdge:
    """A single directed dependency between two code locations.

    Represents a pairwise relationship from a source symbol in one file
    to a target symbol in another file (or an external package).

    Attributes:
        source_file: Path to the file containing the dependency origin.
        source_symbol: Name of the symbol at the origin, or None for
            file-level dependencies.
        target_file: Path to the file being depended on, or None for
            external (third-party) dependencies.
        target_symbol: Name of the target symbol, or None for file-level
            dependencies.
        dep_type: The kind of dependency (import, call, reference).
        metadata: Arbitrary key-value pairs for extractor-specific data
            (e.g., line number, alias, whether it's a wildcard import).
    """

    source_file: str
    source_symbol: str | None
    target_file: str | None
    target_symbol: str | None
    dep_type: str
    metadata: dict = field(default_factory=dict)


@dataclass
class DependencyTree:
    """A recursive tree of dependencies rooted at a symbol.

    Used to represent the full transitive dependency chain starting
    from a given file/symbol. Each node's children are the symbols
    it depends on, forming a tree structure.

    Attributes:
        file: Path to the file at this tree node.
        symbol: Name of the symbol, or None for file-level nodes.
        dep_type: The kind of dependency linking this node to its parent.
        children: Direct dependencies of this node.
    """

    file: str
    symbol: str | None
    dep_type: str
    children: list["DependencyTree"] = field(default_factory=list)
    is_external: bool = False

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dict."""
        d = {
            "file": self.file,
            "symbol": self.symbol,
            "dep_type": self.dep_type,
            "children": [c.to_dict() for c in self.children],
        }
        if self.is_external:
            d["is_external"] = True
        return d


def get_deps_table_name(index_name: str) -> str:
    """Return the PostgreSQL table name for dependency edges.

    Args:
        index_name: The index name (validated for safe SQL use).

    Returns:
        Table name in the form ``cocosearch_deps_{index_name}``.

    Raises:
        IndexValidationError: If the index name is invalid.
    """
    validate_index_name(index_name)
    return f"cocosearch_deps_{index_name}"
