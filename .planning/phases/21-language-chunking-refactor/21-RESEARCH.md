# Phase 21: Language Chunking Refactor - Research

**Researched:** 2026-02-01
**Domain:** Python registry pattern, Protocol-based plugin architecture, package autodiscovery
**Confidence:** HIGH

## Summary

This research investigated how to refactor language chunking handlers (HCL, Dockerfile, Bash) from monolithic modules into a registry-based plugin architecture. The current implementation has two tightly-coupled modules (`languages.py` and `metadata.py`) with hardcoded lists. The goal is clean extensibility where adding a new language requires creating a single module file that self-registers.

Key findings: (1) Python's `typing.Protocol` provides structural subtyping ideal for defining handler interfaces without requiring inheritance; (2) `pkgutil.iter_modules()` with `importlib.import_module()` enables package scanning for autodiscovery at import time; (3) `__init_subclass__` is NOT needed when using Protocol - classes implementing the protocol can be discovered via iteration without registration hooks; (4) pathlib's `.glob("*.py")` is cleaner than pkgutil for simple directory scanning; (5) extension conflict detection should fail-fast at registry initialization to catch configuration errors early.

The standard approach combines Protocol for interface definition, directory scanning for discovery, and a registry dict mapping extensions to handler instances. The registry validates uniqueness constraints and provides a default text handler fallback.

**Primary recommendation:** Use `typing.Protocol` for the `LanguageHandler` interface, scan `handlers/*.py` at module import using pathlib, instantiate handler classes and build extension-to-handler mapping, fail with clear error on extension conflicts.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typing.Protocol | Python 3.11+ stdlib | Handler interface definition | Official structural subtyping, no inheritance required |
| pathlib | Python 3.11+ stdlib | Directory scanning (`handlers/*.py`) | Modern, object-oriented file operations |
| importlib | Python 3.11+ stdlib | Dynamic module loading | Official module import API |
| dataclasses | Python 3.11+ stdlib | Handler config/metadata | Clean data structures with type hints |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pkgutil | Python 3.11+ stdlib | Alternative scanner (`iter_modules`) | If pathlib glob proves insufficient |
| re | Python 3.11+ stdlib | Pattern validation | Already used in metadata.py |
| cocoindex | >=0.3.28 | CustomLanguageSpec, chunk function | Existing dependency |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Protocol | ABC (Abstract Base Class) | Protocol allows structural typing (no inheritance). ABC requires explicit subclassing, making third-party extensions harder. Protocol is more Pythonic for behavior-based interfaces. |
| pathlib.glob() | pkgutil.iter_modules() | pkgutil more robust for installed packages, but pathlib simpler for directory scanning. Use pathlib for local handlers/ package. |
| Import-time discovery | Entry points (importlib.metadata) | Entry points better for installed plugins across packages, but overkill for single-package handlers. Use import-time for cocosearch internal handlers. |

**Installation:**
No additional dependencies. All libraries are Python 3.11+ stdlib.

## Architecture Patterns

### Recommended Project Structure
```
src/cocosearch/
    handlers/                    # NEW: top-level handlers package
        __init__.py              # Registry + Protocol + autodiscovery
        _template.py             # Template for new handlers (underscore excludes from discovery)
        hcl.py                   # HCL handler module
        dockerfile.py            # Dockerfile handler module
        bash.py                  # Bash handler module
        text.py                  # Default text handler (fallback)
        README.md                # Extension workflow documentation
    indexer/
        languages.py             # REMOVED: merged into handlers/
        metadata.py              # REMOVED: merged into handlers/
        flow.py                  # MODIFIED: import from handlers
```

### Pattern 1: Protocol-Based Handler Interface

**What:** Define `LanguageHandler` protocol with `chunk()` method and `EXTENSIONS` class attribute

**When to use:** For all language handlers (existing and future)

**Example:**
```python
# Source: typing.Protocol best practices (PEP 544)
# handlers/__init__.py
from typing import Protocol, ClassVar
import cocoindex

class ChunkConfig:
    """Configuration for chunking operation."""
    chunk_size: int
    chunk_overlap: int

class Chunk:
    """A chunk produced by a handler."""
    text: str
    location: dict  # CocoIndex location metadata
    metadata: dict  # Language-specific metadata

class LanguageHandler(Protocol):
    """Protocol for language-specific chunking handlers.

    Handlers implement this interface via structural subtyping.
    No explicit inheritance required.
    """

    EXTENSIONS: ClassVar[list[str]]
    """File extensions this handler claims (e.g., ['.tf', '.hcl'])."""

    def chunk(self, content: str, config: ChunkConfig) -> list[Chunk]:
        """Chunk file content into semantically meaningful pieces.

        Args:
            content: File content to chunk
            config: Chunking configuration (size, overlap)

        Returns:
            List of chunks with text, location, and metadata
        """
        ...
```

