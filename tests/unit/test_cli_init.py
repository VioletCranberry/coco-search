"""Tests for CLI init command."""

import argparse
import json
from unittest.mock import patch

from cocosearch.cli import init_command
from cocosearch.config import CLAUDE_MD_DUPLICATE_MARKER


def _make_args(**kwargs):
    """Create args namespace with all optional prompts skipped by default."""
    defaults = {"no_claude_md": True, "no_agents_md": True, "no_opencode_mcp": True}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_init_command_creates_config(tmp_path, monkeypatch):
    """Test that init_command creates cocosearch.yaml in cwd."""
    monkeypatch.chdir(tmp_path)
    args = _make_args()

    result = init_command(args)

    assert result == 0

    config_path = tmp_path / "cocosearch.yaml"
    assert config_path.exists()

    content = config_path.read_text()
    assert "# CocoSearch Configuration" in content
    assert "indexing:" in content


def test_init_command_skips_config_if_exists(tmp_path, monkeypatch, capsys):
    """Test that init_command skips cocosearch.yaml if it already exists."""
    monkeypatch.chdir(tmp_path)

    config_path = tmp_path / "cocosearch.yaml"
    config_path.write_text("existing config")

    args = _make_args()

    result = init_command(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "already exists" in captured.out
    # Original content is preserved
    assert config_path.read_text() == "existing config"


def test_init_command_output(tmp_path, monkeypatch, capsys):
    """Test that init_command prints success message."""
    monkeypatch.chdir(tmp_path)
    args = _make_args()

    init_command(args)

    captured = capsys.readouterr()
    assert "Created cocosearch.yaml" in captured.out
    assert "Edit this file" in captured.out


def test_skips_prompt_with_no_claude_md_flag(tmp_path, monkeypatch):
    """Test that --no-claude-md skips the CLAUDE.md prompt entirely."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_claude_md=True)

    with patch("builtins.input") as mock_input:
        result = init_command(args)

    assert result == 0
    mock_input.assert_not_called()


def test_skips_prompt_on_non_tty(tmp_path, monkeypatch):
    """Test that non-TTY stdin skips the CLAUDE.md prompt."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_claude_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = False
        with patch("builtins.input") as mock_input:
            result = init_command(args)

    assert result == 0
    mock_input.assert_not_called()


def test_user_declines_claude_md(tmp_path, monkeypatch):
    """Test that user declining 'n' skips CLAUDE.md creation."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_claude_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", return_value="n"):
            result = init_command(args)

    assert result == 0
    assert not (tmp_path / "CLAUDE.md").exists()


def test_user_accepts_local_claude_md(tmp_path, monkeypatch):
    """Test that user choosing local creates CLAUDE.md in project."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_claude_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "1"]):
            result = init_command(args)

    assert result == 0
    claude_md = tmp_path / "CLAUDE.md"
    assert claude_md.exists()
    assert CLAUDE_MD_DUPLICATE_MARKER in claude_md.read_text()


def test_user_accepts_global_claude_md(tmp_path, monkeypatch):
    """Test that user choosing global creates ~/.claude/CLAUDE.md."""
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fakehome"
    args = _make_args(no_claude_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "2"]):
            with patch("pathlib.Path.home", return_value=fake_home):
                result = init_command(args)

    assert result == 0
    claude_md = fake_home / ".claude" / "CLAUDE.md"
    assert claude_md.exists()
    assert CLAUDE_MD_DUPLICATE_MARKER in claude_md.read_text()


