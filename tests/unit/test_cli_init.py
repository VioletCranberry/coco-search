"""Tests for CLI init command."""

import argparse


from cocosearch.cli import init_command


def test_init_command_creates_config(tmp_path, monkeypatch):
    """Test that init_command creates cocosearch.yaml in cwd."""
    # Change to tmp directory
    monkeypatch.chdir(tmp_path)

    # Create args namespace
    args = argparse.Namespace()

    # Run init command
    result = init_command(args)

    # Verify success
    assert result == 0

    # Verify file created
    config_path = tmp_path / "cocosearch.yaml"
    assert config_path.exists()

    # Verify content has expected header
    content = config_path.read_text()
    assert "# CocoSearch Configuration" in content
    assert "indexing:" in content


def test_init_command_fails_if_exists(tmp_path, monkeypatch):
    """Test that init_command fails if cocosearch.yaml already exists."""
    # Change to tmp directory
    monkeypatch.chdir(tmp_path)

    # Create existing config file
    config_path = tmp_path / "cocosearch.yaml"
    config_path.write_text("existing config")

    # Create args namespace
    args = argparse.Namespace()

    # Run init command
    result = init_command(args)

    # Verify failure
    assert result == 1


def test_init_command_output(tmp_path, monkeypatch, capsys):
    """Test that init_command prints success message."""
    # Change to tmp directory
    monkeypatch.chdir(tmp_path)

    # Create args namespace
    args = argparse.Namespace()

    # Run init command
    init_command(args)

    # Capture output
    captured = capsys.readouterr()

    # Verify success message
    assert "Created cocosearch.yaml" in captured.out
    assert "Edit this file" in captured.out
