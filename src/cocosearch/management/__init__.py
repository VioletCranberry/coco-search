"""Management module for cocosearch.

Provides functions for index discovery, statistics, clearing,
and git-based index name detection.
"""

from cocosearch.management.clear import clear_index
from cocosearch.management.discovery import list_indexes
from cocosearch.management.git import derive_index_from_git, get_git_root
from cocosearch.management.stats import get_stats

__all__ = [
    "clear_index",
    "derive_index_from_git",
    "get_git_root",
    "get_stats",
    "list_indexes",
]
