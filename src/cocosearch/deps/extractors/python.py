"""Python import dependency extractor.

Extracts import statements from Python source files using tree-sitter
and produces DependencyEdge objects for each imported name.

Handles all standard import forms:
- ``import os``
- ``import numpy as np``
- ``from os.path import join``
- ``from os.path import join, exists``
- ``from collections import OrderedDict as OD``
- ``from os.path import *``
- ``from . import utils`` (relative imports)
"""

from tree_sitter import Parser
from tree_sitter_language_pack import get_parser

from cocosearch.deps.models import DependencyEdge, DepType

# Module-level parser cache (lazy, one-time setup)
_parser: Parser | None = None


def _get_parser() -> Parser:
    """Get or create the cached Python tree-sitter parser."""
    global _parser
    if _parser is None:
        _parser = get_parser("python")
    return _parser


def _node_text(source: bytes, node) -> str:
    """Extract text content from a tree-sitter node."""
    return source[node.start_byte : node.end_byte].decode("utf8")


class PythonImportExtractor:
    """Extractor for Python import dependency edges.

    Parses Python source files using tree-sitter and extracts one
    DependencyEdge per imported name. The ``source_file`` field is left
    empty (filled by the orchestrator).
    """

    LANGUAGES: set[str] = {"py"}

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        """Extract import dependency edges from a Python source file.

        Args:
            file_path: Relative path to the source file (unused here;
                source_file is set by the orchestrator).
            content: Full text content of the Python source file.

        Returns:
            List of DependencyEdge instances, one per imported name.
        """
        if not content:
            return []

        parser = _get_parser()
        source = content.encode("utf8")
        tree = parser.parse(source)

        edges: list[DependencyEdge] = []

        # Stack-based walk to find imports nested inside try/except,
        # if TYPE_CHECKING:, function bodies, etc.
        stack = list(tree.root_node.children)
        while stack:
            node = stack.pop()
            if node.type == "import_statement":
                edges.extend(self._handle_import_statement(source, node))
            elif node.type == "import_from_statement":
                edges.extend(self._handle_import_from_statement(source, node))
            else:
                stack.extend(node.children)

        return edges

    # ------------------------------------------------------------------
    # import X / import X as Y
    # ------------------------------------------------------------------

    def _handle_import_statement(self, source: bytes, node) -> list[DependencyEdge]:
        """Handle ``import X`` and ``import X as Y`` statements."""
        edges: list[DependencyEdge] = []
        line = node.start_point.row + 1  # 0-indexed -> 1-indexed

        for child in node.children:
            if child.type == "dotted_name":
                # Plain import: import os / import os.path
                module = _node_text(source, child)
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=None,
                        target_file=None,
                        target_symbol=None,
                        dep_type=DepType.IMPORT,
                        metadata={"module": module, "line": line},
                    )
                )
            elif child.type == "aliased_import":
                # Aliased import: import numpy as np
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                module = _node_text(source, name_node) if name_node else ""
                metadata: dict = {"module": module, "line": line}
                if alias_node:
                    metadata["alias"] = _node_text(source, alias_node)
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=None,
                        target_file=None,
                        target_symbol=None,
                        dep_type=DepType.IMPORT,
                        metadata=metadata,
                    )
                )

        return edges

    # ------------------------------------------------------------------
    # from X import Y / from X import Y as Z / from X import *
    # ------------------------------------------------------------------

    def _handle_import_from_statement(
        self, source: bytes, node
    ) -> list[DependencyEdge]:
        """Handle ``from X import Y`` style statements."""
        line = node.start_point.row + 1

        # Extract the module part (dotted_name or relative_import)
        module = self._extract_module(source, node)

        # Collect imported names
        edges: list[DependencyEdge] = []
        seen_import_keyword = False

        for child in node.children:
            # Skip children before the "import" keyword (module part)
            if child.type == "import":
                seen_import_keyword = True
                continue
            if not seen_import_keyword:
                continue

            if child.type == "dotted_name":
                # from X import name
                name = _node_text(source, child)
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=None,
                        target_file=None,
                        target_symbol=name,
                        dep_type=DepType.IMPORT,
                        metadata={"module": module, "line": line},
                    )
                )
            elif child.type == "aliased_import":
                # from X import name as alias
                name_node = child.child_by_field_name("name")
                alias_node = child.child_by_field_name("alias")
                name = _node_text(source, name_node) if name_node else ""
                metadata: dict = {"module": module, "line": line}
                if alias_node:
                    metadata["alias"] = _node_text(source, alias_node)
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=None,
                        target_file=None,
                        target_symbol=name,
                        dep_type=DepType.IMPORT,
                        metadata=metadata,
                    )
                )
            elif child.type == "wildcard_import":
                # from X import *
                edges.append(
                    DependencyEdge(
                        source_file="",
                        source_symbol=None,
                        target_file=None,
                        target_symbol="*",
                        dep_type=DepType.IMPORT,
                        metadata={"module": module, "line": line},
                    )
                )

        return edges

    # ------------------------------------------------------------------
    # Module name extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_module(source: bytes, node) -> str:
        """Extract the module path from a from-import statement.

        Handles both absolute (``dotted_name``) and relative
        (``relative_import``) module references. Stops at the
        ``import`` keyword to avoid matching imported names.
        """
        for child in node.children:
            if child.type == "import":
                break  # module part comes before 'import' keyword
            if child.type == "dotted_name":
                # Absolute: from os.path import ...
                return _node_text(source, child)
            if child.type == "relative_import":
                # Relative: from . import ... / from ..models import ...
                return _node_text(source, child)

        return ""
