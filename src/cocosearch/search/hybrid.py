"""Hybrid search module combining vector and keyword search.

Implements Reciprocal Rank Fusion (RRF) to merge semantic similarity
and keyword matching results into a single ranked list.

RRF is chosen over score normalization because:
- Vector cosine similarity (0-1) and ts_rank scores have different distributions
- RRF uses rank positions only, making it distribution-agnostic
- Double-matched results naturally rank higher (both ranks contribute)
"""

import logging
from dataclasses import dataclass

from cocosearch.indexer.embedder import code_to_embedding
from cocosearch.search.db import (
    check_column_exists,
    check_symbol_columns_exist,
    get_connection_pool,
    get_table_name,
)
from cocosearch.search.filters import build_symbol_where_clause
from cocosearch.search.query_analyzer import normalize_query_for_keyword

logger = logging.getLogger(__name__)

# RRF constant — standard value from the original RRF paper. Higher values
# reduce the impact of rank differences between result lists.
RRF_K = 60

# Score multiplier for results identified as definitions (function, class, etc.)
# Applied after RRF fusion to boost definition-bearing chunks.
DEFINITION_BOOST_MULTIPLIER = 2.0

# Maximum results to request from each search backend before fusion.
# Fetching more candidates improves fusion quality at modest cost.
MAX_PREFETCH = 100


@dataclass
class KeywordResult:
    """A single keyword search result.

    Attributes:
        filename: Full file path to the source file.
        start_byte: Start byte offset of the chunk in the file.
        end_byte: End byte offset of the chunk in the file.
        ts_rank: PostgreSQL ts_rank score (0-1 scale, higher = better match).
    """

    filename: str
    start_byte: int
    end_byte: int
    ts_rank: float


@dataclass
class VectorResult:
    """A single vector search result.

    Attributes:
        filename: Full file path to the source file.
        start_byte: Start byte offset of the chunk in the file.
        end_byte: End byte offset of the chunk in the file.
        score: Cosine similarity score (0-1, higher = more similar).
        block_type: Handler block type (e.g., "resource", "FROM", "function").
        hierarchy: Handler hierarchy path (e.g., "resource.aws_s3_bucket.data").
        language_id: Handler language identifier (e.g., "hcl", "dockerfile", "bash").
        symbol_type: Symbol type ("function", "class", "method", "interface", or None).
        symbol_name: Symbol name (e.g., "process_data", or None).
        symbol_signature: Symbol signature (e.g., "def process_data(items: list)", or None).
    """

    filename: str
    start_byte: int
    end_byte: int
    score: float
    block_type: str = ""
    hierarchy: str = ""
    language_id: str = ""
    symbol_type: str | None = None
    symbol_name: str | None = None
    symbol_signature: str | None = None


@dataclass
class HybridSearchResult:
    """A hybrid search result combining vector and keyword matches.

    Attributes:
        filename: Full file path to the source file.
        start_byte: Start byte offset of the chunk in the file.
        end_byte: End byte offset of the chunk in the file.
        combined_score: RRF-fused score (higher = better overall match).
        match_type: Source of match - "semantic", "keyword", or "both".
        vector_score: Original cosine similarity (None if keyword-only).
        keyword_score: ts_rank score (None if semantic-only).
        block_type: Handler block type (from vector result if available).
        hierarchy: Handler hierarchy path (from vector result if available).
        language_id: Handler language identifier (from vector result if available).
        symbol_type: Symbol type ("function", "class", "method", "interface", or None).
        symbol_name: Symbol name (e.g., "process_data", or None).
        symbol_signature: Symbol signature (e.g., "def process_data(items: list)", or None).
    """

    filename: str
    start_byte: int
    end_byte: int
    combined_score: float
    match_type: str  # "semantic", "keyword", or "both"
    vector_score: float | None
    keyword_score: float | None
    block_type: str = ""
    hierarchy: str = ""
    language_id: str = ""
    symbol_type: str | None = None
    symbol_name: str | None = None
    symbol_signature: str | None = None


def _make_result_key(filename: str, start_byte: int, end_byte: int) -> str:
    """Create a unique key for a search result based on its location."""
    return f"{filename}:{start_byte}:{end_byte}"


