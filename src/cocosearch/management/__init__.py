"""Management module for cocosearch.

Provides functions for index discovery, statistics, clearing,
and git-based index name detection.
"""

from cocosearch.management.discovery import list_indexes
from cocosearch.management.stats import get_stats

__all__ = [
    "list_indexes",
    "get_stats",
]
