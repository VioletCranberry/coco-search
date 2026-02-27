"""Module resolution framework for dependency edges.

Resolvers translate unresolved module names (stored in ``metadata.module``)
into concrete file paths (``target_file``).  Each language has different
import conventions, so each resolver encapsulates language-specific logic:

- **PythonResolver** — dotted module names, ``__init__.py`` packages,
  ``src/``/``lib/`` prefix stripping, relative imports.
- **JavaScriptResolver** — relative paths (``./utils``), extension probing
  (``*.js``, ``*.ts``, ``*/index.*``).  Bare specifiers are external.
- **GoResolver** — full import paths; matches internal packages by
  directory structure.  External packages are unresolvable.
- **MarkdownResolver** — resolves documentation references to source files.
  Handles relative paths (``../src/cli.py``) and project-relative paths.
  Supports both file and directory references.

The orchestrator in ``extractor.py`` calls :func:`get_resolvers` to obtain
all registered resolvers, then dispatches edges by language.
"""

from __future__ import annotations

import os
from pathlib import PurePosixPath
from typing import Protocol

from cocosearch.deps.models import DependencyEdge

# Common source directory prefixes to strip when building Python module names.
_COMMON_PREFIXES = ("src/", "lib/")

# Extensions to probe for JavaScript/TypeScript resolution.
_JS_EXTENSIONS = (
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".mts",
    ".cts",
)

# Index file names to probe when a JS/TS import resolves to a directory.
_JS_INDEX_FILES = tuple(f"index{ext}" for ext in _JS_EXTENSIONS)


# ============================================================================
# Protocol
# ============================================================================


class ModuleResolver(Protocol):
    """Protocol for language-specific module resolvers.

    Resolvers are responsible for two things:

    1. Building an index from indexed files that maps some form of
       module identifier to relative file paths.
    2. Using that index to resolve individual dependency edges.

    **Optional extension:** A resolver may also implement
    ``resolve_many(edge, module_index) -> list[str] | None`` to support
    one-to-many resolution (e.g., directory references expanding to all
    contained files).  The orchestrator in ``extractor.py`` checks for
    this via ``hasattr`` and prefers it over :meth:`resolve` when present.
    """

    def build_index(self, indexed_files: list[tuple[str, str]]) -> dict[str, str]:
        """Build a module-name-to-file-path mapping from indexed files.

        Args:
            indexed_files: List of (relative_path, language_id) tuples
                for *all* indexed files (not just the resolver's language).

        Returns:
            Dict mapping module identifiers to their relative file paths.
        """
        ...

    def resolve(self, edge: DependencyEdge, module_index: dict[str, str]) -> str | None:
        """Resolve a single dependency edge to a target file path.

        Args:
            edge: The edge to resolve.  ``edge.metadata["module"]``
                contains the raw import string.
            module_index: The index built by :meth:`build_index`.

        Returns:
            Resolved relative file path, or ``None`` if the target is
            external or cannot be resolved.
        """
        ...


# ============================================================================
# Python resolver
# ============================================================================


