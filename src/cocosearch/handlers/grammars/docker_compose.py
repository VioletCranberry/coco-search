"""Grammar handler for Docker Compose configuration files.

Provides domain-specific chunking and metadata extraction for Docker Compose
files (docker-compose.yml, compose.yml, and variants).

Matches: docker-compose*.yml, docker-compose*.yaml, compose*.yml, compose*.yaml
Content markers: 'services:'
"""

import fnmatch
import os
import re

import cocoindex


class DockerComposeHandler:
    """Grammar handler for Docker Compose configuration files."""

    GRAMMAR_NAME = "docker-compose"
    BASE_LANGUAGE = "yaml"
    PATH_PATTERNS = [
        "docker-compose*.yml",
        "docker-compose*.yaml",
        "compose*.yml",
        "compose*.yaml",
    ]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="docker-compose",
        separators_regex=[
            # Level 1: Top-level keys (services, volumes, networks, etc.)
            r"\n[a-zA-Z_][\w-]*:\s*\n",
            # Level 2: Service/volume/network boundaries (2-space indented keys)
            r"\n  [a-zA-Z_][\w-]*:",
            # Level 3: Blank lines
            r"\n\n+",
            # Level 4: Single newlines
            r"\n",
            # Level 5: Whitespace (last resort)
            r" ",
        ],
        aliases=[],
    )

    _COMMENT_LINE = re.compile(r"^\s*#.*$", re.MULTILINE)

    # Top-level key at start of line
    _TOP_KEY_RE = re.compile(r"^([a-zA-Z_][\w-]*):\s*$", re.MULTILINE)

    # Service/item definition (2-space indented key)
    _ITEM_RE = re.compile(r"^  ([a-zA-Z_][\w-]*):", re.MULTILINE)

    # Top-level compose keys
    _TOP_LEVEL_KEYS = frozenset(
        {
            "services",
            "volumes",
            "networks",
            "configs",
            "secrets",
            "version",
            "name",
        }
    )

    def matches(self, filepath: str, content: str | None = None) -> bool:
        """Check if file is a Docker Compose configuration.

        Args:
            filepath: Relative file path within the project.
            content: Optional file content for deeper matching.

        Returns:
            True if this is a Docker Compose file.
        """
        basename = os.path.basename(filepath)
        for pattern in self.PATH_PATTERNS:
            if fnmatch.fnmatch(basename, pattern):
                if content is not None:
                    return "services:" in content
                return True
        return False

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from Docker Compose chunk.

        Identifies services, volumes, networks, and other top-level sections.

        Args:
            text: The chunk text content.

        Returns:
            Dict with block_type, hierarchy, language_id.

        Examples:
            Service chunk: block_type="service", hierarchy="service:web"
            Top-level: block_type="services", hierarchy="services"
        """
        stripped = self._strip_comments(text)

        # Check for service/item definition first (indented key)
        item_match = self._ITEM_RE.match(stripped)
        if item_match:
            item_name = item_match.group(1)
            return {
                "block_type": "service",
                "hierarchy": f"service:{item_name}",
                "language_id": self.GRAMMAR_NAME,
            }

        # Check for top-level keys
        top_match = self._TOP_KEY_RE.match(stripped)
        if top_match:
            key = top_match.group(1)
            return {
                "block_type": key,
                "hierarchy": key,
                "language_id": self.GRAMMAR_NAME,
            }

        return {
            "block_type": "",
            "hierarchy": "",
            "language_id": self.GRAMMAR_NAME,
        }

    def _strip_comments(self, text: str) -> str:
        """Strip leading comments from chunk text, preserving indentation."""
        lines = text.lstrip("\n").split("\n")
        for i, line in enumerate(lines):
            if line.strip() and not self._COMMENT_LINE.match(line):
                return "\n".join(lines[i:])
        return ""
