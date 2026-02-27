"""Tests for config generator module."""

import json
import subprocess
from unittest.mock import patch

import pytest
import yaml

from cocosearch.config import (
    CLAUDE_MD_DUPLICATE_MARKER,
    CLAUDE_MD_ROUTING_SECTION,
    CONFIG_TEMPLATE,
    ConfigError,
    check_claude_plugin_installed,
    generate_agents_md_routing,
    generate_claude_md_routing,
    generate_config,
    generate_opencode_mcp_config,
    generate_opencode_skills,
    install_claude_plugin,
)


def test_generate_config_creates_file(tmp_path):
    """Test that generate_config creates a file with the template."""
    config_path = tmp_path / "cocosearch.yaml"

    generate_config(config_path)

    assert config_path.exists()
    assert config_path.read_text() == CONFIG_TEMPLATE


def test_generate_config_fails_if_exists(tmp_path):
    """Test that generate_config raises ConfigError if file exists."""
    config_path = tmp_path / "cocosearch.yaml"
    config_path.write_text("existing content")

    with pytest.raises(ConfigError) as exc_info:
        generate_config(config_path)

    assert "already exists" in str(exc_info.value)


def test_config_template_is_valid_yaml():
    """Test that CONFIG_TEMPLATE parses as valid YAML."""
    # Parse the template (comments are preserved but ignored by YAML parser)
    data = yaml.safe_load(CONFIG_TEMPLATE)

    # Template has all fields commented, so parsed data should be minimal
    # (only non-commented sections like empty indexing/search/embedding)
    assert data is not None
    assert "indexing" in data
    assert "search" in data
    assert "embedding" in data


class TestClaudeMdRouting:
    """Tests for generate_claude_md_routing."""

    def test_creates_new_file(self, tmp_path):
        """Test that it creates a new CLAUDE.md when none exists."""
        target = tmp_path / "CLAUDE.md"

        result = generate_claude_md_routing(target)

        assert result == "created"
        assert target.exists()
        assert CLAUDE_MD_DUPLICATE_MARKER in target.read_text()

    def test_creates_parent_directories(self, tmp_path):
        """Test that it creates parent dirs (e.g. ~/.claude/)."""
        target = tmp_path / "nested" / "dir" / "CLAUDE.md"

        result = generate_claude_md_routing(target)

        assert result == "created"
        assert target.exists()

    def test_appends_to_existing_file(self, tmp_path):
        """Test that it appends to an existing CLAUDE.md preserving content."""
        target = tmp_path / "CLAUDE.md"
        existing = "# My Project\n\nExisting content.\n"
        target.write_text(existing)

        result = generate_claude_md_routing(target)

        assert result == "appended"
        content = target.read_text()
        assert content.startswith(existing)
        assert CLAUDE_MD_DUPLICATE_MARKER in content

    def test_append_has_blank_line_separator(self, tmp_path):
        """Test that appended content is separated by a newline."""
        target = tmp_path / "CLAUDE.md"
        existing = "# My Project\n\nSome content.\n"
        target.write_text(existing)

        generate_claude_md_routing(target)

        content = target.read_text()
        # Existing ends with \n, so separator is \n (one blank line between)
        assert "\n\n" + CLAUDE_MD_DUPLICATE_MARKER in content

    def test_skips_when_marker_present(self, tmp_path):
        """Test that it skips if routing section already exists."""
        target = tmp_path / "CLAUDE.md"
        target.write_text(f"# Project\n\n{CLAUDE_MD_ROUTING_SECTION}")

        result = generate_claude_md_routing(target)

        assert result == "skipped"

    def test_routing_section_contains_expected_content(self):
        """Test that the routing section has the expected structure."""
        assert "search_code" in CLAUDE_MD_ROUTING_SECTION
        assert "analyze_query" in CLAUDE_MD_ROUTING_SECTION
        assert "get_file_dependencies" in CLAUDE_MD_ROUTING_SECTION
        assert "get_file_impact" in CLAUDE_MD_ROUTING_SECTION
        assert "Grep" in CLAUDE_MD_ROUTING_SECTION
        assert "Glob" in CLAUDE_MD_ROUTING_SECTION


