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
from cocosearch.indexer.embedder import code_to_embedding, extract_language
from cocosearch.indexer.tsvector import text_to_tsvector_sql
from cocosearch.handlers import get_custom_languages, extract_devops_metadata
from cocosearch.indexer.file_filter import build_exclude_patterns
from cocosearch.indexer.symbols import extract_symbol_metadata
from cocosearch.indexer.schema_migration import (
    ensure_symbol_columns,
    ensure_parse_results_table,
)
from cocosearch.indexer.parse_tracking import track_parse_results
from cocosearch.search.cache import invalidate_index_cache

logger = logging.getLogger(__name__)


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

    @cocoindex.flow_def(name=f"CodeIndex_{index_name}")
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
            # Extract language identifier for routing (handles extensionless files like Dockerfile)
            # Note: field is still called "extension" to minimize downstream changes
            file["extension"] = file["filename"].transform(extract_language)

            # Chunk using Tree-sitter + custom DevOps languages (SplitRecursively)
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
                chunk["embedding"] = chunk["text"].call(code_to_embedding)

                # Extract DevOps metadata (block_type, hierarchy, language_id)
                chunk["metadata"] = chunk["text"].transform(
                    extract_devops_metadata,
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
                chunk["content_tsv_input"] = chunk["text"].transform(
                    text_to_tsvector_sql
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
            cocoindex.storages.Postgres(),
            primary_key_fields=["filename", "location"],
            vector_indexes=[
                cocoindex.VectorIndexDef(
                    field_name="embedding",
                    metric=cocoindex.VectorSimilarityMetric.COSINE_SIMILARITY,
                )
            ],
        )

    return code_index_flow


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
    # Use default config if not provided
    if config is None:
        config = IndexingConfig()

    # Preflight: verify infrastructure is reachable before any CocoIndex work
    check_infrastructure(
        db_url=get_database_url(),
        ollama_url=os.environ.get("COCOSEARCH_OLLAMA_URL"),
    )

    # Invalidate query cache for this index before reindexing
    # This ensures stale results aren't served during/after reindex
    try:
        removed = invalidate_index_cache(index_name)
        if removed > 0:
            logger.info(
                f"Invalidated {removed} cached queries for index '{index_name}'"
            )
    except Exception as e:
        logger.warning(f"Cache invalidation failed (non-fatal): {e}")

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
        flow.drop()
        # Also clean up non-CocoIndex tables (parse results) and path metadata
        db_url = get_database_url()
        try:
            with psycopg.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"DROP TABLE IF EXISTS cocosearch_parse_results_{index_name}"
                    )
                conn.commit()
        except Exception:
            pass  # Non-critical cleanup
        try:
            from cocosearch.management.metadata import clear_index_path

            clear_index_path(index_name)
        except Exception:
            pass  # Non-critical cleanup
        logger.info(f"Dropped flow for index '{index_name}' (--fresh)")

    # Setup flow (creates tables if needed)
    flow.setup()

    # Ensure symbol columns exist in target table
    # This must happen after setup (table exists) but before update (data insertion)
    db_url = get_database_url()

    # Get the actual table name following CocoIndex naming convention
    # CocoIndex naming: {flow_name}__{target_name}
    # Flow name: CodeIndex_{index_name} -> lowercased to codeindex_{index_name}
    # Target name: {index_name}_chunks
    table_name = f"codeindex_{index_name}__{index_name}_chunks"

    with psycopg.connect(db_url) as conn:
        ensure_symbol_columns(conn, table_name)
        ensure_parse_results_table(conn, index_name)

    # Run indexing and return statistics
    update_info = flow.update()

    # Track parse status for all indexed files
    try:
        with psycopg.connect(db_url) as conn:
            parse_summary = track_parse_results(
                conn, index_name, codebase_path, table_name
            )
            logger.info(f"Parse tracking complete: {parse_summary}")
    except Exception as e:
        logger.warning(f"Parse tracking failed (non-fatal): {e}")

    return update_info
