"""Symbol extraction using tree-sitter for multiple programming languages.

Extracts function, class, method, and interface definitions from source code
using tree-sitter query-based parsing. Provides metadata for symbol-aware
indexing and search.

Supported languages:
- Python: functions, classes, methods (async supported)
- JavaScript: functions, arrow functions, classes, methods
- TypeScript: functions, classes, methods, interfaces, type aliases
- Go: functions, methods (with receiver), structs, interfaces
- Rust: functions, methods (in impl blocks), structs, traits, enums
- Java: classes, interfaces, enums, methods, constructors
- Ruby: classes, modules, methods, singleton methods
- C: functions, structs, enums, typedefs
- C++: functions, classes, structs, namespaces, methods
- PHP: functions, classes, interfaces, traits, methods
- HCL: blocks (resource, variable, data, module, locals, output, provider)
- Terraform: blocks (same as HCL — identical AST structure)

Features:
- Query-based extraction using external .scm files
- User-extensible: override queries in ~/.cocosearch/queries/ or .cocosearch/queries/
- Methods use qualified names: "ClassName.method_name"
- Graceful error handling (returns NULL fields on parse errors)
"""

import dataclasses
import logging
import importlib.resources
from pathlib import Path
from tree_sitter import Parser, Query, QueryCursor
from tree_sitter_language_pack import get_parser as pack_get_parser, get_language
import cocoindex

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class SymbolMetadata:
    """Metadata extracted from a code symbol."""

    symbol_type: str | None
    symbol_name: str | None
    symbol_signature: str | None


# ============================================================================
# Language Mapping (file extension to tree-sitter language name)
# ============================================================================

LANGUAGE_MAP = {
    # JavaScript
    "js": "javascript",
    "jsx": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    # TypeScript
    "ts": "typescript",
    "tsx": "typescript",
    "mts": "typescript",
    "cts": "typescript",
    # Go
    "go": "go",
    # Rust
    "rs": "rust",
    # Python
    "py": "python",
    "python": "python",
    # Java
    "java": "java",
    # C
    "c": "c",
    "h": "c",
    # C++
    "cpp": "cpp",
    "cxx": "cpp",
    "cc": "cpp",
    "hpp": "cpp",
    "hxx": "cpp",
    "hh": "cpp",
    # Ruby
    "rb": "ruby",
    # PHP
    "php": "php",
    # Bash
    "sh": "bash",
    "bash": "bash",
    "zsh": "bash",
    # HCL / Terraform
    "tf": "terraform",
    "hcl": "hcl",
    "tfvars": "hcl",
    # Scala
    "scala": "scala",
}

# ============================================================================
# Module-level parser cache (lazy, one-time setup per language)
# ============================================================================

_PARSERS: dict[str, Parser] = {}


def _get_parser(language: str) -> Parser:
    """Get or initialize a tree-sitter parser for the given language.

    Lazy initialization to avoid overhead if language not used.
    Parsers are cached by tree-sitter language name (not file extension).

    Args:
        language: Tree-sitter language name (e.g., "python", "javascript").

    Returns:
        Parser configured for the specified language.
    """
    global _PARSERS

    if language not in _PARSERS:
        _PARSERS[language] = pack_get_parser(language)

    return _PARSERS[language]


# ============================================================================
# Query File Resolution
# ============================================================================


def resolve_query_file(language: str, project_path: Path | None = None) -> str | None:
    """Resolve query file with priority: Project > User > Built-in.

    Args:
        language: Tree-sitter language name (e.g., "python", "javascript").
        project_path: Optional project root path for project-level overrides.

    Returns:
        Query file contents as string, or None if language not supported.
    """
    query_name = f"{language}.scm"

    # Priority 1: Project-level override
    if project_path:
        project_query = project_path / ".cocosearch" / "queries" / query_name
        if project_query.exists():
            return project_query.read_text()

    # Priority 2: User-level override
    user_path = Path.home() / ".cocosearch" / "queries" / query_name
    if user_path.exists():
        return user_path.read_text()

    # Priority 3: Built-in queries
    try:
        return (
            importlib.resources.files("cocosearch.indexer.queries")
            .joinpath(query_name)
            .read_text()
        )
    except FileNotFoundError:
        return None


# ============================================================================
# Helper Functions
# ============================================================================


def _get_node_text(source_text: str, node) -> str:
    """Extract text from syntax tree node.

    Args:
        source_text: The full source code text.
        node: Tree-sitter node to extract text from.

    Returns:
        Text content of the node.
    """
    if node is None:
        return ""
    return source_text[node.start_byte : node.end_byte]


