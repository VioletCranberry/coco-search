"""Configuration file generator for CocoSearch."""

import json
import subprocess
from importlib.resources import files
from pathlib import Path

from .schema import ConfigError

CONFIG_TEMPLATE = """\
# CocoSearch Configuration
# https://github.com/VioletCranberry/cocosearch

# Index name (optional - defaults to directory name)
# indexName: my-project

# Linked indexes for cross-project search (monorepo setups)
# Automatically includes these indexes when searching this project
# linkedIndexes:
#   - shared-lib
#   - common-utils

# Indexing settings
indexing: {}
  # File patterns to include (glob patterns)
  # includePatterns:
  #   - "*.py"
  #   - "*.js"
  #   - "*.ts"

  # File patterns to exclude (glob patterns)
  # excludePatterns:
  #   - "*_test.py"
  #   - "*.min.js"

  # Chunk settings
  # chunkSize: 1000
  # chunkOverlap: 300

# Search settings
search: {}
  # Maximum results returned
  # resultLimit: 10

  # Minimum similarity score (0.0 - 1.0)
  # minScore: 0.3

# Embedding settings
embedding: {}
  # Ollama model for embeddings
  # model: nomic-embed-text
"""


def generate_config(path: Path) -> None:
    """Generate a CocoSearch configuration file.

    Args:
        path: Path where the config file should be created.

    Raises:
        ConfigError: If the config file already exists.
    """
    if path.exists():
        raise ConfigError(f"Configuration file already exists: {path}")

    path.write_text(CONFIG_TEMPLATE)


CLAUDE_MD_DUPLICATE_MARKER = "Tool Routing"

CLAUDE_MD_ROUTING_SECTION = """\
## CocoSearch Tool Routing

When CocoSearch MCP tools are available, ALWAYS use them instead of Grep, Glob, or Task/Explore agents for code search and exploration. These rules are mandatory, not advisory.

| Task | Use this | NOT this |
|------|----------|----------|
| Code search / "how does X work?" | `search_code` | Grep, Glob, Task (Explore) |
| Symbol lookup / "find function Y" | `search_code` with `symbol_name`/`symbol_type` | Grep for def/class patterns |
| Dependency tracing / "what imports X?" | `get_file_dependencies` / `get_file_impact` | Grep for import statements |
| Batch dependency analysis (multiple files) | `get_batch_dependencies` / `get_batch_impact` | Per-file `get_file_dependencies` calls |
| Search debugging / "why no results?" | `analyze_query` | Manual pipeline investigation |

Fall back to Grep/Glob ONLY for:
- Exact literal string matches (e.g., a specific error message or config value)
- File path pattern matching (e.g., "find all `*.test.ts` files")
- Editing operations that need line numbers from a known file
"""


def _append_routing_section(path: Path, marker: str, section: str) -> str:
    """Add CocoSearch tool routing section to a markdown file.

    Args:
        path: Path to the markdown file (CLAUDE.md or AGENTS.md).
        marker: Duplicate detection marker string.
        section: The routing section content to add.

    Returns:
        "created" if a new file was created,
        "appended" if the section was appended to an existing file,
        "skipped" if the section already exists.
    """
    if path.exists():
        content = path.read_text()
        if marker in content:
            return "skipped"
        separator = "\n" if content.endswith("\n") else "\n\n"
        path.write_text(content + separator + section)
        return "appended"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(section)
    return "created"


def generate_claude_md_routing(path: Path) -> str:
    """Add CocoSearch tool routing section to a CLAUDE.md file.

    Args:
        path: Path to the CLAUDE.md file.

    Returns:
        "created" if a new file was created,
        "appended" if the section was appended to an existing file,
        "skipped" if the section already exists.
    """
    return _append_routing_section(
        path, CLAUDE_MD_DUPLICATE_MARKER, CLAUDE_MD_ROUTING_SECTION
    )


