"""Code indexing pipeline for CocoSearch.

Indexes a codebase by:
1. Walking files with pattern filtering
2. Chunking code using Tree-sitter (RecursiveSplitter) for semantic boundaries
3. Generating embeddings via LiteLLM
4. Storing results in PostgreSQL with pgvector indexes

Incremental indexing: SHA-256 content hashes track file changes so only
new/modified files are re-embedded on subsequent runs.
"""

import hashlib
import os
import pathlib
import logging

import pathspec
import psycopg
from pgvector.psycopg import register_vector
from psycopg.types.range import Range

from cocoindex.ops.text import RecursiveSplitter

from cocosearch.config.env_validation import get_database_url
from cocosearch.indexer.config import IndexingConfig
from cocosearch.indexer.preflight import check_infrastructure
from cocosearch.indexer.embedder import (
    extract_language,
    add_filename_context,
    embed_query,
    _resolve_output_dimension,
)
from cocosearch.indexer.tsvector import text_to_tsvector_sql
from cocosearch.handlers import get_custom_languages, extract_chunk_metadata
from cocosearch.indexer.file_filter import build_exclude_patterns
from cocosearch.indexer.symbols import extract_symbol_metadata
from cocosearch.indexer.schema_migration import (
    ensure_symbol_columns,
    ensure_parse_results_table,
)
from cocosearch.indexer.parse_tracking import track_parse_results
from cocosearch.search.cache import invalidate_index_cache
from cocosearch.validation import validate_index_name

logger = logging.getLogger(__name__)


def _get_cs_log():
    from cocosearch.logging import cs_log

    return cs_log


def get_table_name(index_name: str) -> str:
    """Return the PostgreSQL table name for an index's chunks."""
    return f"codeindex_{index_name}__{index_name}_chunks"


def _ensure_chunks_table(conn, table_name: str, embedding_dim: int) -> None:
    """Create the chunks table and vector index if they don't exist."""
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS {table_name} ("
            "  filename TEXT NOT NULL,"
            "  location INT4RANGE NOT NULL,"
            f"  embedding VECTOR({embedding_dim}),"
            "  content_text TEXT,"
            "  content_tsv_input TEXT,"
            "  block_type TEXT,"
            "  hierarchy TEXT,"
            "  language_id TEXT,"
            "  symbol_type TEXT,"
            "  symbol_name TEXT,"
            "  symbol_signature TEXT,"
            "  PRIMARY KEY (filename, location)"
            ")"
        )
        cur.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table_name}_embedding "
            f"ON {table_name} USING ivfflat (embedding vector_cosine_ops)"
        )
    conn.commit()


def _ensure_tracking_table(conn, index_name: str) -> None:
    """Create the file tracking table for incremental indexing."""
    tracking_table = f"cocosearch_index_tracking_{index_name}"
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS {tracking_table} ("
            "  filename TEXT PRIMARY KEY,"
            "  content_hash TEXT NOT NULL,"
            "  indexed_at TIMESTAMPTZ DEFAULT now()"
            ")"
        )
    conn.commit()


def _get_file_hashes(conn, index_name: str) -> dict[str, str]:
    """Get stored content hashes for all tracked files."""
    tracking_table = f"cocosearch_index_tracking_{index_name}"
    with conn.cursor() as cur:
        try:
            cur.execute(f"SELECT filename, content_hash FROM {tracking_table}")
            return dict(cur.fetchall())
        except Exception:
            return {}


def _clean_tables(index_name: str, db_url: str) -> None:
    """Drop all tables for an index (used by --fresh and clear_index)."""
    table_name = get_table_name(index_name)
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {table_name}")
            cur.execute(f"DROP TABLE IF EXISTS cocosearch_index_tracking_{index_name}")
            cur.execute(f"DROP TABLE IF EXISTS cocosearch_parse_results_{index_name}")
            cur.execute(f"DROP TABLE IF EXISTS cocosearch_deps_{index_name}")
            cur.execute(f"DROP TABLE IF EXISTS cocosearch_deps_tracking_{index_name}")
            # Legacy v0 CocoIndex tables
            cur.execute(
                f"DROP TABLE IF EXISTS codeindex_{index_name}__cocoindex_tracking"
            )
            try:
                cur.execute(
                    "DELETE FROM cocoindex_setup_metadata WHERE flow_name = %s",
                    (f"CodeIndex_{index_name}",),
                )
            except Exception:
                pass
        conn.commit()
    logger.info("Cleaned tables for index '%s'", index_name)


