"""Configuration file generator for CocoSearch."""

from pathlib import Path

from .schema import ConfigError

CONFIG_TEMPLATE = """\
# CocoSearch Configuration
# https://github.com/VioletCranberry/cocosearch

# Index name (optional - defaults to directory name)
# indexName: my-project

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


CLAUDE_MD_DUPLICATE_MARKER = "## CocoSearch Tool Routing"

CLAUDE_MD_ROUTING_SECTION = f"""\
{CLAUDE_MD_DUPLICATE_MARKER}

When CocoSearch MCP tools are available, ALWAYS use them instead of Grep, Glob, or Task/Explore agents for code search and exploration:

| Task | Use this | NOT this |
|------|----------|----------|
| Code search / "how does X work?" | `search_code` | Grep, Glob, Task (Explore) |
| Symbol lookup / "find function Y" | `search_code` with `symbol_name`/`symbol_type` | Grep for def/class patterns |
| Dependency tracing / "what imports X?" | `get_file_dependencies` / `get_file_impact` | Grep for import statements |
| Search debugging / "why no results?" | `analyze_query` | Manual pipeline investigation |

Fall back to Grep/Glob ONLY for:
- Exact literal string matches (e.g., a specific error message or config value)
- File path pattern matching (e.g., "find all `*.test.ts` files")
- Editing operations that need line numbers from a known file
"""


def generate_claude_md_routing(path: Path) -> str:
    """Add CocoSearch tool routing section to a CLAUDE.md file.

    Args:
        path: Path to the CLAUDE.md file.

    Returns:
        "created" if a new file was created,
        "appended" if the section was appended to an existing file,
        "skipped" if the section already exists.
    """
    if path.exists():
        content = path.read_text()
        if CLAUDE_MD_DUPLICATE_MARKER in content:
            return "skipped"
        separator = "\n" if content.endswith("\n") else "\n\n"
        path.write_text(content + separator + CLAUDE_MD_ROUTING_SECTION)
        return "appended"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(CLAUDE_MD_ROUTING_SECTION)
    return "created"