**Why Protocol over ABC:**
- No inheritance required - handlers just implement the interface
- Type checkers verify compatibility structurally
- Easier to test (mock handlers without subclassing)
- More Pythonic for "has-a" behavior vs "is-a" lineage

### Pattern 2: Directory Scan Autodiscovery

**What:** Scan `handlers/*.py`, import modules, find classes implementing `LanguageHandler`

**When to use:** At handlers package import time (`handlers/__init__.py`)

**Example:**
```python
# Source: pathlib + importlib autodiscovery pattern
# handlers/__init__.py
from pathlib import Path
import importlib
import inspect

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
        if module_file.stem.startswith("_"):
            continue

        # Import module
        module_name = f"cocosearch.handlers.{module_file.stem}"
        module = importlib.import_module(module_name)

        # Find handler classes (implements LanguageHandler protocol)
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Check if class has required protocol attributes
            if not (hasattr(obj, 'EXTENSIONS') and hasattr(obj, 'chunk')):
                continue

            # Instantiate handler
            handler = obj()

            # Register extensions
            for ext in handler.EXTENSIONS:
                if ext in extension_map:
                    existing = extension_map[ext].__class__.__name__
                    raise ValueError(
                        f"Extension conflict: {ext} claimed by both "
                        f"{existing} and {name}"
                    )
                extension_map[ext] = handler

    return extension_map

# Run discovery at module import
_HANDLER_REGISTRY = _discover_handlers()

def get_handler(extension: str) -> LanguageHandler:
    """Get handler for file extension, or default text handler."""
    return _HANDLER_REGISTRY.get(extension, _DEFAULT_TEXT_HANDLER)
```

**Why eager at import:**
- Fails fast if handlers have conflicts or errors
- No runtime discovery overhead
- Clear error messages at startup, not during indexing
- Simpler than lazy loading

### Pattern 3: Handler Module Structure

**What:** Each handler is a single file with one handler class

**When to use:** For all language handlers

**Example:**
```python
# Source: Designed from current languages.py + metadata.py
# handlers/hcl.py
import re
import cocoindex
from cocosearch.handlers import ChunkConfig, Chunk

class HclHandler:
    """Handler for HCL/Terraform files."""

    EXTENSIONS = ['.tf', '.hcl', '.tfvars']

    # Separator spec (moved from languages.py)
    _SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="hcl",
        separators_regex=[
            r"\n(?:resource|data|variable|output|locals|module|provider|terraform|import|moved|removed|check) ",
            r"\n\n+",
            r"\n",
            r" ",
        ],
        aliases=["tf", "tfvars"],
    )

    # Metadata patterns (moved from metadata.py)
    _BLOCK_RE = re.compile(
        r"^(resource|data|variable|output|locals|module|provider|terraform|import|moved|removed|check)"
        r'(?:\s+"([^"]*)")?'
        r'(?:\s+"([^"]*)")?'
        r"\s*\{?",
    )
    _COMMENT_LINE = re.compile(r"^\s*(?:#|//|/\*).*$", re.MULTILINE)

    def chunk(self, content: str, config: ChunkConfig) -> list[Chunk]:
        """Chunk HCL content using SplitRecursively with metadata extraction."""
        # Call CocoIndex SplitRecursively with custom language
        raw_chunks = cocoindex.functions.SplitRecursively(
            custom_languages=[self._SEPARATOR_SPEC]
        )(content, language="hcl", chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap)

        # Enhance chunks with metadata
        enhanced_chunks = []
        for raw_chunk in raw_chunks:
            metadata = self._extract_metadata(raw_chunk.text)
            enhanced_chunks.append(Chunk(
                text=raw_chunk.text,
                location=raw_chunk.location,
                metadata=metadata,
            ))

        return enhanced_chunks

    def _extract_metadata(self, text: str) -> dict:
        """Extract HCL block metadata from chunk text."""
        stripped = self._strip_comments(text)
        match = self._BLOCK_RE.match(stripped)

        if not match:
            return {"block_type": "", "hierarchy": "", "language_id": "hcl"}

        block_type = match.group(1)
        label1 = match.group(2)
        label2 = match.group(3)

        parts = [block_type]
        if label1:
            parts.append(label1)
        if label2:
            parts.append(label2)
        hierarchy = ".".join(parts)

        return {
            "block_type": block_type,
            "hierarchy": hierarchy,
            "language_id": "hcl"
        }

    def _strip_comments(self, text: str) -> str:
        """Strip leading comments from chunk text."""
        lines = text.lstrip().split("\n")
        for i, line in enumerate(lines):
            if line.strip() and not self._COMMENT_LINE.match(line):
                return "\n".join(lines[i:])
        return ""
```

