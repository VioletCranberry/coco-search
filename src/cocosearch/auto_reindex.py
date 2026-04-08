"""Shared auto-reindex core.

Drift detection and trigger logic reused by all three auto-update layers:
- MCP server auto-reindex watchdog (polls this on a daemon thread)
- `cocosearch hooks` installed git hooks (shell out to `cocosearch index`)
- `cocosearch watch` foreground command (uses FlowLiveUpdater + deps refresh)

This module deliberately has no side effects at import time and no global
state beyond a module-level lock that standalone callers can use when they
don't have their own registry.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable

from cocosearch.indexer import IndexingConfig, run_index
from cocosearch.logging import cs_log
from cocosearch.management.stats import check_branch_staleness
from cocosearch.search.db import get_connection_pool
from cocosearch.validation import validate_index_name

# Lock used by standalone callers (CLI, watch command) when they don't supply
# their own. The MCP server passes its existing _indexing_lock instead so the
# watchdog and /api/reindex share one coordination point.
_module_lock = threading.Lock()
_module_active: dict[str, tuple[threading.Thread, threading.Event]] = {}


@dataclass
class DriftReport:
    """Result of a drift detection check."""

    should_reindex: bool
    reason: str  # "in_sync" | "branch_changed" | "commits_changed" | "no_metadata"
    indexed_branch: str | None
    indexed_commit: str | None
    current_branch: str | None
    current_commit: str | None


def detect_drift(index_name: str, project_path: str | None = None) -> DriftReport:
    """Check whether current git state differs from the indexed state.

    Wraps ``check_branch_staleness`` into a structured report. ``should_reindex``
    is True when the branch name OR commit hash has changed. When the index has
    no metadata yet (never indexed or metadata table absent), returns
    ``should_reindex=False, reason="no_metadata"`` — we don't auto-create indexes.
    """
    info = check_branch_staleness(index_name, project_path)

    indexed_branch = info.get("indexed_branch")
    indexed_commit = info.get("indexed_commit")
    current_branch = info.get("current_branch")
    current_commit = info.get("current_commit")
    branch_changed = bool(info.get("branch_changed"))
    commits_changed = bool(info.get("commits_changed"))

    # No metadata recorded → don't auto-trigger. Let the user run `index` first.
    if indexed_commit is None and indexed_branch is None:
        return DriftReport(
            should_reindex=False,
            reason="no_metadata",
            indexed_branch=indexed_branch,
            indexed_commit=indexed_commit,
            current_branch=current_branch,
            current_commit=current_commit,
        )

    if branch_changed:
        reason = "branch_changed"
    elif commits_changed:
        reason = "commits_changed"
    else:
        reason = "in_sync"

    return DriftReport(
        should_reindex=branch_changed or commits_changed,
        reason=reason,
        indexed_branch=indexed_branch,
        indexed_commit=indexed_commit,
        current_branch=current_branch,
        current_commit=current_commit,
    )


def has_deps_table(index_name: str) -> bool:
    """Return True if ``cocosearch_deps_{index_name}`` exists in the database.

    Used to decide whether to re-run dependency extraction after an incremental
    reindex. Only indexes that were originally built with ``--deps`` get their
    deps auto-refreshed.
    """
    try:
        validate_index_name(index_name)
        pool = get_connection_pool()
        deps_table = f"cocosearch_deps_{index_name}"
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name = %s
                    )
                    """,
                    (deps_table,),
                )
                row = cur.fetchone()
                return bool(row and row[0])
    except Exception as e:
        cs_log.index(
            "has_deps_table check failed",
            level="DEBUG",
            index=index_name,
            error=str(e),
        )
        return False