class TestAgentsMdRouting:
    """Tests for generate_agents_md_routing."""

    def test_creates_new_file(self, tmp_path):
        """Test that it creates a new AGENTS.md when none exists."""
        target = tmp_path / "AGENTS.md"

        result = generate_agents_md_routing(target)

        assert result == "created"
        assert target.exists()
        assert CLAUDE_MD_DUPLICATE_MARKER in target.read_text()

    def test_creates_parent_directories(self, tmp_path):
        """Test that it creates parent dirs (e.g. ~/.config/opencode/)."""
        target = tmp_path / "nested" / "dir" / "AGENTS.md"

        result = generate_agents_md_routing(target)

        assert result == "created"
        assert target.exists()

    def test_appends_to_existing_file(self, tmp_path):
        """Test that it appends to an existing AGENTS.md preserving content."""
        target = tmp_path / "AGENTS.md"
        existing = "# My Project\n\nExisting content.\n"
        target.write_text(existing)

        result = generate_agents_md_routing(target)

        assert result == "appended"
        content = target.read_text()
        assert content.startswith(existing)
        assert CLAUDE_MD_DUPLICATE_MARKER in content

    def test_skips_when_marker_present(self, tmp_path):
        """Test that it skips if routing section already exists."""
        target = tmp_path / "AGENTS.md"
        target.write_text(f"# Project\n\n{CLAUDE_MD_ROUTING_SECTION}")

        result = generate_agents_md_routing(target)

        assert result == "skipped"

    def test_same_content_as_claude_md(self, tmp_path):
        """Test that AGENTS.md and CLAUDE.md routing produce the same content."""
        claude_target = tmp_path / "CLAUDE.md"
        agents_target = tmp_path / "AGENTS.md"

        generate_claude_md_routing(claude_target)
        generate_agents_md_routing(agents_target)

        assert claude_target.read_text() == agents_target.read_text()