def test_invalid_choice_skips_gracefully(tmp_path, monkeypatch, capsys):
    """Test that invalid location choice skips without error."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_claude_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "3"]):
            result = init_command(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Invalid choice" in captured.out


def test_duplicate_detection_message(tmp_path, monkeypatch, capsys):
    """Test that duplicate marker is detected and reported."""
    monkeypatch.chdir(tmp_path)

    # Pre-create CLAUDE.md with the routing section
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(f"# Project\n\n{CLAUDE_MD_DUPLICATE_MARKER}\n")

    args = _make_args(no_claude_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "1"]):
            result = init_command(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "already present" in captured.out


def test_append_preserves_existing_content(tmp_path, monkeypatch):
    """Test that appending routing preserves existing CLAUDE.md content."""
    monkeypatch.chdir(tmp_path)

    claude_md = tmp_path / "CLAUDE.md"
    existing = "# My Project\n\nImportant instructions here.\n"
    claude_md.write_text(existing)

    args = _make_args(no_claude_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "1"]):
            result = init_command(args)

    assert result == 0
    content = claude_md.read_text()
    assert content.startswith(existing)
    assert CLAUDE_MD_DUPLICATE_MARKER in content


def test_write_error_does_not_fail_command(tmp_path, monkeypatch, capsys):
    """Test that OSError on write still returns 0 (yaml already succeeded)."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_claude_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "1"]):
            with patch(
                "cocosearch.cli.generate_claude_md_routing",
                side_effect=OSError("Permission denied"),
            ):
                result = init_command(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Warning" in captured.out
    assert "Permission denied" in captured.out


def test_existing_config_still_offers_claude_md(tmp_path, monkeypatch):
    """Test that CLAUDE.md prompt is offered even when cocosearch.yaml exists."""
    monkeypatch.chdir(tmp_path)

    # Pre-create cocosearch.yaml
    (tmp_path / "cocosearch.yaml").write_text("existing config")

    args = _make_args(no_claude_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "1"]):
            result = init_command(args)

    assert result == 0
    claude_md = tmp_path / "CLAUDE.md"
    assert claude_md.exists()
    assert CLAUDE_MD_DUPLICATE_MARKER in claude_md.read_text()


def test_default_choice_is_local(tmp_path, monkeypatch):
    """Test that pressing Enter (empty input) defaults to local CLAUDE.md."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_claude_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", ""]):
            result = init_command(args)

    assert result == 0
    claude_md = tmp_path / "CLAUDE.md"
    assert claude_md.exists()
    assert CLAUDE_MD_DUPLICATE_MARKER in claude_md.read_text()


# --- AGENTS.md tests ---


def test_skips_prompt_with_no_agents_md_flag(tmp_path, monkeypatch):
    """Test that --no-agents-md skips the AGENTS.md prompt entirely."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_claude_md=True, no_agents_md=True)

    with patch("builtins.input") as mock_input:
        result = init_command(args)

    assert result == 0
    mock_input.assert_not_called()


def test_user_accepts_local_agents_md(tmp_path, monkeypatch):
    """Test that user choosing local creates AGENTS.md in project."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_claude_md=True, no_agents_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "1"]):
            result = init_command(args)

    assert result == 0
    agents_md = tmp_path / "AGENTS.md"
    assert agents_md.exists()
    assert CLAUDE_MD_DUPLICATE_MARKER in agents_md.read_text()


def test_user_accepts_global_agents_md(tmp_path, monkeypatch):
    """Test that user choosing global creates ~/.config/opencode/AGENTS.md."""
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fakehome"
    args = _make_args(no_claude_md=True, no_agents_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "2"]):
            with patch("pathlib.Path.home", return_value=fake_home):
                result = init_command(args)

    assert result == 0
    agents_md = fake_home / ".config" / "opencode" / "AGENTS.md"
    assert agents_md.exists()
    assert CLAUDE_MD_DUPLICATE_MARKER in agents_md.read_text()


def test_user_declines_agents_md(tmp_path, monkeypatch):
    """Test that user declining 'n' skips AGENTS.md creation."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_claude_md=True, no_agents_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", return_value="n"):
            result = init_command(args)

    assert result == 0
    assert not (tmp_path / "AGENTS.md").exists()