def _walk_files(
    codebase_path: str,
    include_patterns: list[str],
    exclude_patterns: list[str],
) -> dict[str, str]:
    """Walk codebase and return {relative_path: content} for matching files."""
    root = pathlib.Path(codebase_path).resolve()

    include_spec = (
        pathspec.PathSpec.from_lines("gitwildmatch", include_patterns)
        if include_patterns
        else None
    )
    exclude_spec = (
        pathspec.PathSpec.from_lines("gitwildmatch", exclude_patterns)
        if exclude_patterns
        else None
    )

    files: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue

        rel = str(path.relative_to(root))

        if include_spec and not include_spec.match_file(rel):
            continue
        if exclude_spec and exclude_spec.match_file(rel):
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            files[rel] = content
        except Exception:
            continue

    return files


def _index_file(
    conn,
    table_name: str,
    filename: str,
    content: str,
    splitter: RecursiveSplitter,
    chunk_size: int,
    chunk_overlap: int,
) -> int:
    """Index a single file: chunk, embed, insert rows. Returns chunk count."""
    language = extract_language(filename, content)

    chunks = splitter.split(
        content,
        chunk_size,
        chunk_overlap=chunk_overlap,
        language=language or None,
    )

    if not chunks:
        return 0

    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM {table_name} WHERE filename = %s", (filename,))

        for chunk in chunks:
            embedding_text = add_filename_context(chunk.text, filename)
            embedding = embed_query(embedding_text)
            metadata = extract_chunk_metadata(chunk.text, language)
            symbol_meta = extract_symbol_metadata(chunk.text, language)
            tsv_input = text_to_tsvector_sql(chunk.text, filename)

            cur.execute(
                f"INSERT INTO {table_name}"
                " (filename, location, embedding, content_text, content_tsv_input,"
                "  block_type, hierarchy, language_id,"
                "  symbol_type, symbol_name, symbol_signature)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    filename,
                    Range(chunk.start.byte_offset, chunk.end.byte_offset),
                    embedding,
                    chunk.text,
                    tsv_input,
                    metadata.block_type,
                    metadata.hierarchy,
                    metadata.language_id,
                    symbol_meta.symbol_type,
                    symbol_meta.symbol_name,
                    symbol_meta.symbol_signature,
                ),
            )

    return len(chunks)