def run_reindex_sync(
    index_name: str,
    project_path: str,
    *,
    fresh: bool = False,
    include_deps: bool = True,
) -> dict[str, Any]:
    """Run an incremental reindex synchronously, optionally refreshing deps.

    This is the in-process equivalent of `cocosearch index . [--deps]`, minus
    the Rich progress UI. Used by the MCP watchdog (inside its daemon thread)
    and by the `cocosearch watch` command's post-batch catch-up step.

    Dependency extraction only runs if ``include_deps`` is True AND the deps
    table already exists for this index. Indexes never built with ``--deps``
    stay fast.

    Returns a result dict with keys: ``success: bool``, ``deps_extracted: bool``,
    ``error: str | None``.
    """
    result: dict[str, Any] = {
        "success": False,
        "deps_extracted": False,
        "error": None,
    }
    try:
        run_index(
            index_name=index_name,
            codebase_path=project_path,
            config=IndexingConfig(),
            fresh=fresh,
        )
        # Refresh metadata (branch/commit) after successful indexing so the
        # next drift check compares against the new HEAD.
        try:
            from cocosearch.config.schema import default_model_for_provider
            from cocosearch.management.git import (
                get_branch_commit_count,
                get_commit_hash,
                get_current_branch,
            )
            from cocosearch.management.metadata import (
                ensure_metadata_table,
                register_index_path,
            )
            import os

            ensure_metadata_table()
            embed_provider = os.environ.get("COCOSEARCH_EMBEDDING_PROVIDER", "ollama")
            embed_model = os.environ.get(
                "COCOSEARCH_EMBEDDING_MODEL",
                default_model_for_provider(embed_provider),
            )
            register_index_path(
                index_name,
                project_path,
                branch=get_current_branch(project_path),
                commit_hash=get_commit_hash(project_path),
                branch_commit_count=get_branch_commit_count(project_path),
                embedding_provider=embed_provider,
                embedding_model=embed_model,
            )
        except Exception as meta_err:
            cs_log.index(
                "post-reindex metadata refresh failed",
                level="WARNING",
                index=index_name,
                error=str(meta_err),
            )

        if include_deps and has_deps_table(index_name):
            try:
                from cocosearch.deps.extractor import extract_dependencies

                extract_dependencies(index_name, project_path)
                result["deps_extracted"] = True
            except Exception as dep_err:
                cs_log.deps(
                    "auto deps extraction failed",
                    level="WARNING",
                    index=index_name,
                    error=str(dep_err),
                )

        result["success"] = True
    except Exception as exc:
        result["error"] = str(exc)
        cs_log.index(
            "auto-reindex failed",
            level="ERROR",
            index=index_name,
            error=str(exc),
        )
    return result


def trigger_reindex(
    index_name: str,
    project_path: str,
    *,
    fresh: bool = False,
    include_deps: bool = True,
    lock: threading.Lock | None = None,
    active_registry: dict[str, tuple[threading.Thread, threading.Event]] | None = None,
    on_complete: Callable[[dict[str, Any]], None] | None = None,
) -> threading.Thread | None:
    """Spin up a daemon thread that runs an incremental reindex.

    The lock + registry are pluggable so the MCP server can pass its existing
    ``_indexing_lock`` and ``_active_indexing`` dict — one reindex at a time per
    index, coordinated with the existing /api/reindex endpoint. Standalone
    callers (CLI, tests) get the module-level defaults.

    If another reindex is already active for ``index_name``, returns None
    without starting a new thread (idempotent under concurrent triggers).

    Returns the spawned thread, or None if we deferred to an existing run.
    """
    use_lock = lock if lock is not None else _module_lock
    use_registry = active_registry if active_registry is not None else _module_active

    with use_lock:
        prev = use_registry.get(index_name)
        if prev is not None:
            prev_thread, _cancel = prev
            if prev_thread.is_alive():
                cs_log.index(
                    "auto-reindex skipped — already running",
                    level="DEBUG",
                    index=index_name,
                )
                return None

        cancel_event = threading.Event()

        def _run() -> None:
            try:
                if cancel_event.is_set():
                    return
                cs_log.index(
                    "auto-reindex started",
                    index=index_name,
                    path=project_path,
                    fresh=fresh,
                )
                # Ensure CocoIndex is initialized (no-op if already done).
                try:
                    import cocoindex

                    cocoindex.init()
                except Exception:
                    pass
                result = run_reindex_sync(
                    index_name,
                    project_path,
                    fresh=fresh,
                    include_deps=include_deps,
                )
                if result["success"]:
                    cs_log.index(
                        "auto-reindex complete",
                        index=index_name,
                        deps_extracted=result["deps_extracted"],
                    )
                if on_complete is not None:
                    try:
                        on_complete(result)
                    except Exception:
                        pass
            finally:
                with use_lock:
                    entry = use_registry.get(index_name)
                    if entry is not None and entry[1] is cancel_event:
                        use_registry.pop(index_name, None)

        thread = threading.Thread(
            target=_run,
            name=f"auto-reindex-{index_name}",
            daemon=True,
        )
        use_registry[index_name] = (thread, cancel_event)
        thread.start()
        return thread