def test_invalid_agents_md_choice_skips_gracefully(tmp_path, monkeypatch, capsys):
    """Test that invalid AGENTS.md location choice skips without error."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_claude_md=True, no_agents_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "3"]):
            result = init_command(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Invalid choice" in captured.out


def test_agents_md_write_error_does_not_fail_command(tmp_path, monkeypatch, capsys):
    """Test that OSError on AGENTS.md write still returns 0."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_claude_md=True, no_agents_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "1"]):
            with patch(
                "cocosearch.cli.generate_agents_md_routing",
                side_effect=OSError("Permission denied"),
            ):
                result = init_command(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Warning" in captured.out
    assert "Permission denied" in captured.out


def test_both_claude_md_and_agents_md_prompts(tmp_path, monkeypatch):
    """Test that both CLAUDE.md and AGENTS.md prompts are offered."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_claude_md=False, no_agents_md=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        # Accepts CLAUDE.md (y, 1), then accepts AGENTS.md (y, 1)
        with patch("builtins.input", side_effect=["y", "1", "y", "1"]):
            result = init_command(args)

    assert result == 0
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "AGENTS.md").exists()


# --- OpenCode MCP registration tests ---


def test_skips_mcp_prompt_with_no_opencode_mcp_flag(tmp_path, monkeypatch):
    """Test that --no-opencode-mcp skips the MCP registration prompt."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_opencode_mcp=True)

    with patch("builtins.input") as mock_input:
        result = init_command(args)

    assert result == 0
    mock_input.assert_not_called()


def test_user_accepts_local_opencode_mcp(tmp_path, monkeypatch):
    """Test that user choosing local creates opencode.json in project."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_opencode_mcp=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "1"]):
            result = init_command(args)

    assert result == 0
    opencode_json = tmp_path / "opencode.json"
    assert opencode_json.exists()
    config = json.loads(opencode_json.read_text())
    assert "cocosearch" in config["mcp"]
    assert config["mcp"]["cocosearch"]["enabled"] is True


def test_user_accepts_global_opencode_mcp(tmp_path, monkeypatch):
    """Test that user choosing global creates ~/.config/opencode/opencode.json."""
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fakehome"
    args = _make_args(no_opencode_mcp=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "2"]):
            with patch("pathlib.Path.home", return_value=fake_home):
                result = init_command(args)

    assert result == 0
    opencode_json = fake_home / ".config" / "opencode" / "opencode.json"
    assert opencode_json.exists()
    config = json.loads(opencode_json.read_text())
    assert "cocosearch" in config["mcp"]


def test_user_declines_opencode_mcp(tmp_path, monkeypatch):
    """Test that user declining 'n' skips MCP registration."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_opencode_mcp=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", return_value="n"):
            result = init_command(args)

    assert result == 0
    assert not (tmp_path / "opencode.json").exists()


def test_invalid_opencode_mcp_choice_skips_gracefully(tmp_path, monkeypatch, capsys):
    """Test that invalid MCP location choice skips without error."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_opencode_mcp=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "3"]):
            result = init_command(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Invalid choice" in captured.out


def test_opencode_mcp_skips_when_already_registered(tmp_path, monkeypatch, capsys):
    """Test that duplicate cocosearch entry is detected and reported."""
    monkeypatch.chdir(tmp_path)

    # Pre-create opencode.json with cocosearch already registered
    opencode_json = tmp_path / "opencode.json"
    opencode_json.write_text(json.dumps({"mcp": {"cocosearch": {"type": "local"}}}))

    args = _make_args(no_opencode_mcp=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "1"]):
            result = init_command(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "already registered" in captured.out


def test_opencode_mcp_adds_to_existing_config(tmp_path, monkeypatch):
    """Test that MCP entry is merged into existing opencode.json."""
    monkeypatch.chdir(tmp_path)

    opencode_json = tmp_path / "opencode.json"
    opencode_json.write_text(json.dumps({"model": "anthropic/claude-sonnet-4-5"}))

    args = _make_args(no_opencode_mcp=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "1"]):
            result = init_command(args)

    assert result == 0
    config = json.loads(opencode_json.read_text())
    assert config["model"] == "anthropic/claude-sonnet-4-5"
    assert "cocosearch" in config["mcp"]


def test_opencode_mcp_write_error_does_not_fail_command(tmp_path, monkeypatch, capsys):
    """Test that OSError on write still returns 0."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_opencode_mcp=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "1"]):
            with patch(
                "cocosearch.cli.generate_opencode_mcp_config",
                side_effect=OSError("Permission denied"),
            ):
                result = init_command(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Warning" in captured.out
    assert "Permission denied" in captured.out


def test_opencode_mcp_json_parse_error_does_not_fail_command(
    tmp_path, monkeypatch, capsys
):
    """Test that invalid JSON in existing opencode.json is handled gracefully."""
    monkeypatch.chdir(tmp_path)

    opencode_json = tmp_path / "opencode.json"
    opencode_json.write_text("{ // this is JSONC, not valid JSON }")

    args = _make_args(no_opencode_mcp=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        with patch("builtins.input", side_effect=["y", "1"]):
            result = init_command(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Warning" in captured.out


def test_all_three_prompts_together(tmp_path, monkeypatch):
    """Test that all three prompts (CLAUDE.md, AGENTS.md, MCP) work together."""
    monkeypatch.chdir(tmp_path)
    args = _make_args(no_claude_md=False, no_agents_md=False, no_opencode_mcp=False)

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = True
        # CLAUDE.md (y, 1), AGENTS.md (y, 1), MCP (y, 1)
        with patch("builtins.input", side_effect=["y", "1", "y", "1", "y", "1"]):
            result = init_command(args)

    assert result == 0
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "opencode.json").exists()