def run_index(
    index_name: str,
    codebase_path: str,
    config: IndexingConfig | None = None,
    respect_gitignore: bool = True,
    fresh: bool = False,
    stop_event=None,
):
    """Run indexing for a codebase.

    Orchestrates the full indexing process:
    1. Preflight: verify infrastructure is reachable
    2. Walk files and compute content hashes
    3. Determine changed/new/deleted files (incremental)
    4. Chunk, embed, and store changed files
    5. Post-processing: cache invalidation, parse tracking

    Args:
        index_name: Unique name for this index.
        codebase_path: Path to the codebase root directory.
        config: Optional indexing configuration (uses defaults if not provided).
        respect_gitignore: Whether to respect .gitignore patterns (default True).
        fresh: If True, drop and recreate all tables.
        stop_event: Optional threading.Event checked between files to allow
            cancellation from the dashboard or MCP server.

    Returns:
        Dict with indexing statistics.
    """
    _get_cs_log().index(
        "Indexing started", index=index_name, path=codebase_path, fresh=fresh
    )

    validate_index_name(index_name)

    if config is None:
        config = IndexingConfig()

    from cocosearch.config.schema import default_model_for_provider

    embedding_provider = os.environ.get("COCOSEARCH_EMBEDDING_PROVIDER", "ollama")
    embedding_model = os.environ.get(
        "COCOSEARCH_EMBEDDING_MODEL", default_model_for_provider(embedding_provider)
    )

    check_infrastructure(
        db_url=get_database_url(),
        ollama_url=os.environ.get("COCOSEARCH_OLLAMA_URL"),
        embedding_model=embedding_model,
        provider=embedding_provider,
        base_url=os.environ.get("COCOSEARCH_EMBEDDING_BASE_URL"),
    )

    _get_cs_log().infra(
        "Preflight checks passed", provider=embedding_provider, model=embedding_model
    )

    from cocosearch.management.metadata import get_index_metadata

    existing = get_index_metadata(index_name)
    if existing and existing.get("embedding_model"):
        if (
            existing["embedding_model"] != embedding_model
            or existing.get("embedding_provider") != embedding_provider
        ):
            logger.warning(
                "Index '%s' was built with %s/%s but current config uses %s/%s. "
                "Use --fresh to reindex with the new model.",
                index_name,
                existing.get("embedding_provider", "unknown"),
                existing["embedding_model"],
                embedding_provider,
                embedding_model,
            )

    db_url = get_database_url()
    table_name = get_table_name(index_name)

    if fresh:
        _clean_tables(index_name, db_url)
        logger.info("Dropped all tables for index '%s' (--fresh)", index_name)

    raw_model = os.environ.get(
        "COCOSEARCH_EMBEDDING_MODEL",
        default_model_for_provider(embedding_provider),
    )
    embedding_dim = _resolve_output_dimension(raw_model) or 768

    with psycopg.connect(db_url) as conn:
        register_vector(conn)
        _ensure_chunks_table(conn, table_name, embedding_dim)
        _ensure_tracking_table(conn, index_name)
        ensure_symbol_columns(conn, table_name)
        ensure_parse_results_table(conn, index_name)

    exclude_patterns = build_exclude_patterns(
        codebase_path=codebase_path,
        user_excludes=config.exclude_patterns,
        respect_gitignore=respect_gitignore,
    )

    files = _walk_files(codebase_path, config.include_patterns, exclude_patterns)

    with psycopg.connect(db_url) as conn:
        stored_hashes = _get_file_hashes(conn, index_name)

    current_hashes = {
        fname: hashlib.sha256(content.encode("utf-8")).hexdigest()
        for fname, content in files.items()
    }

    new_files = set(current_hashes) - set(stored_hashes)
    deleted_files = set(stored_hashes) - set(current_hashes)
    changed_files = {
        f
        for f in set(current_hashes) & set(stored_hashes)
        if current_hashes[f] != stored_hashes[f]
    }

    files_to_index = new_files | changed_files
    total_changes = len(files_to_index) + len(deleted_files)

    if total_changes == 0 and not fresh:
        logger.info(
            "No file changes detected — skipping parse tracking and cache invalidation"
        )
        _get_cs_log().index("No changes detected", index=index_name)
        return {"files_indexed": 0, "files_deleted": 0, "chunks_total": 0}

    splitter = RecursiveSplitter(custom_languages=get_custom_languages())

    chunks_total = 0
    files_indexed = 0
    cancelled = False
    with psycopg.connect(db_url) as conn:
        register_vector(conn)
        tracking_table = f"cocosearch_index_tracking_{index_name}"

        for filename in files_to_index:
            if stop_event is not None and stop_event.is_set():
                logger.info("Indexing cancelled after %d files", files_indexed)
                cancelled = True
                break

            try:
                n = _index_file(
                    conn,
                    table_name,
                    filename,
                    files[filename],
                    splitter,
                    config.chunk_size,
                    config.chunk_overlap,
                )
                chunks_total += n
                files_indexed += 1

                with conn.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO {tracking_table} (filename, content_hash)"
                        " VALUES (%s, %s)"
                        " ON CONFLICT (filename) DO UPDATE SET"
                        "   content_hash = EXCLUDED.content_hash,"
                        "   indexed_at = now()",
                        (filename, current_hashes[filename]),
                    )
                conn.commit()
            except Exception as e:
                logger.warning("Failed to index %s: %s", filename, e)
                conn.rollback()

        if deleted_files and not cancelled:
            with conn.cursor() as cur:
                for filename in deleted_files:
                    cur.execute(
                        f"DELETE FROM {table_name} WHERE filename = %s",
                        (filename,),
                    )
                    cur.execute(
                        f"DELETE FROM {tracking_table} WHERE filename = %s",
                        (filename,),
                    )
            conn.commit()

    if cancelled:
        _get_cs_log().index("Indexing cancelled", index=index_name)
    else:
        _get_cs_log().index("Indexing completed", index=index_name)

    if files_indexed > 0 or deleted_files:
        try:
            removed = invalidate_index_cache(index_name)
            if removed > 0:
                logger.info(
                    "Invalidated %d cached queries for index '%s'",
                    removed,
                    index_name,
                )
                _get_cs_log().cache(
                    "Post-index cache invalidated",
                    index=index_name,
                    entries_removed=removed,
                )
        except Exception as e:
            logger.warning("Cache invalidation failed (non-fatal): %s", e)

        if not cancelled:
            try:
                with psycopg.connect(db_url) as conn:
                    parse_summary = track_parse_results(
                        conn, index_name, codebase_path, table_name
                    )
                    logger.info("Parse tracking complete: %s", parse_summary)
            except Exception as e:
                logger.warning("Parse tracking failed (non-fatal): %s", e)

    update_info = {
        "files_indexed": files_indexed,
        "files_deleted": len(deleted_files) if not cancelled else 0,
        "chunks_total": chunks_total,
    }
    return update_info
