"""Language chunking handlers with registry-based autodiscovery.

Handlers implement the LanguageHandler protocol and are autodiscovered
by scanning handlers/*.py at module import time.

Each handler provides:
- EXTENSIONS: List of file extensions (e.g., ['.tf', '.hcl'])
- SEPARATOR_SPEC: CocoIndex CustomLanguageSpec for chunking
- extract_metadata(text): Extract structured metadata from chunks

The extract_devops_metadata() function is a CocoIndex transform that
dispatches to the appropriate handler based on language_id.
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
class ChunkConfig:
    """Configuration for chunking operation."""

    chunk_size: int
    chunk_overlap: int


@dataclasses.dataclass
class Chunk:
    """A chunk produced by a handler."""

    text: str
    location: dict
    metadata: dict


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


# ============================================================================
# Registry Discovery
# ============================================================================


def _discover_handlers() -> dict[str, LanguageHandler]:
    """Discover and load all handler modules in handlers/ directory.

    Scans for *.py files (excluding _ prefix), imports them,
    finds classes implementing LanguageHandler protocol.

    Returns:
        Dict mapping file extension to handler instance

    Raises:
        ValueError: If two handlers claim the same extension
    """
    handlers_dir = Path(__file__).parent
    extension_map = {}

    # Scan handlers/*.py (exclude __init__.py and _template.py)
    for module_file in handlers_dir.glob("*.py"):
        if module_file.stem.startswith("_") or module_file.stem == "__init__":
            continue

        # Import module
        module_name = f"cocosearch.handlers.{module_file.stem}"
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.warning(f"Failed to import handler {module_name}: {e}")
            continue

        # Find handler classes (implements LanguageHandler protocol)
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Check if class has required protocol attributes (duck typing)
            if not (
                hasattr(obj, "EXTENSIONS") and hasattr(obj, "extract_metadata")
            ):
                continue

            # Instantiate handler
            try:
                handler = obj()
            except Exception as e:
                logger.warning(f"Failed to instantiate {name}: {e}")
                continue

            # Register extensions
            for ext in handler.EXTENSIONS:
                if ext in extension_map:
                    existing = extension_map[ext].__class__.__name__
                    raise ValueError(
                        f"Extension conflict: {ext} claimed by both "
                        f"{existing} and {name}"
                    )
                extension_map[ext] = handler

            logger.info(f"Registered {name} for extensions: {handler.EXTENSIONS}")

    return extension_map


# Run discovery at module import (fail-fast on conflicts)
_HANDLER_REGISTRY = _discover_handlers()


# ============================================================================
# Public API
# ============================================================================


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


def get_custom_languages() -> list[cocoindex.functions.CustomLanguageSpec]:
    """Get all CustomLanguageSpec from registered handlers.

    Returns:
        List of CustomLanguageSpec for all handlers that define one
    """
    seen_handlers = set()
    specs = []
    for handler in _HANDLER_REGISTRY.values():
        handler_id = id(handler)
        if handler_id not in seen_handlers and handler.SEPARATOR_SPEC is not None:
            seen_handlers.add(handler_id)
            specs.append(handler.SEPARATOR_SPEC)
    return specs


@cocoindex.op.function()
def extract_devops_metadata(text: str, language_id: str) -> dict:
    """Extract metadata from code chunk using appropriate handler.

    This is a CocoIndex transform function that dispatches to the
    appropriate language handler based on language_id.

    Args:
        text: The chunk text content.
        language_id: Language identifier (e.g., "tf", "dockerfile", "sh")

    Returns:
        Dict with metadata fields (block_type, hierarchy, language_id)
    """
    # Map language_id to extension (handlers register by extension)
    # This is a simple mapping - could be enhanced if needed
    extension_map = {
        "hcl": ".hcl",
        "tf": ".tf",
        "tfvars": ".tfvars",
        "dockerfile": ".dockerfile",
        "sh": ".sh",
        "bash": ".bash",
        "zsh": ".zsh",
        "shell": ".sh",
    }

    extension = extension_map.get(language_id, f".{language_id}")
    handler = get_handler(extension)
    return handler.extract_metadata(text)


__all__ = [
    "LanguageHandler",
    "ChunkConfig",
    "Chunk",
    "get_handler",
    "get_custom_languages",
    "extract_devops_metadata",
]
