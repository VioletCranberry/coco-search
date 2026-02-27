"""Extraction orchestrator for dependency graph construction.

Runs language-specific dependency extractors over all indexed files,
collecting edges and batch-inserting them into the deps table.
After extraction, delegates module resolution to language-specific
resolvers (see ``resolver.py``), so that both forward
(get_dependencies) and reverse (get_dependents) queries work.

Supports incremental extraction: only re-extracts files whose content
has changed (via SHA-256 hashing), while re-resolving ALL edges to
maintain correctness.
"""

import hashlib
import json
import logging
import os

from cocosearch.deps.db import (
    create_deps_table,
    create_tracking_table,
    get_stored_hashes,
    insert_edges,
    read_edges_excluding,
    truncate_deps_table,
    update_tracking,
)
from cocosearch.deps.models import DependencyEdge
from cocosearch.deps.registry import get_extractor
from cocosearch.deps.resolver import get_resolver
from cocosearch.management.metadata import set_deps_extracted_at
from cocosearch.search.db import get_connection_pool, get_table_name

logger = logging.getLogger(__name__)


def _get_cs_log():
    from cocosearch.logging import cs_log

    return cs_log


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
    extra_edges: list[DependencyEdge] = []

    for resolver, lang_ids in resolver_map.values():
        module_index = resolver.build_index(indexed_files)
        has_resolve_many = hasattr(resolver, "resolve_many")

        for edge in all_edges:
            if edge.target_file is not None:
                continue
            source_lang = file_lang.get(edge.source_file)
            if source_lang not in lang_ids:
                continue

            # Use resolve_many when available (e.g., directory expansion)
            if has_resolve_many:
                targets = resolver.resolve_many(edge, module_index)
                if targets:
                    edge.target_file = targets[0]
                    for extra_target in targets[1:]:
                        extra_edges.append(
                            DependencyEdge(
                                source_file=edge.source_file,
                                source_symbol=edge.source_symbol,
                                target_file=extra_target,
                                target_symbol=edge.target_symbol,
                                dep_type=edge.dep_type,
                                metadata=dict(edge.metadata),
                            )
                        )
            else:
                resolved = resolver.resolve(edge, module_index)
                if resolved is not None:
                    edge.target_file = resolved

    all_edges.extend(extra_edges)


def _compute_file_hashes(
    indexed_files: list[tuple[str, str]],
    codebase_path: str,
) -> dict[str, tuple[str, str]]:
    """Compute SHA-256 hashes for indexed files.

    Args:
        indexed_files: List of (filename, language_id) tuples.
        codebase_path: Absolute path to the codebase root directory.

    Returns:
        Dict mapping filename to (content_hash, language_id).
        Files that can't be read are excluded.
    """
    result: dict[str, tuple[str, str]] = {}
    for filename, language_id in indexed_files:
        file_path = os.path.join(codebase_path, filename)
        try:
            with open(file_path, "rb") as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()
            result[filename] = (content_hash, language_id)
        except OSError:
            pass
    return result


def _diff_file_hashes(
    current: dict[str, tuple[str, str]],
    stored: dict[str, str],
) -> tuple[set[str], set[str], set[str]]:
    """Compare current vs stored hashes.

    Args:
        current: Dict mapping filename to (content_hash, language_id).
        stored: Dict mapping filename to content_hash.

    Returns:
        Tuple of (changed_files, added_files, deleted_files).
    """
    current_files = set(current.keys())
    stored_files = set(stored.keys())

    added = current_files - stored_files
    deleted = stored_files - current_files
    changed = {f for f in current_files & stored_files if current[f][0] != stored[f]}

    return changed, added, deleted


def _deduplicate_edges(edges: list[DependencyEdge]) -> list[DependencyEdge]:
    """Collapse expanded edges back to originals before re-resolution.

    Edges from resolve_many (e.g., Markdown directory expansion) create
    additional edges in the DB. When read back with target_file cleared,
    they become identical to originals. Dedup prevents proliferation.
    """
    seen: set[tuple] = set()
    result: list[DependencyEdge] = []

    for edge in edges:
        key = (
            edge.source_file,
            edge.source_symbol,
            edge.target_symbol,
            edge.dep_type,
            json.dumps(edge.metadata, sort_keys=True),
        )
        if key not in seen:
            seen.add(key)
            result.append(edge)

    return result


def _extract_files(
    files: list[tuple[str, str]],
    codebase_path: str,
) -> tuple[list[DependencyEdge], int, int, int, int]:
    """Extract dependency edges from a list of files.

    Args:
        files: List of (filename, language_id) tuples to extract.
        codebase_path: Absolute path to the codebase root directory.

    Returns:
        Tuple of (edges, files_processed, files_skipped, edges_found, errors).
    """
    all_edges: list[DependencyEdge] = []
    files_processed = 0
    files_skipped = 0
    edges_found = 0
    errors = 0

    for filename, language_id in files:
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

    return all_edges, files_processed, files_skipped, edges_found, errors