**Key characteristics:**
- Self-contained: all patterns, specs, and logic in one file
- No global dispatch maps (replaced by registry)
- Clear separation: public `chunk()` method, private helpers
- Protocol compliance via structure (no explicit `implements`)

### Pattern 4: Default Text Handler

**What:** Fallback handler for unrecognized extensions using plain text chunking

**When to use:** Automatically when no specialized handler matches

**Example:**
```python
# handlers/text.py
import cocoindex
from cocosearch.handlers import ChunkConfig, Chunk

class TextHandler:
    """Default handler for plain text files."""

    EXTENSIONS = []  # No specific extensions - used as fallback

    def chunk(self, content: str, config: ChunkConfig) -> list[Chunk]:
        """Chunk text using paragraph/line-based splitting."""
        # Use CocoIndex SplitRecursively with generic separators
        raw_chunks = cocoindex.functions.SplitRecursively()(
            content,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap
        )

        # Convert to Chunk objects with empty metadata
        return [
            Chunk(
                text=raw_chunk.text,
                location=raw_chunk.location,
                metadata={"block_type": "", "hierarchy": "", "language_id": ""}
            )
            for raw_chunk in raw_chunks
        ]
```

### Anti-Patterns to Avoid

- **Using `__init_subclass__` for registration:** Protocol already provides structural checking. Adding `__init_subclass__` couples handlers to a base class, defeating Protocol's flexibility.

- **Lazy discovery on first use:** Import-time discovery catches errors early. Delaying until runtime means indexing jobs fail partway through instead of at startup.

- **Extension strings without leading dot:** Inconsistent with Python conventions (`.py` not `py`). Store as `['.tf']` not `['tf']` to match `os.path.splitext()` return format.

- **Multiple handler classes per file:** Complicates discovery logic. One file = one handler is clear and predictable.

- **Global state in handler modules:** Handlers may be instantiated multiple times during tests. Use instance attributes or class-level constants, not module globals.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structural typing | Custom metaclass with interface validation | `typing.Protocol` | Standard library, type checker support, zero runtime overhead |
| Module discovery | Manual `__all__` lists in `__init__.py` | `pathlib.glob()` + `importlib.import_module()` | Automatic discovery, no manual updates |
| Extension conflict detection | Runtime warnings or overwrite-last-wins | Fail-fast `ValueError` at import | Catches config errors before indexing starts |
| Default handler fallback | Special "unknown" extension key | Separate `TextHandler` with `EXTENSIONS = []` | Clean separation, explicit fallback logic |

**Key insight:** Python's standard library provides all needed primitives for plugin systems. Resist adding third-party registry/plugin libraries - they add complexity without benefit for this single-package use case.

## Common Pitfalls

### Pitfall 1: Protocol Runtime Validation

**What goes wrong:** Protocol classes don't enforce interface compliance at runtime unless decorated with `@runtime_checkable`

**Why it happens:** Protocols are primarily for static type checking. Without `@runtime_checkable`, `isinstance(obj, Protocol)` raises `TypeError`.

**How to avoid:** Either (a) don't use `isinstance()` checks, rely on structural duck typing, OR (b) add `@runtime_checkable` decorator to `LanguageHandler` if runtime validation is needed.

**Warning signs:** `TypeError: Protocols with non-method members don't support isinstance()` during discovery

**Recommendation:** Use duck typing (check for `hasattr(obj, 'EXTENSIONS')`) instead of `isinstance()`. Protocols are for type checkers, not runtime validation.

### Pitfall 2: Module Import Side Effects

