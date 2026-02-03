# Phase 31: Context Expansion Enhancement - Research

**Researched:** 2026-02-03
**Domain:** Context line expansion with tree-sitter boundary detection
**Confidence:** HIGH

## Summary

This phase adds grep-style context expansion to CocoSearch search results, showing surrounding code lines with smart function/class boundary detection. The implementation combines three proven approaches: Python's built-in `linecache` module for efficient line access, tree-sitter's AST node traversal for boundary detection, and `functools.lru_cache` for session-level file caching.

The existing codebase already has the infrastructure needed: tree-sitter parsers are initialized for Python, JavaScript, TypeScript, Go, and Rust (Phase 29-30), and the formatter module already implements basic context line retrieval. This phase extends that foundation with smart boundaries and performance optimizations.

Tree-sitter provides reliable parent node traversal for finding enclosing function/class definitions, with clear APIs for accessing node byte ranges and types. The `linecache` module automatically caches file contents after first read, making repeated line access nearly free. Combined with batched file reads (read once, extract multiple ranges), this provides the performance profile needed for real-time search response.

**Primary recommendation:** Use tree-sitter's parent node traversal to find enclosing function_definition/class_definition nodes, fall back to fixed line counts when tree-sitter parse fails or for non-code files, and leverage linecache for all line-by-line access with functools.lru_cache wrapping file content for session duration.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tree-sitter | 0.25.2+ (py-tree-sitter) | AST parsing and node boundary detection | Already integrated in Phase 29-30, proven for multi-language parsing |
| linecache | stdlib | Efficient random line access with automatic caching | Python stdlib, designed for this exact use case (debuggers/tracebacks) |
| functools.lru_cache | stdlib | Session-level file content caching | Python stdlib, thread-safe, zero-config caching |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Rich (Syntax) | 13+ | Syntax-highlighted output with line numbers | Already used in formatter.py for pretty output |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| linecache | Manual file reading with custom cache | More code, duplicate effort - linecache already optimized for this |
| functools.lru_cache | Custom cache with TTL (cachetools) | Over-engineering - search sessions are short-lived, no TTL needed |
| tree-sitter parent traversal | Regex-based boundary detection | Unreliable for complex syntax, fails on nested functions/classes |

**Installation:**

No new dependencies - all libraries already in use or Python stdlib.

## Architecture Patterns

### Recommended Module Structure

```
src/cocosearch/search/
├── utils.py              # Already exists - add smart boundary functions here
├── formatter.py          # Already exists - extend with new context modes
└── context_expander.py   # NEW - encapsulates smart boundary logic
```

### Pattern 1: Smart Boundary Detection

**What:** Use tree-sitter to find enclosing function/class nodes, expand context to those boundaries

**When to use:** When result is in a code file with tree-sitter support and smart expansion is enabled (default)

**Example:**

```python
# Source: py-tree-sitter documentation + CocoSearch existing patterns
from tree_sitter import Parser
from tree_sitter_languages import get_language

def find_enclosing_scope(filepath: str, start_line: int, end_line: int, language: str) -> tuple[int, int]:
    """Find enclosing function or class boundaries using tree-sitter.

    Returns:
        (start_line, end_line) of enclosing scope, or original range if none found.
    """
    # Parse file with tree-sitter
    parser = _get_parser(language)
    with open(filepath, 'rb') as f:
        source = f.read()
    tree = parser.parse(source)

    # Convert line numbers to byte offsets
    start_byte = line_to_byte(filepath, start_line)

    # Find node at start position
    node = tree.root_node.descendant_for_byte_range(start_byte, start_byte)

    # Walk up parent chain to find function_definition or class_definition
    while node is not None:
        if node.type in ('function_definition', 'class_definition',
                         'function_declaration', 'class_declaration',
                         'method_definition', 'impl_item'):
            # Found enclosing scope - convert byte range to lines
            scope_start = byte_to_line(filepath, node.start_byte)
            scope_end = byte_to_line(filepath, node.end_byte)
            return (scope_start, scope_end)
        node = node.parent

    # No enclosing scope found - return original range
    return (start_line, end_line)
```

### Pattern 2: Batched File Reading

**What:** When multiple results come from same file, read file once and extract all ranges

**When to use:** Always - minimize I/O operations

**Example:**

