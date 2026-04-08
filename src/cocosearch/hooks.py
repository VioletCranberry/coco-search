"""Git hook management for CocoSearch auto-reindex.

Installs post-checkout, post-merge, post-commit, and post-rewrite hooks into
the repo's main hooks directory (``$(git rev-parse --git-common-dir)/hooks``).
Each hook fires ``cocosearch index . --deps --if-exists --quiet`` in the
background so the user's git operations are never blocked.

Design notes:
    * Hook files are marker-wrapped so we can append to existing hooks (husky,
      pre-commit, lefthook) without clobbering their content. The ``install``
      operation is idempotent — repeated runs produce the same content.
    * Worktree-safe: we resolve the main repo's hooks dir via
      ``git rev-parse --git-common-dir`` so one install covers all worktrees.
    * Fail-silent: installed hooks no-op when ``cocosearch`` is not on PATH.
      The git operation never fails because of us.
    * Uninstall removes only the marker block and deletes the file if nothing
      else is left (aside from a shebang line).
"""

from __future__ import annotations

import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Markers that delimit the CocoSearch-managed section in each hook file.
# If you change these, existing installations will be treated as foreign
# content on the next upgrade — so keep them stable.
MARKER_START = "# >>> cocosearch auto-reindex >>>"
MARKER_END = "# <<< cocosearch auto-reindex <<<"

# Hooks we manage. Each entry maps hook name → shell snippet that fires a
# background reindex when appropriate for that event.
#
# `post-checkout` receives: $1=prev_head $2=new_head $3=branch_flag
#   branch_flag=1 for branch checkout, 0 for file checkout. We only react
#   to branch checkouts to avoid spurious runs on `git checkout -- file`.
_HOOK_BODIES: dict[str, str] = {
    "post-checkout": (
        'if [ "$3" = "1" ] && command -v cocosearch >/dev/null 2>&1; then\n'
        '    (cd "$(git rev-parse --show-toplevel)" && '
        "nohup cocosearch index . --deps --if-exists --quiet "
        ">/dev/null 2>&1 &) || true\n"
        "fi"
    ),
    "post-merge": (
        "if command -v cocosearch >/dev/null 2>&1; then\n"
        '    (cd "$(git rev-parse --show-toplevel)" && '
        "nohup cocosearch index . --deps --if-exists --quiet "
        ">/dev/null 2>&1 &) || true\n"
        "fi"
    ),
    "post-commit": (
        "if command -v cocosearch >/dev/null 2>&1; then\n"
        '    (cd "$(git rev-parse --show-toplevel)" && '
        "nohup cocosearch index . --deps --if-exists --quiet "
        ">/dev/null 2>&1 &) || true\n"
        "fi"
    ),
    "post-rewrite": (
        "if command -v cocosearch >/dev/null 2>&1; then\n"
        '    (cd "$(git rev-parse --show-toplevel)" && '
        "nohup cocosearch index . --deps --if-exists --quiet "
        ">/dev/null 2>&1 &) || true\n"
        "fi"
    ),
}

HOOK_NAMES = tuple(_HOOK_BODIES.keys())
_SHEBANG = "#!/bin/sh"


class HooksError(Exception):
    """Raised when hook installation/uninstallation cannot proceed."""


@dataclass
class HookStatus:
    """Per-hook installation state reported by ``status``."""

    name: str
    path: Path
    installed: bool  # cocosearch markers present
    has_other_content: bool  # file has non-marker content besides shebang
    foreign_manager: str | None = None  # "husky" | "pre-commit" | "lefthook" | None


# ---------------------------------------------------------------------------
# Git discovery
# ---------------------------------------------------------------------------


def get_hooks_dir(project_path: Path | None = None) -> Path:
    """Return the shared hooks directory for the containing git repo.

    Uses ``git rev-parse --git-common-dir`` so worktrees share one install.

    Raises:
        HooksError: If the path is not inside a git repository.
    """
    base = project_path or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "-C", str(base), "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise HooksError(
            f"Not inside a git repository (or git not found): {base}"
        ) from e

    git_common = Path(result.stdout.strip())
    if not git_common.is_absolute():
        git_common = (base / git_common).resolve()
    return git_common / "hooks"


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------


def _managed_block(hook_name: str) -> str:
    """Return the complete marker-wrapped block for a hook."""
    body = _HOOK_BODIES[hook_name]
    return f"{MARKER_START}\n{body}\n{MARKER_END}\n"


def _strip_existing_block(content: str) -> str:
    """Return *content* with any existing cocosearch-managed block removed."""
    start = content.find(MARKER_START)
    if start == -1:
        return content
    end = content.find(MARKER_END, start)
    if end == -1:
        # Malformed — treat rest of file as ours to clean up.
        return content[:start].rstrip() + "\n"
    end_after = end + len(MARKER_END)
    # Also consume the trailing newline if present.
    if end_after < len(content) and content[end_after] == "\n":
        end_after += 1
    return (content[:start] + content[end_after:]).rstrip() + "\n"


