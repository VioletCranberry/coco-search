"""CocoIndex flow definition for code indexing.

Defines the main indexing flow that:
1. Reads files from a codebase directory
2. Chunks code using Tree-sitter for semantic boundaries
3. Generates embeddings via Ollama
4. Stores results in PostgreSQL with vector indexes
"""

import os

import cocoindex
import psycopg

import logging

from cocosearch.config.env_validation import get_database_url
from cocosearch.indexer.config import IndexingConfig
from cocosearch.indexer.preflight import check_infrastructure
from cocosearch.indexer.embedder import (
    code_to_embedding,
    extract_language,
    add_filename_context,
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


def _clean_stale_flow_state(index_name: str, db_url: str) -> None:
    """Remove stale CocoIndex metadata and data tables for a flow.

    Called when CocoIndex's own drop()/setup() fail due to version mismatch
    in the cocoindex_setup_metadata table.  Cleans up directly via SQL so
    a fresh flow can be created from scratch.
    """
    flow_name = f"CodeIndex_{index_name}"
    data_table = f"codeindex_{index_name}__{index_name}_chunks"

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM cocoindex_setup_metadata WHERE flow_name = %s",
                (flow_name,),
            )
            cur.execute(f"DROP TABLE IF EXISTS {data_table}")
            cur.execute(f"DROP TABLE IF EXISTS cocosearch_parse_results_{index_name}")
            cur.execute(f"DROP TABLE IF EXISTS cocosearch_deps_{index_name}")
            cur.execute(
                f"DROP TABLE IF EXISTS codeindex_{index_name}__cocoindex_tracking"
            )
        conn.commit()
    logger.info("Cleaned stale flow state for index '%s'", index_name)