def extract_dependencies(
    index_name: str, codebase_path: str, *, fresh: bool = False
) -> dict:
    """Extract dependency edges from all indexed files and store them.

    Supports incremental extraction: on subsequent runs, only files whose
    content has changed are re-extracted. All edges are then re-resolved
    to maintain correctness (new files may resolve previously unresolved
    imports). Use ``fresh=True`` to force a full extraction.

    Args:
        index_name: The index name to extract dependencies for.
        codebase_path: Absolute path to the codebase root directory.
        fresh: If True, ignore tracking and re-extract everything.

    Returns:
        Stats dict with keys: ``files_processed``, ``files_skipped``,
        ``edges_found``, ``errors``, ``incremental``, ``files_unchanged``.
    """
    _get_cs_log().deps(
        "Dependency extraction started", index=index_name, path=codebase_path
    )

    indexed_files = get_indexed_files(index_name)

    create_deps_table(index_name)
    create_tracking_table(index_name)

    # Determine if incremental extraction is possible
    stored_hashes: dict[str, str] = {}
    if not fresh:
        try:
            stored_hashes = get_stored_hashes(index_name)
        except Exception:
            # Table might be empty or not populated yet
            stored_hashes = {}

    is_full_run = fresh or not stored_hashes

    if is_full_run:
        # Full extraction: process all files
        all_edges, files_processed, files_skipped, edges_found, errors = _extract_files(
            indexed_files, codebase_path
        )

        _resolve_all_edges(all_edges, indexed_files)

        truncate_deps_table(index_name)
        insert_edges(index_name, all_edges)

        # Update tracking with current hashes
        current_hashes = _compute_file_hashes(indexed_files, codebase_path)
        update_tracking(index_name, current_hashes)

        try:
            set_deps_extracted_at(index_name)
        except Exception:
            pass  # Best-effort — don't break extraction on metadata failure

        _get_cs_log().deps(
            "Dependency extraction completed (full)",
            files_processed=files_processed,
            edges=len(all_edges),
            errors=errors,
        )

        return {
            "files_processed": files_processed,
            "files_skipped": files_skipped,
            "edges_found": len(all_edges),
            "errors": errors,
            "incremental": False,
            "files_unchanged": 0,
        }

    # Incremental extraction
    current_hashes = _compute_file_hashes(indexed_files, codebase_path)
    changed, added, deleted = _diff_file_hashes(current_hashes, stored_hashes)

    dirty_files = changed | added

    if not dirty_files and not deleted:
        # Nothing changed — early return
        _get_cs_log().deps(
            "Dependency extraction skipped (no changes)",
            files_unchanged=len(indexed_files),
        )

        return {
            "files_processed": 0,
            "files_skipped": 0,
            "edges_found": 0,
            "errors": 0,
            "incremental": True,
            "files_unchanged": len(current_hashes),
        }

    # Read existing edges, excluding those from changed/deleted files
    exclude_sources = dirty_files | deleted
    existing_edges = read_edges_excluding(index_name, exclude_sources)

    # Extract new edges for changed + added files
    files_to_extract = [(f, lang) for f, lang in indexed_files if f in dirty_files]
    new_edges, files_processed, files_skipped, edges_found, errors = _extract_files(
        files_to_extract, codebase_path
    )

    # Combine existing + new edges
    all_edges = existing_edges + new_edges

    # Clear target_file on ALL edges for re-resolution
    for edge in all_edges:
        edge.target_file = None

    # Deduplicate (collapse resolve_many expansions from DB read-back)
    all_edges = _deduplicate_edges(all_edges)

    # Re-resolve all edges
    _resolve_all_edges(all_edges, indexed_files)

    # Replace all edges in DB
    truncate_deps_table(index_name)
    insert_edges(index_name, all_edges)

    # Update tracking
    update_tracking(index_name, current_hashes)

    try:
        set_deps_extracted_at(index_name)
    except Exception:
        pass  # Best-effort — don't break extraction on metadata failure

    files_unchanged = len(current_hashes) - len(dirty_files)

    _get_cs_log().deps(
        "Dependency extraction completed (incremental)",
        files_processed=files_processed,
        files_changed=len(changed),
        files_added=len(added),
        files_deleted=len(deleted),
        edges=len(all_edges),
        errors=errors,
    )

    return {
        "files_processed": files_processed,
        "files_skipped": files_skipped,
        "edges_found": len(all_edges),
        "errors": errors,
        "incremental": True,
        "files_unchanged": files_unchanged,
    }
