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
from cocosearch.search.db import check_column_exists, get_connection_pool, get_table_name
from cocosearch.search.query_analyzer import normalize_query_for_keyword

logger = logging.getLogger(__name__)


def _is_definition_chunk(content: str) -> bool:
    """Check if chunk content starts with a definition keyword.

    Heuristic: definition chunks start with keywords like:
    - def, class, async def (Python)
    - function, const, let, var (JavaScript/TypeScript)
    - func, type (Go)
    - fn, struct, trait, enum, impl (Rust)

    Args:
        content: Chunk text content.

    Returns:
        True if chunk appears to be a definition.
    """
    stripped = content.lstrip()
    definition_keywords = [
        # Python
        "def ",
        "class ",
        "async def ",
        # JavaScript/TypeScript
        "function ",
        "const ",
        "let ",
        "var ",
        "interface ",
        "type ",
        # Go
        "func ",
        # Rust
        "fn ",
        "struct ",
        "trait ",
        "enum ",
        "impl ",
    ]
    return any(stripped.startswith(kw) for kw in definition_keywords)


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
        block_type: DevOps block type (from vector result if available).
        hierarchy: DevOps hierarchy path (from vector result if available).
        language_id: DevOps language identifier (from vector result if available).
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


def _make_result_key(filename: str, start_byte: int, end_byte: int) -> str:
    """Create a unique key for a search result based on its location."""
    return f"{filename}:{start_byte}:{end_byte}"


def execute_keyword_search(
    query: str,
    table_name: str,
    limit: int = 10,
) -> list[KeywordResult]:
    """Execute keyword search using PostgreSQL full-text search.

    Builds a tsquery from the normalized query and searches against
    the content_tsv column using the GIN index.

    Args:
        query: Search query (will be normalized to split identifiers).
        table_name: PostgreSQL table name.
        limit: Maximum results to return.

    Returns:
        List of KeywordResult ordered by ts_rank (highest first).
        Empty list if content_tsv column doesn't exist or no matches.
    """
    pool = get_connection_pool()

    # Check if hybrid search column exists
    if not check_column_exists(table_name, "content_tsv"):
        logger.debug(f"Table {table_name} lacks content_tsv column, skipping keyword search")
        return []

    # Normalize query to split identifiers
    normalized = normalize_query_for_keyword(query)

    # Build tsquery using plainto_tsquery (handles spaces, simple matching)
    # Using 'simple' config for consistency with indexing (no stemming)
    sql = """
        SELECT
            filename,
            lower(location) as start_byte,
            upper(location) as end_byte,
            ts_rank(content_tsv, plainto_tsquery('simple', %s)) as rank
        FROM {table}
        WHERE content_tsv @@ plainto_tsquery('simple', %s)
        ORDER BY rank DESC
        LIMIT %s
    """.format(table=table_name)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(sql, (normalized, normalized, limit))
                rows = cur.fetchall()
            except Exception as e:
                # Log and return empty on any error (graceful degradation)
                logger.warning(f"Keyword search failed: {e}")
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
) -> list[VectorResult]:
    """Execute vector similarity search.

    Embeds the query and performs cosine similarity search against
    the embedding column.

    Args:
        query: Search query (will be embedded).
        table_name: PostgreSQL table name.
        limit: Maximum results to return.

    Returns:
        List of VectorResult ordered by similarity (highest first).
    """
    pool = get_connection_pool()

    # Embed query
    query_embedding = code_to_embedding.eval(query)

    # Query with metadata columns
    sql = """
        SELECT
            filename,
            lower(location) as start_byte,
            upper(location) as end_byte,
            1 - (embedding <=> %s::vector) AS score,
            block_type,
            hierarchy,
            language_id
        FROM {table}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """.format(table=table_name)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(sql, (query_embedding, query_embedding, limit))
                rows = cur.fetchall()
            except Exception as e:
                # Graceful degradation for pre-v1.2 indexes without metadata
                logger.debug(f"Falling back to query without metadata: {e}")
                sql_fallback = """
                    SELECT
                        filename,
                        lower(location) as start_byte,
                        upper(location) as end_byte,
                        1 - (embedding <=> %s::vector) AS score
                    FROM {table}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """.format(table=table_name)
                cur.execute(sql_fallback, (query_embedding, query_embedding, limit))
                rows = cur.fetchall()
                # Return results without metadata
                return [
                    VectorResult(
                        filename=row[0],
                        start_byte=int(row[1]),
                        end_byte=int(row[2]),
                        score=float(row[3]),
                    )
                    for row in rows
                ]

    return [
        VectorResult(
            filename=row[0],
            start_byte=int(row[1]),
            end_byte=int(row[2]),
            score=float(row[3]),
            block_type=row[4] if row[4] else "",
            hierarchy=row[5] if row[5] else "",
            language_id=row[6] if row[6] else "",
        )
        for row in rows
    ]


def rrf_fusion(
    vector_results: list[VectorResult],
    keyword_results: list[KeywordResult],
    k: int = 60,
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

        # Get filename and byte positions from either source
        if key in vector_by_key:
            v_rank, v_result = vector_by_key[key]
            rrf_score += 1 / (k + v_rank)
            vector_score = v_result.score
            block_type = v_result.block_type
            hierarchy = v_result.hierarchy
            language_id = v_result.language_id
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
            )
        )

    # Sort by combined RRF score descending
    # On tie, favor keyword matches per CONTEXT.md decision
    fused_results.sort(
        key=lambda r: (r.combined_score, 1 if r.keyword_score is not None else 0),
        reverse=True,
    )

    return fused_results


def hybrid_search(
    query: str,
    index_name: str,
    limit: int = 10,
) -> list[HybridSearchResult]:
    """Execute hybrid search combining vector and keyword matching.

    Performs both vector similarity search and keyword search (if available),
    then fuses results using RRF algorithm.

    Args:
        query: Search query (natural language or code identifier).
        index_name: Name of the index to search.
        limit: Maximum results to return.

    Returns:
        List of HybridSearchResult ordered by combined score (highest first).
        Falls back to vector-only results if keyword search unavailable.
    """
    table_name = get_table_name(index_name)

    # Execute both searches
    # Request more results from each to have better fusion
    vector_limit = min(limit * 2, 100)
    keyword_limit = min(limit * 2, 100)

    vector_results = execute_vector_search(query, table_name, vector_limit)
    keyword_results = execute_keyword_search(query, table_name, keyword_limit)

    # If no keyword results, return vector-only with match_type="semantic"
    if not keyword_results:
        return [
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
            )
            for r in vector_results[:limit]
        ]

    # Fuse results using RRF
    fused = rrf_fusion(vector_results, keyword_results)

    return fused[:limit]