```python
# Pattern from existing formatter.py grouping logic
def format_results_with_context(results: list[SearchResult]) -> None:
    """Format results with optimized file reading."""
    # Group by filename (already done in formatter.py)
    by_file: dict[str, list[SearchResult]] = {}
    for r in results:
        if r.filename not in by_file:
            by_file[r.filename] = []
        by_file[r.filename].append(r)

    # Process each file once
    for filepath, file_results in by_file.items():
        # Open file once, use linecache for all line access
        # linecache automatically caches after first access
        for r in file_results:
            # Each getline call after first is cache hit
            lines = get_context_with_boundaries(r, filepath)
            display_result(r, lines)
```

### Pattern 3: LRU Cache for File Content

**What:** Cache full file content for duration of search session using functools.lru_cache

**When to use:** Wrap file reading functions with @lru_cache decorator

**Example:**

```python
# Source: Python functools documentation
from functools import lru_cache

@lru_cache(maxsize=128)  # Cache up to 128 files per search session
def read_file_lines(filepath: str) -> list[str]:
    """Read file lines with LRU caching.

    Cached by filepath - multiple results from same file hit cache.
    Cache cleared between search invocations (new session).
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return f.readlines()
    except (FileNotFoundError, IOError):
        return []

# Clear cache between searches (in search entry point)
def search_with_context(...):
    results = perform_search(...)
    format_with_context(results)
    read_file_lines.cache_clear()  # Free memory after search completes
```

### Pattern 4: Grep-Style Output Markers

**What:** Use `:` for context lines, `>` for matched lines (per CONTEXT.md decision)

**When to use:** Pretty output mode with context enabled

**Example:**

```python
# Grep uses these conventions (from GNU grep manual):
# - Matching lines: ':' separator
# - Context lines: '-' separator
# CocoSearch variation (per CONTEXT.md):
# - Matched chunk: '>' prefix
# - Context lines: ':' prefix

def format_result_with_context(result, context_before, context_after):
    """Format result with grep-style markers."""
    output = []

    # Context before (line_num: line_content)
    for line_num, line in context_before:
        output.append(f"{line_num}: {line}")

    # Matched chunk (line_num> line_content)
    for line_num, line in matched_lines:
        output.append(f"{line_num}> {line}")

    # Context after (line_num: line_content)
    for line_num, line in context_after:
        output.append(f"{line_num}: {line}")

    return '\n'.join(output)
```

### Anti-Patterns to Avoid

- **Reading entire file for every result:** Use linecache or LRU cached function instead
- **Parsing with tree-sitter multiple times:** Cache parser instances (already done in symbols.py)
- **Ignoring parse errors:** Always provide fallback to fixed line count on tree-sitter failure
- **Not clearing LRU cache:** Memory leak if cache persists across many searches
- **Synchronous tree-sitter in tight loop:** Parse once per file, not once per result

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Line-by-line file access | Custom file reader with manual caching | linecache.getline() | Stdlib, optimized for repeated line access, handles edge cases |
| Result-level caching | Custom cache dict with manual eviction | functools.lru_cache | Stdlib, thread-safe, automatic eviction, decorator syntax |
| AST node parent traversal | Regex patterns for function/class detection | tree-sitter Node.parent API | Already integrated, handles all language syntax, no regex fragility |
| Byte offset to line conversion | Manual newline counting each time | Cache line offset map or use linecache | Repeated conversion is O(n) each time without caching |

**Key insight:** Python's standard library already provides optimized solutions for line-based file access (linecache) and caching (functools.lru_cache). Tree-sitter is already integrated and proven. Avoid building custom solutions for these well-solved problems.

## Common Pitfalls

### Pitfall 1: Tree-sitter Parse Errors on Partial Code

**What goes wrong:** Tree-sitter may fail or return incomplete AST on syntax errors or partial chunks

**Why it happens:** Search results may be incomplete code fragments, not full valid files

**How to avoid:** Always wrap tree-sitter calls in try-except and provide fallback behavior

**Warning signs:** Empty or None results from tree-sitter queries, has_error flag set on tree.root_node

```python
# Example defensive parsing
try:
    tree = parser.parse(source_bytes)
    if tree.root_node.has_error:
        # Parse succeeded but has errors - partial AST available
        # Still try to use it, but be ready for incomplete results
        logger.debug(f"Parse errors in {filepath}, using best-effort boundaries")
    result = find_enclosing_scope_with_tree(tree, ...)
except Exception as e:
    logger.debug(f"Tree-sitter failed for {filepath}: {e}, falling back to fixed lines")
    result = use_fixed_line_count(...)
```

### Pitfall 2: File Deleted After Indexing

**What goes wrong:** Search result references file that no longer exists on disk

**Why it happens:** Index is stale - file deleted/moved after indexing

**How to avoid:** Catch FileNotFoundError and skip result (per CONTEXT.md edge case decision)

