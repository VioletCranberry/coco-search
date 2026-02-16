"""Utility functions for search result processing.

Provides byte offset to line number conversion and chunk content
reading from source files for result formatting.
"""


def byte_to_line(filepath: str, byte_offset: int) -> int:
    """Convert byte offset to 1-based line number.

    Args:
        filepath: Path to the source file.
        byte_offset: Byte offset in the file.

    Returns:
        1-based line number, or 0 if file not accessible.
    """
    try:
        with open(filepath, "rb") as f:
            content = f.read(byte_offset)
            return content.count(b"\n") + 1
    except (FileNotFoundError, IOError):
        return 0  # File not accessible


def read_chunk_content(filepath: str, start_byte: int, end_byte: int) -> str:
    """Read chunk content from source file.

    Args:
        filepath: Path to the source file.
        start_byte: Start byte offset.
        end_byte: End byte offset.

    Returns:
        Chunk text content, or empty string if file not accessible.
    """
    try:
        with open(filepath, "rb") as f:
            f.seek(start_byte)
            content = f.read(end_byte - start_byte)
            return content.decode("utf-8", errors="replace")
    except (FileNotFoundError, IOError):
        return ""