def generate_agents_md_routing(path: Path) -> str:
    """Add CocoSearch tool routing section to an AGENTS.md file.

    Args:
        path: Path to the AGENTS.md file.

    Returns:
        "created" if a new file was created,
        "appended" if the section was appended to an existing file,
        "skipped" if the section already exists.
    """
    return _append_routing_section(
        path, CLAUDE_MD_DUPLICATE_MARKER, CLAUDE_MD_ROUTING_SECTION
    )


OPENCODE_MCP_ENTRY = {
    "type": "local",
    "command": [
        "uvx",
        "--from",
        "cocosearch",
        "cocosearch",
        "mcp",
        "--project-from-cwd",
    ],
    "enabled": True,
}

OPENCODE_SCHEMA_URL = "https://opencode.ai/config.json"


def generate_opencode_mcp_config(path: Path) -> str:
    """Register CocoSearch MCP server in an OpenCode config file.

    Merges the CocoSearch MCP server entry into an existing opencode.json,
    or creates a new one. Preserves all existing configuration.

    Args:
        path: Path to the opencode.json file.

    Returns:
        "created" if a new file was created,
        "added" if the entry was added to an existing file,
        "skipped" if the entry already exists.
    """
    if path.exists():
        raw = path.read_text()
        try:
            config = json.loads(raw)
        except json.JSONDecodeError:
            raise ConfigError(
                f"Cannot parse {path} as JSON. "
                "If it uses JSONC (comments), please add the CocoSearch MCP entry manually."
            )

        if not isinstance(config, dict):
            raise ConfigError(
                f"Expected a JSON object in {path}, got {type(config).__name__}"
            )

        mcp = config.get("mcp")
        if isinstance(mcp, dict) and "cocosearch" in mcp:
            return "skipped"

        if not isinstance(mcp, dict):
            config["mcp"] = {}
        config["mcp"]["cocosearch"] = OPENCODE_MCP_ENTRY

        path.write_text(json.dumps(config, indent=2) + "\n")
        return "added"

    path.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "$schema": OPENCODE_SCHEMA_URL,
        "mcp": {
            "cocosearch": OPENCODE_MCP_ENTRY,
        },
    }
    path.write_text(json.dumps(config, indent=2) + "\n")
    return "created"


CLAUDE_PLUGIN_ID = "cocosearch@cocosearch"
CLAUDE_MARKETPLACE_REPO = "VioletCranberry/coco-search"


def check_claude_plugin_installed() -> bool:
    """Check if the CocoSearch plugin is installed in Claude Code.

    Reads ~/.claude/plugins/installed_plugins.json and checks for the
    'cocosearch@cocosearch' key in the plugins dict.

    Returns:
        True if the plugin is installed, False otherwise.
    """
    plugins_file = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    try:
        data = json.loads(plugins_file.read_text())
        plugins = data.get("plugins", {})
        return CLAUDE_PLUGIN_ID in plugins
    except (FileNotFoundError, json.JSONDecodeError, TypeError, AttributeError):
        return False