**Warning signs:** FileNotFoundError, IOError, PermissionError on file access

```python
def read_with_context(filepath, start_line, end_line):
    try:
        lines = linecache.getlines(filepath)
        if not lines:
            # File not found or empty
            raise FileNotFoundError(f"Cannot read {filepath}")
        return extract_range(lines, start_line, end_line)
    except (FileNotFoundError, IOError) as e:
        logger.warning(f"Skipping result - file not accessible: {filepath}")
        return None  # Caller should skip this result
```

### Pitfall 3: Memory Exhaustion with Large Files

**What goes wrong:** Loading entire file content for large files (>100MB) exhausts memory

**Why it happens:** linecache and lru_cache both store full file in memory

**How to avoid:** Set reasonable LRU cache size (128 files max), clear cache after search

**Warning signs:** Growing memory usage during search, slow GC, out-of-memory errors

```python
# Mitigation strategy
@lru_cache(maxsize=128)  # Limit cache size
def read_file_cached(filepath: str) -> list[str]:
    # For very large files, consider streaming or partial read
    file_size = os.path.getsize(filepath)
    if file_size > 100 * 1024 * 1024:  # 100MB threshold
        logger.warning(f"Large file {filepath} ({file_size} bytes), may impact memory")
    return read_file(filepath)

# Always clear after search session
def search_entry_point(...):
    try:
        results = search(...)
        format_results(results)
    finally:
        read_file_cached.cache_clear()  # Free memory
        linecache.clearcache()  # Clear linecache too
```

### Pitfall 4: Not Respecting 50-Line Hard Limit

**What goes wrong:** Smart expansion returns 500-line function, overwhelming output

**Why it happens:** Some functions are genuinely very large

**How to avoid:** Apply hard 50-line cap AFTER smart expansion (per CONTEXT.md decision)

**Warning signs:** Massive output blocks, degraded terminal performance

```python
def expand_with_smart_boundaries(filepath, start_line, end_line, max_lines=50):
    """Expand to function boundaries, but cap at max_lines."""
    # Get smart boundaries
    smart_start, smart_end = find_enclosing_scope(filepath, start_line, end_line)

    # Calculate total lines
    total_lines = smart_end - smart_start + 1

    # Apply hard cap
    if total_lines > max_lines:
        # Truncate to max_lines centered on original range
        center = (start_line + end_line) // 2
        capped_start = max(smart_start, center - max_lines // 2)
        capped_end = min(smart_end, capped_start + max_lines - 1)
        return (capped_start, capped_end)

    return (smart_start, smart_end)
```

## Code Examples

Verified patterns from official sources and existing codebase:

### Using linecache for Line Access

```python
# Source: Python linecache documentation
import linecache

def get_context_lines(filepath: str, start_line: int, end_line: int,
                      context: int) -> tuple[list[str], list[str]]:
    """Get context lines using linecache for efficiency.

    linecache automatically caches file contents after first access.
    """
    # Get lines before match (line numbers are 1-indexed)
    before_start = max(1, start_line - context)
    lines_before = []
    for line_num in range(before_start, start_line):
        line = linecache.getline(filepath, line_num)
        if line:  # getline returns '' for invalid lines
            lines_before.append((line_num, line.rstrip('\n\r')))

    # Get lines after match
    after_end = end_line + context
    lines_after = []
    for line_num in range(end_line + 1, after_end + 1):
        line = linecache.getline(filepath, line_num)
        if line:
            lines_after.append((line_num, line.rstrip('\n\r')))

    return (lines_before, lines_after)
```

### Tree-sitter Node Traversal for Boundaries

```python
# Source: py-tree-sitter Node API documentation + existing symbols.py patterns
from tree_sitter import Node

def find_enclosing_definition_node(node: Node) -> Node | None:
    """Walk up parent chain to find function or class definition.

    Uses patterns from existing symbols.py implementation.
    """
    DEFINITION_TYPES = {
        # Python
        'function_definition', 'class_definition',
        # JavaScript/TypeScript
        'function_declaration', 'class_declaration', 'method_definition',
        # Go
        'function_declaration', 'method_declaration', 'type_declaration',
        # Rust
        'function_item', 'impl_item', 'struct_item', 'trait_item',
    }

    current = node.parent
    while current is not None:
        if current.type in DEFINITION_TYPES:
            return current
        current = current.parent

    return None  # No enclosing definition found
```

### LRU Cache Pattern for File Content

