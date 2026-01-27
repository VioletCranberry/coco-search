"""Search query module for cocosearch.

Provides the core search functionality that embeds queries and
performs vector similarity searches against the PostgreSQL database.
"""

import logging
from dataclasses import dataclass

from cocosearch.indexer.embedder import code_to_embedding
from cocosearch.search.db import get_connection_pool, get_table_name

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result.

    Attributes:
        filename: Full file path to the source file.
        start_byte: Start byte offset of the chunk in the file.
        end_byte: End byte offset of the chunk in the file.
        score: Similarity score (0-1, higher = more similar).
        block_type: DevOps block type (e.g., "resource", "FROM", "function").
        hierarchy: DevOps hierarchy path (e.g., "resource.aws_s3_bucket.data").
        language_id: DevOps language identifier (e.g., "hcl", "dockerfile", "bash").
    """

    filename: str
    start_byte: int
    end_byte: int
    score: float
    block_type: str = ""
    hierarchy: str = ""
    language_id: str = ""


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

# DevOps language canonical names mapped to language_id values in the database
DEVOPS_LANGUAGES = {
    "hcl": "hcl",
    "dockerfile": "dockerfile",
    "bash": "bash",
}

# Alias mapping for REQ-20 compatibility (resolved silently before validation)
LANGUAGE_ALIASES = {
    "terraform": "hcl",
    "shell": "bash",
    "sh": "bash",
}

# Combined set of all recognized language names for validation/suggestions.
# Alias keys are NOT included -- they are resolved before validation.
ALL_LANGUAGES = set(LANGUAGE_EXTENSIONS.keys()) | set(DEVOPS_LANGUAGES.keys())

# Module-level flag for metadata column availability (pre-v1.2 graceful degradation)
_has_metadata_columns = True
_metadata_warning_emitted = False


def get_extension_patterns(language: str) -> list[str]:
    """Get SQL LIKE patterns for a language.

    Args:
        language: Programming language name (e.g., "python", "typescript").

    Returns:
        List of SQL LIKE patterns (e.g., ["%.py", "%.pyw", "%.pyi"]).
    """
    exts = LANGUAGE_EXTENSIONS.get(language.lower(), [f".{language}"])
    return [f"%{ext}" for ext in exts]


def validate_language_filter(lang_str: str) -> list[str]:
    """Validate and resolve a language filter string.

    Splits on commas, resolves aliases (e.g., terraform -> hcl),
    and validates against known languages.

    Args:
        lang_str: Comma-separated language names (e.g., "python,hcl").

    Returns:
        List of validated canonical language names.

    Raises:
        ValueError: If any language name is unrecognized after alias resolution.
    """
    languages = [lang.strip() for lang in lang_str.split(",")]
    resolved = []
    for lang in languages:
        # Resolve aliases first (e.g., terraform -> hcl, shell -> bash)
        canonical = LANGUAGE_ALIASES.get(lang, lang)
        resolved.append(canonical)

    # Validate all resolved names
    unknown = [lang for lang in resolved if lang not in ALL_LANGUAGES]
    if unknown:
        available = sorted(ALL_LANGUAGES)
        raise ValueError(
            f"Unknown language(s): {', '.join(unknown)}. "
            f"Available: {', '.join(available)}"
        )

    return resolved


def search(
    query: str,
    index_name: str,
    limit: int = 10,
    min_score: float = 0.0,
    language_filter: str | None = None,
) -> list[SearchResult]:
    """Search for code similar to query.

    Embeds the query using the same model as indexing, then performs
    a cosine similarity search against the PostgreSQL database.

    Args:
        query: Natural language search query.
        index_name: Name of the index to search.
        limit: Maximum results to return (default 10).
        min_score: Minimum similarity score to include (0-1, default 0.0).
        language_filter: Optional language filter (e.g., "python", "hcl,bash").

    Returns:
        List of SearchResult ordered by similarity (highest first).

    Raises:
        ValueError: If language_filter contains unrecognized language names,
            or if DevOps language filter is used on a pre-v1.2 index.
    """
    global _has_metadata_columns, _metadata_warning_emitted

    # Validate and resolve language filter
    validated_languages = None
    if language_filter:
        validated_languages = validate_language_filter(language_filter)

        # Check if any DevOps languages require metadata columns
        devops_langs = [l for l in validated_languages if l in DEVOPS_LANGUAGES]
        if devops_langs and not _has_metadata_columns:
            raise ValueError(
                "Language filtering requires v1.2 index. "
                "Run 'cocosearch index' to upgrade."
            )

    # Embed query using same model as indexing
    query_embedding = code_to_embedding.eval(query)

    pool = get_connection_pool()
    table_name = get_table_name(index_name)

    # Determine whether to include metadata columns in SELECT
    include_metadata = _has_metadata_columns

    # Build base SELECT columns
    if include_metadata:
        select_cols = (
            "filename, lower(location) as start_byte, upper(location) as end_byte, "
            "1 - (embedding <=> %s::vector) AS score, "
            "block_type, hierarchy, language_id"
        )
    else:
        select_cols = (
            "filename, lower(location) as start_byte, upper(location) as end_byte, "
            "1 - (embedding <=> %s::vector) AS score"
        )

    # Build WHERE clause for language filter
    where_parts = []
    filter_params = []
    if validated_languages:
        lang_conditions = []
        for lang in validated_languages:
            if lang in DEVOPS_LANGUAGES:
                # DevOps language: filter by language_id column
                lang_conditions.append("language_id = %s")
                filter_params.append(DEVOPS_LANGUAGES[lang])
            elif lang in LANGUAGE_EXTENSIONS:
                # Extension-based language: filter by filename LIKE
                extensions = get_extension_patterns(lang)
                ext_parts = ["filename LIKE %s" for _ in extensions]
                lang_conditions.append(f"({' OR '.join(ext_parts)})")
                filter_params.extend(extensions)
        if lang_conditions:
            where_parts.append(f"({' OR '.join(lang_conditions)})")

    where_clause = ""
    if where_parts:
        where_clause = "WHERE " + " AND ".join(where_parts)

    # Build full SQL
    sql = f"""
        SELECT {select_cols}
        FROM {table_name}
        {where_clause}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    params = [query_embedding] + filter_params + [query_embedding, limit]

    # Execute with graceful degradation for pre-v1.2 indexes
    rows = []
    with pool.connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(sql, params)
                rows = cur.fetchall()
            except Exception as e:
                # Check for UndefinedColumn error (pre-v1.2 index)
                error_type = type(e).__name__
                if error_type == "UndefinedColumn" or "UndefinedColumn" in str(
                    type(e)
                ):
                    _has_metadata_columns = False
                    if not _metadata_warning_emitted:
                        logger.warning(
                            "Index lacks metadata columns. "
                            "Run 'cocosearch index' to upgrade."
                        )
                        _metadata_warning_emitted = True
                    include_metadata = False

                    # Re-execute without metadata columns
                    select_cols_fallback = (
                        "filename, lower(location) as start_byte, "
                        "upper(location) as end_byte, "
                        "1 - (embedding <=> %s::vector) AS score"
                    )

                    # Rebuild WHERE without language_id conditions
                    fallback_where_parts = []
                    fallback_params = []
                    if validated_languages:
                        lang_conditions = []
                        for lang in validated_languages:
                            if lang in LANGUAGE_EXTENSIONS:
                                extensions = get_extension_patterns(lang)
                                ext_parts = [
                                    "filename LIKE %s" for _ in extensions
                                ]
                                lang_conditions.append(
                                    f"({' OR '.join(ext_parts)})"
                                )
                                fallback_params.extend(extensions)
                        if lang_conditions:
                            fallback_where_parts.append(
                                f"({' OR '.join(lang_conditions)})"
                            )

                    fallback_where = ""
                    if fallback_where_parts:
                        fallback_where = "WHERE " + " AND ".join(
                            fallback_where_parts
                        )

                    fallback_sql = f"""
                        SELECT {select_cols_fallback}
                        FROM {table_name}
                        {fallback_where}
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    """
                    fallback_all_params = (
                        [query_embedding]
                        + fallback_params
                        + [query_embedding, limit]
                    )
                    cur.execute(fallback_sql, fallback_all_params)
                    rows = cur.fetchall()
                else:
                    raise

    # Filter by min_score and convert to SearchResult
    results = []
    for row in rows:
        score = float(row[3])
        if score >= min_score:
            if include_metadata:
                results.append(
                    SearchResult(
                        filename=row[0],
                        start_byte=int(row[1]),
                        end_byte=int(row[2]),
                        score=score,
                        block_type=row[4] if row[4] else "",
                        hierarchy=row[5] if row[5] else "",
                        language_id=row[6] if row[6] else "",
                    )
                )
            else:
                results.append(
                    SearchResult(
                        filename=row[0],
                        start_byte=int(row[1]),
                        end_byte=int(row[2]),
                        score=score,
                    )
                )

    return results
