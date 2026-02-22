"""Autodiscovery registry for dependency extractors.

Scans ``deps/extractors/*.py`` at import time, finds classes implementing
the ``DependencyExtractor`` protocol via duck-type checking, and builds a
language_id -> instance mapping.

This mirrors the handler autodiscovery pattern in
``cocosearch.handlers.__init__``.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from pathlib import Path
from typing import ClassVar, Protocol

from cocosearch.deps.models import DependencyEdge

logger = logging.getLogger(__name__)


# ============================================================================
# Protocol
# ============================================================================


class DependencyExtractor(Protocol):
    """Protocol for language-specific dependency extractors.

    Extractors implement this interface via structural subtyping.
    No explicit inheritance required.
    """

    LANGUAGES: ClassVar[set[str]]
    """Set of language_ids this extractor handles (e.g., {"python"})."""

    def extract(self, file_path: str, content: str) -> list[DependencyEdge]:
        """Extract dependency edges from a source file.

        Args:
            file_path: Relative path to the source file within the project.
            content: Full text content of the source file.

        Returns:
            List of DependencyEdge instances found in the file.
        """
        ...


# ============================================================================
# Duck-type check
# ============================================================================


def _is_dependency_extractor(cls) -> bool:
    """Check if *cls* implements the DependencyExtractor protocol.

    Uses duck-type checking: the class must have a ``LANGUAGES`` attribute
    and a callable ``extract`` attribute.

    Args:
        cls: Any object to test.

    Returns:
        True if *cls* looks like a dependency extractor.
    """
    return (
        hasattr(cls, "LANGUAGES")
        and hasattr(cls, "extract")
        and callable(getattr(cls, "extract", None))
    )


# ============================================================================
# Discovery
# ============================================================================


def _discover_extractors() -> dict[str, DependencyExtractor]:
    """Discover and load all extractor modules in ``deps/extractors/``.

    Scans for ``*.py`` files (excluding ``_`` prefix and ``__init__``),
    imports each module, and finds classes implementing the
    DependencyExtractor protocol via :func:`_is_dependency_extractor`.

    Classes with empty ``LANGUAGES`` are skipped silently (this is how
    the ``_template.py`` avoids registration).

    Returns:
        Dict mapping language_id to DependencyExtractor instance.

    Raises:
        ValueError: If two extractors claim the same language_id.
    """
    extractors_dir = Path(__file__).parent / "extractors"
    language_map: dict[str, DependencyExtractor] = {}

    if not extractors_dir.is_dir():
        return language_map

    for module_file in sorted(extractors_dir.glob("*.py")):
        if module_file.stem.startswith("_") or module_file.stem == "__init__":
            continue

        module_name = f"cocosearch.deps.extractors.{module_file.stem}"
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.warning("Failed to import extractor %s: %s", module_name, e)
            continue

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if not _is_dependency_extractor(obj):
                continue

            # Skip classes with empty LANGUAGES (e.g., the template)
            if not obj.LANGUAGES:
                continue

            try:
                instance = obj()
            except Exception as e:
                logger.warning("Failed to instantiate extractor %s: %s", name, e)
                continue

            for lang_id in instance.LANGUAGES:
                if lang_id in language_map:
                    existing = language_map[lang_id].__class__.__name__
                    raise ValueError(
                        f"Language conflict: '{lang_id}' claimed by both "
                        f"{existing} and {name}"
                    )
                language_map[lang_id] = instance

            logger.info(
                "Registered extractor %s for languages: %s",
                name,
                instance.LANGUAGES,
            )

    return language_map


# Run discovery at module import time (fail-fast on conflicts)
_EXTRACTOR_REGISTRY: dict[str, DependencyExtractor] = _discover_extractors()


# ============================================================================
# Public API
# ============================================================================


def get_extractor(language_id: str) -> DependencyExtractor | None:
    """Get the dependency extractor for a language.

    Args:
        language_id: Language identifier (e.g., ``"python"``).

    Returns:
        DependencyExtractor instance, or ``None`` if no extractor is
        registered for the given language.
    """
    return _EXTRACTOR_REGISTRY.get(language_id)


def get_registered_extractors() -> list[DependencyExtractor]:
    """Get unique registered extractor instances.

    Returns:
        List of unique DependencyExtractor instances discovered from
        ``deps/extractors/*.py``.
    """
    seen: set[int] = set()
    extractors: list[DependencyExtractor] = []
    for instance in _EXTRACTOR_REGISTRY.values():
        obj_id = id(instance)
        if obj_id not in seen:
            seen.add(obj_id)
            extractors.append(instance)
    return extractors


def get_all_extractor_language_ids() -> set[str]:
    """Get all language IDs that have registered dependency extractors.

    Returns:
        Set of language_id strings (e.g., ``{"py", "js", "go"}``).
    """
    return set(_EXTRACTOR_REGISTRY.keys())


__all__ = [
    "DependencyExtractor",
    "get_all_extractor_language_ids",
    "get_extractor",
    "get_registered_extractors",
]