```python
# Source: Python functools documentation
from functools import lru_cache

class ContextExpander:
    """Manages context expansion with caching."""

    def __init__(self):
        # Cache is per-instance, cleared after each search
        self._read_file_cached = lru_cache(maxsize=128)(self._read_file_impl)

    def _read_file_impl(self, filepath: str) -> list[str]:
        """Implementation of file reading."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                return f.readlines()
        except (FileNotFoundError, IOError):
            return []

    def get_file_lines(self, filepath: str) -> list[str]:
        """Get file lines with caching."""
        return self._read_file_cached(filepath)

    def clear_cache(self):
        """Clear cache after search session."""
        self._read_file_cached.cache_clear()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed context lines only | Smart boundary expansion to functions/classes | 2024+ | Better code comprehension in results |
| Read file multiple times per result | linecache automatic caching | Python 1.5+ (1997) | Standard approach for line-based access |
| Manual cache implementation | functools.lru_cache decorator | Python 3.2+ (2011) | Simpler, thread-safe caching |
| Regex-based scope detection | Tree-sitter AST traversal | 2018+ | Reliable multi-language parsing |

**Deprecated/outdated:**
- Manual file caching with dictionaries: Use functools.lru_cache instead
- Regex patterns for function boundaries: Use tree-sitter AST instead
- Reading entire file into memory per result: Use linecache for line access

## Open Questions

1. **Line truncation length for long lines**
   - What we know: CONTEXT.md specifies "reasonable length with ... suffix"
   - What's unclear: Exact character count (200? 500?)
   - Recommendation: Use 200 chars as standard (readable in 80-120 char terminals, leaves room for indentation)

2. **Grouping strategy for overlapping results**
   - What we know: CONTEXT.md defers to "Claude's discretion" for grouping multiple results from same file
   - What's unclear: Merge overlapping contexts or show separately?
   - Recommendation: Start with separate results (simpler), add merging in future if users report clutter

3. **BOF/EOF marker format**
   - What we know: Should indicate when context hits beginning/end of file
   - What's unclear: Exact marker text
   - Recommendation: Use `[Beginning of file]` and `[End of file]` markers (clear, grep-like style)

4. **Non-code file fallback behavior**
   - What we know: Smart expansion doesn't apply to JSON, Markdown, etc.
   - What's unclear: Should we attempt tree-sitter parse anyway, or skip directly to fixed lines?
   - Recommendation: Skip tree-sitter for known non-code extensions (json, md, txt, yaml), always use fixed line count

## Sources

### Primary (HIGH confidence)

- [Python linecache documentation](https://docs.python.org/3/library/linecache.html) - Stdlib module for efficient line access
- [Python functools.lru_cache documentation](https://realpython.com/lru-cache-python/) - Caching decorator usage patterns
- [py-tree-sitter Node API](https://tree-sitter.github.io/py-tree-sitter/classes/tree_sitter.Node.html) - Node traversal and parent access
- [GNU grep Context Line Control](http://www.gnu.org/s/grep/manual/html_node/Context-Line-Control.html) - Standard context line behavior
- [ripgrep manual](https://manpages.debian.org/testing/ripgrep/rg.1.en.html) - Modern context output patterns
- Existing CocoSearch codebase:
  - `/src/cocosearch/indexer/symbols.py` - Tree-sitter parser patterns already implemented
  - `/src/cocosearch/search/utils.py` - Existing context line retrieval function
  - `/src/cocosearch/search/formatter.py` - Existing file grouping and output formatting

### Secondary (MEDIUM confidence)

- [Tree-sitter syntax highlighting guide](https://tree-sitter.github.io/tree-sitter/3-syntax-highlighting.html) - Node boundary concepts
- [Sourcegraph code search features](https://sourcegraph.com/docs/code-search/features) - Context expansion in production tools
- [SQLPey Python file reading techniques](https://sqlpey.com/python/python-specific-line-extraction-methods/) - Line extraction patterns

### Tertiary (LOW confidence)

- Web search results on batch file processing - General patterns, not specific to context expansion

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in use or Python stdlib with extensive documentation
- Architecture patterns: HIGH - Tree-sitter integration proven in Phase 29-30, linecache is stdlib standard
- Pitfalls: MEDIUM - Based on general Python experience and tree-sitter characteristics, not CocoSearch-specific testing

**Research date:** 2026-02-03
**Valid until:** 90 days (stable domain - linecache and tree-sitter APIs rarely change)

**Key decisions validated:**
- Smart expansion by default: Confirmed viable with tree-sitter parent traversal
- 50-line hard limit: Standard practice, prevents output overflow
- Grep-style markers: Established convention from GNU grep and ripgrep
- Batched file I/O: Proven pattern in existing formatter.py code
