"""JavaScript and TypeScript import dependency extractor.

Extracts import statements from JS/TS source files using tree-sitter
and produces DependencyEdge objects for each imported module.

Handles all standard import forms:
- ES6: ``import X from 'Y'``, ``import { A, B } from 'Y'``,
  ``import * as X from 'Y'``
- Re-exports: ``export { X } from 'Y'``, ``export * from 'Y'``
- CommonJS: ``require('Y')``, ``const X = require('Y')``
- TypeScript: ``import type { X } from 'Y'``
"""

from tree_sitter import Parser
from tree_sitter_language_pack import get_parser

from cocosearch.deps.models import DependencyEdge, DepType

# Lazy parser caches (one per grammar)
_js_parser: Parser | None = None
_ts_parser: Parser | None = None

_TS_EXTENSIONS = frozenset({"ts", "tsx", "mts", "cts"})


def _get_parser(ext: str) -> Parser:
    """Get or create the cached tree-sitter parser for the given extension."""
    global _js_parser, _ts_parser

    if ext in _TS_EXTENSIONS:
        if _ts_parser is None:
            _ts_parser = get_parser("typescript")
        return _ts_parser

    if _js_parser is None:
        _js_parser = get_parser("javascript")
    return _js_parser


def _node_text(source: bytes, node) -> str:
    """Extract text content from a tree-sitter node."""
    return source[node.start_byte : node.end_byte].decode("utf8")


def _strip_quotes(s: str) -> str:
    """Strip surrounding quotes from a string literal."""
    if len(s) >= 2 and s[0] in ('"', "'", "`") and s[-1] == s[0]:
        return s[1:-1]
    return s


class JavaScriptImportExtractor:
    """Extractor for JavaScript/TypeScript import dependency edges.

    Parses JS/TS source files using tree-sitter and extracts one
    DependencyEdge per import/require statement.  The ``source_file``
    field is left empty (filled by the orchestrator).
    """

    LANGUAGES: set[str] = {"js", "jsx", "mjs", "cjs", "ts", "tsx", "mts", "cts"}

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        if not content:
            return []

        ext = file_path.rsplit(".", 1)[-1] if "." in file_path else "js"
        parser = _get_parser(ext)
        source = content.encode("utf8")
        tree = parser.parse(source)

        edges: list[DependencyEdge] = []
        self._walk(source, tree.root_node, edges, ext)
        return edges

    def _walk(self, source: bytes, node, edges: list[DependencyEdge], ext: str):
        """Recursively walk the AST to find imports and requires."""
        if node.type == "import_statement":
            edges.extend(self._handle_import(source, node, ext))
        elif node.type == "export_statement":
            edges.extend(self._handle_export(source, node, ext))
        elif node.type == "call_expression":
            edge = self._handle_require(source, node)
            if edge is not None:
                edges.append(edge)

        for child in node.children:
            self._walk(source, child, edges, ext)

    # ------------------------------------------------------------------
    # ES6 imports
    # ------------------------------------------------------------------

    def _handle_import(
        self, source: bytes, node, ext: str
    ) -> list[DependencyEdge]:
        """Handle ES6 import statements."""
        line = node.start_point.row + 1
        module = self._extract_source_string(source, node)
        if not module:
            return []

        metadata: dict = {"module": module, "line": line}

        # Detect TypeScript `import type`
        if ext in _TS_EXTENSIONS:
            text = _node_text(source, node)
            if text.startswith("import type ") or text.startswith("import type{"):
                metadata["import_kind"] = "type"
            else:
                metadata["import_kind"] = "value"

        return [
            DependencyEdge(
                source_file="",
                source_symbol=None,
                target_file=None,
                target_symbol=None,
                dep_type=DepType.IMPORT,
                metadata=metadata,
            )
        ]

    # ------------------------------------------------------------------
    # Re-exports
    # ------------------------------------------------------------------

    def _handle_export(
        self, source: bytes, node, ext: str
    ) -> list[DependencyEdge]:
        """Handle re-export statements with a source (``export { X } from 'Y'``)."""
        line = node.start_point.row + 1
        module = self._extract_source_string(source, node)
        if not module:
            return []

        metadata: dict = {"module": module, "line": line}

        if ext in _TS_EXTENSIONS:
            text = _node_text(source, node)
            if "export type" in text:
                metadata["import_kind"] = "type"
            else:
                metadata["import_kind"] = "value"

        return [
            DependencyEdge(
                source_file="",
                source_symbol=None,
                target_file=None,
                target_symbol=None,
                dep_type=DepType.IMPORT,
                metadata=metadata,
            )
        ]

    # ------------------------------------------------------------------
    # CommonJS require()
    # ------------------------------------------------------------------

    def _handle_require(
        self, source: bytes, node
    ) -> DependencyEdge | None:
        """Handle ``require('module')`` calls."""
        # Callee must be the identifier 'require'
        callee = node.child_by_field_name("function")
        if callee is None:
            return None
        if callee.type != "identifier" or _node_text(source, callee) != "require":
            return None

        # Get the arguments
        args = node.child_by_field_name("arguments")
        if args is None:
            return None

        # First argument should be a string
        for child in args.children:
            if child.type == "string":
                module = _strip_quotes(_node_text(source, child))
                line = node.start_point.row + 1
                return DependencyEdge(
                    source_file="",
                    source_symbol=None,
                    target_file=None,
                    target_symbol=None,
                    dep_type=DepType.IMPORT,
                    metadata={"module": module, "line": line},
                )

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_source_string(source: bytes, node) -> str:
        """Extract the module path string from an import/export statement.

        Looks for a ``source`` field or a ``string`` child node.
        """
        # Try the 'source' field first (ES6 standard)
        source_node = node.child_by_field_name("source")
        if source_node is not None:
            return _strip_quotes(_node_text(source, source_node))

        # Fall back to finding a string child
        for child in node.children:
            if child.type == "string":
                return _strip_quotes(_node_text(source, child))

        return ""