def install_claude_plugin() -> str:
    """Install the CocoSearch plugin for Claude Code via the claude CLI.

    Runs two commands sequentially:
    1. claude plugin marketplace add VioletCranberry/coco-search
    2. claude plugin install cocosearch@cocosearch

    Returns:
        "installed" if the plugin was successfully installed,
        "skipped" if the plugin is already installed.

    Raises:
        ConfigError: If the claude CLI is not found or a command fails.
    """
    if check_claude_plugin_installed():
        return "skipped"

    try:
        # Step 1: Register the marketplace
        result = subprocess.run(
            ["claude", "plugin", "marketplace", "add", CLAUDE_MARKETPLACE_REPO],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise ConfigError(
                f"Failed to add marketplace: {stderr or result.stdout.strip()}"
            )

        # Step 2: Install the plugin
        result = subprocess.run(
            ["claude", "plugin", "install", CLAUDE_PLUGIN_ID],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise ConfigError(
                f"Failed to install plugin: {stderr or result.stdout.strip()}"
            )

    except FileNotFoundError:
        raise ConfigError(
            "Claude CLI not found. Install it from https://claude.ai/download "
            "or install the plugin manually: "
            "claude plugin marketplace add VioletCranberry/coco-search && "
            "claude plugin install cocosearch@cocosearch"
        )

    return "installed"


COCOSEARCH_MCP_TOOL_PERMISSIONS = [
    "mcp__plugin_cocosearch_cocosearch__search_code",
    "mcp__plugin_cocosearch_cocosearch__analyze_query",
    "mcp__plugin_cocosearch_cocosearch__index_codebase",
    "mcp__plugin_cocosearch_cocosearch__list_indexes",
    "mcp__plugin_cocosearch_cocosearch__index_stats",
    "mcp__plugin_cocosearch_cocosearch__clear_index",
    "mcp__plugin_cocosearch_cocosearch__open_dashboard",
    "mcp__plugin_cocosearch_cocosearch__get_file_dependencies",
    "mcp__plugin_cocosearch_cocosearch__get_file_impact",
    "mcp__plugin_cocosearch_cocosearch__get_batch_dependencies",
    "mcp__plugin_cocosearch_cocosearch__get_batch_impact",
]


def generate_claude_settings(path: Path) -> str:
    """Add CocoSearch tool permissions to a Claude Code settings file.

    Merges CocoSearch MCP tool permissions into an existing settings file,
    or creates a new one. Preserves all existing configuration.

    Args:
        path: Path to the settings file (e.g., .claude/settings.local.json).

    Returns:
        "created" if a new file was created,
        "added" if permissions were added to an existing file,
        "skipped" if all permissions already exist.
    """
    if path.exists():
        raw = path.read_text()
        try:
            config = json.loads(raw)
        except json.JSONDecodeError:
            raise ConfigError(
                f"Cannot parse {path} as JSON. "
                "If it uses JSONC (comments), please add the permissions manually."
            )

        if not isinstance(config, dict):
            raise ConfigError(
                f"Expected a JSON object in {path}, got {type(config).__name__}"
            )

        permissions = config.get("permissions")
        if not isinstance(permissions, dict):
            config["permissions"] = {"allow": []}
        allow = config["permissions"].get("allow")
        if not isinstance(allow, list):
            config["permissions"]["allow"] = []

        existing = set(config["permissions"]["allow"])
        missing = [p for p in COCOSEARCH_MCP_TOOL_PERMISSIONS if p not in existing]

        if not missing:
            return "skipped"

        config["permissions"]["allow"].extend(missing)
        path.write_text(json.dumps(config, indent=2) + "\n")
        return "added"

    path.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "permissions": {
            "allow": list(COCOSEARCH_MCP_TOOL_PERMISSIONS),
        },
    }
    path.write_text(json.dumps(config, indent=2) + "\n")
    return "created"


def _get_bundled_skills() -> dict[str, str]:
    """Discover bundled SKILL.md files from the cocosearch.skills package.

    Returns:
        Dict mapping skill name to SKILL.md content.
    """
    skills_pkg = files("cocosearch.skills")
    skills: dict[str, str] = {}

    for item in skills_pkg.iterdir():
        if not item.name.startswith("cocosearch-"):
            continue
        skill_md = item / "SKILL.md"
        if skill_md.is_file():
            skills[item.name] = skill_md.read_text()

    return skills


def generate_opencode_skills(target_dir: Path) -> dict[str, int]:
    """Install CocoSearch workflow skills into an OpenCode discovery directory.

    Copies bundled SKILL.md files into the target directory (e.g.,
    ``.opencode/skills/`` or ``~/.config/opencode/skills/``). Each skill
    is placed in its own subdirectory matching the skill name.

    Skills that already exist at the target are skipped.

    Args:
        target_dir: Directory where skills should be installed
            (e.g., ``<project>/.opencode/skills`` or
            ``~/.config/opencode/skills``).

    Returns:
        Dict with ``installed`` and ``skipped`` counts.
    """
    bundled = _get_bundled_skills()
    installed = 0
    skipped = 0

    for name, content in sorted(bundled.items()):
        skill_dir = target_dir / name
        skill_file = skill_dir / "SKILL.md"

        if skill_file.exists():
            skipped += 1
            continue

        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(content)
        installed += 1

    return {"installed": installed, "skipped": skipped}