class TestOpencodeMcpConfig:
    """Tests for generate_opencode_mcp_config."""

    def test_creates_new_file(self, tmp_path):
        """Test that it creates a new opencode.json when none exists."""
        target = tmp_path / "opencode.json"

        result = generate_opencode_mcp_config(target)

        assert result == "created"
        assert target.exists()
        config = json.loads(target.read_text())
        assert config["$schema"] == "https://opencode.ai/config.json"
        assert config["mcp"]["cocosearch"]["type"] == "local"
        assert config["mcp"]["cocosearch"]["enabled"] is True
        assert "cocosearch" in config["mcp"]["cocosearch"]["command"]

    def test_creates_parent_directories(self, tmp_path):
        """Test that it creates parent dirs (e.g. ~/.config/opencode/)."""
        target = tmp_path / "nested" / "dir" / "opencode.json"

        result = generate_opencode_mcp_config(target)

        assert result == "created"
        assert target.exists()

    def test_adds_to_existing_config_without_mcp(self, tmp_path):
        """Test that it adds mcp section to existing config without one."""
        target = tmp_path / "opencode.json"
        existing = {
            "$schema": "https://opencode.ai/config.json",
            "model": "anthropic/claude-sonnet-4-5",
        }
        target.write_text(json.dumps(existing, indent=2))

        result = generate_opencode_mcp_config(target)

        assert result == "added"
        config = json.loads(target.read_text())
        assert config["model"] == "anthropic/claude-sonnet-4-5"
        assert config["mcp"]["cocosearch"]["type"] == "local"

    def test_adds_to_existing_mcp_section(self, tmp_path):
        """Test that it adds cocosearch to existing mcp section with other servers."""
        target = tmp_path / "opencode.json"
        existing = {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {"other-server": {"type": "remote", "url": "https://example.com"}},
        }
        target.write_text(json.dumps(existing, indent=2))

        result = generate_opencode_mcp_config(target)

        assert result == "added"
        config = json.loads(target.read_text())
        assert "other-server" in config["mcp"]
        assert "cocosearch" in config["mcp"]

    def test_skips_when_cocosearch_already_registered(self, tmp_path):
        """Test that it skips if cocosearch MCP entry already exists."""
        target = tmp_path / "opencode.json"
        existing = {
            "mcp": {
                "cocosearch": {"type": "local", "command": ["custom"], "enabled": True}
            }
        }
        target.write_text(json.dumps(existing, indent=2))

        result = generate_opencode_mcp_config(target)

        assert result == "skipped"
        # Original entry is preserved, not overwritten
        config = json.loads(target.read_text())
        assert config["mcp"]["cocosearch"]["command"] == ["custom"]

    def test_raises_on_invalid_json(self, tmp_path):
        """Test that it raises ConfigError on malformed JSON."""
        target = tmp_path / "opencode.json"
        target.write_text("{ invalid json // with comments }")

        with pytest.raises(ConfigError, match="Cannot parse"):
            generate_opencode_mcp_config(target)

    def test_raises_on_non_object_json(self, tmp_path):
        """Test that it raises ConfigError if JSON root is not an object."""
        target = tmp_path / "opencode.json"
        target.write_text('"just a string"')

        with pytest.raises(ConfigError, match="Expected a JSON object"):
            generate_opencode_mcp_config(target)

    def test_output_is_valid_json(self, tmp_path):
        """Test that created file is valid, pretty-printed JSON."""
        target = tmp_path / "opencode.json"

        generate_opencode_mcp_config(target)

        raw = target.read_text()
        assert raw.endswith("\n")
        config = json.loads(raw)
        # Re-serialize and compare to verify it's pretty-printed
        assert raw == json.dumps(config, indent=2) + "\n"

    def test_command_includes_project_from_cwd(self, tmp_path):
        """Test that the MCP command includes --project-from-cwd."""
        target = tmp_path / "opencode.json"

        generate_opencode_mcp_config(target)

        config = json.loads(target.read_text())
        command = config["mcp"]["cocosearch"]["command"]
        assert "--project-from-cwd" in command
        assert "uvx" == command[0]


