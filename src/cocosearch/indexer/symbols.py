"""Symbol extraction using tree-sitter for Python code.

Extracts function, class, and method definitions from Python source code
using tree-sitter query-based parsing. Provides metadata for symbol-aware
indexing and search.

Features:
- Extracts standalone functions, classes, and class methods
- Methods use qualified names: "ClassName.method_name"
- Handles decorated functions (@property, @classmethod, etc.)
- Skips nested functions (implementation details)
- Includes async keyword in signatures
- Graceful error handling (returns NULL fields on parse errors)
"""

import logging
from tree_sitter import Parser
from tree_sitter_languages import get_language
import cocoindex

logger = logging.getLogger(__name__)

# ============================================================================
# Module-level parser initialization (lazy, one-time setup)
# ============================================================================

_PY_LANGUAGE = None
_PY_PARSER = None


def _get_python_parser() -> Parser:
    """Get or initialize the Python tree-sitter parser.

    Lazy initialization to avoid overhead if symbols not used.

    Returns:
        Parser configured for Python language.
    """
    global _PY_LANGUAGE, _PY_PARSER

    if _PY_PARSER is None:
        _PY_LANGUAGE = get_language("python")
        _PY_PARSER = Parser()
        _PY_PARSER.set_language(_PY_LANGUAGE)

    return _PY_PARSER


# ============================================================================
# Symbol Extraction Logic
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
    return source_text[node.start_byte:node.end_byte]


def _find_parent_of_type(node, type_name: str):
    """Find first parent node of given type.

    Args:
        node: Starting node.
        type_name: Type to search for.

    Returns:
        Parent node of that type, or None if not found.
    """
    parent = node.parent
    while parent is not None:
        if parent.type == type_name:
            return parent
        parent = parent.parent
    return None


def _is_inside_class(node) -> bool:
    """Check if node is inside a class definition."""
    return _find_parent_of_type(node, "class_definition") is not None


def _is_nested_function(func_node) -> bool:
    """Check if function is nested inside another function.

    Nested functions are implementation details and should not be
    extracted as symbols.

    Args:
        func_node: Tree-sitter function_definition node.

    Returns:
        True if function is nested, False otherwise.
    """
    # Walk up parent chain looking for another function_definition
    # before hitting class_definition or module
    parent = func_node.parent
    while parent is not None:
        if parent.type == "function_definition":
            return True
        if parent.type in ("class_definition", "module"):
            return False
        parent = parent.parent
    return False


def _extract_all_symbols(chunk_text: str, parser: Parser) -> list[dict]:
    """Extract all symbols from chunk using a unified approach.

    This function walks the syntax tree and extracts:
    - Classes with their signatures
    - Methods (functions inside classes) with qualified names
    - Standalone functions (not in classes, not nested)

    Args:
        chunk_text: Source code text to parse.
        parser: Tree-sitter parser instance.

    Returns:
        List of symbol dicts with symbol_type, symbol_name, symbol_signature.
    """
    tree = parser.parse(bytes(chunk_text, "utf8"))
    symbols = []

    def walk_node(node, current_class=None):
        """Recursively walk tree and extract symbols."""

        if node.type == "class_definition":
            # Extract class symbol
            class_name_node = node.child_by_field_name("name")
            if class_name_node:
                class_name = _get_node_text(chunk_text, class_name_node)

                # Get superclasses if any
                superclasses_node = node.child_by_field_name("superclasses")
                if superclasses_node:
                    bases = _get_node_text(chunk_text, superclasses_node)
                    signature = f"class {class_name}{bases}:"
                else:
                    signature = f"class {class_name}:"

                symbols.append({
                    "symbol_type": "class",
                    "symbol_name": class_name,
                    "symbol_signature": signature,
                })

                # Now walk class body to find methods
                body_node = node.child_by_field_name("body")
                if body_node:
                    for child in body_node.children:
                        walk_node(child, current_class=class_name)

        elif node.type == "function_definition":
            # Check if nested (skip if so)
            if _is_nested_function(node):
                return

            # Extract function/method symbol
            func_name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")

            if func_name_node and params_node:
                func_name = _get_node_text(chunk_text, func_name_node)
                params = _get_node_text(chunk_text, params_node)

                # Check if async (async is a child node of function_definition)
                is_async = any(child.type == "async" for child in node.children)

                # Build signature
                prefix = "async def" if is_async else "def"
                signature = f"{prefix} {func_name}{params}"

                # Add return type if present
                return_type_node = node.child_by_field_name("return_type")
                if return_type_node:
                    return_type = _get_node_text(chunk_text, return_type_node)
                    signature += f" -> {return_type}"

                # Determine if method or function
                if current_class:
                    symbols.append({
                        "symbol_type": "method",
                        "symbol_name": f"{current_class}.{func_name}",
                        "symbol_signature": signature,
                    })
                else:
                    symbols.append({
                        "symbol_type": "function",
                        "symbol_name": func_name,
                        "symbol_signature": signature,
                    })

        elif node.type == "decorated_definition":
            # Handle decorated functions/classes
            # The actual definition is inside
            definition_node = node.child_by_field_name("definition")
            if definition_node:
                walk_node(definition_node, current_class=current_class)

        else:
            # For other node types, recurse into children
            # But only at module level (not inside functions/classes already handled)
            if current_class is None and node.type in ("module", "block"):
                for child in node.children:
                    # Don't recurse if we're not at top level
                    walk_node(child, current_class=None)

    # Start walking from root
    walk_node(tree.root_node)

    return symbols


@cocoindex.op.function()
def extract_symbol_metadata(text: str, language: str) -> dict:
    """Extract symbol metadata from code chunk.

    This is a CocoIndex transform function that extracts symbol information
    from code chunks during indexing. Supports Python only in Phase 29.

    Args:
        text: The chunk text content.
        language: Language identifier (e.g., "py", "python").

    Returns:
        Dict with three fields:
        - symbol_type: "function", "class", "method", or None
        - symbol_name: Symbol name (qualified for methods), or None
        - symbol_signature: Full signature as written, or None

        Returns NULL fields if:
        - Chunk contains no symbols
        - Parse error occurs
        - Language not supported (non-Python)
    """
    # Only Python supported in Phase 29
    if language not in ("py", "python"):
        return {
            "symbol_type": None,
            "symbol_name": None,
            "symbol_signature": None,
        }

    try:
        parser = _get_python_parser()

        # Parse the chunk
        tree = parser.parse(bytes(text, "utf8"))

        # Log parse errors (debug level only)
        if tree.root_node.has_error:
            logger.debug("Parse errors in chunk (continuing with partial tree)")

        # Extract all symbols
        symbols = _extract_all_symbols(text, parser)

        # Return first symbol if any found
        if symbols:
            return symbols[0]
        else:
            # No symbols in this chunk
            return {
                "symbol_type": None,
                "symbol_name": None,
                "symbol_signature": None,
            }

    except Exception as e:
        # Catastrophic failure - log and return NULLs
        logger.error(f"Symbol extraction failed: {e}", exc_info=True)
        return {
            "symbol_type": None,
            "symbol_name": None,
            "symbol_signature": None,
        }


__all__ = ["extract_symbol_metadata"]
