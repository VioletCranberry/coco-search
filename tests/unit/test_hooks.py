"""Unit tests for cocosearch.hooks — git hook install/uninstall/status."""

import stat
import subprocess
from pathlib import Path

import pytest

from cocosearch import hooks
from cocosearch.hooks import (
    HOOK_NAMES,
    MARKER_END,
    MARKER_START,
    HooksError,
    hook_status,
    install_hooks,
    uninstall_hooks,
)


def _run_git_init(path: Path) -> None:
    """Initialize a fresh git repo at *path*."""
    subprocess.run(
        ["git", "init", "--quiet", str(path)],
        capture_output=True,
        check=True,
    )


@pytest.fixture
def git_repo(tmp_path):
    """A pristine git repo at a temp directory."""
    _run_git_init(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# get_hooks_dir
# ---------------------------------------------------------------------------


class TestGetHooksDir:
    def test_returns_hooks_dir_in_main_checkout(self, git_repo):
        d = hooks.get_hooks_dir(git_repo)
        assert d == (git_repo / ".git" / "hooks").resolve()

    def test_raises_outside_git_repo(self, tmp_path):
        # tmp_path is not a git repo
        with pytest.raises(HooksError):
            hooks.get_hooks_dir(tmp_path)


# ---------------------------------------------------------------------------
# install_hooks
# ---------------------------------------------------------------------------


class TestInstallHooks:
    def test_fresh_install_creates_all_hooks(self, git_repo):
        result = install_hooks(git_repo)

        assert result.hooks_dir.exists()
        for hook_name in HOOK_NAMES:
            p = result.hooks_dir / hook_name
            assert p.exists(), f"{hook_name} should have been created"
            content = p.read_text()
            assert MARKER_START in content
            assert MARKER_END in content
            # Executable for owner
            mode = p.stat().st_mode
            assert mode & stat.S_IXUSR

        assert sorted(result.installed) == sorted(HOOK_NAMES)
        assert result.updated == []
        assert result.coexisted_with == []

    def test_install_is_idempotent(self, git_repo):
        install_hooks(git_repo)
        first_contents = {
            h: (git_repo / ".git" / "hooks" / h).read_text() for h in HOOK_NAMES
        }
        install_hooks(git_repo)
        second_contents = {
            h: (git_repo / ".git" / "hooks" / h).read_text() for h in HOOK_NAMES
        }
        assert first_contents == second_contents

    def test_install_appends_to_existing_hook(self, git_repo):
        """Existing hook content is preserved; our block is appended."""
        hooks_dir = git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        existing = "#!/bin/sh\necho 'user custom hook'\nexit 0\n"
        (hooks_dir / "post-commit").write_text(existing)

        result = install_hooks(git_repo)

        final = (hooks_dir / "post-commit").read_text()
        # Original content preserved
        assert "echo 'user custom hook'" in final
        # Our markers present
        assert MARKER_START in final
        assert MARKER_END in final
        # Our block comes AFTER the existing content
        assert final.find("echo 'user custom hook'") < final.find(MARKER_START)
        assert "post-commit" in result.installed

    def test_install_replaces_existing_marker_block(self, git_repo):
        """Re-install cleanly replaces the marker block without duplication."""
        install_hooks(git_repo)
        first = (git_repo / ".git" / "hooks" / "post-commit").read_text()
        # Manually tamper: add extra marker content outside the block
        tampered = first.replace(MARKER_START, "# rogue marker\n" + MARKER_START)
        (git_repo / ".git" / "hooks" / "post-commit").write_text(tampered)

        result = install_hooks(git_repo)
        second = (git_repo / ".git" / "hooks" / "post-commit").read_text()

        # Still exactly one marker block
        assert second.count(MARKER_START) == 1
        assert second.count(MARKER_END) == 1
        assert "post-commit" in result.updated

    def test_detects_husky_coexistence(self, git_repo):
        """Appending to a husky-managed hook is reported."""
        hooks_dir = git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        (hooks_dir / "post-commit").write_text(
            '#!/bin/sh\n. "$(dirname -- "$0")/_/husky.sh"\n'
        )

        result = install_hooks(git_repo)
        coexist_entries = [
            e for e in result.coexisted_with if e.startswith("post-commit")
        ]
        assert any("husky" in e for e in coexist_entries)


# ---------------------------------------------------------------------------
# uninstall_hooks
# ---------------------------------------------------------------------------


class TestUninstallHooks:
    def test_uninstall_removes_created_files(self, git_repo):
        """Hooks that we created ourselves (shebang + block only) get deleted."""
        install_hooks(git_repo)
        result = uninstall_hooks(git_repo)

        for hook_name in HOOK_NAMES:
            p = git_repo / ".git" / "hooks" / hook_name
            assert not p.exists(), f"{hook_name} should be gone"
        assert sorted(result.deleted) == sorted(HOOK_NAMES)
        assert result.removed == []

    def test_uninstall_preserves_other_content(self, git_repo):
        """Hooks that had pre-existing user content keep it; our block is gone."""
        hooks_dir = git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        user_content = "#!/bin/sh\necho 'user hook'\nexit 0\n"
        (hooks_dir / "post-commit").write_text(user_content)

        install_hooks(git_repo)
        result = uninstall_hooks(git_repo)

        final = (hooks_dir / "post-commit").read_text()
        assert "user hook" in final
        assert MARKER_START not in final
        assert MARKER_END not in final
        assert "post-commit" in result.removed
        # Other hooks were ours-only → deleted
        assert "post-checkout" in result.deleted

    def test_uninstall_noop_when_absent(self, git_repo):
        """Uninstall is safe when no hooks were installed."""
        result = uninstall_hooks(git_repo)
        assert result.removed == []
        assert result.deleted == []
        assert sorted(result.skipped) == sorted(HOOK_NAMES)


# ---------------------------------------------------------------------------
# hook_status
# ---------------------------------------------------------------------------


class TestHookStatus:
    def test_all_absent_initially(self, git_repo):
        statuses = hook_status(git_repo)
        assert len(statuses) == len(HOOK_NAMES)
        assert all(not s.installed for s in statuses)
        assert all(not s.has_other_content for s in statuses)

    def test_reports_installed_after_install(self, git_repo):
        install_hooks(git_repo)
        statuses = hook_status(git_repo)
        assert all(s.installed for s in statuses)
        # Since we created the files, no other content
        assert all(not s.has_other_content for s in statuses)

    def test_reports_coexistence(self, git_repo):
        hooks_dir = git_repo / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        (hooks_dir / "post-commit").write_text(
            '#!/bin/sh\n. "$(dirname -- "$0")/_/husky.sh"\n'
        )
        install_hooks(git_repo)

        statuses = {s.name: s for s in hook_status(git_repo)}
        pc = statuses["post-commit"]
        assert pc.installed is True
        assert pc.has_other_content is True
        assert pc.foreign_manager == "husky"
