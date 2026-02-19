"""Search query module for cocosearch.

Provides the core search functionality that embeds queries and
performs vector similarity searches against the PostgreSQL database.
"""

import logging
from dataclasses import dataclass

from cocosearch.indexer.embedder import code_to_embedding
from cocosearch.search.cache import get_query_cache
from cocosearch.search.db import (
    check_column_exists,
    check_symbol_columns_exist,
    get_connection_pool,
    get_table_name,
)
from cocosearch.search.filters import build_symbol_where_clause
from cocosearch.search.hybrid import hybrid_search as execute_hybrid_search
from cocosearch.search.query_analyzer import has_identifier_pattern
from cocosearch.validation import validate_query

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result.

    Attributes:
        filename: Full file path to the source file.
        start_byte: Start byte offset of the chunk in the file.
        end_byte: End byte offset of the chunk in the file.
        score: Similarity score (0-1, higher = more similar).
        block_type: Handler block type (e.g., "resource", "FROM", "function").
        hierarchy: Handler hierarchy path (e.g., "resource.aws_s3_bucket.data").
        language_id: Handler language identifier (e.g., "hcl", "dockerfile", "bash").
        match_type: Source of match for hybrid search ("semantic", "keyword", "both", or "" for vector-only).
        vector_score: Original vector similarity score (for hybrid search breakdown).
        keyword_score: Keyword/ts_rank score (for hybrid search breakdown).
        symbol_type: Symbol type ("function", "class", "method", "interface", or None).
        symbol_name: Symbol name (e.g., "process_data", "UserService.get_user", or None).
        symbol_signature: Symbol signature (e.g., "def process_data(items: list)", or None).
    """

    filename: str
    start_byte: int
    end_byte: int
    score: float
    block_type: str = ""
    hierarchy: str = ""
    language_id: str = ""
    match_type: str = (
        ""  # "" for backward compat, "semantic"/"keyword"/"both" for hybrid
    )
    vector_score: float | None = None
    keyword_score: float | None = None
    symbol_type: str | None = None
    symbol_name: str | None = None
    symbol_signature: str | None = None


# Language to file extension mapping
LANGUAGE_EXTENSIONS = {
    "c": [".c", ".h"],
    "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".hxx"],
    "csharp": [".cs"],
    "css": [".css", ".scss"],
    "dtd": [".dtd"],
    "fortran": [".f", ".f90", ".f95", ".f03"],
    "go": [".go"],
    "html": [".html", ".htm"],
    "java": [".java"],
    "javascript": [".js", ".mjs", ".cjs", ".jsx"],
    "json": [".json"],
    "kotlin": [".kt", ".kts"],
    "markdown": [".md", ".mdx"],
    "pascal": [".pas", ".dpr"],
    "php": [".php"],
    "python": [".py", ".pyw", ".pyi"],
    "r": [".r", ".R"],
    "ruby": [".rb"],
    "rust": [".rs"],
    "scala": [".scala"],
    "groovy": [".groovy", ".gradle"],
    "solidity": [".sol"],
    "sql": [".sql"],
    "swift": [".swift"],
    "toml": [".toml"],
    "typescript": [".ts", ".tsx", ".mts", ".cts"],
    "xml": [".xml"],
    "yaml": [".yaml", ".yml"],
}

# Symbol-aware languages (support symbol extraction via tree-sitter)
SYMBOL_AWARE_LANGUAGES = {
    "python",
    "javascript",
    "typescript",
    "go",
    "rust",
    "java",
    "c",
    "cpp",
    "ruby",
    "php",
    "hcl",
    "terraform",
    "bash",
    "scala",
    "css",
}

# Handler language canonical names mapped to language_id values in the database
HANDLER_LANGUAGES = {
    "hcl": "hcl",
    "dockerfile": "dockerfile",
    "bash": "bash",
}

# Alias mapping for REQ-20 compatibility (resolved silently before validation)
LANGUAGE_ALIASES = {
    "shell": "bash",
    "sh": "bash",
}

# Combined set of all recognized language names for validation/suggestions.
# Alias keys are NOT included -- they are resolved before validation.
# Grammar names (e.g., github-actions, docker-compose) are added lazily
# via _get_all_languages() to avoid heavy imports at module level.
_ALL_LANGUAGES_CACHE: set[str] | None = None
_LANGUAGE_ID_MAP_CACHE: dict[str, str] | None = None


def _get_grammar_names() -> list[str]:
    """Get grammar handler names from the autodiscovery registry.

    Returns an empty list if handlers can't be imported (e.g., cocoindex
    not available).
    """
    try:
        from cocosearch.handlers import get_registered_grammars

        return [g.GRAMMAR_NAME for g in get_registered_grammars()]
    except Exception:
        return []


def _get_all_languages() -> set[str]:
    """Get all recognized language names including grammar handler names.

    Lazily includes grammar names from the autodiscovery registry to avoid
    importing the handler module (and cocoindex) at module load time.
    """
    global _ALL_LANGUAGES_CACHE
    if _ALL_LANGUAGES_CACHE is None:
        base = set(LANGUAGE_EXTENSIONS.keys()) | set(HANDLER_LANGUAGES.keys())
        for name in _get_grammar_names():
            base.add(name)
        _ALL_LANGUAGES_CACHE = base
    return _ALL_LANGUAGES_CACHE


def _get_language_id_map() -> dict[str, str]:
    """Get mapping of language names to language_id values in the database.

    Includes both handler languages (hcl, dockerfile, bash) and grammar
    handler names (github-actions, docker-compose, etc.) which all use
    the language_id column for filtering.
    """
    global _LANGUAGE_ID_MAP_CACHE
    if _LANGUAGE_ID_MAP_CACHE is None:
        result = dict(HANDLER_LANGUAGES)
        for name in _get_grammar_names():
            result[name] = name
        _LANGUAGE_ID_MAP_CACHE = result
    return _LANGUAGE_ID_MAP_CACHE


# Module-level flag for hybrid search column availability (pre-v1.7 graceful degradation)
_has_content_text_column = True
_hybrid_warning_emitted = False


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
    unknown = [lang for lang in resolved if lang not in _get_all_languages()]
    if unknown:
        available = sorted(_get_all_languages())
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
    use_hybrid: bool | None = None,
    symbol_type: str | list[str] | None = None,
    symbol_name: str | None = None,
    no_cache: bool = False,
) -> list[SearchResult]:
    """Search for code similar to query.

    Embeds the query using the same model as indexing, then performs
    a cosine similarity search against the PostgreSQL database.
    Optionally uses hybrid search (vector + keyword) for better results
    when searching for code identifiers.

    Args:
        query: Natural language search query.
        index_name: Name of the index to search.
        limit: Maximum results to return (default 10).
        min_score: Minimum similarity score to include (0-1, default 0.0).
        language_filter: Optional language filter (e.g., "python", "hcl,bash").
        use_hybrid: Hybrid search mode:
            - None (default): Auto-detect from query (enabled for identifier patterns)
            - True: Force hybrid search (falls back to vector-only if unavailable)
            - False: Use vector-only search
        symbol_type: Filter by symbol type ("function", "class", "method", "interface").
            Can be a single string or list of types.
        symbol_name: Filter by symbol name using glob pattern (supports * and ?).
        no_cache: If True, bypass query cache (default False).

    Returns:
        List of SearchResult ordered by similarity (highest first).
        When hybrid search is used, results include match_type indicator.
        When symbol filtering is used, results include symbol_type, symbol_name,
        and symbol_signature fields.

    Raises:
        ValueError: If language_filter contains unrecognized language names,
            if symbol filter is used on a pre-v1.7 index,
            or if symbol_type contains invalid type names.
    """
    global _has_content_text_column, _hybrid_warning_emitted

    # Validate query input
    query = validate_query(query)

    # Check cache first (exact match only at this point, semantic check after embedding)
    if not no_cache:
        cache = get_query_cache()
        cached_results, hit_type = cache.get(
            query=query,
            index_name=index_name,
            limit=limit,
            min_score=min_score,
            language_filter=language_filter,
            use_hybrid=use_hybrid,
            symbol_type=symbol_type,
            symbol_name=symbol_name,
            query_embedding=None,  # No embedding yet for semantic check
        )
        if cached_results is not None:
            logger.debug(f"Cache hit ({hit_type})")
            return cached_results

    # Validate and resolve language filter
    validated_languages = None
    if language_filter:
        validated_languages = validate_language_filter(language_filter)

    pool = get_connection_pool()
    table_name = get_table_name(index_name)

    # Validate symbol filter (requires v1.7+ index with symbol columns)
    if symbol_type is not None or symbol_name is not None:
        if not check_symbol_columns_exist(table_name):
            raise ValueError(
                f"Symbol filtering requires v1.7+ index. Index '{index_name}' lacks symbol columns. "
                "Re-index with 'cocosearch index' to enable symbol filtering."
            )

    # Always include symbol columns when available (used by definition boost)
    include_symbol_columns = check_symbol_columns_exist(table_name)

    # Check for hybrid search capability (content_text column) on first call
    if _has_content_text_column and not _hybrid_warning_emitted:
        if not check_column_exists(table_name, "content_text"):
            _has_content_text_column = False
            logger.warning(
                "Index lacks hybrid search columns (content_text). "
                "Run 'cocosearch index' to enable hybrid search."
            )
            _hybrid_warning_emitted = True

    # Determine whether to use hybrid search
    should_use_hybrid = False
    if use_hybrid is True:
        # Explicit request for hybrid search
        if _has_content_text_column:
            should_use_hybrid = True
        else:
            # Fall back to vector-only silently (already warned above)
            logger.debug(
                "Hybrid search requested but content_text column missing, using vector-only"
            )
    elif use_hybrid is None:
        # Auto-detect: use hybrid if query has identifier patterns AND column exists
        if _has_content_text_column and has_identifier_pattern(query):
            should_use_hybrid = True
            logger.debug(
                "Auto-detected identifier pattern in query, using hybrid search"
            )
    # use_hybrid is False: always use vector-only (no action needed)

    # Execute hybrid search if applicable
    # Hybrid search now supports language and symbol filtering (applied before RRF fusion)
    if should_use_hybrid:
        hybrid_results = execute_hybrid_search(
            query,
            index_name,
            limit,
            symbol_type=symbol_type,
            symbol_name=symbol_name,
            language_filter=",".join(validated_languages)
            if validated_languages
            else language_filter,
        )

        # Convert HybridSearchResult to SearchResult, applying min_score filter
        results = []
        for hr in hybrid_results:
            if hr.combined_score >= min_score:
                results.append(
                    SearchResult(
                        filename=hr.filename,
                        start_byte=hr.start_byte,
                        end_byte=hr.end_byte,
                        score=hr.combined_score,
                        block_type=hr.block_type,
                        hierarchy=hr.hierarchy,
                        language_id=hr.language_id,
                        match_type=hr.match_type,
                        vector_score=hr.vector_score,
                        keyword_score=hr.keyword_score,
                        symbol_type=hr.symbol_type,
                        symbol_name=hr.symbol_name,
                        symbol_signature=hr.symbol_signature,
                    )
                )

        # Cache results for future queries (hybrid search doesn't have embedding)
        if not no_cache:
            cache = get_query_cache()
            cache.put(
                query=query,
                index_name=index_name,
                limit=limit,
                min_score=min_score,
                language_filter=language_filter,
                use_hybrid=use_hybrid,
                symbol_type=symbol_type,
                symbol_name=symbol_name,
                results=results,
                query_embedding=None,  # Hybrid search doesn't expose query embedding
            )

        return results

    # Vector-only search (existing behavior)
    # Embed query using same model as indexing
    query_embedding = code_to_embedding.eval(query)

    # Build base SELECT columns (always include metadata)
    select_cols = (
        "filename, lower(location) as start_byte, upper(location) as end_byte, "
        "1 - (embedding <=> %s::vector) AS score, "
        "block_type, hierarchy, language_id"
    )
    # Add symbol columns when symbol filtering is active
    if include_symbol_columns:
        select_cols += ", symbol_type, symbol_name, symbol_signature"

    # Build WHERE clause for language filter
    where_parts = []
    filter_params = []
    if validated_languages:
        lang_id_map = _get_language_id_map()
        lang_conditions = []
        for lang in validated_languages:
            if lang in lang_id_map:
                # Handler/grammar language: filter by language_id column
                lang_conditions.append("language_id = %s")
                filter_params.append(lang_id_map[lang])
            elif lang in LANGUAGE_EXTENSIONS:
                # Extension-based language: filter by filename LIKE
                extensions = get_extension_patterns(lang)
                ext_parts = ["filename LIKE %s" for _ in extensions]
                lang_conditions.append(f"({' OR '.join(ext_parts)})")
                filter_params.extend(extensions)
        if lang_conditions:
            where_parts.append(f"({' OR '.join(lang_conditions)})")

    # Build WHERE clause for symbol filter (combines with language filter via AND)
    if symbol_type is not None or symbol_name is not None:
        symbol_where, symbol_params = build_symbol_where_clause(
            symbol_type, symbol_name
        )
        if symbol_where:
            where_parts.append(symbol_where)
            filter_params.extend(symbol_params)

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

    # Execute query (expects metadata columns to exist)
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    # Filter by min_score and convert to SearchResult
    results = []
    for row in rows:
        score = float(row[3])
        if score >= min_score:
            # Base result with metadata columns (indices 0-6)
            result = SearchResult(
                filename=row[0],
                start_byte=int(row[1]),
                end_byte=int(row[2]),
                score=score,
                block_type=row[4] if row[4] else "",
                hierarchy=row[5] if row[5] else "",
                language_id=row[6] if row[6] else "",
            )
            # Add symbol columns if included (indices 7-9)
            if include_symbol_columns:
                result.symbol_type = row[7] if row[7] else None
                result.symbol_name = row[8] if row[8] else None
                result.symbol_signature = row[9] if row[9] else None
            results.append(result)

    # Cache results for future queries (vector search includes embedding for semantic matching)
    if not no_cache:
        cache = get_query_cache()
        cache.put(
            query=query,
            index_name=index_name,
            limit=limit,
            min_score=min_score,
            language_filter=language_filter,
            use_hybrid=use_hybrid,
            symbol_type=symbol_type,
            symbol_name=symbol_name,
            results=results,
            query_embedding=query_embedding,
        )

    return results