**What goes wrong:** Handler modules execute code at import that depends on external state (database, config files, network)

**Why it happens:** Python imports modules completely when first referenced. Module-level code runs immediately.

**How to avoid:** Keep handler module level code to class/function definitions and simple constants. Move expensive operations (regex compilation is fine, database connections are not) into class `__init__` or methods.

**Warning signs:** Slow import times, import failures in tests due to missing dependencies

### Pitfall 3: Extension Conflicts Detected Too Late

**What goes wrong:** Two handlers claim `.tf` extension, but error surfaces during indexing instead of at startup

**Why it happens:** Lazy discovery or lenient conflict handling (last-wins)

**How to avoid:** Run discovery at module import time in `handlers/__init__.py`. Raise `ValueError` immediately on extension conflicts with clear message naming both handlers.

**Warning signs:** Indexing uses wrong handler for some files, or switches handlers unpredictably

### Pitfall 4: Circular Import Between Registry and Handlers

**What goes wrong:** `handlers/__init__.py` imports handler modules, but handlers import from `handlers/__init__.py` (e.g., for `ChunkConfig`), causing circular import

**Why it happens:** Shared types (Protocol, Config classes) defined in `__init__.py` alongside discovery code

**How to avoid:** Define shared types (`LanguageHandler` protocol, `ChunkConfig`, `Chunk`) BEFORE discovery code in `__init__.py`. Handlers can import them without triggering discovery. Discovery code runs at module bottom after all definitions.

**Warning signs:** `ImportError: cannot import name 'X' from partially initialized module`

### Pitfall 5: Test File Validation Too Strict

**What goes wrong:** Registry requires `test_<handler>.py` to exist at import time, breaking development flow (write handler first, tests later)

**Why it happens:** CONTEXT.md decision says "Required test file: registry validates test_<handler>.py exists"

**How to avoid:** Make test validation optional (warning, not error) OR run validation only in CI (environment variable gate) OR defer to pytest discovery instead of registry validation

**Warning signs:** Can't import `handlers` package until test file exists, blocking iterative development

**Recommendation:** Use warning log instead of exception, or skip validation in development mode

## Code Examples

### Example 1: Complete handlers/__init__.py

```python
# Source: Designed from Protocol + pathlib patterns researched
"""Language chunking handlers with registry-based autodiscovery.

Handlers implement the LanguageHandler protocol and are autodiscovered
by scanning handlers/*.py at module import time.
"""

from pathlib import Path
from typing import Protocol, ClassVar
import importlib
import inspect
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# Shared Types (defined BEFORE discovery to avoid circular imports)
# ============================================================================

class ChunkConfig:
    """Configuration for chunking operation."""
    def __init__(self, chunk_size: int, chunk_overlap: int):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

class Chunk:
    """A chunk produced by a handler."""
    def __init__(self, text: str, location: dict, metadata: dict):
        self.text = text
        self.location = location
        self.metadata = metadata

class LanguageHandler(Protocol):
    """Protocol for language-specific chunking handlers.

    Handlers implement this interface via structural subtyping.
    No explicit inheritance required.
    """

    EXTENSIONS: ClassVar[list[str]]
    """File extensions this handler claims (e.g., ['.tf', '.hcl'])."""

    def chunk(self, content: str, config: ChunkConfig) -> list[Chunk]:
        """Chunk file content into semantically meaningful pieces."""
        ...

# ============================================================================
# Registry Discovery
# ============================================================================

def _discover_handlers() -> dict[str, LanguageHandler]:
    """Discover and load all handler modules in handlers/ directory.

    Returns:
        Dict mapping file extension to handler instance

    Raises:
        ValueError: If two handlers claim the same extension
    """
    handlers_dir = Path(__file__).parent
    extension_map = {}

    for module_file in handlers_dir.glob("*.py"):
        # Skip private modules (_ prefix) and __init__.py
        if module_file.stem.startswith("_") or module_file.stem == "__init__":
            continue

        # Import module
        module_name = f"cocosearch.handlers.{module_file.stem}"
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.warning(f"Failed to import handler {module_name}: {e}")
            continue

        # Find handler classes
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Check for LanguageHandler protocol compliance (duck typing)
            if not (hasattr(obj, 'EXTENSIONS') and callable(getattr(obj, 'chunk', None))):
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
                    existing_handler = extension_map[ext].__class__.__name__
                    raise ValueError(
                        f"Extension conflict: {ext} claimed by both "
                        f"{existing_handler} and {name}"
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
    # Import default handler lazily to avoid circular import
    from cocosearch.handlers.text import TextHandler

    return _HANDLER_REGISTRY.get(extension, TextHandler())

__all__ = [
    'LanguageHandler',
    'ChunkConfig',
    'Chunk',
    'get_handler',
]
```

