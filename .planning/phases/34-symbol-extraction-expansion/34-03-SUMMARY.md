---
phase: 34-symbol-extraction-expansion
plan: 03
subsystem: indexer
type: feature
tags: [symbol-extraction, tree-sitter, c, cpp, query-files]

dependency-graph:
  requires: ["34-01"]
  provides: ["c-symbol-extraction", "cpp-symbol-extraction"]
  affects: ["34-04"]

tech-stack:
  added: []
  patterns: [tree-sitter-queries]

key-files:
  created:
    - src/cocosearch/indexer/queries/c.scm
    - src/cocosearch/indexer/queries/cpp.scm
  modified:
    - src/cocosearch/indexer/symbols.py
    - tests/unit/indexer/test_symbols.py

decisions: []

metrics:
  duration: "5m 7s"
  tasks-completed: 3
  commits: 3
  tests-added: 29
  tests-passing: 29
  completed: 2026-02-03
---

# Phase 34 Plan 03: C and C++ Symbol Extraction

C and C++ symbol extraction using external tree-sitter query files

## Summary

Added comprehensive symbol extraction support for C and C++ languages. Both languages now extract functions, classes/structs, and type definitions using query-based patterns. C++ includes namespace support and qualified method names with "::" separator.

## Tasks Completed

### Task 1: Add C symbol extraction
- Created `c.scm` query file for C symbol patterns
- Extracts functions (with body), structs (with body), enums, typedefs
- Correctly ignores forward declarations (no body)
- Added C extensions (.c, .h) to LANGUAGE_MAP
- Configured container types for struct qualification
- Commit: `1b604fc`

### Task 2: Add C++ symbol extraction
- Created `cpp.scm` query file for C++ symbol patterns
- Extracts classes, structs, namespaces, functions, methods
- Supports qualified method names (MyClass::method)
- Supports template classes and functions
- Added C++ extensions (.cpp, .cxx, .cc, .hpp, .hxx, .hh) to LANGUAGE_MAP
- Configured container types and "::" separator for C++
- Commit: `18eea1f`

### Task 3: Add tests for C and C++ extraction
- Added TestCSymbols class with 11 test cases
- Added TestCppSymbols class with 11 test cases
- Updated TestLanguageMap for new extensions (23 total)
- All 29 new tests passing
- Commit: `b6d2c28`

## Technical Details

### C Symbol Patterns
```scheme
;; Functions (definitions only)
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @name)) @definition.function

;; Structs (with body - excludes forward declarations)
(struct_specifier
  name: (type_identifier) @name
  body: (field_declaration_list)) @definition.struct

;; Enums
(enum_specifier
  name: (type_identifier) @name) @definition.enum

;; Typedefs
(type_definition
  declarator: (type_identifier) @name) @definition.type
```

### C++ Symbol Patterns
```scheme
;; Classes
(class_specifier
  name: (type_identifier) @name) @definition.class

;; Namespaces
(namespace_definition
  (namespace_identifier) @name) @definition.namespace

;; Methods with qualified names
(function_definition
  declarator: (function_declarator
    declarator: (qualified_identifier
      name: (identifier) @name))) @definition.method

;; Template classes and functions
(template_declaration
  (class_specifier
    name: (type_identifier) @name)) @definition.class
```

### Symbol Type Mappings
- C: struct → class, enum → class, typedef → interface
- C++: namespace → class, struct → class

### Qualified Names
- C: struct-based qualification (MyStruct.field_access patterns)
- C++: uses "::" separator (MyClass::method, MyNamespace::function)

## Verification

### Manual Testing
```bash
# C function extraction
uv run python -c "from cocosearch.indexer.symbols import extract_symbol_metadata; \
  print(extract_symbol_metadata('int foo() { return 0; }', 'c'))"
# → {"symbol_type": "function", "symbol_name": "foo", "symbol_signature": "int foo()"}

# C forward declaration ignored
uv run python -c "from cocosearch.indexer.symbols import extract_symbol_metadata; \
  print(extract_symbol_metadata('int foo();', 'c'))"
# → {"symbol_type": null, "symbol_name": null, "symbol_signature": null}

# C++ namespace
uv run python -c "from cocosearch.indexer.symbols import extract_symbol_metadata; \
  print(extract_symbol_metadata('namespace MyLib {}', 'cpp'))"
# → {"symbol_type": "class", "symbol_name": "MyLib", "symbol_signature": "namespace MyLib"}

# C++ method with qualified name
uv run python -c "from cocosearch.indexer.symbols import extract_symbol_metadata; \
  print(extract_symbol_metadata('void MyClass::myMethod() {}', 'cpp'))"
# → {"symbol_type": "method", "symbol_name": "myMethod", "symbol_signature": "void MyClass::myMethod()"}
```

### Automated Testing
```bash
# All C tests pass
uv run pytest tests/unit/indexer/test_symbols.py::TestCSymbols -v
# 11 passed

# All C++ tests pass
uv run pytest tests/unit/indexer/test_symbols.py::TestCppSymbols -v
# 11 passed

# Language map tests pass
uv run pytest tests/unit/indexer/test_symbols.py::TestLanguageMap -v
# 7 passed
```

## Decisions Made

1. **Forward declaration handling**: Only extract definitions with body. This prevents duplicate symbols and matches user expectations (definitions are the primary symbols of interest).

2. **C++ namespace mapping**: Map namespaces to "class" symbol type. Namespaces are organizational containers, similar to modules/classes in other languages.

3. **Qualified name format**: C++ uses "::" separator (MyClass::method) to match C++ convention, while other languages use "." separator.

4. **Template support**: Extract template classes and functions as regular symbols. Template parameters are preserved in signatures but don't affect symbol name.

5. **Header file extension**: .h files map to C (not C++). Users can override via .cocosearch/queries/ if needed.

## Deviations from Plan

None - plan executed exactly as written.

## Impact

### Language Coverage
- Total languages: 10 (Python, JS, TS, Go, Rust, Java, Ruby, PHP, C, C++)
- Total file extensions: 23

### Symbol Coverage
- C: functions, structs, enums, typedefs
- C++: functions, classes, structs, namespaces, methods (qualified), templates

### User Impact
- C and C++ codebases now fully indexed with symbol metadata
- Search results can filter by symbol type (function, class, etc.)
- Symbol names appear in search snippets for better context
- Qualified C++ method names improve disambiguation

## Next Phase Readiness

### Blockers
None

### Concerns
None

### Ready for
- Phase 34-04: Additional language support (if planned)
- Phase 35: Symbol-based search features
- Production deployment