def execute_keyword_search(
    query: str,
    table_name: str,
    limit: int = 10,
    where_clause: str = "",
    where_params: list | None = None,
) -> list[KeywordResult]:
    """Execute keyword search using PostgreSQL full-text search.

    Builds a tsquery from the normalized query and searches against
    the content_tsv column using the GIN index.

    Args:
        query: Search query (will be normalized to split identifiers).
        table_name: PostgreSQL table name.
        limit: Maximum results to return.
        where_clause: Optional SQL condition (without "WHERE") to filter results.
        where_params: Optional list of parameters for where_clause placeholders.

    Returns:
        List of KeywordResult ordered by ts_rank (highest first).
        Empty list if content_tsv column doesn't exist or no matches.
    """
    pool = get_connection_pool()

    # Check if hybrid search column exists
    if not check_column_exists(table_name, "content_tsv"):
        logger.debug(
            f"Table {table_name} lacks content_tsv column, skipping keyword search"
        )
        return []

    # Normalize query to split identifiers
    normalized = normalize_query_for_keyword(query)

    # Build WHERE clause: always include tsquery, optionally add extra conditions
    where_parts = ["content_tsv @@ plainto_tsquery('simple', %s)"]
    if where_clause:
        where_parts.append(f"({where_clause})")
    full_where = " AND ".join(where_parts)

    # Build tsquery using plainto_tsquery (handles spaces, simple matching)
    # Using 'simple' config for consistency with indexing (no stemming)
    sql = f"""
        SELECT
            filename,
            lower(location) as start_byte,
            upper(location) as end_byte,
            ts_rank(content_tsv, plainto_tsquery('simple', %s)) as rank
        FROM {table_name}
        WHERE {full_where}
        ORDER BY rank DESC
        LIMIT %s
    """

    # Build parameters: normalized (for ts_rank), normalized (for tsquery), where_params, limit
    params: list = [normalized, normalized]
    if where_params:
        params.extend(where_params)
    params.append(limit)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(sql, params)
                rows = cur.fetchall()
            except Exception as e:
                # Log at warning level and fall back to vector-only.
                # Common causes: malformed tsquery, missing column, connection error.
                logger.warning(
                    f"Keyword search failed (falling back to vector-only): {e}"
                )
                return []

    return [
        KeywordResult(
            filename=row[0],
            start_byte=int(row[1]),
            end_byte=int(row[2]),
            ts_rank=float(row[3]),
        )
        for row in rows
    ]


def execute_vector_search(
    query: str,
    table_name: str,
    limit: int = 10,
    where_clause: str = "",
    where_params: list | None = None,
) -> list[VectorResult]:
    """Execute vector similarity search.

    Embeds the query and performs cosine similarity search against
    the embedding column. Automatically includes symbol columns
    when available (v1.7+ indexes).

    Args:
        query: Search query (will be embedded).
        table_name: PostgreSQL table name.
        limit: Maximum results to return.
        where_clause: Optional SQL condition (without "WHERE") to filter results.
        where_params: Optional list of parameters for where_clause placeholders.

    Returns:
        List of VectorResult ordered by similarity (highest first).
    """
    pool = get_connection_pool()

    # Embed query
    query_embedding = code_to_embedding.eval(query)

    # Build WHERE clause if provided
    where_sql = f"WHERE {where_clause}" if where_clause else ""

    # Check if symbol columns exist (cached, essentially free)
    include_symbol_columns = check_symbol_columns_exist(table_name)

    # Build SELECT columns
    select_cols = """
            filename,
            lower(location) as start_byte,
            upper(location) as end_byte,
            1 - (embedding <=> %s::vector) AS score,
            block_type,
            hierarchy,
            language_id"""
    if include_symbol_columns:
        select_cols += """,
            symbol_type,
            symbol_name,
            symbol_signature"""

    # Query with metadata columns
    sql = f"""
        SELECT{select_cols}
        FROM {table_name}
        {where_sql}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """

    # Build parameters: embedding (for score), where_params, embedding (for ORDER BY), limit
    params: list = [query_embedding]
    if where_params:
        params.extend(where_params)
    params.extend([query_embedding, limit])

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    # Build results, including symbol columns when available
    return [
        VectorResult(
            filename=row[0],
            start_byte=int(row[1]),
            end_byte=int(row[2]),
            score=float(row[3]),
            block_type=row[4] if row[4] else "",
            hierarchy=row[5] if row[5] else "",
            language_id=row[6] if row[6] else "",
            **(
                {
                    "symbol_type": row[7] if row[7] else None,
                    "symbol_name": row[8] if row[8] else None,
                    "symbol_signature": row[9] if row[9] else None,
                }
                if include_symbol_columns
                else {}
            ),
        )
        for row in rows
    ]


