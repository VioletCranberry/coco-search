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
        lang = get_language(language)
        parser = Parser()
        parser.set_language(lang)
        _PARSERS[language] = parser

    return _PARSERS[language]


def _get_python_parser() -> Parser:
    """Get or initialize the Python tree-sitter parser.

    Backward compatible wrapper for existing code.

    Returns:
        Parser configured for Python language.
    """
    return _get_parser("python")


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


def _extract_python_symbols(chunk_text: str, parser: Parser) -> list[dict]:
    """Extract all symbols from Python code.

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


# ============================================================================
# JavaScript Symbol Extraction
# ============================================================================


def _extract_javascript_symbols(chunk_text: str, parser: Parser) -> list[dict]:
    """Extract symbols from JavaScript/JSX code.

    Extracts:
    - Function declarations: function fetchUser() {}
    - Arrow functions: const fetchUser = () => {} (named only)
    - Class declarations: class UserService {}
    - Methods: methods inside class bodies

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

        # Function declarations
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")
            if name_node and params_node:
                name = _get_node_text(chunk_text, name_node)
                params = _get_node_text(chunk_text, params_node)

                symbol_type = "method" if current_class else "function"
                symbol_name = f"{current_class}.{name}" if current_class else name

                symbols.append({
                    "symbol_type": symbol_type,
                    "symbol_name": symbol_name,
                    "symbol_signature": f"function {name}{params}",
                })

        # Arrow functions (named only: const name = () => {})
        elif node.type == "lexical_declaration":
            # Look for pattern: const/let name = arrow_function
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    value_node = child.child_by_field_name("value")
                    if name_node and value_node and value_node.type == "arrow_function":
                        name = _get_node_text(chunk_text, name_node)
                        params_node = value_node.child_by_field_name("parameters")
                        if params_node:
                            params = _get_node_text(chunk_text, params_node)
                        else:
                            # Single parameter without parens: x => x
                            param_node = value_node.child_by_field_name("parameter")
                            params = f"({_get_node_text(chunk_text, param_node)})" if param_node else "()"

                        symbols.append({
                            "symbol_type": "function",
                            "symbol_name": name,
                            "symbol_signature": f"const {name} = {params} => ...",
                        })

        # Class declarations
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                class_name = _get_node_text(chunk_text, name_node)
                symbols.append({
                    "symbol_type": "class",
                    "symbol_name": class_name,
                    "symbol_signature": f"class {class_name}",
                })

                # Walk class body for methods
                body_node = node.child_by_field_name("body")
                if body_node:
                    for child in body_node.children:
                        walk_node(child, current_class=class_name)

        # Method definitions (inside classes)
        elif node.type == "method_definition" and current_class:
            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")
            if name_node and params_node:
                method_name = _get_node_text(chunk_text, name_node)
                params = _get_node_text(chunk_text, params_node)

                symbols.append({
                    "symbol_type": "method",
                    "symbol_name": f"{current_class}.{method_name}",
                    "symbol_signature": f"{method_name}{params}",
                })

        else:
            # Recurse for module-level nodes
            if current_class is None and node.type in ("program", "statement_block"):
                for child in node.children:
                    walk_node(child, current_class=None)
            elif current_class and node.type == "class_body":
                for child in node.children:
                    walk_node(child, current_class=current_class)

    walk_node(tree.root_node)
    return symbols


# ============================================================================
# TypeScript Symbol Extraction
# ============================================================================