def _map_symbol_type(raw_type: str) -> str:
    """Map query capture types to database symbol types.

    Args:
        raw_type: Raw capture type from query (e.g., "class", "function", "struct").

    Returns:
        Normalized symbol type for database.
    """
    mapping = {
        "function": "function",
        "method": "method",
        "class": "class",
        "interface": "interface",
        "struct": "class",
        "enum": "class",
        "trait": "interface",
        "module": "class",
        "namespace": "class",
        "type": "interface",
        "block": "class",
    }
    return mapping.get(raw_type, "function")


def _get_container_name(node, chunk_text: str, language: str) -> str | None:
    """Extract name from container node (class, struct, module, etc.).

    Args:
        node: Container node.
        chunk_text: Source code text.
        language: Language name.

    Returns:
        Container name, or None if not found.
    """
    # Try field name "name" first (most common)
    name_node = node.child_by_field_name("name")
    if name_node:
        return _get_node_text(chunk_text, name_node)

    # For some languages, scan children for identifier nodes
    for child in node.children:
        if child.type in ("identifier", "type_identifier"):
            return _get_node_text(chunk_text, child)

    return None


def _build_qualified_name(node, name: str, chunk_text: str, language: str) -> str:
    """Build qualified name with parent context (e.g., ClassName.method_name).

    Args:
        node: Definition node.
        name: Symbol name.
        chunk_text: Source code text.
        language: Language name.

    Returns:
        Qualified name with parent context.
    """
    # Special handling for Go methods - extract receiver type
    if language == "go" and node.type == "method_declaration":
        # Find the receiver parameter_list (first parameter_list child)
        for child in node.children:
            if child.type == "parameter_list":
                # This is the receiver
                for param_child in child.children:
                    if param_child.type == "parameter_declaration":
                        # Find the type (pointer_type or type_identifier)
                        for type_child in param_child.children:
                            if type_child.type == "pointer_type":
                                # Extract type_identifier from pointer_type
                                for ptr_child in type_child.children:
                                    if ptr_child.type == "type_identifier":
                                        receiver_type = _get_node_text(
                                            chunk_text, ptr_child
                                        )
                                        return f"{receiver_type}.{name}"
                            elif type_child.type == "type_identifier":
                                receiver_type = _get_node_text(chunk_text, type_child)
                                return f"{receiver_type}.{name}"
                break

    # HCL/Terraform: extract labels from string_lit children of the block node
    if language in ("hcl", "terraform"):
        labels = []
        for child in node.children:
            if child.type == "string_lit":
                for sub in child.children:
                    if sub.type == "template_literal":
                        labels.append(_get_node_text(chunk_text, sub))
                        break
        if labels:
            return ".".join(labels)
        return name  # fallback to identifier (e.g., "locals")

    container_types = {
        "python": ["class_definition"],
        "javascript": ["class_declaration", "class_body"],
        "typescript": ["class_declaration", "class_body"],
        "go": [],  # Go methods use receiver extraction above
        "rust": ["impl_item"],
        "java": ["class_declaration", "interface_declaration", "enum_declaration"],
        "c": ["struct_specifier"],
        "cpp": ["class_specifier", "struct_specifier", "namespace_definition"],
        "ruby": ["class", "module"],
        "php": ["class_declaration", "interface_declaration", "trait_declaration"],
        "scala": ["class_definition", "trait_definition", "object_definition"],
    }

    parents = []
    parent = node.parent
    while parent:
        if parent.type in container_types.get(language, []):
            parent_name = _get_container_name(parent, chunk_text, language)
            if parent_name:
                parents.append(parent_name)
        parent = parent.parent

    if not parents:
        return name

    separator = "::" if language in ("cpp",) else "."
    return separator.join(reversed(parents)) + separator + name


def _build_signature(node, chunk_text: str, language: str, symbol_type: str) -> str:
    """Build symbol signature from node.

    Extracts the declaration line without the body. For functions, this means
    everything up to (but not including) the opening brace or up to and including
    the colon for Python.

    Args:
        node: Definition node.
        chunk_text: Source code text.
        language: Language name.
        symbol_type: Symbol type (function, class, etc.).

    Returns:
        Symbol signature string.
    """
    node_text = _get_node_text(chunk_text, node)

    # For most languages, find the body and extract everything before it
    if language == "python":
        # Python uses colon at end of definition line - include it
        # The colon appears after the closing ) of parameters and optional -> return_type
        # For multiline signatures, we need to find where the signature ends

        # Find the colon that marks the end of the definition
        # Strategy: find first occurrence of ":\n" which marks definition end
        colon_newline = node_text.find(":\n")
        if colon_newline != -1:
            # Found definition-ending colon followed by newline
            signature = node_text[: colon_newline + 1].strip()
        else:
            # Single-line or no body - find last colon before end
            colon_pos = node_text.rfind(":")
            if colon_pos != -1:
                signature = node_text[: colon_pos + 1].strip()
            else:
                # No colon found (shouldn't happen for valid Python)
                lines = node_text.split("\n")
                signature = lines[0].strip()
    else:
        # Other languages use braces - exclude the brace
        brace_pos = node_text.find("{")
        if brace_pos != -1:
            signature = node_text[:brace_pos].strip()
        else:
            # No body found, use first line
            lines = node_text.split("\n")
            signature = lines[0].strip()

    # Truncate if too long (200 chars accommodates most realistic signatures)
    if len(signature) > 200:
        signature = signature[:197] + "..."

    return signature