def create_code_index_flow(
    index_name: str,
    codebase_path: str,
    include_patterns: list[str],
    exclude_patterns: list[str],
    chunk_size: int = 1000,
    chunk_overlap: int = 300,
) -> cocoindex.Flow:
    """Create a CocoIndex flow for indexing a codebase.

    Args:
        index_name: Unique name for this index (used in flow name and table name).
        codebase_path: Path to the codebase root directory.
        include_patterns: File patterns to include (e.g., ["*.py", "*.js"]).
        exclude_patterns: File patterns to exclude.
        chunk_size: Maximum chunk size in bytes (default 1000).
        chunk_overlap: Overlap between chunks in bytes (default 300).

    Returns:
        CocoIndex Flow instance configured for the codebase.
    """

    def code_index_flow(
        flow_builder: cocoindex.FlowBuilder,
        data_scope: cocoindex.DataScope,
    ) -> None:
        # Step 1: Add LocalFile source for reading codebase files
        data_scope["files"] = flow_builder.add_source(
            cocoindex.sources.LocalFile(
                path=codebase_path,
                included_patterns=include_patterns,
                excluded_patterns=exclude_patterns,
                binary=False,  # Read files as text, not binary
            )
        )

        # Step 2: Create collector for code chunks with embeddings
        code_embeddings = data_scope.add_collector()

        # Step 3: Process each file
        with data_scope["files"].row() as file:
            # Extract language identifier for routing (grammar > filename > extension)
            # Note: field is still called "extension" to minimize downstream changes
            file["extension"] = file["filename"].transform(
                extract_language, content=file["content"]
            )

            # Chunk using Tree-sitter + custom handler languages (SplitRecursively)
            file["chunks"] = file["content"].transform(
                cocoindex.functions.SplitRecursively(
                    custom_languages=get_custom_languages(),
                ),
                language=file["extension"],
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

            # Step 4: Process each chunk
            with file["chunks"].row() as chunk:
                # Generate embedding via Ollama using shared transform
                # Prepend filename context so embeddings capture file path relevance
                chunk["embedding_text"] = chunk["text"].transform(
                    add_filename_context, filename=file["filename"]
                )
                chunk["embedding"] = chunk["embedding_text"].call(code_to_embedding)

                # Extract Handler metadata (block_type, hierarchy, language_id)
                chunk["metadata"] = chunk["text"].transform(
                    extract_chunk_metadata,
                    language_id=file["extension"],
                )

                # Extract symbol metadata (function/class/method info)
                chunk["symbol_metadata"] = chunk["text"].transform(
                    extract_symbol_metadata,
                    language=file["extension"],
                )

                # v1.7 Hybrid Search: Store chunk text and tsvector for keyword search
                # content_text: Raw text for storage and potential future use
                # content_tsv_input: Preprocessed text for PostgreSQL to_tsvector()
                # Filename tokens appended so keyword search matches file paths
                chunk["content_tsv_input"] = chunk["text"].transform(
                    text_to_tsvector_sql, filename=file["filename"]
                )

                # Collect with metadata (includes hybrid search and symbol columns)
                code_embeddings.collect(
                    filename=file["filename"],
                    location=chunk["location"],
                    embedding=chunk["embedding"],
                    content_text=chunk["text"],  # Raw text for hybrid search
                    content_tsv_input=chunk[
                        "content_tsv_input"
                    ],  # Preprocessed for tsvector
                    block_type=chunk["metadata"]["block_type"],
                    hierarchy=chunk["metadata"]["hierarchy"],
                    language_id=chunk["metadata"]["language_id"],
                    symbol_type=chunk["symbol_metadata"]["symbol_type"],
                    symbol_name=chunk["symbol_metadata"]["symbol_name"],
                    symbol_signature=chunk["symbol_metadata"]["symbol_signature"],
                )

        # Step 5: Export to PostgreSQL with vector index
        code_embeddings.export(
            f"{index_name}_chunks",
            cocoindex.targets.Postgres(),
            primary_key_fields=["filename", "location"],
            vector_indexes=[
                cocoindex.VectorIndexDef(
                    field_name="embedding",
                    metric=cocoindex.VectorSimilarityMetric.COSINE_SIMILARITY,
                )
            ],
        )

    flow_name = f"CodeIndex_{index_name}"
    # Always close any existing in-memory registration before opening.
    # This frees the registry slot (does NOT touch persistent data) and
    # avoids stale state from previous runs or clear_index() in the same process.
    from cocoindex.flow import _flows

    old = _flows.get(flow_name)
    if old is not None:
        old.close()
    return cocoindex.open_flow(flow_name, code_index_flow)


def run_index(
    index_name: str,
    codebase_path: str,
    config: IndexingConfig | None = None,
    respect_gitignore: bool = True,
    fresh: bool = False,
):
    """Run indexing for a codebase.

    Orchestrates the full indexing process:
    1. Initialize CocoIndex (if not already)
    2. Build exclude patterns from defaults + .gitignore + config
    3. Create the indexing flow
    4. Setup and update the flow

    Args:
        index_name: Unique name for this index.
        codebase_path: Path to the codebase root directory.
        config: Optional indexing configuration (uses defaults if not provided).
        respect_gitignore: Whether to respect .gitignore patterns (default True).
        fresh: If True, drop and recreate the flow's persistent backends.

    Returns:
        IndexUpdateInfo with statistics about the indexing run.
    """
    _get_cs_log().index(
        "Indexing started", index=index_name, path=codebase_path, fresh=fresh
    )

    # Validate index name before any database operations
    validate_index_name(index_name)

    # Use default config if not provided
    if config is None:
        config = IndexingConfig()

    # Resolve embedding provider and model for preflight + metadata
    from cocosearch.config.schema import default_model_for_provider

    embedding_provider = os.environ.get("COCOSEARCH_EMBEDDING_PROVIDER", "ollama")
    embedding_model = os.environ.get(
        "COCOSEARCH_EMBEDDING_MODEL", default_model_for_provider(embedding_provider)
    )

    # Preflight: verify infrastructure is reachable before any CocoIndex work
    check_infrastructure(
        db_url=get_database_url(),
        ollama_url=os.environ.get("COCOSEARCH_OLLAMA_URL"),
        embedding_model=embedding_model,
        provider=embedding_provider,
    )

    _get_cs_log().infra(
        "Preflight checks passed", provider=embedding_provider, model=embedding_model
    )

    # Mismatch detection: warn if index was built with different provider/model
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

    # Initialize CocoIndex (database configured via COCOSEARCH_DATABASE_URL)
    cocoindex.init()

    # Build exclude patterns: defaults + .gitignore + user config
    exclude_patterns = build_exclude_patterns(
        codebase_path=codebase_path,
        user_excludes=config.exclude_patterns,
        respect_gitignore=respect_gitignore,
    )

    # Create the flow
    flow = create_code_index_flow(
        index_name=index_name,
        codebase_path=codebase_path,
        include_patterns=config.include_patterns,
        exclude_patterns=exclude_patterns,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
    )

    # Drop and recreate if --fresh (cleans up both table and CocoIndex metadata)
    if fresh:
        try:
            flow.drop()
        except Exception as e:
            logger.warning("flow.drop() failed (will clean up via SQL): %s", e)
        db_url = get_database_url()
        _clean_stale_flow_state(index_name, db_url)
        flow = create_code_index_flow(
            index_name=index_name,
            codebase_path=codebase_path,
            include_patterns=config.include_patterns,
            exclude_patterns=exclude_patterns,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )
        logger.info("Dropped flow for index '%s' (--fresh)", index_name)

    # Setup flow, ensure schema, and run indexing.
    db_url = get_database_url()

    # CocoIndex naming: {flow_name}__{target_name}
    # Flow name: CodeIndex_{index_name} -> lowercased to codeindex_{index_name}
    # Target name: {index_name}_chunks
    table_name = f"codeindex_{index_name}__{index_name}_chunks"

    def _setup_and_update():
        """Setup flow, ensure schema columns, and run flow.update()."""
        flow.setup()
        # Verify the data table actually exists after setup.
        # CocoIndex may skip table creation if metadata says the schema is
        # current, but the table could have been dropped externally (e.g.
        # failed migration during embedding dimension change).  Raising here
        # lets the stale-state recovery block clean metadata and retry.
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = %s",
                    (table_name,),
                )
                if not cur.fetchone():
                    raise RuntimeError(
                        f"Table {table_name} does not exist after flow.setup()"
                    )
            symbol_result = ensure_symbol_columns(conn, table_name)
            ensure_parse_results_table(conn, index_name)
        if symbol_result.get("columns_added"):
            from cocosearch.search.db import reset_symbol_columns_cache

            reset_symbol_columns_cache()
        return flow.update()

    # Stale-state recovery: if the flow definition changed (e.g. different
    # codebase_path from a worktree, or updated CocoSearch code), setup/update
    # will fail with "does not exist" or "newer version" errors.  CocoIndex's
    # own drop() also fails in this case (same version check), so we clean the
    # internal metadata table directly via SQL and retry with a fresh flow.
    try:
        update_info = _setup_and_update()
    except Exception as e:
        err_msg = str(e)
        if ("does not exist" in err_msg or "newer version" in err_msg) and not fresh:
            logger.warning(
                "Stale CocoIndex state detected during setup/update — "
                "resetting and retrying"
            )
            _get_cs_log().index(
                "Stale state detected, resetting", level="WARNING", index=index_name
            )
            try:
                flow.close()
            except Exception:
                logger.debug("flow.close() failed during recovery (non-fatal)")
            _clean_stale_flow_state(index_name, db_url)
            flow = create_code_index_flow(
                index_name=index_name,
                codebase_path=codebase_path,
                include_patterns=config.include_patterns,
                exclude_patterns=exclude_patterns,
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
            )
            update_info = _setup_and_update()
        else:
            raise

    _get_cs_log().index("Indexing completed", index=index_name)

    # Determine if any files actually changed
    has_changes = True  # conservative default
    if hasattr(update_info, "stats") and isinstance(update_info.stats, dict):
        file_stats = update_info.stats.get("files", {})
        total = (
            file_stats.get("num_insertions", 0)
            + file_stats.get("num_deletions", 0)
            + file_stats.get("num_updates", 0)
        )
        has_changes = total > 0

    if has_changes:
        # Invalidate query cache so stale results aren't served after reindex
        try:
            removed = invalidate_index_cache(index_name)
            if removed > 0:
                logger.info(
                    f"Invalidated {removed} cached queries for index '{index_name}'"
                )
                _get_cs_log().cache(
                    "Post-index cache invalidated",
                    index=index_name,
                    entries_removed=removed,
                )
        except Exception as e:
            logger.warning(f"Cache invalidation failed (non-fatal): {e}")

        # Track parse status for all indexed files
        try:
            with psycopg.connect(db_url) as conn:
                parse_summary = track_parse_results(
                    conn, index_name, codebase_path, table_name
                )
                logger.info(f"Parse tracking complete: {parse_summary}")
        except Exception as e:
            logger.warning(f"Parse tracking failed (non-fatal): {e}")
    else:
        logger.info(
            "No file changes detected — skipping parse tracking and cache invalidation"
        )

    return update_info