def _extract_typescript_symbols(chunk_text: str, parser: Parser) -> list[dict]:
    """Extract symbols from TypeScript/TSX code.

    Extends JavaScript extraction with:
    - Interfaces: interface User {}
    - Type aliases: type UserID = string (mapped to "interface" symbol_type)

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

        # Function declarations
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")
            if name_node and params_node:
                name = _get_node_text(chunk_text, name_node)
                params = _get_node_text(chunk_text, params_node)

                symbol_type = "method" if current_class else "function"
                symbol_name = f"{current_class}.{name}" if current_class else name

                symbols.append({
                    "symbol_type": symbol_type,
                    "symbol_name": symbol_name,
                    "symbol_signature": f"function {name}{params}",
                })

        # Arrow functions (named only: const name = () => {})
        elif node.type == "lexical_declaration":
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    value_node = child.child_by_field_name("value")
                    if name_node and value_node and value_node.type == "arrow_function":
                        name = _get_node_text(chunk_text, name_node)
                        params_node = value_node.child_by_field_name("parameters")
                        if params_node:
                            params = _get_node_text(chunk_text, params_node)
                        else:
                            param_node = value_node.child_by_field_name("parameter")
                            params = f"({_get_node_text(chunk_text, param_node)})" if param_node else "()"

                        symbols.append({
                            "symbol_type": "function",
                            "symbol_name": name,
                            "symbol_signature": f"const {name} = {params} => ...",
                        })

        # Class declarations
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                class_name = _get_node_text(chunk_text, name_node)
                symbols.append({
                    "symbol_type": "class",
                    "symbol_name": class_name,
                    "symbol_signature": f"class {class_name}",
                })

                body_node = node.child_by_field_name("body")
                if body_node:
                    for child in body_node.children:
                        walk_node(child, current_class=class_name)

        # Method definitions (inside classes)
        elif node.type == "method_definition" and current_class:
            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")
            if name_node and params_node:
                method_name = _get_node_text(chunk_text, name_node)
                params = _get_node_text(chunk_text, params_node)

                symbols.append({
                    "symbol_type": "method",
                    "symbol_name": f"{current_class}.{method_name}",
                    "symbol_signature": f"{method_name}{params}",
                })

        # TypeScript-specific: Interface declarations
        elif node.type == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                interface_name = _get_node_text(chunk_text, name_node)
                symbols.append({
                    "symbol_type": "interface",
                    "symbol_name": interface_name,
                    "symbol_signature": f"interface {interface_name}",
                })

        # TypeScript-specific: Type alias declarations (mapped to "interface")
        elif node.type == "type_alias_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                type_name = _get_node_text(chunk_text, name_node)
                symbols.append({
                    "symbol_type": "interface",  # Map type alias to interface per CONTEXT.md
                    "symbol_name": type_name,
                    "symbol_signature": f"type {type_name}",
                })

        else:
            # Recurse for module-level nodes
            if current_class is None and node.type in ("program", "statement_block"):
                for child in node.children:
                    walk_node(child, current_class=None)
            elif current_class and node.type == "class_body":
                for child in node.children:
                    walk_node(child, current_class=current_class)

    walk_node(tree.root_node)
    return symbols


# ============================================================================
# Go Symbol Extraction
# ============================================================================


def _extract_go_symbols(chunk_text: str, parser: Parser) -> list[dict]:
    """Extract symbols from Go code.

    Extracts:
    - Functions: func Process() error
    - Methods: func (s *Server) Start() error -> Server.Start
    - Structs: type Server struct {} (mapped to "class" symbol_type)
    - Interfaces: type Handler interface {}

    Args:
        chunk_text: Source code text to parse.
        parser: Tree-sitter parser instance.

    Returns:
        List of symbol dicts with symbol_type, symbol_name, symbol_signature.
    """
    tree = parser.parse(bytes(chunk_text, "utf8"))
    symbols = []

    for node in tree.root_node.children:
        # Function declarations (including methods with receivers)
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")

            if name_node:
                func_name = _get_node_text(chunk_text, name_node)
                params = _get_node_text(chunk_text, params_node) if params_node else "()"

                # Check for receiver (method)
                receiver = None
                for child in node.children:
                    if child.type == "parameter_list" and child.start_byte < name_node.start_byte:
                        # This is the receiver, extract type name
                        receiver_text = _get_node_text(chunk_text, child)
                        # Parse receiver: (s *Server) -> Server, (s Server) -> Server
                        inner = receiver_text.strip("()")
                        parts = inner.split()
                        if len(parts) >= 2:
                            type_part = parts[-1].lstrip("*")
                            receiver = type_part
                        elif len(parts) == 1:
                            receiver = parts[0].lstrip("*")
                        break

                if receiver:
                    symbols.append({
                        "symbol_type": "method",
                        "symbol_name": f"{receiver}.{func_name}",
                        "symbol_signature": f"func {func_name}{params}",
                    })
                else:
                    symbols.append({
                        "symbol_type": "function",
                        "symbol_name": func_name,
                        "symbol_signature": f"func {func_name}{params}",
                    })

        # Method declarations (alternative syntax)
        elif node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")
            receiver_node = node.child_by_field_name("receiver")

            if name_node:
                method_name = _get_node_text(chunk_text, name_node)
                params = _get_node_text(chunk_text, params_node) if params_node else "()"

                receiver = None
                if receiver_node:
                    receiver_text = _get_node_text(chunk_text, receiver_node)
                    inner = receiver_text.strip("()")
                    parts = inner.split()
                    if len(parts) >= 2:
                        receiver = parts[-1].lstrip("*")
                    elif len(parts) == 1:
                        receiver = parts[0].lstrip("*")

                if receiver:
                    symbols.append({
                        "symbol_type": "method",
                        "symbol_name": f"{receiver}.{method_name}",
                        "symbol_signature": f"func {method_name}{params}",
                    })
                else:
                    symbols.append({
                        "symbol_type": "function",
                        "symbol_name": method_name,
                        "symbol_signature": f"func {method_name}{params}",
                    })

        # Type declarations (structs, interfaces)
        elif node.type == "type_declaration":
            for spec in node.children:
                if spec.type == "type_spec":
                    name_node = spec.child_by_field_name("name")
                    type_node = spec.child_by_field_name("type")

                    if name_node and type_node:
                        type_name = _get_node_text(chunk_text, name_node)

                        if type_node.type == "struct_type":
                            symbols.append({
                                "symbol_type": "class",
                                "symbol_name": type_name,
                                "symbol_signature": f"type {type_name} struct",
                            })
                        elif type_node.type == "interface_type":
                            symbols.append({
                                "symbol_type": "interface",
                                "symbol_name": type_name,
                                "symbol_signature": f"type {type_name} interface",
                            })

    return symbols


# ============================================================================
# Rust Symbol Extraction
# ============================================================================


def _extract_rust_symbols(chunk_text: str, parser: Parser) -> list[dict]:
    """Extract symbols from Rust code.

    Extracts:
    - Functions: fn process() -> Result<(), Error>
    - Methods: impl Server { fn start() } -> Server.start
    - Structs: struct Server {} (mapped to "class" symbol_type)
    - Traits: trait Handler {} (mapped to "interface" symbol_type)
    - Enums: enum Status {} (mapped to "class" symbol_type)

    Args:
        chunk_text: Source code text to parse.
        parser: Tree-sitter parser instance.

    Returns:
        List of symbol dicts with symbol_type, symbol_name, symbol_signature.
    """
    tree = parser.parse(bytes(chunk_text, "utf8"))
    symbols = []

    for node in tree.root_node.children:
        # Function definitions (top-level)
        if node.type == "function_item":
            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")

            if name_node:
                func_name = _get_node_text(chunk_text, name_node)
                params = _get_node_text(chunk_text, params_node) if params_node else "()"

                symbols.append({
                    "symbol_type": "function",
                    "symbol_name": func_name,
                    "symbol_signature": f"fn {func_name}{params}",
                })

        # Impl blocks (methods)
        elif node.type == "impl_item":
            type_node = node.child_by_field_name("type")
            type_name = None
            if type_node:
                type_name = _get_node_text(chunk_text, type_node)

            body_node = node.child_by_field_name("body")
            if body_node and type_name:
                for child in body_node.children:
                    if child.type == "function_item":
                        name_node = child.child_by_field_name("name")
                        params_node = child.child_by_field_name("parameters")

                        if name_node:
                            method_name = _get_node_text(chunk_text, name_node)
                            params = _get_node_text(chunk_text, params_node) if params_node else "()"

                            symbols.append({
                                "symbol_type": "method",
                                "symbol_name": f"{type_name}.{method_name}",
                                "symbol_signature": f"fn {method_name}{params}",
                            })

        # Struct definitions
        elif node.type == "struct_item":
            name_node = node.child_by_field_name("name")
            if name_node:
                struct_name = _get_node_text(chunk_text, name_node)
                symbols.append({
                    "symbol_type": "class",
                    "symbol_name": struct_name,
                    "symbol_signature": f"struct {struct_name}",
                })

        # Trait definitions
        elif node.type == "trait_item":
            name_node = node.child_by_field_name("name")
            if name_node:
                trait_name = _get_node_text(chunk_text, name_node)
                symbols.append({
                    "symbol_type": "interface",
                    "symbol_name": trait_name,
                    "symbol_signature": f"trait {trait_name}",
                })

        # Enum definitions
        elif node.type == "enum_item":
            name_node = node.child_by_field_name("name")
            if name_node:
                enum_name = _get_node_text(chunk_text, name_node)
                symbols.append({
                    "symbol_type": "class",
                    "symbol_name": enum_name,
                    "symbol_signature": f"enum {enum_name}",
                })

    return symbols


@cocoindex.op.function()
def extract_symbol_metadata(text: str, language: str) -> dict:
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
        return {
            "symbol_type": None,
            "symbol_name": None,
            "symbol_signature": None,
        }

    try:
        parser = _get_parser(ts_language)

        # Parse the chunk
        tree = parser.parse(bytes(text, "utf8"))

        # Log parse errors (debug level only)
        if tree.root_node.has_error:
            logger.debug("Parse errors in chunk (continuing with partial tree)")

        # Dispatch to language-specific extractor
        if ts_language == "python":
            symbols = _extract_python_symbols(text, parser)
        elif ts_language == "javascript":
            symbols = _extract_javascript_symbols(text, parser)
        elif ts_language == "typescript":
            symbols = _extract_typescript_symbols(text, parser)
        elif ts_language == "go":
            symbols = _extract_go_symbols(text, parser)
        elif ts_language == "rust":
            symbols = _extract_rust_symbols(text, parser)
        else:
            # Fallback (should not happen with LANGUAGE_MAP)
            symbols = []

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


__all__ = ["extract_symbol_metadata", "LANGUAGE_MAP"]
