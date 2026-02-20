"""Grammar handler for Docker Compose configuration files.

Provides domain-specific chunking and metadata extraction for Docker Compose
files (docker-compose.yml, compose.yml, and variants).

Matches: docker-compose*.yml, docker-compose*.yaml, compose*.yml, compose*.yaml
Content markers: 'services:'
"""

import cocoindex

from cocosearch.handlers.grammars._base import YamlGrammarBase


class DockerComposeHandler(YamlGrammarBase):
    """Grammar handler for Docker Compose configuration files."""

    GRAMMAR_NAME = "docker-compose"
    PATH_PATTERNS = [
        "docker-compose*.yml",
        "docker-compose*.yaml",
        "compose*.yml",
        "compose*.yaml",
    ]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="docker-compose",
        separators_regex=[
            # Level 1: YAML document separator
            r"\n---",
            # Level 2: Top-level keys (services, volumes, networks, etc.)
            r"\n[a-zA-Z_][\w-]*:\s*\n",
            # Level 3: Service/volume/network boundaries (2-space indented keys)
            r"\n  [a-zA-Z_][\w-]*:",
            # Level 4: Nested keys (4-space indented, e.g. ports:, environment:)
            r"\n    [a-zA-Z_][\w-]*:",
            # Level 5: Blank lines
            r"\n\n+",
            # Level 6: Single newlines
            r"\n",
            # Level 7: Whitespace (last resort)
            r" ",
        ],
        aliases=[],
    )

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
            "include",
        }
    )

    def _has_content_markers(self, content: str) -> bool:
        return "services:" in content

    def _extract_grammar_metadata(self, stripped: str, text: str) -> dict | None:
        """Extract metadata from Docker Compose chunk.

        Identifies services, volumes, networks, and other top-level sections.

        Examples:
            Service chunk: block_type="service", hierarchy="service:web"
            Top-level: block_type="services", hierarchy="services"
            Nested key: block_type="nested-key", hierarchy="nested-key:ports"
            List item: block_type="list-item", hierarchy="list-item:image"
        """
        # Check for service/item definition first (2-space indented key)
        item_match = self._ITEM_RE.match(stripped)
        if item_match:
            return self._make_result("service", f"service:{item_match.group(1)}")

        # Check for nested key (4+ space indented)
        nested_match = self._NESTED_KEY_RE.match(stripped)
        if nested_match:
            key = nested_match.group(1)
            return self._make_result("nested-key", f"nested-key:{key}")

        # Check for YAML list item key (e.g., "- name: value")
        list_match = self._LIST_ITEM_KEY_RE.match(stripped)
        if list_match:
            key = list_match.group(1)
            return self._make_result("list-item", f"list-item:{key}")

        # Check for top-level keys
        top_match = self._TOP_KEY_RE.match(stripped)
        if top_match:
            key = top_match.group(1)
            return self._make_result(key, key)

        return None
