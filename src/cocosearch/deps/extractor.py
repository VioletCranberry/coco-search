"""Extraction orchestrator for dependency graph construction.

Runs language-specific dependency extractors over all indexed files,
collecting edges and batch-inserting them into the deps table.
After extraction, delegates module resolution to language-specific
resolvers (see ``resolver.py``), so that both forward
(get_dependencies) and reverse (get_dependents) queries work.
"""

import logging
import os

from cocosearch.deps.db import create_deps_table, drop_deps_table, insert_edges
from cocosearch.deps.models import DependencyEdge
from cocosearch.deps.registry import get_extractor
from cocosearch.deps.resolver import get_resolver
from cocosearch.search.db import get_connection_pool, get_table_name

logger = logging.getLogger(__name__)


def get_indexed_files(index_name: str) -> list[tuple[str, str]]:
    """Query the chunks table for distinct indexed file paths and languages.

    Args:
        index_name: The index name to look up files in.

    Returns:
        List of (filename, language_id) tuples for all files that have
        a non-null language_id in the chunks table.
    """
    table = get_table_name(index_name)
    pool = get_connection_pool()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT DISTINCT filename, language_id "
                f"FROM {table} "
                f"WHERE language_id IS NOT NULL"
            )
            return cur.fetchall()


def _resolve_all_edges(
    all_edges: list[DependencyEdge],
    indexed_files: list[tuple[str, str]],
) -> None:
    """Resolve target_file on all edges using language-specific resolvers.

    Groups edges by their source file's language, looks up the appropriate
    resolver, builds a module index, and resolves each edge in place.

    Args:
        all_edges: All collected dependency edges (mutated in place).
        indexed_files: List of (relative_path, language_id) tuples.
    """
    # Build file -> language_id lookup
    file_lang: dict[str, str] = {f: lang for f, lang in indexed_files}

    # Collect unique resolvers (many language_ids may share one resolver)
    resolver_map: dict[int, tuple[object, set[str]]] = {}

    for _file, lang in indexed_files:
        resolver = get_resolver(lang)
        if resolver is None:
            continue
        rid = id(resolver)
        if rid not in resolver_map:
            resolver_map[rid] = (resolver, set())
        resolver_map[rid][1].add(lang)

    # Run resolution per resolver
    for resolver, lang_ids in resolver_map.values():
        module_index = resolver.build_index(indexed_files)

        for edge in all_edges:
            if edge.target_file is not None:
                continue
            source_lang = file_lang.get(edge.source_file)
            if source_lang not in lang_ids:
                continue
            resolved = resolver.resolve(edge, module_index)
            if resolved is not None:
                edge.target_file = resolved


def extract_dependencies(index_name: str, codebase_path: str) -> dict:
    """Extract dependency edges from all indexed files and store them.

    Drops and recreates the deps table, then iterates over all indexed
    files. For each file with a registered extractor, reads the file
    content, runs the extractor, and sets ``source_file`` on each
    returned edge. All edges are batch-inserted at the end.

    Args:
        index_name: The index name to extract dependencies for.
        codebase_path: Absolute path to the codebase root directory.

    Returns:
        Stats dict with keys: ``files_processed``, ``files_skipped``,
        ``edges_found``, ``errors``.
    """
    indexed_files = get_indexed_files(index_name)

    drop_deps_table(index_name)
    create_deps_table(index_name)

    all_edges: list[DependencyEdge] = []
    files_processed = 0
    files_skipped = 0
    edges_found = 0
    errors = 0

    for filename, language_id in indexed_files:
        extractor = get_extractor(language_id)

        if extractor is None:
            logger.info(
                "No extractor for language_id=%s, skipping %s",
                language_id,
                filename,
            )
            files_skipped += 1
            continue

        file_path = os.path.join(codebase_path, filename)

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except OSError as exc:
            logger.warning("Could not read %s: %s", file_path, exc)
            errors += 1
            continue

        try:
            edges = extractor.extract(filename, content)
        except Exception as exc:
            logger.warning("Extraction failed for %s: %s", filename, exc)
            errors += 1
            continue

        for edge in edges:
            edge.source_file = filename

        all_edges.extend(edges)
        files_processed += 1
        edges_found += len(edges)

    _resolve_all_edges(all_edges, indexed_files)

    insert_edges(index_name, all_edges)

    logger.info(
        "Dependency extraction complete: %d files processed, "
        "%d skipped, %d edges found, %d errors",
        files_processed,
        files_skipped,
        edges_found,
        errors,
    )

    return {
        "files_processed": files_processed,
        "files_skipped": files_skipped,
        "edges_found": edges_found,
        "errors": errors,
    }