def rrf_fusion(
    vector_results: list[VectorResult],
    keyword_results: list[KeywordResult],
    k: int = RRF_K,
) -> list[HybridSearchResult]:
    """Combine vector and keyword results using Reciprocal Rank Fusion.

    RRF score = sum(1 / (k + rank)) for each result across both lists.
    Results appearing in both lists get contributions from both ranks,
    naturally boosting double-matched results.

    Args:
        vector_results: Results from vector similarity search.
        keyword_results: Results from keyword/tsquery search.
        k: RRF constant (default 60, standard value). Higher k reduces
           the impact of rank differences.

    Returns:
        List of HybridSearchResult sorted by combined RRF score (highest first).
        Includes match_type indicator showing result source.
    """
    # Build lookup tables by result key
    vector_by_key: dict[str, tuple[int, VectorResult]] = {}
    keyword_by_key: dict[str, tuple[int, KeywordResult]] = {}

    # Store rank and result for vector results
    for rank, result in enumerate(vector_results, start=1):
        key = _make_result_key(result.filename, result.start_byte, result.end_byte)
        vector_by_key[key] = (rank, result)

    # Store rank and result for keyword results
    for rank, result in enumerate(keyword_results, start=1):
        key = _make_result_key(result.filename, result.start_byte, result.end_byte)
        keyword_by_key[key] = (rank, result)

    # Collect all unique keys
    all_keys = set(vector_by_key.keys()) | set(keyword_by_key.keys())

    # Calculate RRF score for each result
    fused_results: list[HybridSearchResult] = []

    for key in all_keys:
        rrf_score = 0.0
        vector_score: float | None = None
        keyword_score: float | None = None
        match_type = ""

        # Metadata from vector result (if available)
        block_type = ""
        hierarchy = ""
        language_id = ""
        symbol_type: str | None = None
        symbol_name: str | None = None
        symbol_signature: str | None = None

        # Get filename and byte positions from either source
        if key in vector_by_key:
            v_rank, v_result = vector_by_key[key]
            rrf_score += 1 / (k + v_rank)
            vector_score = v_result.score
            block_type = v_result.block_type
            hierarchy = v_result.hierarchy
            language_id = v_result.language_id
            symbol_type = v_result.symbol_type
            symbol_name = v_result.symbol_name
            symbol_signature = v_result.symbol_signature
            filename = v_result.filename
            start_byte = v_result.start_byte
            end_byte = v_result.end_byte
            match_type = "semantic"

        if key in keyword_by_key:
            k_rank, k_result = keyword_by_key[key]
            rrf_score += 1 / (k + k_rank)
            keyword_score = k_result.ts_rank

            # If we already have vector result, this is "both"
            if match_type == "semantic":
                match_type = "both"
            else:
                match_type = "keyword"
                filename = k_result.filename
                start_byte = k_result.start_byte
                end_byte = k_result.end_byte

        fused_results.append(
            HybridSearchResult(
                filename=filename,
                start_byte=start_byte,
                end_byte=end_byte,
                combined_score=rrf_score,
                match_type=match_type,
                vector_score=vector_score,
                keyword_score=keyword_score,
                block_type=block_type,
                hierarchy=hierarchy,
                language_id=language_id,
                symbol_type=symbol_type,
                symbol_name=symbol_name,
                symbol_signature=symbol_signature,
            )
        )

    # Sort by combined RRF score descending
    # On tie, favor keyword matches per CONTEXT.md decision
    fused_results.sort(
        key=lambda r: (r.combined_score, 1 if r.keyword_score is not None else 0),
        reverse=True,
    )

    return fused_results


def apply_definition_boost(
    results: list[HybridSearchResult],
    index_name: str,
    boost_multiplier: float = DEFINITION_BOOST_MULTIPLIER,
) -> list[HybridSearchResult]:
    """Apply score boost to definition symbols.

    Definitions are identified by the presence of symbol_type from
    tree-sitter extraction (e.g., "function", "class", "method").
    Boost is applied after RRF fusion to preserve rank-based algorithm
    semantics.

    Args:
        results: Fused hybrid search results.
        index_name: Name of the index (for symbol column check).
        boost_multiplier: Multiplier for definition scores (default 2.0).

    Returns:
        Results with boosted scores, re-sorted by new scores.
    """
    if not results:
        return results

    # Check if symbol columns exist (v1.7+ index)
    # If not, skip boost - can't identify definitions
    table_name = get_table_name(index_name)
    if not check_symbol_columns_exist(table_name):
        logger.debug("Skipping definition boost - symbol columns not available")
        return results

    boosted_results = []
    for result in results:
        is_definition = result.symbol_type is not None

        if is_definition:
            boosted_results.append(
                HybridSearchResult(
                    filename=result.filename,
                    start_byte=result.start_byte,
                    end_byte=result.end_byte,
                    combined_score=result.combined_score * boost_multiplier,
                    match_type=result.match_type,
                    vector_score=result.vector_score,
                    keyword_score=result.keyword_score,
                    block_type=result.block_type,
                    hierarchy=result.hierarchy,
                    language_id=result.language_id,
                    symbol_type=result.symbol_type,
                    symbol_name=result.symbol_name,
                    symbol_signature=result.symbol_signature,
                )
            )
        else:
            boosted_results.append(result)

    # Re-sort by boosted scores (descending)
    # Maintain keyword tiebreaker from rrf_fusion
    boosted_results.sort(
        key=lambda r: (r.combined_score, 1 if r.keyword_score is not None else 0),
        reverse=True,
    )

    return boosted_results


