"""Go import dependency extractor.

Extracts import declarations from Go source files using tree-sitter
and produces DependencyEdge objects for each imported package.

Handles all standard import forms:
- Single: ``import "fmt"``
- Grouped: ``import ("fmt"; "os")``
- Aliased: ``import f "fmt"``
- Blank: ``import _ "database/sql"``
"""

from tree_sitter import Parser
from tree_sitter_language_pack import get_parser

from cocosearch.deps.models import DependencyEdge, DepType

_parser: Parser | None = None


def _get_parser() -> Parser:
    """Get or create the cached Go tree-sitter parser."""
    global _parser
    if _parser is None:
        _parser = get_parser("go")
    return _parser


def _node_text(source: bytes, node) -> str:
    """Extract text content from a tree-sitter node."""
    return source[node.start_byte : node.end_byte].decode("utf8")


def _strip_quotes(s: str) -> str:
    """Strip surrounding quotes from a Go string literal."""
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


class GoImportExtractor:
    """Extractor for Go import dependency edges.

    Parses Go source files using tree-sitter and extracts one
    DependencyEdge per imported package.  The ``source_file`` field
    is left empty (filled by the orchestrator).
    """

    LANGUAGES: set[str] = {"go"}

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        if not content:
            return []

        parser = _get_parser()
        source = content.encode("utf8")
        tree = parser.parse(source)

        edges: list[DependencyEdge] = []

        # Stack-based walk to find imports nested inside function bodies, etc.
        stack = list(tree.root_node.children)
        while stack:
            node = stack.pop()
            if node.type == "import_declaration":
                edges.extend(self._handle_import_declaration(source, node))
            else:
                stack.extend(node.children)

        return edges

    def _handle_import_declaration(self, source: bytes, node) -> list[DependencyEdge]:
        """Handle an import declaration (single or grouped)."""
        edges: list[DependencyEdge] = []

        for child in node.children:
            if child.type == "import_spec":
                edge = self._handle_import_spec(source, child)
                if edge is not None:
                    edges.append(edge)
            elif child.type == "import_spec_list":
                for spec in child.children:
                    if spec.type == "import_spec":
                        edge = self._handle_import_spec(source, spec)
                        if edge is not None:
                            edges.append(edge)

        return edges

    def _handle_import_spec(self, source: bytes, node) -> DependencyEdge | None:
        """Handle a single import spec."""
        line = node.start_point.row + 1
        path_node = node.child_by_field_name("path")
        if path_node is None:
            return None

        module = _strip_quotes(_node_text(source, path_node))
        metadata: dict = {"module": module, "line": line}

        # Check for alias (including blank import `_`)
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            alias = _node_text(source, name_node)
            if alias == ".":
                metadata["alias"] = "."
            else:
                metadata["alias"] = alias

        return DependencyEdge(
            source_file="",
            source_symbol=None,
            target_file=None,
            target_symbol=None,
            dep_type=DepType.IMPORT,
            metadata=metadata,
        )
