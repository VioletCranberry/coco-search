"""Search query module for cocosearch.

Provides the core search functionality that embeds queries and
performs vector similarity searches against the PostgreSQL database.
"""

from dataclasses import dataclass

from cocosearch.indexer.embedder import code_to_embedding
from cocosearch.search.db import get_connection_pool, get_table_name


@dataclass
class SearchResult:
    """A single search result.

    Attributes:
        filename: Full file path to the source file.
        start_byte: Start byte offset of the chunk in the file.
        end_byte: End byte offset of the chunk in the file.
        score: Similarity score (0-1, higher = more similar).
    """

    filename: str
    start_byte: int
    end_byte: int
    score: float


# Language to file extension mapping
LANGUAGE_EXTENSIONS = {
    "python": [".py", ".pyw", ".pyi"],
    "javascript": [".js", ".mjs", ".cjs"],
    "typescript": [".ts", ".tsx", ".mts", ".cts"],
    "rust": [".rs"],
    "go": [".go"],
    "java": [".java"],
    "ruby": [".rb"],
    "php": [".php"],
    "c": [".c", ".h"],
    "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".hxx"],
    "csharp": [".cs"],
    "swift": [".swift"],
    "kotlin": [".kt", ".kts"],
    "scala": [".scala"],
    "shell": [".sh", ".bash", ".zsh"],
}


def get_extension_patterns(language: str) -> list[str]:
    """Get SQL LIKE patterns for a language.

    Args:
        language: Programming language name (e.g., "python", "typescript").

    Returns:
        List of SQL LIKE patterns (e.g., ["%.py", "%.pyw", "%.pyi"]).
    """
    exts = LANGUAGE_EXTENSIONS.get(language.lower(), [f".{language}"])
    return [f"%{ext}" for ext in exts]


def search(
    query: str,
    index_name: str,
    limit: int = 10,
    min_score: float = 0.0,
    language_filter: str | None = None,
) -> list[SearchResult]:
    """Search for code similar to query.

    Embeds the query using the same model as indexing, then performs
    a cosine similarity search against the indexed code chunks.

    Args:
        query: Natural language search query.
        index_name: Name of the index to search.
        limit: Maximum results to return (default 10).
        min_score: Minimum similarity score to include (0-1, default 0.0).
        language_filter: Optional language filter (e.g., "python").

    Returns:
        List of SearchResult ordered by similarity (highest first).
    """
    # Embed query using same model as indexing
    query_embedding = code_to_embedding.eval(query)

    pool = get_connection_pool()
    table_name = get_table_name(index_name)

    # Build query with optional language filter
    # Note: location is stored as int4range [start, end)
    if language_filter:
        extensions = get_extension_patterns(language_filter)
        # Build OR clause for multiple extensions
        ext_conditions = " OR ".join(["filename LIKE %s" for _ in extensions])
        sql = f"""
            SELECT filename, lower(location) as start_byte, upper(location) as end_byte,
                   1 - (embedding <=> %s::vector) AS score
            FROM {table_name}
            WHERE ({ext_conditions})
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        params = [query_embedding] + extensions + [query_embedding, limit]
    else:
        sql = f"""
            SELECT filename, lower(location) as start_byte, upper(location) as end_byte,
                   1 - (embedding <=> %s::vector) AS score
            FROM {table_name}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        params = [query_embedding, query_embedding, limit]

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    # Filter by min_score and convert to SearchResult
    results = []
    for row in rows:
        score = float(row[3])
        if score >= min_score:
            results.append(
                SearchResult(
                    filename=row[0],
                    start_byte=int(row[1]),
                    end_byte=int(row[2]),
                    score=score,
                )
            )

    return results
