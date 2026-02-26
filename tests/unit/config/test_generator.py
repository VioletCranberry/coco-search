"""Tests for config generator module."""

import pytest
import yaml

from cocosearch.config import (
    CLAUDE_MD_DUPLICATE_MARKER,
    CLAUDE_MD_ROUTING_SECTION,
    CONFIG_TEMPLATE,
    ConfigError,
    generate_claude_md_routing,
    generate_config,
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