class PythonResolver:
    """Resolve Python dotted module names to file paths.

    Handles absolute imports (``import cocosearch.cli``), relative
    imports (``from . import utils``, ``from ..models import X``),
    ``__init__.py`` packages, and ``src/``/``lib/`` prefix stripping.
    """

    def build_index(self, indexed_files: list[tuple[str, str]]) -> dict[str, str]:
        index: dict[str, str] = {}

        for filepath, language_id in indexed_files:
            if language_id != "py":
                continue

            filepath_posix = filepath.replace("\\", "/")

            if filepath_posix.endswith("/__init__.py"):
                module_path = filepath_posix[: -len("/__init__.py")]
            elif filepath_posix.endswith(".py"):
                module_path = filepath_posix[:-3]
            else:
                continue

            dotted = module_path.replace("/", ".")
            index[dotted] = filepath

            for prefix in _COMMON_PREFIXES:
                if filepath_posix.startswith(prefix):
                    stripped = module_path[len(prefix) :]
                    index[stripped.replace("/", ".")] = filepath

        return index

    def resolve(self, edge: DependencyEdge, module_index: dict[str, str]) -> str | None:
        module = edge.metadata.get("module")
        if not module:
            return None

        if module.startswith("."):
            return self._resolve_relative(edge.source_file, module, module_index)
        return self._resolve_absolute(module, module_index)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_absolute(module: str, module_index: dict[str, str]) -> str | None:
        if module in module_index:
            return module_index[module]

        parts = module.split(".")
        for i in range(len(parts) - 1, 0, -1):
            parent = ".".join(parts[:i])
            if parent in module_index:
                return module_index[parent]

        return None

    def _resolve_relative(
        self,
        source_file: str,
        module: str,
        module_index: dict[str, str],
    ) -> str | None:
        dots = 0
        for ch in module:
            if ch == ".":
                dots += 1
            else:
                break
        remainder = module[dots:]

        source_posix = source_file.replace("\\", "/")
        source_path = PurePosixPath(source_posix)

        package_dir = source_path.parent
        for _ in range(dots - 1):
            package_dir = package_dir.parent

        package_module = str(package_dir).replace("/", ".")

        if remainder:
            absolute_module = f"{package_module}.{remainder}"
        else:
            absolute_module = package_module

        result = self._resolve_absolute(absolute_module, module_index)
        if result is not None:
            return result

        for prefix in _COMMON_PREFIXES:
            dotted_prefix = prefix.replace("/", ".")
            if absolute_module.startswith(dotted_prefix):
                stripped = absolute_module[len(dotted_prefix) :]
                result = self._resolve_absolute(stripped, module_index)
                if result is not None:
                    return result

        return None


# ============================================================================
# JavaScript / TypeScript resolver
# ============================================================================


class JavaScriptResolver:
    """Resolve JS/TS import paths to file paths.

    Handles relative imports (``./utils``, ``../lib/helpers``) by probing
    for known extensions and ``index.*`` files.  Bare specifiers
    (``react``, ``@mui/material``) are treated as external (returns None).
    """

    def build_index(self, indexed_files: list[tuple[str, str]]) -> dict[str, str]:
        index: dict[str, str] = {}
        js_langs = {"js", "jsx", "mjs", "cjs", "ts", "tsx", "mts", "cts"}

        for filepath, language_id in indexed_files:
            if language_id not in js_langs:
                continue
            filepath_posix = filepath.replace("\\", "/")
            index[filepath_posix] = filepath

        return index

    def resolve(self, edge: DependencyEdge, module_index: dict[str, str]) -> str | None:
        module = edge.metadata.get("module")
        if not module:
            return None

        # Only resolve relative imports (starting with . or ..)
        if not module.startswith("."):
            return None

        source_posix = edge.source_file.replace("\\", "/")
        source_dir = str(PurePosixPath(source_posix).parent)

        # Normalise the relative path
        if source_dir == ".":
            candidate_base = module
        else:
            candidate_base = os.path.normpath(f"{source_dir}/{module}").replace(
                "\\", "/"
            )

        # 1. Try exact path (e.g., ./utils.js imported as ./utils.js)
        if candidate_base in module_index:
            return module_index[candidate_base]

        # 2. Try appending extensions (./utils -> ./utils.js, ./utils.ts, ...)
        for ext in _JS_EXTENSIONS:
            probe = f"{candidate_base}{ext}"
            if probe in module_index:
                return module_index[probe]

        # 3. Try as directory with index file (./utils -> ./utils/index.js, ...)
        for idx_file in _JS_INDEX_FILES:
            probe = f"{candidate_base}/{idx_file}"
            if probe in module_index:
                return module_index[probe]

        return None


# ============================================================================
# Go resolver
# ============================================================================