# ============================================================================
# Query-Based Symbol Extraction
# ============================================================================


def _extract_symbols_with_query(
    chunk_text: str, language: str, query_text: str
) -> list[dict]:
    """Extract symbols using tree-sitter query.

    Args:
        chunk_text: Source code text.
        language: Tree-sitter language name.
        query_text: Query file contents (.scm format).

    Returns:
        List of symbol dicts with symbol_type, symbol_name, symbol_signature.
    """
    lang = get_language(language)
    parser = _get_parser(language)
    tree = parser.parse(bytes(chunk_text, "utf8"))

    query = Query(lang, query_text)
    cursor = QueryCursor(query)
    captures_dict = cursor.captures(tree.root_node)

    symbols = []
    # Build mappings: definition_node -> (symbol_type, name_text)
    definitions = {}  # node.id -> (node, capture_type)
    names = {}  # parent_node.id -> name_text

    # Process captures from dict structure - definitions first, then names
    # This ensures all definition nodes are registered before we try to match names
    for capture_name, nodes in captures_dict.items():
        if capture_name.startswith("definition."):
            symbol_type = capture_name.split(".", 1)[1]
            for node in nodes:
                definitions[node.id] = (node, symbol_type)

    for capture_name, nodes in captures_dict.items():
        if capture_name == "name":
            for node in nodes:
                # Find parent that is a definition
                parent = node.parent
                while parent:
                    if parent.id in definitions:
                        names[parent.id] = chunk_text[node.start_byte : node.end_byte]
                        break
                    parent = parent.parent

    for node_id, (node, symbol_type) in definitions.items():
        name = names.get(node_id)
        if name:
            # Build qualified name for methods
            qualified_name = _build_qualified_name(node, name, chunk_text, language)
            signature = _build_signature(node, chunk_text, language, symbol_type)

            symbols.append(
                {
                    "symbol_type": _map_symbol_type(symbol_type),
                    "symbol_name": qualified_name,
                    "symbol_signature": signature,
                }
            )

    return symbols


# ============================================================================
# Main Extract Function
# ============================================================================


@cocoindex.op.function()
def extract_symbol_metadata(text: str, language: str) -> SymbolMetadata:
    """Extract symbol metadata from code chunk.

    This is a CocoIndex transform function that extracts symbol information
    from code chunks during indexing. Supports Python, JavaScript, TypeScript,
    Go, and Rust.

    Args:
        text: The chunk text content.
        language: Language identifier (e.g., "py", "python", "js", "ts", "go", "rs").

    Returns:
        Dict with three fields:
        - symbol_type: "function", "class", "method", "interface", or None
        - symbol_name: Symbol name (qualified for methods), or None
        - symbol_signature: Full signature as written, or None

        Returns NULL fields if:
        - Chunk contains no symbols
        - Parse error occurs
        - Language not supported
    """
    # Map extension to tree-sitter language name
    ts_language = LANGUAGE_MAP.get(language)

    # Return NULL fields for unsupported languages
    if ts_language is None:
        return SymbolMetadata(
            symbol_type=None,
            symbol_name=None,
            symbol_signature=None,
        )

    try:
        query_text = resolve_query_file(ts_language)
        if query_text is None:
            # No query file for this language - index without symbols
            return SymbolMetadata(
                symbol_type=None,
                symbol_name=None,
                symbol_signature=None,
            )

        symbols = _extract_symbols_with_query(text, ts_language, query_text)

        if symbols:
            return SymbolMetadata(**symbols[0])
        return SymbolMetadata(
            symbol_type=None,
            symbol_name=None,
            symbol_signature=None,
        )

    except Exception as e:
        # Catastrophic failure - log and return NULLs
        logger.error(f"Symbol extraction failed: {e}", exc_info=True)
        return SymbolMetadata(
            symbol_type=None,
            symbol_name=None,
            symbol_signature=None,
        )


__all__ = ["extract_symbol_metadata", "SymbolMetadata", "LANGUAGE_MAP"]
