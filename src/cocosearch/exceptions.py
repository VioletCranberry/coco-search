"""Exception hierarchy for cocosearch.

Provides structured error types for different failure modes,
replacing generic ValueError/Exception usage throughout the codebase.
"""


class CocoSearchError(Exception):
    """Base exception for all cocosearch errors."""


class IndexNotFoundError(CocoSearchError, ValueError):
    """Raised when a requested index does not exist.

    Inherits from ValueError for backward compatibility with existing
    except ValueError handlers.
    """


class IndexValidationError(CocoSearchError, ValueError):
    """Raised when an index name fails validation.

    Inherits from ValueError for backward compatibility.
    """


class SearchError(CocoSearchError):
    """Raised when a search operation fails."""


class InfrastructureError(CocoSearchError):
    """Raised when required infrastructure (DB, Ollama) is unavailable."""
