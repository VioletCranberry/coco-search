"""Language and grammar chunking handlers with registry-based autodiscovery.

Handlers implement the LanguageHandler or GrammarHandler protocol and are
autodiscovered by scanning handlers/*.py and handlers/grammars/*.py at
module import time.

Language handlers match by file extension (1:1 mapping).
Grammar handlers match by file path + content patterns, providing
domain-specific chunking within a base language (e.g., GitHub Actions
is a grammar of YAML).

Priority: Grammar match > Language match > TextHandler fallback.
"""

from pathlib import Path
from typing import Protocol, ClassVar
import importlib
import inspect
import logging
import dataclasses

import cocoindex

logger = logging.getLogger(__name__)

# ============================================================================
# Shared Types (defined BEFORE discovery to avoid circular imports)
# ============================================================================


@dataclasses.dataclass
class ChunkMetadata:
    """Metadata extracted from a code chunk."""

    block_type: str
    hierarchy: str
    language_id: str


class LanguageHandler(Protocol):
    """Protocol for language-specific chunking handlers.

    Handlers implement this interface via structural subtyping.
    No explicit inheritance required.

    This protocol defines handlers that work with CocoIndex's Rust-based
    chunking. Handlers provide the CustomLanguageSpec for chunking and
    extract_metadata() for Python-based metadata extraction.
    """

    EXTENSIONS: ClassVar[list[str]]
    """File extensions this handler claims (e.g., ['.tf', '.hcl'])."""

    SEPARATOR_SPEC: ClassVar[cocoindex.functions.CustomLanguageSpec | None]
    """CocoIndex CustomLanguageSpec for chunking, or None for default."""

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from chunk text.

        Args:
            text: The chunk text content.

        Returns:
            Dict with at least: block_type, hierarchy, language_id
        """
        ...


class GrammarHandler(Protocol):
    """Protocol for domain-specific grammar handlers.

    Grammar handlers provide schema-aware chunking for files that share
    a base language but have distinct structure (e.g., GitHub Actions
    workflows are YAML files with a specific schema).

    Matched by file path + content patterns rather than extension.
    """

    GRAMMAR_NAME: ClassVar[str]
    """Unique grammar identifier (e.g., 'github-actions')."""

    BASE_LANGUAGE: ClassVar[str]
    """Base language this grammar extends (e.g., 'yaml')."""

    PATH_PATTERNS: ClassVar[list[str]]
    """File path glob patterns that suggest this grammar."""

    SEPARATOR_SPEC: ClassVar[cocoindex.functions.CustomLanguageSpec | None]
    """CocoIndex CustomLanguageSpec for chunking, or None for default."""

    def matches(self, filepath: str, content: str | None = None) -> bool:
        """Check if this grammar applies to the given file."""
        ...

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from chunk text.

        Returns:
            Dict with at least: block_type, hierarchy, language_id
        """
        ...


# ============================================================================
# Registry Discovery
# ============================================================================


def _is_language_handler(cls) -> bool:
    """Check if class implements LanguageHandler protocol (duck typing)."""
    return hasattr(cls, "EXTENSIONS") and hasattr(cls, "extract_metadata")


def _is_grammar_handler(cls) -> bool:
    """Check if class implements GrammarHandler protocol (duck typing)."""
    return (
        hasattr(cls, "GRAMMAR_NAME")
        and hasattr(cls, "BASE_LANGUAGE")
        and hasattr(cls, "PATH_PATTERNS")
        and hasattr(cls, "matches")
        and hasattr(cls, "extract_metadata")
    )


def _discover_handlers() -> tuple[dict[str, LanguageHandler], list]:
    """Discover and load all handler modules in handlers/ and handlers/grammars/.

    Scans for *.py files (excluding _ prefix), imports them,
    finds classes implementing LanguageHandler or GrammarHandler protocol.

    Returns:
        Tuple of (extension_map, grammar_list):
        - extension_map: Dict mapping file extension to LanguageHandler instance
        - grammar_list: List of GrammarHandler instances

    Raises:
        ValueError: If two language handlers claim the same extension
        ValueError: If two grammar handlers claim the same grammar name
    """
    handlers_dir = Path(__file__).parent
    extension_map: dict[str, LanguageHandler] = {}
    grammar_list: list = []
    grammar_names: set[str] = set()

    # --- Scan handlers/*.py for LanguageHandlers ---
    for module_file in handlers_dir.glob("*.py"):
        if module_file.stem.startswith("_") or module_file.stem == "__init__":
            continue

        module_name = f"cocosearch.handlers.{module_file.stem}"
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.warning(f"Failed to import handler {module_name}: {e}")
            continue

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if not _is_language_handler(obj):
                continue

            try:
                handler = obj()
            except Exception as e:
                logger.warning(f"Failed to instantiate {name}: {e}")
                continue

            for ext in handler.EXTENSIONS:
                if ext in extension_map:
                    existing = extension_map[ext].__class__.__name__
                    raise ValueError(
                        f"Extension conflict: {ext} claimed by both "
                        f"{existing} and {name}"
                    )
                extension_map[ext] = handler

            logger.info(f"Registered {name} for extensions: {handler.EXTENSIONS}")

    # --- Scan handlers/grammars/*.py for GrammarHandlers ---
    grammars_dir = handlers_dir / "grammars"
    if grammars_dir.is_dir():
        for module_file in grammars_dir.glob("*.py"):
            if module_file.stem.startswith("_") or module_file.stem == "__init__":
                continue

            module_name = f"cocosearch.handlers.grammars.{module_file.stem}"
            try:
                module = importlib.import_module(module_name)
            except Exception as e:
                logger.warning(f"Failed to import grammar {module_name}: {e}")
                continue

            for name, obj in inspect.getmembers(module, inspect.isclass):
                if not _is_grammar_handler(obj):
                    continue

                try:
                    handler = obj()
                except Exception as e:
                    logger.warning(f"Failed to instantiate grammar {name}: {e}")
                    continue

                if handler.GRAMMAR_NAME in grammar_names:
                    raise ValueError(
                        f"Grammar name conflict: '{handler.GRAMMAR_NAME}' "
                        f"already registered"
                    )
                grammar_names.add(handler.GRAMMAR_NAME)
                grammar_list.append(handler)

                logger.info(
                    f"Registered grammar {name} "
                    f"('{handler.GRAMMAR_NAME}' for {handler.BASE_LANGUAGE})"
                )

    return extension_map, grammar_list


