"""Index statistics module for cocosearch.

Provides functions to retrieve storage and content statistics
for indexed codebases.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime

from cocosearch.management.metadata import (
    auto_recover_stale_indexing,
    get_index_metadata,
)
from cocosearch.search.db import get_connection_pool, get_table_name


def format_bytes(size: int) -> str:
    """Format bytes as human-readable string.

    Args:
        size: Size in bytes.

    Returns:
        Human-readable string (e.g., "1.5 MB", "256 KB").
    """
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"


def get_stats(index_name: str) -> dict:
    """Get statistics for an index.

    Args:
        index_name: The name of the index.

    Returns:
        Dict with keys:
        - name: Index name
        - file_count: Number of unique files indexed
        - chunk_count: Total number of chunks
        - storage_size: Storage size in bytes
        - storage_size_pretty: Human-readable storage size

    Raises:
        ValueError: If the index does not exist.
    """
    pool = get_connection_pool()
    table_name = get_table_name(index_name)

    # First verify the table exists
    check_query = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        )
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(check_query, (table_name,))
            (exists,) = cur.fetchone()

            if not exists:
                raise ValueError(f"Index '{index_name}' not found")

            # Get file count and chunk count
            stats_query = f"""
                SELECT
                    COUNT(DISTINCT filename) as file_count,
                    COUNT(*) as chunk_count
                FROM {table_name}
            """
            cur.execute(stats_query)
            file_count, chunk_count = cur.fetchone()

            # Get storage size
            size_query = "SELECT pg_table_size(%s)"
            cur.execute(size_query, (table_name,))
            (storage_size,) = cur.fetchone()

    return {
        "name": index_name,
        "file_count": file_count,
        "chunk_count": chunk_count,
        "storage_size": storage_size,
        "storage_size_pretty": format_bytes(storage_size),
    }


def get_language_stats(index_name: str) -> list[dict]:
    """Get per-language statistics for an index.

    Uses SQL GROUP BY for efficient aggregation at database level.
    Line counting requires content_text column added in v1.7.

    Args:
        index_name: The name of the index.

    Returns:
        List of dicts with keys:
        - language: Language identifier (e.g., "python", "hcl")
        - file_count: Number of unique files for this language
        - chunk_count: Number of chunks for this language
        - line_count: Number of lines (None if index lacks content_text column)

        List is sorted by chunk_count descending.

    Raises:
        ValueError: If the index does not exist.
    """
    pool = get_connection_pool()
    table_name = get_table_name(index_name)

    # First verify the table exists
    check_query = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        )
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(check_query, (table_name,))
            (exists,) = cur.fetchone()

            if not exists:
                raise ValueError(f"Index '{index_name}' not found")

            # Check if content_text column exists (v1.7+)
            col_check = """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'content_text'
            """
            cur.execute(col_check, (table_name,))
            has_content_text = cur.fetchone() is not None

            # Build query with conditional line count
            if has_content_text:
                stats_query = f"""
                    SELECT
                        COALESCE(language_id, 'unknown') as language,
                        COUNT(DISTINCT filename) as file_count,
                        COUNT(*) as chunk_count,
                        SUM(array_length(string_to_array(content_text, E'\\n'), 1)) as line_count
                    FROM {table_name}
                    GROUP BY language_id
                    ORDER BY chunk_count DESC
                """
            else:
                # Pre-v1.7 indexes lack content_text column for line counting
                stats_query = f"""
                    SELECT
                        COALESCE(language_id, 'unknown') as language,
                        COUNT(DISTINCT filename) as file_count,
                        COUNT(*) as chunk_count,
                        NULL as line_count
                    FROM {table_name}
                    GROUP BY language_id
                    ORDER BY chunk_count DESC
                """

            cur.execute(stats_query)
            rows = cur.fetchall()

            return [
                {
                    "language": row[0] if row[0] else "unknown",
                    "file_count": row[1],
                    "chunk_count": row[2],
                    "line_count": row[3],
                }
                for row in rows
            ]


@dataclass
class IndexStats:
    """Comprehensive statistics for an index.

    Attributes:
        name: Index name
        file_count: Number of unique files indexed
        chunk_count: Total number of chunks
        storage_size: Storage size in bytes
        storage_size_pretty: Human-readable storage size
        created_at: Index creation timestamp (None if no metadata)
        updated_at: Index last update timestamp (None if no metadata)
        is_stale: True if index hasn't been updated in threshold_days
        staleness_days: Days since last update (-1 if no metadata)
        languages: Per-language statistics (from get_language_stats)
        symbols: Symbol type counts (e.g., {"function": 150, "class": 25})
        warnings: List of warning messages (staleness, zero-chunk files, etc.)
    """

    name: str
    file_count: int
    chunk_count: int
    storage_size: int
    storage_size_pretty: str
    created_at: datetime | None
    updated_at: datetime | None
    is_stale: bool
    staleness_days: int
    languages: list[dict]
    symbols: dict[str, int]
    warnings: list[str]
    parse_stats: (
        dict  # Parse failure breakdown per language (empty dict for pre-v46 indexes)
    )
    source_path: str | None  # Canonical path where index was created from
    status: str | None  # Index status: 'indexed', 'indexing', etc.
    indexing_elapsed_seconds: (
        float | None
    )  # Seconds since indexing started (only when status='indexing')
    repo_url: str | None  # Browsable HTTPS URL for the git remote origin
    branch: str | None = None  # Git branch at time of indexing
    commit_hash: str | None = None  # Git commit hash at time of indexing
    commits_behind: int | None = None  # How many commits behind HEAD
    branch_commit_count: int | None = None  # Total commits in branch at index time
    grammars: list[dict] = field(default_factory=list)  # Per-grammar stats

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Converts datetime fields to ISO format strings.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        data = asdict(self)
        # Convert datetime to ISO format string for JSON serialization
        if data["created_at"] is not None:
            data["created_at"] = data["created_at"].isoformat()
        if data["updated_at"] is not None:
            data["updated_at"] = data["updated_at"].isoformat()
        return data


def get_grammar_stats(index_name: str) -> list[dict]:
    """Get per-grammar statistics for an index.

    Queries the chunks table for files handled by registered grammar handlers,
    reporting file/chunk counts and metadata extraction quality.

    Args:
        index_name: The name of the index.

    Returns:
        List of dicts with keys: grammar_name, base_language, file_count,
        chunk_count, recognized_chunks, unrecognized_chunks, recognition_pct.
        Empty list if no grammars are registered or no grammar-handled files exist.
    """
    from cocosearch.handlers import get_registered_grammars

    grammars = get_registered_grammars()
    if not grammars:
        return []

    grammar_names = [g.GRAMMAR_NAME for g in grammars]
    grammar_base_map = {g.GRAMMAR_NAME: g.BASE_LANGUAGE for g in grammars}

    pool = get_connection_pool()
    table_name = get_table_name(index_name)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            query = f"""
                SELECT language_id,
                       COUNT(DISTINCT filename) as file_count,
                       COUNT(*) as chunk_count,
                       SUM(CASE WHEN block_type IS NOT NULL AND block_type != '' THEN 1 ELSE 0 END) as recognized,
                       SUM(CASE WHEN block_type IS NULL OR block_type = '' THEN 1 ELSE 0 END) as unrecognized
                FROM {table_name}
                WHERE language_id = ANY(%s)
                GROUP BY language_id
                ORDER BY chunk_count DESC
            """
            cur.execute(query, (grammar_names,))
            rows = cur.fetchall()

    return [
        {
            "grammar_name": row[0],
            "base_language": grammar_base_map.get(row[0], "unknown"),
            "file_count": row[1],
            "chunk_count": row[2],
            "recognized_chunks": row[3],
            "unrecognized_chunks": row[4],
            "recognition_pct": (round(row[3] / row[2] * 100, 1) if row[2] > 0 else 0.0),
        }
        for row in rows
    ]


def get_grammar_failures(index_name: str) -> list[dict]:
    """Get per-file failure details for grammar-handled files with unrecognized chunks.

    Queries the chunks table for files handled by registered grammar handlers
    where at least one chunk has no block_type (unrecognized), grouped by grammar
    and filename.

    Args:
        index_name: The name of the index.

    Returns:
        List of dicts with keys: grammar_name, file_path, total_chunks,
        unrecognized_chunks. Empty list if no grammars registered or no failures.
    """
    from cocosearch.handlers import get_registered_grammars

    grammars = get_registered_grammars()
    if not grammars:
        return []

    grammar_names = [g.GRAMMAR_NAME for g in grammars]

    pool = get_connection_pool()
    table_name = get_table_name(index_name)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            query = f"""
                SELECT language_id,
                       filename,
                       COUNT(*) as total_chunks,
                       SUM(CASE WHEN block_type IS NULL OR block_type = '' THEN 1 ELSE 0 END) as unrecognized
                FROM {table_name}
                WHERE language_id = ANY(%s)
                GROUP BY language_id, filename
                HAVING SUM(CASE WHEN block_type IS NULL OR block_type = '' THEN 1 ELSE 0 END) > 0
                ORDER BY language_id, filename
            """
            cur.execute(query, (grammar_names,))
            rows = cur.fetchall()

    return [
        {
            "grammar_name": row[0],
            "file_path": row[1],
            "total_chunks": row[2],
            "unrecognized_chunks": row[3],
        }
        for row in rows
    ]


def get_parse_stats(index_name: str) -> dict:
    """Get aggregated parse statistics per language for an index.

    Queries the parse_results table (created by phase 46) for per-language
    parse status counts. Gracefully returns empty dict for pre-v46 indexes
    that lack the parse_results table.

    Args:
        index_name: The name of the index.

    Returns:
        Dict with keys:
        - by_language: Per-language breakdown with ok/partial/error/no_grammar counts
        - parse_health_pct: Percentage of files that parsed cleanly
        - total_files: Total files tracked
        - total_ok: Total files with ok status

        Empty dict {} if parse_results table does not exist.
    """
    pool = get_connection_pool()
    table_name = f"cocosearch_parse_results_{index_name}"

    # Check if parse_results table exists (pre-v46 indexes won't have it)
    check_query = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        )
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(check_query, (table_name,))
            (exists,) = cur.fetchone()

            if not exists:
                return {}

            # Aggregate parse status counts per language
            agg_query = f"""
                SELECT language, parse_status, COUNT(*)
                FROM {table_name}
                GROUP BY language, parse_status
                ORDER BY language, parse_status
            """
            cur.execute(agg_query)
            rows = cur.fetchall()

    # Build by_language dict
    by_language: dict[str, dict[str, int]] = {}
    total_files = 0
    total_ok = 0

    for language, parse_status, count in rows:
        if language not in by_language:
            by_language[language] = {
                "files": 0,
                "ok": 0,
                "partial": 0,
                "error": 0,
                "no_grammar": 0,
            }
        by_language[language][parse_status] += count
        by_language[language]["files"] += count
        total_files += count
        if parse_status == "ok":
            total_ok += count

    parse_health_pct = (
        round((total_ok / total_files * 100), 1) if total_files > 0 else 100.0
    )

    return {
        "by_language": by_language,
        "parse_health_pct": parse_health_pct,
        "total_files": total_files,
        "total_ok": total_ok,
    }


def get_parse_failures(
    index_name: str, status_filter: list[str] | None = None
) -> list[dict]:
    """Get individual file parse failure details for an index.

    Returns details for files with non-ok parse statuses, useful for
    the --show-failures CLI flag and MCP/HTTP optional detail.

    Grammar-handled languages (docker-compose, github-actions, etc.) are
    excluded — they use domain-specific chunking, not tree-sitter parsing,
    so "no_grammar" status is misleading for them.

    Args:
        index_name: The name of the index.
        status_filter: List of parse statuses to include.
            Default: ["partial", "error", "no_grammar"] (all non-ok).

    Returns:
        List of dicts with keys: file_path, language, parse_status, error_message.
        Empty list [] if parse_results table does not exist.
    """
    if status_filter is None:
        status_filter = ["partial", "error", "no_grammar"]

    pool = get_connection_pool()
    table_name = f"cocosearch_parse_results_{index_name}"

    # Grammar-handled and no-grammar languages should not appear in parse
    # failures — they use domain-specific chunking, not tree-sitter parsing
    from cocosearch.handlers import get_registered_grammars
    from cocosearch.indexer.parse_tracking import _SKIP_PARSE_EXTENSIONS

    excluded = {
        g.GRAMMAR_NAME for g in get_registered_grammars()
    } | _SKIP_PARSE_EXTENSIONS

    # Check if parse_results table exists
    check_query = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        )
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(check_query, (table_name,))
            (exists,) = cur.fetchone()

            if not exists:
                return []

            # Query individual file failures
            failures_query = f"""
                SELECT file_path, language, parse_status, error_message
                FROM {table_name}
                WHERE parse_status = ANY(%s)
                ORDER BY language, parse_status, file_path
            """
            cur.execute(failures_query, (status_filter,))
            rows = cur.fetchall()

    return [
        {
            "file_path": row[0],
            "language": row[1],
            "parse_status": row[2],
            "error_message": row[3],
        }
        for row in rows
        if row[1] not in excluded
    ]


def check_staleness(index_name: str, threshold_days: int = 7) -> tuple[bool, int]:
    """Check if an index is stale (not updated recently).

    Args:
        index_name: The name of the index.
        threshold_days: Days before considering index stale (default: 7).

    Returns:
        Tuple of (is_stale, days_since_update):
        - is_stale: True if index hasn't been updated in threshold_days
        - days_since_update: Days since last update, -1 if no metadata

    Note:
        If metadata is missing or updated_at is NULL, returns (True, -1).
    """
    pool = get_connection_pool()

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Query cocosearch_index_metadata for updated_at
                metadata_query = """
                    SELECT updated_at
                    FROM cocosearch_index_metadata
                    WHERE index_name = %s
                """
                cur.execute(metadata_query, (index_name,))
                row = cur.fetchone()

                if not row or row[0] is None:
                    # No metadata or no updated_at
                    return True, -1

                updated_at = row[0]
                # Calculate days since update
                from datetime import datetime, timezone

                now = datetime.now(timezone.utc)
                # Handle timezone-aware and naive datetimes
                if updated_at.tzinfo is None:
                    # Assume UTC if naive
                    from datetime import timezone

                    updated_at = updated_at.replace(tzinfo=timezone.utc)

                delta = now - updated_at
                days_since_update = delta.days

                is_stale = days_since_update >= threshold_days

                return is_stale, days_since_update
    except Exception:
        # Table doesn't exist or other database error - treat as no metadata
        return True, -1


def check_branch_staleness(index_name: str, project_path: str | None = None) -> dict:
    """Check if current git state differs from indexed state.

    Args:
        index_name: The name of the index.
        project_path: Path to the project directory. If None, uses the
            canonical_path from index metadata.

    Returns:
        Dict with keys:
        - branch_changed: bool
        - commits_changed: bool
        - indexed_branch: str | None
        - indexed_commit: str | None
        - current_branch: str | None
        - current_commit: str | None
    """
    from cocosearch.management.git import (
        get_current_branch,
        get_commit_hash,
        get_commits_behind,
    )

    result = {
        "branch_changed": False,
        "commits_changed": False,
        "indexed_branch": None,
        "indexed_commit": None,
        "current_branch": None,
        "current_commit": None,
        "commits_behind": None,
    }

    # Get indexed branch/commit from metadata
    metadata = get_index_metadata(index_name)
    if metadata is None:
        return result

    result["indexed_branch"] = metadata.get("branch")
    result["indexed_commit"] = metadata.get("commit_hash")

    # Determine project path
    check_path = project_path or metadata.get("canonical_path")
    if not check_path:
        return result

    # Get current git state
    result["current_branch"] = get_current_branch(check_path)
    result["current_commit"] = get_commit_hash(check_path)

    # Compare
    if result["indexed_branch"] and result["current_branch"]:
        result["branch_changed"] = result["indexed_branch"] != result["current_branch"]

    if result["indexed_commit"] and result["current_commit"]:
        result["commits_changed"] = result["indexed_commit"] != result["current_commit"]

        # Count how many commits behind
        if result["commits_changed"]:
            result["commits_behind"] = get_commits_behind(
                check_path, result["indexed_commit"]
            )
        else:
            result["commits_behind"] = 0

    return result


def get_symbol_stats(index_name: str) -> dict[str, int]:
    """Get symbol type counts for an index.

    Args:
        index_name: The name of the index.

    Returns:
        Dictionary mapping symbol types to counts (e.g., {"function": 150, "class": 25}).
        Empty dict if symbol_type column doesn't exist (requires v1.7+ index).

    Raises:
        ValueError: If the index does not exist.
    """
    pool = get_connection_pool()
    table_name = get_table_name(index_name)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            # Check if symbol_type column exists
            col_check = """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'symbol_type'
            """
            cur.execute(col_check, (table_name,))
            has_symbol_type = cur.fetchone() is not None

            if not has_symbol_type:
                # Pre-v1.7 indexes lack symbol_type column
                return {}

            # Get symbol type counts
            stats_query = f"""
                SELECT symbol_type, COUNT(*) as count
                FROM {table_name}
                WHERE symbol_type IS NOT NULL
                GROUP BY symbol_type
                ORDER BY count DESC
            """
            cur.execute(stats_query)
            rows = cur.fetchall()

            return {row[0]: row[1] for row in rows}


def collect_warnings(
    index_name: str,
    is_stale: bool,
    staleness_days: int,
    branch_staleness: dict | None = None,
) -> list[str]:
    """Collect warnings for an index.

    Args:
        index_name: The name of the index.
        is_stale: Whether the index is stale.
        staleness_days: Days since last update.
        branch_staleness: Result from check_branch_staleness() (optional).

    Returns:
        List of warning messages.
    """
    warnings = []

    # Branch staleness warning
    if branch_staleness and branch_staleness.get("branch_changed"):
        indexed_branch = branch_staleness["indexed_branch"]
        indexed_commit = branch_staleness.get("indexed_commit", "")
        current_branch = branch_staleness["current_branch"]
        current_commit = branch_staleness.get("current_commit", "")

        indexed_ref = f"'{indexed_branch}'"
        if indexed_commit:
            indexed_ref += f" ({indexed_commit})"
        current_ref = f"'{current_branch}'"
        if current_commit:
            current_ref += f" ({current_commit})"

        warnings.append(
            f"Index was built from branch {indexed_ref}, "
            f"but you're on {current_ref}. "
            f"Run 'cocosearch index .' to update."
        )
    elif branch_staleness and branch_staleness.get("commits_changed"):
        indexed_commit = branch_staleness.get("indexed_commit", "")
        current_commit = branch_staleness.get("current_commit", "")
        branch = branch_staleness.get("current_branch", "unknown")
        commits_behind = branch_staleness.get("commits_behind")
        behind_str = (
            f"{commits_behind} commits behind"
            if commits_behind is not None
            else "behind"
        )
        warnings.append(
            f"Index is {behind_str} on branch '{branch}': "
            f"indexed at {indexed_commit}, now at {current_commit}. "
            f"Run 'cocosearch index .' to update."
        )

    # Staleness warning
    if is_stale:
        if staleness_days == -1:
            warnings.append("No metadata found - index may be corrupted or very old")
        else:
            warnings.append(f"Index is stale ({staleness_days} days since last update)")

    # Check for files with zero chunks
    pool = get_connection_pool()
    table_name = get_table_name(index_name)

    with pool.connection() as conn:
        with conn.cursor() as cur:
            # Count distinct files
            file_count_query = f"""
                SELECT COUNT(DISTINCT filename) FROM {table_name}
            """
            cur.execute(file_count_query)
            cur.fetchone()[0]

            # Count files with at least one chunk
            files_with_chunks_query = f"""
                SELECT COUNT(DISTINCT filename)
                FROM {table_name}
                WHERE 1=1
            """
            cur.execute(files_with_chunks_query)
            cur.fetchone()[0]

            # If there's a discrepancy, it would show in the metadata
            # For now, we skip this check as it requires joining with metadata
            # which may not exist for all indexes

    return warnings


def get_comprehensive_stats(
    index_name: str, staleness_threshold: int = 7
) -> IndexStats:
    """Get comprehensive statistics for an index.

    Combines all available statistics into a single IndexStats object:
    - Basic stats (files, chunks, size)
    - Language distribution
    - Symbol type counts (if available)
    - Staleness information
    - Warnings

    Args:
        index_name: The name of the index.
        staleness_threshold: Days before considering index stale (default: 7).

    Returns:
        IndexStats instance with all available information.

    Raises:
        ValueError: If the index does not exist.
    """
    # Get basic stats
    basic_stats = get_stats(index_name)

    # Get language stats
    languages = get_language_stats(index_name)

    # Get symbol stats
    symbols = get_symbol_stats(index_name)

    # Get parse failure stats
    parse_stats = get_parse_stats(index_name)

    # Get grammar stats
    grammars = get_grammar_stats(index_name)

    # Clean up and enrich parse_stats for dashboard display.
    # Grammar-handled languages (docker-compose, github-actions, etc.) are removed
    # — they have their own Grammar Stats section and aren't tree-sitter parsed.
    # Text-only formats (md, yaml, json) are added as "skipped" so dashboards
    # show all languages.
    # Note: chunks table stores raw extensions (e.g., "py") while parse_results
    # stores tree-sitter names (e.g., "python") via LANGUAGE_MAP. We must check
    # both the raw extension and its mapped name to avoid duplicates.
    if parse_stats and "by_language" in parse_stats:
        from cocosearch.indexer.symbols import LANGUAGE_MAP
        from cocosearch.handlers import get_registered_grammars
        from cocosearch.indexer.parse_tracking import _SKIP_PARSE_EXTENSIONS

        grammar_names = {g.GRAMMAR_NAME for g in get_registered_grammars()}
        # Languages to exclude from parse stats (grammars + no-grammar handlers)
        excluded_from_parse = grammar_names | _SKIP_PARSE_EXTENSIONS

        # Remove excluded languages from parse stats (stale DB entries
        # or languages that shouldn't appear in parse health)
        for name in list(parse_stats["by_language"].keys()):
            if name in excluded_from_parse:
                removed = parse_stats["by_language"].pop(name)
                parse_stats["total_files"] -= removed["files"]
                parse_stats["total_ok"] -= removed.get("ok", 0)

        # Recalculate health percentage after removals
        total = parse_stats["total_files"]
        ok = parse_stats["total_ok"]
        parse_stats["parse_health_pct"] = (
            round((ok / total * 100), 1) if total > 0 else 100.0
        )

        # Enrich with skipped text-only languages from chunks table
        tracked_languages = set(parse_stats["by_language"].keys())
        for lang_stat in languages:
            lang = lang_stat["language"]
            # Skip grammar-handled and excluded languages
            if lang in excluded_from_parse:
                continue
            mapped_lang = LANGUAGE_MAP.get(lang)
            # Skip if already tracked under either the raw extension or mapped name
            if lang in tracked_languages or (
                mapped_lang and mapped_lang in tracked_languages
            ):
                continue
            parse_stats["by_language"][lang] = {
                "files": lang_stat["file_count"],
                "ok": 0,
                "partial": 0,
                "error": 0,
                "no_grammar": 0,
                "skipped": True,
            }

    # Check staleness
    is_stale, staleness_days = check_staleness(index_name, staleness_threshold)

    # Auto-recover indexes stuck in 'indexing' status (e.g., interrupted process)
    auto_recover_stale_indexing(index_name)

    # Get metadata (timestamps, source path, status)
    metadata = get_index_metadata(index_name)
    created_at = metadata["created_at"] if metadata else None
    updated_at = metadata["updated_at"] if metadata else None
    source_path = metadata.get("canonical_path") if metadata else None
    status = metadata.get("status", "indexed") if metadata else None
    indexing_elapsed_seconds = (
        metadata.get("indexing_elapsed_seconds") if metadata else None
    )

    # Derive repo URL from source path
    from cocosearch.management.git import get_repo_url

    repo_url = get_repo_url(source_path) if source_path else None

    # Get branch info from metadata
    branch = metadata.get("branch") if metadata else None
    commit_hash = metadata.get("commit_hash") if metadata else None
    branch_commit_count = metadata.get("branch_commit_count") if metadata else None

    # Check branch staleness (best-effort, skip if git not available)
    branch_staleness = None
    if source_path:
        try:
            branch_staleness = check_branch_staleness(index_name, source_path)
        except Exception:
            pass

    # Extract commits_behind from branch staleness check
    commits_behind = (
        branch_staleness.get("commits_behind") if branch_staleness else None
    )

    # Collect warnings
    warnings = collect_warnings(
        index_name, is_stale, staleness_days, branch_staleness=branch_staleness
    )

    return IndexStats(
        name=index_name,
        file_count=basic_stats["file_count"],
        chunk_count=basic_stats["chunk_count"],
        storage_size=basic_stats["storage_size"],
        storage_size_pretty=basic_stats["storage_size_pretty"],
        created_at=created_at,
        updated_at=updated_at,
        is_stale=is_stale,
        staleness_days=staleness_days,
        languages=languages,
        symbols=symbols,
        warnings=warnings,
        parse_stats=parse_stats,
        source_path=source_path,
        status=status,
        indexing_elapsed_seconds=indexing_elapsed_seconds,
        repo_url=repo_url,
        branch=branch,
        commit_hash=commit_hash,
        commits_behind=commits_behind,
        branch_commit_count=branch_commit_count,
        grammars=grammars,
    )