class TestOpencodeSkills:
    """Tests for generate_opencode_skills."""

    def test_installs_all_bundled_skills(self, tmp_path):
        """Test that all bundled skills are installed to the target directory."""
        target = tmp_path / "skills"

        result = generate_opencode_skills(target)

        assert result["installed"] > 0
        assert result["skipped"] == 0
        # Verify each installed skill has a SKILL.md
        for skill_dir in sorted(target.iterdir()):
            assert skill_dir.is_dir()
            assert (skill_dir / "SKILL.md").exists()
            assert skill_dir.name.startswith("cocosearch-")

    def test_creates_target_directory(self, tmp_path):
        """Test that it creates the target directory if it doesn't exist."""
        target = tmp_path / "nested" / "dir" / "skills"

        result = generate_opencode_skills(target)

        assert target.exists()
        assert result["installed"] > 0

    def test_skips_existing_skills(self, tmp_path):
        """Test that existing skills are not overwritten."""
        target = tmp_path / "skills"

        # First install
        result1 = generate_opencode_skills(target)
        installed_count = result1["installed"]

        # Modify one skill to verify it's not overwritten
        first_skill = sorted(target.iterdir())[0]
        (first_skill / "SKILL.md").write_text("custom content")

        # Second install
        result2 = generate_opencode_skills(target)

        assert result2["installed"] == 0
        assert result2["skipped"] == installed_count
        # Verify the modified skill was not overwritten
        assert (first_skill / "SKILL.md").read_text() == "custom content"

    def test_installs_only_missing_skills(self, tmp_path):
        """Test that only missing skills are installed when some already exist."""
        target = tmp_path / "skills"

        # First install all skills
        result1 = generate_opencode_skills(target)
        total = result1["installed"]
        assert total > 1

        # Remove one skill
        skill_dirs = sorted(target.iterdir())
        removed_name = skill_dirs[0].name
        import shutil

        shutil.rmtree(skill_dirs[0])

        # Second install should install only the removed one
        result2 = generate_opencode_skills(target)

        assert result2["installed"] == 1
        assert result2["skipped"] == total - 1
        assert (target / removed_name / "SKILL.md").exists()

    def test_skill_content_is_valid(self, tmp_path):
        """Test that installed SKILL.md files have valid YAML frontmatter."""
        target = tmp_path / "skills"

        generate_opencode_skills(target)

        for skill_dir in target.iterdir():
            content = (skill_dir / "SKILL.md").read_text()
            # Each SKILL.md should start with YAML frontmatter
            assert content.startswith("---\n"), (
                f"{skill_dir.name}/SKILL.md missing YAML frontmatter"
            )
            # Extract frontmatter
            parts = content.split("---\n", 2)
            assert len(parts) >= 3, (
                f"{skill_dir.name}/SKILL.md has malformed frontmatter"
            )
            frontmatter = yaml.safe_load(parts[1])
            assert "name" in frontmatter, (
                f"{skill_dir.name}/SKILL.md missing 'name' in frontmatter"
            )
            assert "description" in frontmatter, (
                f"{skill_dir.name}/SKILL.md missing 'description' in frontmatter"
            )

    def test_installs_expected_skill_count(self, tmp_path):
        """Test that the expected number of skills are installed."""
        target = tmp_path / "skills"

        result = generate_opencode_skills(target)

        # Should install at least 11 skills (the current count)
        assert result["installed"] >= 11

    def test_skill_names_match_directory_names(self, tmp_path):
        """Test that skill directory names match the 'name' in frontmatter."""
        target = tmp_path / "skills"

        generate_opencode_skills(target)

        for skill_dir in target.iterdir():
            content = (skill_dir / "SKILL.md").read_text()
            parts = content.split("---\n", 2)
            frontmatter = yaml.safe_load(parts[1])
            assert frontmatter["name"] == skill_dir.name, (
                f"Directory '{skill_dir.name}' doesn't match frontmatter name '{frontmatter['name']}'"
            )


class TestClaudePluginDetection:
    """Tests for check_claude_plugin_installed."""

    def test_not_installed_when_file_missing(self, tmp_path):
        """Test that missing plugins file returns False."""
        with patch("pathlib.Path.home", return_value=tmp_path):
            assert check_claude_plugin_installed() is False

    def test_not_installed_when_key_missing(self, tmp_path):
        """Test that file without cocosearch key returns False."""
        plugins_dir = tmp_path / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True)
        plugins_file = plugins_dir / "installed_plugins.json"
        plugins_file.write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {"other-plugin@marketplace": {"version": "1.0.0"}},
                }
            )
        )

        with patch("pathlib.Path.home", return_value=tmp_path):
            assert check_claude_plugin_installed() is False

    def test_installed_when_key_present(self, tmp_path):
        """Test that file with cocosearch key returns True."""
        plugins_dir = tmp_path / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True)
        plugins_file = plugins_dir / "installed_plugins.json"
        plugins_file.write_text(
            json.dumps(
                {
                    "version": 2,
                    "plugins": {"cocosearch@cocosearch": {"version": "0.5.0"}},
                }
            )
        )

        with patch("pathlib.Path.home", return_value=tmp_path):
            assert check_claude_plugin_installed() is True

    def test_handles_invalid_json(self, tmp_path):
        """Test that malformed JSON returns False without raising."""
        plugins_dir = tmp_path / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True)
        plugins_file = plugins_dir / "installed_plugins.json"
        plugins_file.write_text("{ not valid json }")

        with patch("pathlib.Path.home", return_value=tmp_path):
            assert check_claude_plugin_installed() is False

    def test_handles_empty_file(self, tmp_path):
        """Test that empty file returns False without raising."""
        plugins_dir = tmp_path / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True)
        plugins_file = plugins_dir / "installed_plugins.json"
        plugins_file.write_text("")

        with patch("pathlib.Path.home", return_value=tmp_path):
            assert check_claude_plugin_installed() is False

    def test_handles_non_dict_json(self, tmp_path):
        """Test that non-dict JSON returns False without raising."""
        plugins_dir = tmp_path / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True)
        plugins_file = plugins_dir / "installed_plugins.json"
        plugins_file.write_text('"just a string"')

        with patch("pathlib.Path.home", return_value=tmp_path):
            assert check_claude_plugin_installed() is False

    def test_handles_missing_plugins_key(self, tmp_path):
        """Test that JSON without 'plugins' key returns False."""
        plugins_dir = tmp_path / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True)
        plugins_file = plugins_dir / "installed_plugins.json"
        plugins_file.write_text(json.dumps({"version": 2}))

        with patch("pathlib.Path.home", return_value=tmp_path):
            assert check_claude_plugin_installed() is False