def _is_effectively_empty(content: str) -> bool:
    """Return True if content has no useful lines beyond a shebang."""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#!"):
            continue
        return False
    return True


def _detect_foreign_manager(content: str) -> str | None:
    """Return the name of a detected foreign hook manager, if any."""
    lowered = content.lower()
    if "husky" in lowered:
        return "husky"
    if "pre-commit" in lowered and "sourceforge" not in lowered:
        return "pre-commit"
    if "lefthook" in lowered:
        return "lefthook"
    return None


def _ensure_executable(path: Path) -> None:
    """Set +x on owner/group/other for the given file, if it exists."""
    if not path.exists():
        return
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


# ---------------------------------------------------------------------------
# Public operations
# ---------------------------------------------------------------------------


@dataclass
class InstallResult:
    hooks_dir: Path
    installed: list[str]
    updated: list[str]  # had our markers already; block was replaced
    coexisted_with: list[str]  # hook name → detected foreign manager


def install_hooks(project_path: Path | None = None) -> InstallResult:
    """Install/refresh CocoSearch hooks in the repo's shared hooks dir.

    Idempotent: running this twice produces the same result. Existing hooks
    from other managers are preserved — we append our marker block to them.
    """
    hooks_dir = get_hooks_dir(project_path)
    hooks_dir.mkdir(parents=True, exist_ok=True)

    installed: list[str] = []
    updated: list[str] = []
    coexisted: list[str] = []

    for hook_name in HOOK_NAMES:
        hook_path = hooks_dir / hook_name
        managed = _managed_block(hook_name)

        if hook_path.exists():
            existing = hook_path.read_text()
            has_marker = MARKER_START in existing
            if has_marker:
                # Replace our block in place.
                new_content = _strip_existing_block(existing).rstrip() + "\n"
                new_content += managed
                updated.append(hook_name)
            else:
                foreign = _detect_foreign_manager(existing)
                if foreign:
                    coexisted.append(f"{hook_name}:{foreign}")
                # Append our block after existing content.
                if not existing.endswith("\n"):
                    existing += "\n"
                new_content = existing + managed
                installed.append(hook_name)
        else:
            new_content = f"{_SHEBANG}\n{managed}"
            installed.append(hook_name)

        hook_path.write_text(new_content)
        _ensure_executable(hook_path)

    return InstallResult(
        hooks_dir=hooks_dir,
        installed=installed,
        updated=updated,
        coexisted_with=coexisted,
    )


@dataclass
class UninstallResult:
    hooks_dir: Path
    removed: list[str]  # block removed, file kept (had other content)
    deleted: list[str]  # file deleted entirely
    skipped: list[str]  # hook not present or no markers


def uninstall_hooks(project_path: Path | None = None) -> UninstallResult:
    """Remove the CocoSearch marker block from each managed hook."""
    hooks_dir = get_hooks_dir(project_path)
    removed: list[str] = []
    deleted: list[str] = []
    skipped: list[str] = []

    for hook_name in HOOK_NAMES:
        hook_path = hooks_dir / hook_name
        if not hook_path.exists():
            skipped.append(hook_name)
            continue
        existing = hook_path.read_text()
        if MARKER_START not in existing:
            skipped.append(hook_name)
            continue

        new_content = _strip_existing_block(existing)
        if _is_effectively_empty(new_content):
            hook_path.unlink()
            deleted.append(hook_name)
        else:
            hook_path.write_text(new_content)
            removed.append(hook_name)

    return UninstallResult(
        hooks_dir=hooks_dir,
        removed=removed,
        deleted=deleted,
        skipped=skipped,
    )


def hook_status(project_path: Path | None = None) -> list[HookStatus]:
    """Report per-hook installation state.

    Returns a list (one entry per managed hook, even if not installed).
    """
    hooks_dir = get_hooks_dir(project_path)
    statuses: list[HookStatus] = []
    for hook_name in HOOK_NAMES:
        hook_path = hooks_dir / hook_name
        if not hook_path.exists():
            statuses.append(
                HookStatus(
                    name=hook_name,
                    path=hook_path,
                    installed=False,
                    has_other_content=False,
                    foreign_manager=None,
                )
            )
            continue
        content = hook_path.read_text()
        installed = MARKER_START in content
        stripped = _strip_existing_block(content) if installed else content
        has_other = not _is_effectively_empty(stripped)
        foreign = _detect_foreign_manager(stripped) if has_other else None
        statuses.append(
            HookStatus(
                name=hook_name,
                path=hook_path,
                installed=installed,
                has_other_content=has_other,
                foreign_manager=foreign,
            )
        )
    return statuses