class GoResolver:
    """Resolve Go import paths to file paths.

    Go imports are full paths (e.g., ``github.com/user/repo/pkg``).
    For internal packages, matches the import path suffix against
    indexed file directories.  External packages return None.
    """

    def build_index(self, indexed_files: list[tuple[str, str]]) -> dict[str, str]:
        index: dict[str, str] = {}

        for filepath, language_id in indexed_files:
            if language_id != "go":
                continue
            filepath_posix = filepath.replace("\\", "/")
            dir_path = str(PurePosixPath(filepath_posix).parent)
            # Map directory to any file in it (for package-level resolution)
            # Only store if not already set (first file wins)
            if dir_path not in index:
                index[dir_path] = filepath

        return index

    def resolve(self, edge: DependencyEdge, module_index: dict[str, str]) -> str | None:
        module = edge.metadata.get("module")
        if not module:
            return None

        # Strip surrounding quotes if present (Go import paths are quoted)
        module = module.strip('"')

        # Standard library imports (no dots in first segment) are external
        # e.g., "fmt", "os/exec" — skip these
        if "/" not in module:
            return None

        # Match import path suffix against known directories.
        # Go internal imports often look like "github.com/user/repo/pkg/foo"
        # and the indexed files are at "pkg/foo/bar.go".
        # Try longest suffix first for most specific match.
        parts = module.split("/")
        for n in range(len(parts), 0, -1):
            suffix = "/".join(parts[-n:])
            if suffix in module_index:
                return module_index[suffix]

        return None


# ============================================================================
# Terraform resolver
# ============================================================================


class TerraformResolver:
    """Resolve Terraform module source paths to file paths.

    Only local sources (starting with ``./`` or ``../``) are resolvable.
    Registry and remote sources return None.
    """

    def build_index(self, indexed_files: list[tuple[str, str]]) -> dict[str, str]:
        index: dict[str, str] = {}

        for filepath, language_id in indexed_files:
            if language_id != "terraform":
                continue
            filepath_posix = filepath.replace("\\", "/")
            dir_path = str(PurePosixPath(filepath_posix).parent)
            if dir_path not in index:
                index[dir_path] = filepath

        return index

    def resolve(self, edge: DependencyEdge, module_index: dict[str, str]) -> str | None:
        value = edge.metadata.get("value")
        if not value:
            return None

        if not (value.startswith("./") or value.startswith("../")):
            return None

        # Normalise the path relative to the source file's directory
        source_posix = edge.source_file.replace("\\", "/")
        source_dir = str(PurePosixPath(source_posix).parent)

        if source_dir == ".":
            candidate = value
        else:
            candidate = os.path.normpath(f"{source_dir}/{value}").replace("\\", "/")

        # Strip leading ./
        if candidate.startswith("./"):
            candidate = candidate[2:]

        if candidate in module_index:
            return module_index[candidate]

        return None


# ============================================================================
# Markdown resolver
# ============================================================================