class TestClaudePluginInstall:
    """Tests for install_claude_plugin."""

    def test_skips_when_already_installed(self, tmp_path):
        """Test that install returns 'skipped' when plugin is already installed."""
        with patch(
            "cocosearch.config.generator.check_claude_plugin_installed",
            return_value=True,
        ):
            result = install_claude_plugin()
            assert result == "skipped"

    def test_install_calls_two_subprocess_commands(self):
        """Test that install runs marketplace add then plugin install."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        with patch(
            "cocosearch.config.generator.check_claude_plugin_installed",
            return_value=False,
        ):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                result = install_claude_plugin()

        assert result == "installed"
        assert mock_run.call_count == 2
        # First call: marketplace add
        first_call = mock_run.call_args_list[0]
        assert "marketplace" in first_call[0][0]
        assert "add" in first_call[0][0]
        assert "VioletCranberry/coco-search" in first_call[0][0]
        # Second call: plugin install
        second_call = mock_run.call_args_list[1]
        assert "install" in second_call[0][0]
        assert "cocosearch@cocosearch" in second_call[0][0]

    def test_raises_when_claude_cli_not_found(self):
        """Test that FileNotFoundError from subprocess raises ConfigError."""
        with patch(
            "cocosearch.config.generator.check_claude_plugin_installed",
            return_value=False,
        ):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with pytest.raises(ConfigError, match="Claude CLI not found"):
                    install_claude_plugin()

    def test_raises_on_marketplace_add_failure(self):
        """Test that non-zero exit from marketplace add raises ConfigError."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="marketplace error"
        )

        with patch(
            "cocosearch.config.generator.check_claude_plugin_installed",
            return_value=False,
        ):
            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(ConfigError, match="Failed to add marketplace"):
                    install_claude_plugin()

    def test_raises_on_plugin_install_failure(self):
        """Test that non-zero exit from plugin install raises ConfigError."""
        success = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        failure = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="install error"
        )

        with patch(
            "cocosearch.config.generator.check_claude_plugin_installed",
            return_value=False,
        ):
            with patch("subprocess.run", side_effect=[success, failure]):
                with pytest.raises(ConfigError, match="Failed to install plugin"):
                    install_claude_plugin()

    def test_error_message_includes_stderr(self):
        """Test that error messages include stderr content."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="specific error detail"
        )

        with patch(
            "cocosearch.config.generator.check_claude_plugin_installed",
            return_value=False,
        ):
            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(ConfigError, match="specific error detail"):
                    install_claude_plugin()

    def test_falls_back_to_stdout_when_stderr_empty(self):
        """Test that error falls back to stdout when stderr is empty."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="stdout error info", stderr=""
        )

        with patch(
            "cocosearch.config.generator.check_claude_plugin_installed",
            return_value=False,
        ):
            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(ConfigError, match="stdout error info"):
                    install_claude_plugin()

    def test_subprocess_called_with_timeout(self):
        """Test that subprocess calls include a timeout."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        with patch(
            "cocosearch.config.generator.check_claude_plugin_installed",
            return_value=False,
        ):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                install_claude_plugin()

        for call in mock_run.call_args_list:
            assert call[1]["timeout"] == 60
