"""Query files for tree-sitter symbol extraction.

This package contains .scm query files for each supported language.
Query files define patterns for extracting symbols (functions, classes, methods, etc.)
using tree-sitter's declarative query language.

Users can override built-in queries by placing custom .scm files in:
- Project level: $PROJECT/.cocosearch/queries/
- User level: ~/.cocosearch/queries/
"""