class MarkdownResolver:
    """Resolve Markdown documentation references to file paths.

    Handles relative paths (``../src/cli.py`` from ``docs/guide.md``)
    and project-relative paths (``src/cli.py``).  Supports both file-level
    and directory-level references.

    Directory references are expanded to all files within the directory
    via :meth:`resolve_many`, so that ``deps impact`` on any file in
    a referenced directory surfaces the documentation.
    """

    def __init__(self) -> None:
        self._dir_files: dict[str, list[str]] = {}

    def build_index(self, indexed_files: list[tuple[str, str]]) -> dict[str, str]:
        index: dict[str, str] = {}
        dir_files: dict[str, list[str]] = {}

        for filepath, _language_id in indexed_files:
            filepath_posix = filepath.replace("\\", "/")
            # Map each file path to itself
            index[filepath_posix] = filepath

            # Track all files per directory (for expand-on-resolve)
            dir_path = str(PurePosixPath(filepath_posix).parent)
            if dir_path != ".":
                dir_files.setdefault(dir_path, []).append(filepath)
                # Map directory to first file (for single-resolve fallback)
                if dir_path not in index:
                    index[dir_path] = filepath
                    index[dir_path + "/"] = filepath

        self._dir_files = dir_files
        return index

    def resolve(self, edge: DependencyEdge, module_index: dict[str, str]) -> str | None:
        module = edge.metadata.get("module")
        if not module:
            return None

        # Normalise: strip trailing / for lookup (we try both)
        module_stripped = module.rstrip("/")

        # Relative paths: normalise against source file's directory
        if module.startswith("./") or module.startswith("../"):
            candidate = self._normalize_relative(edge.source_file, module_stripped)
            if candidate in module_index:
                return module_index[candidate]
            if candidate + "/" in module_index:
                return module_index[candidate + "/"]
            return None

        # Project-relative paths: direct lookup, then ancestor-prefix probing
        match = self._find_with_prefix(edge.source_file, module_stripped, module_index)
        if match is not None:
            return module_index[match]
        match = self._find_with_prefix(
            edge.source_file, module_stripped + "/", module_index
        )
        if match is not None:
            return module_index[match]

        return None

    def resolve_many(
        self, edge: DependencyEdge, module_index: dict[str, str]
    ) -> list[str] | None:
        """Resolve a single edge, potentially to multiple target files.

        For directory references, returns all files within the directory.
        For file references, returns a single-element list.

        Returns:
            List of resolved file paths, or ``None`` if unresolvable.
        """
        module = edge.metadata.get("module")
        if not module:
            return None

        module_stripped = module.rstrip("/")

        # Determine the normalised directory key
        if module.startswith("./") or module.startswith("../"):
            candidate = self._normalize_relative(edge.source_file, module_stripped)
        else:
            candidate = module_stripped

        # Check for directory expansion (with ancestor-prefix probing)
        dir_match = self._find_with_prefix(edge.source_file, candidate, self._dir_files)
        if dir_match is not None:
            return list(self._dir_files[dir_match])

        # Fall back to single-file resolution
        result = self.resolve(edge, module_index)
        return [result] if result else None

    @staticmethod
    def _find_with_prefix(source_file: str, candidate: str, lookup: dict) -> str | None:
        """Try candidate directly, then with source file ancestor prefixes."""
        if candidate in lookup:
            return candidate

        source_posix = source_file.replace("\\", "/")
        parts = PurePosixPath(source_posix).parts
        # Try each ancestor (shallowest first: "project/", "project/sub/", ...)
        for i in range(1, len(parts)):  # exclude filename
            prefix = "/".join(parts[:i])
            prefixed = f"{prefix}/{candidate}"
            if prefixed in lookup:
                return prefixed

        return None

    @staticmethod
    def _normalize_relative(source_file: str, module_stripped: str) -> str:
        """Normalize a relative path against the source file's directory."""
        source_posix = source_file.replace("\\", "/")
        source_dir = str(PurePosixPath(source_posix).parent)

        if source_dir == ".":
            candidate = module_stripped
        else:
            candidate = os.path.normpath(f"{source_dir}/{module_stripped}").replace(
                "\\", "/"
            )

        # Strip leading ./
        if candidate.startswith("./"):
            candidate = candidate[2:]

        return candidate


# ============================================================================
# Registry
# ============================================================================


_RESOLVERS: dict[str, ModuleResolver] = {}


def _build_resolver_registry() -> dict[str, ModuleResolver]:
    """Build the language_id -> resolver mapping."""
    registry: dict[str, ModuleResolver] = {}

    py = PythonResolver()
    registry["py"] = py

    js = JavaScriptResolver()
    for lang_id in ("js", "jsx", "mjs", "cjs", "ts", "tsx", "mts", "cts"):
        registry[lang_id] = js

    go = GoResolver()
    registry["go"] = go

    tf = TerraformResolver()
    registry["terraform"] = tf

    md = MarkdownResolver()
    registry["md"] = md
    registry["mdx"] = md

    return registry


_RESOLVERS = _build_resolver_registry()


def get_resolver(language_id: str) -> ModuleResolver | None:
    """Get the module resolver for a language.

    Args:
        language_id: Language identifier (e.g., ``"py"``, ``"js"``).

    Returns:
        ModuleResolver instance, or ``None`` if no resolver exists.
    """
    return _RESOLVERS.get(language_id)


def get_resolvers() -> dict[str, ModuleResolver]:
    """Get all registered resolvers.

    Returns:
        Dict mapping language_id to ModuleResolver instance.
    """
    return dict(_RESOLVERS)
