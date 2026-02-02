"""Management module for cocosearch.

Provides functions for index discovery, statistics, clearing,
git-based index name detection, project context detection,
and path-to-index metadata storage.
"""

from cocosearch.management.clear import clear_index
from cocosearch.management.context import (
    find_project_root,
    get_canonical_path,
    resolve_index_name,
)
from cocosearch.management.discovery import list_indexes
from cocosearch.management.git import derive_index_from_git, get_git_root
from cocosearch.management.metadata import (
    clear_index_path,
    ensure_metadata_table,
    get_index_for_path,
    get_index_metadata,
    register_index_path,
)
from cocosearch.management.stats import get_stats

__all__ = [
    "clear_index",
    "clear_index_path",
    "derive_index_from_git",
    "ensure_metadata_table",
    "find_project_root",
    "get_canonical_path",
    "get_git_root",
    "get_index_for_path",
    "get_index_metadata",
    "get_stats",
    "list_indexes",
    "register_index_path",
    "resolve_index_name",
]
