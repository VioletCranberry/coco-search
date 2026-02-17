"""Pipeline analysis module for cocosearch.

Runs the same search pipeline as search() but captures and displays
diagnostic data at each stage: query analysis, mode selection, cache
check, vector search, keyword search, RRF fusion, definition boost,
filtering, and timing breakdown.
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field

from cocosearch.search.cache import _compute_cache_key, get_query_cache
from cocosearch.search.db import (
    check_column_exists,
    check_symbol_columns_exist,
    get_table_name,
)
from cocosearch.search.filters import build_symbol_where_clause
from cocosearch.search.hybrid import (
    DEFINITION_BOOST_MULTIPLIER,
    MAX_PREFETCH,
    RRF_K,
    HybridSearchResult,
    KeywordResult,
    VectorResult,
    apply_definition_boost,
    execute_keyword_search,
    execute_vector_search,
    rrf_fusion,
)
from cocosearch.search.query import (
    LANGUAGE_EXTENSIONS,
    SearchResult,
    _get_language_id_map,
    get_extension_patterns,
    validate_language_filter,
)
from cocosearch.search.query_analyzer import (
    has_identifier_pattern,
    normalize_query_for_keyword,
)
from cocosearch.validation import validate_query

logger = logging.getLogger(__name__)


@dataclass
class QueryAnalysisInfo:
    """Diagnostics from query analysis stage."""

    original_query: str
    has_identifier: bool
    normalized_keyword_query: str


@dataclass
class SearchModeInfo:
    """Diagnostics from search mode selection."""

    mode: str  # "hybrid" or "vector-only"
    reason: str
    use_hybrid_flag: bool | None
    has_content_text_column: bool
    has_identifier_pattern: bool


@dataclass
class CacheInfo:
    """Diagnostics from cache lookup."""

    checked: bool
    hit: bool
    hit_type: str  # "exact", "semantic", "miss"
    cache_key_prefix: str


@dataclass
class VectorSearchInfo:
    """Diagnostics from vector search stage."""

    result_count: int
    top_score: float | None
    bottom_score: float | None
    results: list[VectorResult]


@dataclass
class KeywordSearchInfo:
    """Diagnostics from keyword search stage."""

    executed: bool
    normalized_query: str
    result_count: int
    top_ts_rank: float | None
    results: list[KeywordResult]


@dataclass
class FusionInfo:
    """Diagnostics from RRF fusion stage."""

    executed: bool
    k_constant: int
    vector_only_count: int
    keyword_only_count: int
    both_count: int
    total_fused: int
    results: list[HybridSearchResult] = field(default_factory=list)


@dataclass
class DefinitionBoostInfo:
    """Diagnostics from definition boost stage."""

    executed: bool
    boost_multiplier: float
    boosted_count: int
    rank_changes: int


@dataclass
class FilterInfo:
    """Diagnostics from result filtering."""

    language_filter: str | None
    symbol_type_filter: str | list[str] | None
    symbol_name_filter: str | None
    min_score: float
    pre_filter_count: int
    post_filter_count: int


@dataclass
class StageTimings:
    """Timing breakdown for each pipeline stage in milliseconds."""

    query_analysis_ms: float
    cache_check_ms: float
    embedding_ms: float
    vector_search_ms: float
    keyword_search_ms: float
    rrf_fusion_ms: float
    definition_boost_ms: float
    total_ms: float


@dataclass
class AnalysisResult:
    """Complete pipeline analysis result."""

    query_analysis: QueryAnalysisInfo
    search_mode: SearchModeInfo
    cache: CacheInfo
    vector_search: VectorSearchInfo
    keyword_search: KeywordSearchInfo
    fusion: FusionInfo
    definition_boost: DefinitionBoostInfo
    filtering: FilterInfo
    timings: StageTimings
    results: list[SearchResult]

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        # VectorResult/KeywordResult/HybridSearchResult/SearchResult are
        # all plain dataclasses — asdict handles them recursively.
        return d


def analyze(
    query: str,
    index_name: str,
    limit: int = 10,
    min_score: float = 0.0,
    language_filter: str | None = None,
    use_hybrid: bool | None = None,
    symbol_type: str | list[str] | None = None,
    symbol_name: str | None = None,
    no_cache: bool = False,
) -> AnalysisResult:
    """Analyze the search pipeline for a query.

    Runs the same pipeline as search() but captures diagnostics at each
    stage. The signature mirrors search() exactly.

    Args:
        query: Natural language search query.
        index_name: Name of the index to search.
        limit: Maximum results to return (default 10).
        min_score: Minimum similarity score to include (0-1, default 0.0).
        language_filter: Optional language filter (e.g., "python", "hcl,bash").
        use_hybrid: Hybrid search mode (None=auto, True=force, False=vector-only).
        symbol_type: Filter by symbol type.
        symbol_name: Filter by symbol name using glob pattern.
        no_cache: If True, bypass query cache (default False).

    Returns:
        AnalysisResult with full pipeline diagnostics and search results.
    """
    total_start = time.perf_counter()

    # --- Stage 1: Query analysis ---
    t0 = time.perf_counter()
    query = validate_query(query)
    has_ident = has_identifier_pattern(query)
    normalized_kw = normalize_query_for_keyword(query)
    query_analysis_ms = (time.perf_counter() - t0) * 1000

    query_info = QueryAnalysisInfo(
        original_query=query,
        has_identifier=has_ident,
        normalized_keyword_query=normalized_kw,
    )

    # --- Stage 2: Cache check ---
    t0 = time.perf_counter()
    cache_hit = False
    cache_hit_type = "miss"
    cache_key = _compute_cache_key(
        query,
        index_name,
        limit,
        min_score,
        language_filter,
        use_hybrid,
        symbol_type,
        symbol_name,
    )
    cache_key_prefix = cache_key[:16]

    if not no_cache:
        cache = get_query_cache()
        cached_results, cache_hit_type = cache.get(
            query=query,
            index_name=index_name,
            limit=limit,
            min_score=min_score,
            language_filter=language_filter,
            use_hybrid=use_hybrid,
            symbol_type=symbol_type,
            symbol_name=symbol_name,
            query_embedding=None,
        )
        cache_hit = cached_results is not None
    cache_check_ms = (time.perf_counter() - t0) * 1000

    cache_info = CacheInfo(
        checked=not no_cache,
        hit=cache_hit,
        hit_type=cache_hit_type,
        cache_key_prefix=cache_key_prefix,
    )

    # --- Stage 3: Search mode decision ---
    table_name = get_table_name(index_name)
    has_content_text = check_column_exists(table_name, "content_text")

    should_use_hybrid = False
    mode_reason = ""
    if use_hybrid is True:
        if has_content_text:
            should_use_hybrid = True
            mode_reason = "Explicitly enabled via use_hybrid=True"
        else:
            mode_reason = "Hybrid requested but content_text column missing, falling back to vector-only"
    elif use_hybrid is None:
        if has_content_text and has_ident:
            should_use_hybrid = True
            mode_reason = "Auto-detected identifier pattern in query"
        elif has_content_text:
            mode_reason = "No identifier pattern detected, using vector-only"
        else:
            mode_reason = "content_text column missing, using vector-only"
    else:
        mode_reason = "Explicitly disabled via use_hybrid=False"

    search_mode_info = SearchModeInfo(
        mode="hybrid" if should_use_hybrid else "vector-only",
        reason=mode_reason,
        use_hybrid_flag=use_hybrid,
        has_content_text_column=has_content_text,
        has_identifier_pattern=has_ident,
    )

    # --- Build WHERE clause (shared by vector and keyword) ---
    validated_languages = None
    if language_filter:
        validated_languages = validate_language_filter(language_filter)

    if symbol_type is not None or symbol_name is not None:
        if not check_symbol_columns_exist(table_name):
            raise ValueError(
                f"Symbol filtering requires v1.7+ index. Index '{index_name}' lacks symbol columns. "
                "Re-index with 'cocosearch index' to enable symbol filtering."
            )

    where_parts: list[str] = []
    where_params: list = []

    if symbol_type is not None or symbol_name is not None:
        sym_where, sym_params = build_symbol_where_clause(symbol_type, symbol_name)
        if sym_where:
            where_parts.append(sym_where)
            where_params.extend(sym_params)

    if language_filter and validated_languages:
        lang_id_map = _get_language_id_map()
        lang_conditions: list[str] = []
        for lang in validated_languages:
            if lang in lang_id_map:
                lang_conditions.append("language_id = %s")
                where_params.append(lang_id_map[lang])
            elif lang in LANGUAGE_EXTENSIONS:
                extensions = get_extension_patterns(lang)
                ext_parts = ["filename LIKE %s" for _ in extensions]
                lang_conditions.append(f"({' OR '.join(ext_parts)})")
                where_params.extend(extensions)
        if lang_conditions:
            where_parts.append(f"({' OR '.join(lang_conditions)})")

    where_clause = " AND ".join(where_parts) if where_parts else ""

    # --- Stage 4: Embedding ---
    t0 = time.perf_counter()
    # Embedding is always needed for vector search (even in hybrid mode,
    # execute_vector_search calls code_to_embedding internally).
    # We time it here but the actual embedding happens inside execute_vector_search.
    embedding_ms = 0.0  # Will be measured around vector search

    # --- Stage 5: Vector search ---
    vector_limit = min(limit * 2, MAX_PREFETCH) if should_use_hybrid else limit
    t0 = time.perf_counter()
    if should_use_hybrid:
        vector_results = execute_vector_search(
            query,
            table_name,
            vector_limit,
            where_clause,
            where_params if where_params else None,
        )
    else:
        vector_results = execute_vector_search(
            query,
            table_name,
            vector_limit,
            where_clause,
            where_params if where_params else None,
        )
    vector_search_ms = (time.perf_counter() - t0) * 1000
    # embedding_ms is included in vector_search_ms since execute_vector_search
    # does its own embedding internally
    embedding_ms = 0.0  # Cannot separate — included in vector_search_ms

    vector_info = VectorSearchInfo(
        result_count=len(vector_results),
        top_score=vector_results[0].score if vector_results else None,
        bottom_score=vector_results[-1].score if vector_results else None,
        results=vector_results,
    )

    # --- Stage 6: Keyword search ---
    t0 = time.perf_counter()
    keyword_results: list[KeywordResult] = []
    keyword_executed = False
    if should_use_hybrid:
        keyword_executed = True
        keyword_limit = min(limit * 2, MAX_PREFETCH)
        keyword_results = execute_keyword_search(
            query,
            table_name,
            keyword_limit,
            where_clause,
            where_params if where_params else None,
        )
    keyword_search_ms = (time.perf_counter() - t0) * 1000

    keyword_info = KeywordSearchInfo(
        executed=keyword_executed,
        normalized_query=normalized_kw,
        result_count=len(keyword_results),
        top_ts_rank=keyword_results[0].ts_rank if keyword_results else None,
        results=keyword_results,
    )

    # --- Stage 7: RRF fusion ---
    t0 = time.perf_counter()
    fused_results: list[HybridSearchResult] = []
    fusion_executed = False
    vector_only_count = 0
    keyword_only_count = 0
    both_count = 0

    if should_use_hybrid and keyword_results:
        fusion_executed = True
        fused_results = rrf_fusion(vector_results, keyword_results)
        for r in fused_results:
            if r.match_type == "both":
                both_count += 1
            elif r.match_type == "semantic":
                vector_only_count += 1
            elif r.match_type == "keyword":
                keyword_only_count += 1
    elif should_use_hybrid:
        # Hybrid mode but no keyword results — vector-only fallback
        fused_results = [
            HybridSearchResult(
                filename=r.filename,
                start_byte=r.start_byte,
                end_byte=r.end_byte,
                combined_score=r.score,
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
        vector_only_count = len(fused_results)
    rrf_fusion_ms = (time.perf_counter() - t0) * 1000

    fusion_info = FusionInfo(
        executed=fusion_executed,
        k_constant=RRF_K,
        vector_only_count=vector_only_count,
        keyword_only_count=keyword_only_count,
        both_count=both_count,
        total_fused=len(fused_results),
        results=fused_results,
    )

    # --- Stage 8: Definition boost ---
    t0 = time.perf_counter()
    boost_executed = False
    boosted_count = 0
    rank_changes = 0

    if should_use_hybrid and fused_results:
        pre_boost_order = [
            (r.filename, r.start_byte, r.end_byte) for r in fused_results
        ]
        boosted_results = apply_definition_boost(fused_results, index_name)
        post_boost_order = [
            (r.filename, r.start_byte, r.end_byte) for r in boosted_results
        ]
        boost_executed = True

        # Count boosted and rank changes
        for r_before, r_after in zip(fused_results, boosted_results):
            if (
                r_after.symbol_type is not None
                and r_after.combined_score != r_before.combined_score
            ):
                boosted_count += 1

        for i, key in enumerate(pre_boost_order):
            if i < len(post_boost_order) and key != post_boost_order[i]:
                rank_changes += 1
        # Each rank change involves a pair, so don't double count
        rank_changes = rank_changes // 2 if rank_changes > 1 else rank_changes

        fused_results = boosted_results
    definition_boost_ms = (time.perf_counter() - t0) * 1000

    definition_boost_info = DefinitionBoostInfo(
        executed=boost_executed,
        boost_multiplier=DEFINITION_BOOST_MULTIPLIER,
        boosted_count=boosted_count,
        rank_changes=rank_changes,
    )

    # --- Stage 9: Convert to SearchResult and apply min_score filter ---
    if should_use_hybrid:
        pre_filter = fused_results[:limit]
        all_results = [
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
            for hr in pre_filter
        ]
    else:
        # Vector-only: convert directly
        all_results = [
            SearchResult(
                filename=r.filename,
                start_byte=r.start_byte,
                end_byte=r.end_byte,
                score=r.score,
                block_type=r.block_type,
                hierarchy=r.hierarchy,
                language_id=r.language_id,
                symbol_type=r.symbol_type,
                symbol_name=r.symbol_name,
                symbol_signature=r.symbol_signature,
            )
            for r in vector_results[:limit]
        ]

    pre_filter_count = len(all_results)
    final_results = [r for r in all_results if r.score >= min_score]
    post_filter_count = len(final_results)

    filter_info = FilterInfo(
        language_filter=language_filter,
        symbol_type_filter=symbol_type,
        symbol_name_filter=symbol_name,
        min_score=min_score,
        pre_filter_count=pre_filter_count,
        post_filter_count=post_filter_count,
    )

    total_ms = (time.perf_counter() - total_start) * 1000

    timings = StageTimings(
        query_analysis_ms=query_analysis_ms,
        cache_check_ms=cache_check_ms,
        embedding_ms=embedding_ms,
        vector_search_ms=vector_search_ms,
        keyword_search_ms=keyword_search_ms,
        rrf_fusion_ms=rrf_fusion_ms,
        definition_boost_ms=definition_boost_ms,
        total_ms=total_ms,
    )

    return AnalysisResult(
        query_analysis=query_info,
        search_mode=search_mode_info,
        cache=cache_info,
        vector_search=vector_info,
        keyword_search=keyword_info,
        fusion=fusion_info,
        definition_boost=definition_boost_info,
        filtering=filter_info,
        timings=timings,
        results=final_results,
    )


def format_analysis_pretty(analysis: AnalysisResult, index_name: str) -> None:
    """Print pipeline analysis using Rich panels and tables.

    Args:
        analysis: AnalysisResult from analyze().
        index_name: Index name for display.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    # Header
    console.print(
        f'\n[bold]Pipeline Analysis:[/bold] "{analysis.query_analysis.original_query}"'
    )
    console.print(f"[dim]Index: {index_name}[/dim]\n")

    # --- Query Analysis panel ---
    qa = analysis.query_analysis
    sm = analysis.search_mode
    qa_lines = []
    qa_lines.append(
        f"Has identifier:  [{'green' if qa.has_identifier else 'dim'}]"
        f"{'Yes' if qa.has_identifier else 'No'}[/{'green' if qa.has_identifier else 'dim'}]"
    )
    qa_lines.append(f"Normalized:      {qa.normalized_keyword_query}")
    mode_color = "cyan" if sm.mode == "hybrid" else "dim"
    qa_lines.append(f"Search mode:     [{mode_color}]{sm.mode}[/{mode_color}]")
    qa_lines.append(f"Reason:          [dim]{sm.reason}[/dim]")
    console.print(
        Panel("\n".join(qa_lines), title="Query Analysis", border_style="blue")
    )

    # --- Cache panel ---
    ci = analysis.cache
    if not ci.checked:
        cache_status = "[dim]SKIPPED (--no-cache)[/dim]"
    elif ci.hit:
        cache_status = f"[green]HIT ({ci.hit_type})[/green]"
    else:
        cache_status = "[yellow]MISS[/yellow]"
    cache_line = f"Status: {cache_status}  Key: {ci.cache_key_prefix}..."
    console.print(Panel(cache_line, title="Cache", border_style="blue"))

    # --- Vector Search panel ---
    vi = analysis.vector_search
    vec_table = Table(show_header=True, header_style="bold", expand=True)
    vec_table.add_column("#", width=3, justify="right")
    vec_table.add_column("Score", width=7, justify="right")
    vec_table.add_column("File", ratio=3)
    vec_table.add_column("Symbol", ratio=2)

    for i, r in enumerate(vi.results[:10], 1):
        score_color = "green" if r.score > 0.7 else "yellow" if r.score > 0.5 else "red"
        symbol_display = r.symbol_type or r.block_type or ""
        if r.symbol_name:
            symbol_display = (
                f"{symbol_display} {r.symbol_name}" if symbol_display else r.symbol_name
            )
        vec_table.add_row(
            str(i),
            f"[{score_color}]{r.score:.3f}[/{score_color}]",
            _truncate(r.filename, 40),
            symbol_display,
        )

    title = f"Vector Search ({vi.result_count} results)"
    if vi.top_score is not None:
        title += f" | top={vi.top_score:.3f}"
    console.print(Panel(vec_table, title=title, border_style="blue"))

    # --- Keyword Search panel ---
    ki = analysis.keyword_search
    if ki.executed:
        kw_table = Table(show_header=True, header_style="bold", expand=True)
        kw_table.add_column("#", width=3, justify="right")
        kw_table.add_column("ts_rank", width=8, justify="right")
        kw_table.add_column("File", ratio=3)

        for i, r in enumerate(ki.results[:10], 1):
            kw_table.add_row(
                str(i),
                f"{r.ts_rank:.4f}",
                _truncate(r.filename, 50),
            )

        kw_title = f"Keyword Search ({ki.result_count} results)"
        console.print(Panel(kw_table, title=kw_title, border_style="blue"))
    else:
        console.print(
            Panel(
                "[dim]Not executed (vector-only mode)[/dim]",
                title="Keyword Search",
                border_style="dim",
            )
        )

    # --- RRF Fusion panel ---
    fi = analysis.fusion
    if fi.executed:
        fusion_summary = (
            f"Both: {fi.both_count} | Semantic-only: {fi.vector_only_count} | "
            f"Keyword-only: {fi.keyword_only_count}"
        )

        fusion_table = Table(show_header=True, header_style="bold", expand=True)
        fusion_table.add_column("#", width=3, justify="right")
        fusion_table.add_column("RRF", width=8, justify="right")
        fusion_table.add_column("Match", width=9)
        fusion_table.add_column("Vec", width=7, justify="right")
        fusion_table.add_column("KW", width=7, justify="right")
        fusion_table.add_column("File", ratio=3)

        for i, r in enumerate(fi.results[:10], 1):
            match_color = {
                "both": "yellow",
                "semantic": "cyan",
                "keyword": "green",
            }.get(r.match_type, "dim")
            vec_str = f"{r.vector_score:.3f}" if r.vector_score is not None else "-"
            kw_str = f"{r.keyword_score:.4f}" if r.keyword_score is not None else "-"
            fusion_table.add_row(
                str(i),
                f"{r.combined_score:.4f}",
                f"[{match_color}]{r.match_type}[/{match_color}]",
                vec_str,
                kw_str,
                _truncate(r.filename, 40),
            )

        console.print(
            Panel(
                f"{fusion_summary}\n\n" + _render_table_to_str(fusion_table, console),
                title=f"RRF Fusion (k={fi.k_constant})",
                border_style="blue",
            )
        )
    else:
        console.print(
            Panel(
                "[dim]Not executed (vector-only mode)[/dim]",
                title="RRF Fusion",
                border_style="dim",
            )
        )

    # --- Definition Boost panel ---
    db = analysis.definition_boost
    if db.executed:
        boost_line = (
            f"Boosted: {db.boosted_count} results (x{db.boost_multiplier}) | "
            f"Rank changes: {db.rank_changes}"
        )
        console.print(Panel(boost_line, title="Definition Boost", border_style="blue"))
    else:
        console.print(
            Panel(
                "[dim]Not executed[/dim]", title="Definition Boost", border_style="dim"
            )
        )

    # --- Timings panel ---
    t = analysis.timings
    timing_entries = [
        ("Vector search", t.vector_search_ms),
        ("Keyword search", t.keyword_search_ms),
        ("RRF fusion", t.rrf_fusion_ms),
        ("Def. boost", t.definition_boost_ms),
        ("Query analysis", t.query_analysis_ms),
        ("Cache check", t.cache_check_ms),
    ]

    max_time = max((v for _, v in timing_entries), default=1.0)
    if max_time == 0:
        max_time = 1.0

    timing_lines = []
    for label, ms in timing_entries:
        bar_len = int((ms / max_time) * 20) if max_time > 0 else 0
        bar = "\u2588" * bar_len
        timing_lines.append(f"{label:>16s}: {ms:7.1f}ms {bar}")

    timing_lines.append(f"{'Total':>16s}: {t.total_ms:7.1f}ms")
    console.print(Panel("\n".join(timing_lines), title="Timings", border_style="blue"))

    # --- Results ---
    console.print(f"\n[bold]Results ({len(analysis.results)} matches)[/bold]")
    if analysis.results:
        from cocosearch.search.formatter import format_pretty

        format_pretty(analysis.results, smart_context=True, console=console)
    else:
        console.print("[dim]No results found.[/dim]")


def format_analysis_json(analysis: AnalysisResult) -> str:
    """Format analysis result as JSON string.

    Args:
        analysis: AnalysisResult from analyze().

    Returns:
        JSON string of the analysis.
    """
    return json.dumps(analysis.to_dict(), indent=2)


def _truncate(s: str, max_len: int) -> str:
    """Truncate string with ellipsis if too long."""
    if len(s) <= max_len:
        return s
    return s[-(max_len - 3) :].lstrip("/")


def _render_table_to_str(table, console) -> str:
    """Render a Rich Table to a string for embedding in panels."""
    from io import StringIO

    from rich.console import Console as RichConsole

    buf = StringIO()
    temp_console = RichConsole(file=buf, width=console.width - 4)
    temp_console.print(table)
    return buf.getvalue()