### Example 2: Handler Template (_template.py)

```python
# handlers/_template.py
"""Template for creating new language handlers.

Copy this file to <language>.py and implement the TODOs.
"""

import re
import cocoindex
from cocosearch.handlers import ChunkConfig, Chunk

class TemplateHandler:
    """Handler for <LANGUAGE> files.

    TODO: Replace <LANGUAGE> with language name (e.g., "YAML", "JSON").
    """

    # TODO: List file extensions this handler manages
    EXTENSIONS = ['.example']

    # TODO: Define CustomLanguageSpec with separators
    _SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="example",
        separators_regex=[
            r"\n\n+",  # Blank lines
            r"\n",     # Single newlines
            r" ",      # Whitespace
        ],
        aliases=[],
    )

    # TODO: Define regex patterns for metadata extraction
    _BLOCK_RE = re.compile(r"^some_pattern")

    def chunk(self, content: str, config: ChunkConfig) -> list[Chunk]:
        """Chunk <LANGUAGE> content using SplitRecursively with metadata.

        TODO: Implement chunking logic:
        1. Call SplitRecursively with custom language spec
        2. Extract metadata from each chunk
        3. Return list of Chunk objects
        """
        raw_chunks = cocoindex.functions.SplitRecursively(
            custom_languages=[self._SEPARATOR_SPEC]
        )(content, language="example", chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap)

        enhanced_chunks = []
        for raw_chunk in raw_chunks:
            metadata = self._extract_metadata(raw_chunk.text)
            enhanced_chunks.append(Chunk(
                text=raw_chunk.text,
                location=raw_chunk.location,
                metadata=metadata,
            ))

        return enhanced_chunks

    def _extract_metadata(self, text: str) -> dict:
        """Extract metadata from chunk text.

        TODO: Implement metadata extraction logic.
        Return dict with at least: block_type, hierarchy, language_id
        """
        return {
            "block_type": "",
            "hierarchy": "",
            "language_id": "example"
        }
```

### Example 3: Integration with flow.py

```python
# indexer/flow.py (modified to use handlers)
from cocosearch.handlers import get_handler, ChunkConfig

def create_code_index_flow(
    index_name: str,
    codebase_path: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 300,
) -> cocoindex.Flow:
    """Create indexing flow using handler registry."""

    @cocoindex.flow_def(name=f"CodeIndex_{index_name}")
    def code_index_flow(flow_builder, data_scope):
        # Source files
        data_scope["files"] = flow_builder.add_source(...)

        code_embeddings = data_scope.add_collector()

        with data_scope["files"].row() as file:
            # Extract extension from filename
            file["extension"] = file["filename"].transform(extract_extension)

            # Get handler for extension and chunk content
            # NOTE: This is pseudocode - CocoIndex transform can't call Python directly
            # Real implementation would need CocoIndex-compatible approach
            config = ChunkConfig(chunk_size, chunk_overlap)
            handler = get_handler(file["extension"])
            chunks = handler.chunk(file["content"], config)

            # ... rest of flow
```

**Note:** The above integration is conceptual. CocoIndex transforms operate in Rust, so direct Python handler calls won't work. The actual integration requires adapting handlers to CocoIndex's transform API or restructuring the flow to call handlers before CocoIndex flow creation.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded language lists | Protocol + autodiscovery | Phase 21 (planned) | Add languages by creating single file |
| Global dispatch dicts | Registry with fail-fast conflicts | Phase 21 (planned) | Extension conflicts caught at startup |
| Monolithic metadata.py | Per-handler metadata logic | Phase 21 (planned) | Handlers fully self-contained |
| `__init_subclass__` registration | Protocol structural typing | Recent Python best practice (2024+) | No inheritance required for plugins |

**Recent patterns (2025-2026):**
- Protocol preferred over ABC for plugin interfaces (more Pythonic, less coupling)
- pathlib.glob() replacing pkgutil for simple directory scanning (cleaner API)
- Fail-fast at import preferred over lazy validation (DevOps culture shift)

