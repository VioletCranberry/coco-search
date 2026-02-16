"""Parse failure tracking for indexed files.

Detects tree-sitter parse status for each file after indexing completes.
Stores results in a per-index parse_results table for stats and diagnostics.

Parse status categories:
- ok: Clean parse, no ERROR nodes in tree
- partial: Tree produced but with ERROR nodes (chunks still extracted)
- error: Total failure (exception during parsing)
- no_grammar: No tree-sitter grammar available for this language
"""

import logging
from pathlib import Path

import psycopg
from tree_sitter_language_pack import get_parser as pack_get_parser

from cocosearch.indexer.symbols import LANGUAGE_MAP
from cocosearch.handlers import get_registered_grammars
from cocosearch.validation import validate_index_name

logger = logging.getLogger(__name__)

# Extensions/language IDs that are indexed as plain text — no tree-sitter grammar
# exists or parse health is meaningless. Excluded from parse tracking entirely.
_SKIP_PARSE_EXTENSIONS = frozenset(
    {
        "md",
        "mdx",
        "txt",
        "rst",
        "csv",
        "json",
        "yaml",
        "yml",
        "toml",
        "xml",
        "html",
        "css",
        "svg",
        "lock",
        "ini",
        "cfg",
        "conf",
        "env",
        "properties",
        # Language handlers without a tree-sitter grammar
        "gotmpl",
    }
)

# Grammar handler names — these files get domain-specific chunking, not tree-sitter parsing
_GRAMMAR_NAMES = frozenset(g.GRAMMAR_NAME for g in get_registered_grammars())


def detect_parse_status(file_content: str, language_ext: str) -> tuple[str, str | None]:
    """Detect parse status for a file using tree-sitter.

    Args:
        file_content: Full file content as string.
        language_ext: File extension (e.g., "py", "ts", "go").

    Returns:
        Tuple of (status, error_message):
        - ("ok", None) - clean parse, no ERROR nodes
        - ("partial", "ERROR nodes at lines: 5, 12") - tree produced but with errors
        - ("error", "Exception: ...") - total failure
        - ("no_grammar", None) - language not in LANGUAGE_MAP
    """
    ts_language = LANGUAGE_MAP.get(language_ext)
    if ts_language is None:
        return ("no_grammar", None)

    try:
        parser = pack_get_parser(ts_language)
        tree = parser.parse(bytes(file_content, "utf8"))

        if not tree.root_node.has_error:
            return ("ok", None)

        # Collect ERROR node locations for diagnostics
        error_lines = _collect_error_lines(tree.root_node)
        error_msg = (
            f"ERROR nodes at lines: {', '.join(str(line) for line in error_lines[:10])}"
        )
        if len(error_lines) > 10:
            error_msg += f" (+{len(error_lines) - 10} more)"

        return ("partial", error_msg)

    except Exception as e:
        return ("error", str(e))


def _collect_error_lines(node) -> list[int]:
    """Recursively find all ERROR and MISSING node line numbers.

    Args:
        node: Tree-sitter node to walk.

    Returns:
        Sorted list of 1-indexed line numbers where errors were found.
    """
    lines = []
    if node.is_error or node.is_missing:
        lines.append(node.start_point[0] + 1)  # 1-indexed
    for child in node.children:
        lines.extend(_collect_error_lines(child))
    return sorted(lines)


def track_parse_results(
    conn: psycopg.Connection,
    index_name: str,
    codebase_path: str,
    table_name: str,
) -> dict:
    """Track parse status for all indexed files.

    Main orchestration function called from run_index() after flow.update().
    Queries the chunks table for distinct files, reads each from disk,
    runs tree-sitter parse detection, and stores results.

    Args:
        conn: PostgreSQL connection.
        index_name: Index name (used for parse_results table naming).
        codebase_path: Absolute path to the codebase root.
        table_name: Name of the chunks table to query for indexed files.

    Returns:
        Summary dict: {"total_files": N, "ok": N, "partial": N, "error": N, "no_grammar": N}
    """
    # Query chunks table for distinct indexed files
    with conn.cursor() as cur:
        cur.execute(f"SELECT DISTINCT filename, language_id FROM {table_name}")
        files = cur.fetchall()

    results = []
    summary = {"total_files": 0, "ok": 0, "partial": 0, "error": 0, "no_grammar": 0}

    for filename, language_id in files:
        # Skip text-only formats — no tree-sitter grammar, parse health is meaningless
        if language_id in _SKIP_PARSE_EXTENSIONS:
            continue
        # Skip grammar-handled files — they use domain-specific chunking, not tree-sitter
        if language_id in _GRAMMAR_NAMES:
            continue

        summary["total_files"] += 1

        # Read file content from disk
        file_path = Path(codebase_path) / filename
        if not file_path.is_file():
            # File deleted from disk but chunks remain in DB (stale index)
            # — skip silently rather than reporting a false error
            continue
        try:
            file_content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            # File exists but unreadable — record as error
            results.append(
                {
                    "file_path": filename,
                    "language": language_id,
                    "parse_status": "error",
                    "error_message": f"Read error: {e}",
                }
            )
            summary["error"] += 1
            continue

        # Detect parse status
        status, error_message = detect_parse_status(file_content, language_id)

        # Map extension to tree-sitter language name for storage
        # For languages without a grammar, store the language_id as-is
        ts_language = LANGUAGE_MAP.get(language_id, language_id)

        results.append(
            {
                "file_path": filename,
                "language": ts_language,
                "parse_status": status,
                "error_message": error_message,
            }
        )
        summary[status] += 1

    # Persist results
    rebuild_parse_results(conn, index_name, results)

    logger.info(
        f"Parse tracking complete for '{index_name}': "
        f"{summary['total_files']} files, "
        f"{summary['ok']} ok, {summary['partial']} partial, "
        f"{summary['error']} error, {summary['no_grammar']} no_grammar"
    )

    return summary


def rebuild_parse_results(
    conn: psycopg.Connection,
    index_name: str,
    results: list[dict],
) -> None:
    """Truncate and rebuild parse results for an index.

    Matches CONTEXT.md decision: rebuild on each index run, always reflects
    current state.

    Args:
        conn: PostgreSQL connection.
        index_name: Index name.
        results: List of dicts with file_path, language, parse_status, error_message.
    """
    validate_index_name(index_name)
    parse_table = f"cocosearch_parse_results_{index_name}"

    with conn.cursor() as cur:
        # Truncate existing results
        cur.execute(f"TRUNCATE TABLE {parse_table}")

        # Batch insert all results
        if results:
            cur.executemany(
                f"INSERT INTO {parse_table} (file_path, language, parse_status, error_message) "
                f"VALUES (%s, %s, %s, %s)",
                [
                    (
                        r["file_path"],
                        r["language"],
                        r["parse_status"],
                        r["error_message"],
                    )
                    for r in results
                ],
            )

    conn.commit()
