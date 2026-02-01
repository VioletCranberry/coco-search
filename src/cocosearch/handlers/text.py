"""Default handler for plain text files (fallback).

This handler is used when no specialized language handler matches the
file extension. It returns empty metadata and relies on CocoIndex's
default text splitting behavior.
"""


class TextHandler:
    """Default handler for plain text files."""

    EXTENSIONS: list[str] = []  # No specific extensions - used as fallback

    # No SEPARATOR_SPEC - uses CocoIndex default text splitting
    SEPARATOR_SPEC = None

    def extract_metadata(self, text: str) -> dict:
        """Return empty metadata for plain text.

        Args:
            text: The chunk text content.

        Returns:
            Dict with empty metadata fields
        """
        return {"block_type": "", "hierarchy": "", "language_id": ""}