def hybrid_search(
    query: str,
    index_name: str,
    limit: int = 10,
    symbol_type: str | list[str] | None = None,
    symbol_name: str | None = None,
    language_filter: str | None = None,
) -> list[HybridSearchResult]:
    """Execute hybrid search combining vector and keyword matching.

    Performs both vector similarity search and keyword search (if available),
    then fuses results using RRF algorithm. Supports symbol and language filtering
    applied BEFORE RRF fusion for accurate filtering.

    Args:
        query: Search query (natural language or code identifier).
        index_name: Name of the index to search.
        limit: Maximum results to return.
        symbol_type: Filter by symbol type ("function", "class", "method", "interface").
            Can be a single string or list of types.
        symbol_name: Filter by symbol name using glob pattern (supports * and ?).
        language_filter: Filter by language via filename extension pattern.
            Format: comma-separated language names (e.g., "python,javascript").

    Returns:
        List of HybridSearchResult ordered by combined score (highest first).
        Falls back to vector-only results if keyword search unavailable.
    """
    table_name = get_table_name(index_name)

    # Build WHERE clause for symbol filters (applied before fusion)
    where_parts = []
    where_params: list = []

    # Add symbol filter conditions
    if symbol_type is not None or symbol_name is not None:
        symbol_where, symbol_params = build_symbol_where_clause(
            symbol_type, symbol_name
        )
        if symbol_where:
            where_parts.append(symbol_where)
            where_params.extend(symbol_params)

    # Add language filter conditions (handler language_id + filename-based)
    if language_filter:
        from cocosearch.search.query import (
            LANGUAGE_EXTENSIONS,
            HANDLER_LANGUAGES,
            get_extension_patterns,
        )

        languages = [lang.strip() for lang in language_filter.split(",")]
        lang_conditions = []
        for lang in languages:
            if lang in HANDLER_LANGUAGES:
                lang_conditions.append("language_id = %s")
                where_params.append(HANDLER_LANGUAGES[lang])
            elif lang in LANGUAGE_EXTENSIONS:
                extensions = get_extension_patterns(lang)
                ext_parts = ["filename LIKE %s" for _ in extensions]
                lang_conditions.append(f"({' OR '.join(ext_parts)})")
                where_params.extend(extensions)
        if lang_conditions:
            where_parts.append(f"({' OR '.join(lang_conditions)})")

    # Combine WHERE parts
    where_clause = " AND ".join(where_parts) if where_parts else ""

    # Execute both searches
    # Request more results from each to have better fusion
    vector_limit = min(limit * 2, MAX_PREFETCH)
    keyword_limit = min(limit * 2, MAX_PREFETCH)

    vector_results = execute_vector_search(
        query,
        table_name,
        vector_limit,
        where_clause,
        where_params if where_params else None,
    )
    keyword_results = execute_keyword_search(
        query,
        table_name,
        keyword_limit,
        where_clause,
        where_params if where_params else None,
    )

    # If no keyword results, return vector-only with match_type="semantic"
    if not keyword_results:
        vector_only_results = [
            HybridSearchResult(
                filename=r.filename,
                start_byte=r.start_byte,
                end_byte=r.end_byte,
                combined_score=r.score,  # Use vector score directly
                match_type="semantic",
                vector_score=r.score,
                keyword_score=None,
                block_type=r.block_type,
                hierarchy=r.hierarchy,
                language_id=r.language_id,
                symbol_type=r.symbol_type,
                symbol_name=r.symbol_name,
                symbol_signature=r.symbol_signature,
            )
            for r in vector_results[:limit]
        ]
        # Apply definition boost even in vector-only mode
        return apply_definition_boost(vector_only_results, index_name)[:limit]

    # Fuse results using RRF
    fused = rrf_fusion(vector_results, keyword_results)

    # Apply definition boost (after RRF, before limit)
    boosted = apply_definition_boost(fused, index_name)

    return boosted[:limit]