# Run discovery at module import (fail-fast on conflicts)
_HANDLER_REGISTRY, _GRAMMAR_REGISTRY = _discover_handlers()


# ============================================================================
# Public API
# ============================================================================


def detect_grammar(filepath: str, content: str | None = None) -> str | None:
    """Detect grammar for a file by checking all registered grammar handlers.

    Iterates _GRAMMAR_REGISTRY and returns the first matching GRAMMAR_NAME.

    Args:
        filepath: Relative file path within the project.
        content: Optional file content for deeper matching.

    Returns:
        Grammar name string (e.g., 'github-actions') or None if no match.
    """
    for handler in _GRAMMAR_REGISTRY:
        if handler.matches(filepath, content):
            return handler.GRAMMAR_NAME
    return None


def get_grammar_handler(grammar_name: str):
    """Get grammar handler by grammar name.

    Args:
        grammar_name: Grammar identifier (e.g., 'github-actions')

    Returns:
        GrammarHandler instance, or None if not found.
    """
    for handler in _GRAMMAR_REGISTRY:
        if handler.GRAMMAR_NAME == grammar_name:
            return handler
    return None


def get_handler(extension: str) -> LanguageHandler:
    """Get handler for file extension.

    Args:
        extension: File extension including dot (e.g., '.tf')

    Returns:
        Handler for extension, or TextHandler if no match
    """
    # Import default handler lazily to avoid issues during discovery
    from cocosearch.handlers.text import TextHandler

    return _HANDLER_REGISTRY.get(extension, TextHandler())


def get_registered_handlers() -> list[LanguageHandler]:
    """Get unique registered handlers (excluding TextHandler fallback).

    Returns:
        List of unique handler instances discovered from handlers/*.py
    """
    seen = set()
    handlers = []
    for handler in _HANDLER_REGISTRY.values():
        handler_id = id(handler)
        if handler_id not in seen:
            seen.add(handler_id)
            handlers.append(handler)
    return handlers


def get_registered_grammars() -> list:
    """Get all registered grammar handlers.

    Returns:
        List of GrammarHandler instances discovered from handlers/grammars/*.py
    """
    return list(_GRAMMAR_REGISTRY)


def get_custom_languages() -> list[cocoindex.functions.CustomLanguageSpec]:
    """Get all CustomLanguageSpec from registered handlers and grammars.

    Returns:
        List of CustomLanguageSpec for all handlers/grammars that define one
    """
    seen = set()
    specs = []

    # Collect from language handlers
    for handler in _HANDLER_REGISTRY.values():
        handler_id = id(handler)
        if handler_id not in seen and handler.SEPARATOR_SPEC is not None:
            seen.add(handler_id)
            specs.append(handler.SEPARATOR_SPEC)

    # Collect from grammar handlers
    for handler in _GRAMMAR_REGISTRY:
        handler_id = id(handler)
        if handler_id not in seen and handler.SEPARATOR_SPEC is not None:
            seen.add(handler_id)
            specs.append(handler.SEPARATOR_SPEC)

    return specs


@cocoindex.op.function(behavior_version=1)
def extract_chunk_metadata(text: str, language_id: str) -> ChunkMetadata:
    """Extract metadata from code chunk using appropriate handler.

    This is a CocoIndex transform function that dispatches to the
    appropriate handler based on language_id. Checks grammar handlers
    first (by GRAMMAR_NAME match), then falls back to extension-based
    language handler lookup.

    Args:
        text: The chunk text content.
        language_id: Language identifier (e.g., "tf", "dockerfile", "github-actions")

    Returns:
        ChunkMetadata with fields: block_type, hierarchy, language_id
    """
    # Check grammar handlers first (grammar names like "github-actions")
    grammar_handler = get_grammar_handler(language_id)
    if grammar_handler is not None:
        metadata = grammar_handler.extract_metadata(text)
        if not metadata.get("language_id"):
            metadata["language_id"] = language_id
        return ChunkMetadata(**metadata)

    # Fall back to extension-based language handler
    extension = f".{language_id}"
    handler = get_handler(extension)
    metadata = handler.extract_metadata(text)
    # Preserve original language_id when handler returns empty (files without a handler)
    if not metadata.get("language_id"):
        metadata["language_id"] = language_id
    return ChunkMetadata(**metadata)


__all__ = [
    "ChunkMetadata",
    "get_handler",
    "get_grammar_handler",
    "get_registered_handlers",
    "get_registered_grammars",
    "get_custom_languages",
    "detect_grammar",
    "extract_chunk_metadata",
]