## Open Questions

### 1. CocoIndex Transform Integration

- **What we know:** Current flow uses `SplitRecursively` as a CocoIndex transform. Handlers call SplitRecursively internally. CocoIndex transforms execute in Rust, not Python.
- **What's unclear:** How to integrate Python-based handlers into CocoIndex flow without breaking the transform abstraction. Options: (a) pre-chunk in Python before CocoIndex, (b) make handlers export CustomLanguageSpec only, (c) restructure flow to Python-first pipeline.
- **Recommendation:** Start with option (b) - handlers export `SEPARATOR_SPEC` and `extract_metadata()`, flow calls them as separate transforms. This keeps CocoIndex chunking in Rust but metadata in Python.

### 2. Test File Validation Strictness

- **What we know:** CONTEXT.md says "Required test file: registry validates test_<handler>.py exists"
- **What's unclear:** Whether to enforce at import (breaks development flow) or CI only (misses local errors)
- **Recommendation:** Log warning at import, fail in CI via environment variable (`COCOSEARCH_STRICT_HANDLERS=1`). Best of both worlds - friendly locally, strict in CI.

### 3. Extension Format with vs without Dot

- **What we know:** Python `os.path.splitext()` returns `('.py', 'script')` - extension includes dot. Current code stores extensions without dot (e.g., `"tf"`).
- **What's unclear:** Whether to store `['.tf']` or `['tf']` in `EXTENSIONS` class attribute
- **Recommendation:** Store WITH dot `['.tf']` to match `splitext()` format. Requires updating extract_extension/extract_language to return `.tf` not `tf`.

### 4. Chunk vs Raw CocoIndex Output

- **What we know:** CocoIndex `SplitRecursively` returns chunks with `text` and `location` fields
- **What's unclear:** Exact structure of CocoIndex chunk objects (is it a dataclass? dict? Pydantic model?)
- **Recommendation:** Inspect `cocoindex.functions.SplitRecursively` output type at implementation time. Define `Chunk` dataclass to match or wrap CocoIndex chunks.

## Sources

### Primary (HIGH confidence)

- [Python typing.Protocol specification](https://typing.python.org/en/latest/spec/protocol.html) - Official typing documentation
- [PEP 544 – Protocols: Structural subtyping](https://peps.python.org/pep-0544/) - Protocol design rationale
- [Python pathlib documentation](https://docs.python.org/3/library/pathlib.html) - Updated Jan 30, 2026
- [Python importlib documentation](https://docs.python.org/3/library/importlib.html) - Module import API
- [Creating and discovering plugins - Python Packaging User Guide](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/) - Official plugin patterns

### Secondary (MEDIUM confidence)

- [Real Python: Python Protocols](https://realpython.com/python-protocol/) - Best practices guide
- [Modern Python Interfaces: ABC, Protocol, or Both? (Nov 2025)](https://tconsta.medium.com/python-interfaces-abc-protocol-or-both-3c5871ea6642) - Recent comparison
- [pytest test discovery](https://docs.pytest.org/en/stable/example/pythoncollection.html) - Test file patterns
- [Python pkgutil.iter_modules examples](https://www.programcreek.com/python/example/2916/pkgutil.iter_modules) - Directory scanning

### Tertiary (LOW confidence - existing codebase analysis)

- `/Users/fedorzhdanov/GIT/personal/coco-s/src/cocosearch/indexer/languages.py` - Current CustomLanguageSpec implementation
- `/Users/fedorzhdanov/GIT/personal/coco-s/src/cocosearch/indexer/metadata.py` - Current metadata extraction patterns
- `.planning/phases/08-custom-language-definitions-and-file-routing/08-RESEARCH.md` - Prior Phase 8 research on CocoIndex regex constraints

## Metadata

**Confidence breakdown:**
- Protocol pattern for handlers: HIGH - official Python typing approach, well-documented
- pathlib.glob() for discovery: HIGH - standard library, straightforward API
- Fail-fast extension conflicts: HIGH - common pattern in plugin systems
- Integration with CocoIndex flow: MEDIUM - requires understanding CocoIndex transform execution model
- Test validation approach: LOW - trade-off between strictness and developer experience

**Research date:** 2026-02-01
**Valid until:** 90 days (stable Python stdlib APIs, minimal language evolution)
