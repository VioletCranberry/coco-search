"""Grammar handler for GitLab CI configuration files.

Provides domain-specific chunking and metadata extraction for GitLab CI/CD
pipeline configuration (.gitlab-ci.yml).

Matches: .gitlab-ci.yml
Content markers: 'stages:' or ('script:' and ('image:' or 'stage:'))
"""

import fnmatch
import re

import cocoindex


class GitLabCIHandler:
    """Grammar handler for GitLab CI configuration files."""

    GRAMMAR_NAME = "gitlab-ci"
    BASE_LANGUAGE = "yaml"
    PATH_PATTERNS = [".gitlab-ci.yml"]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="gitlab-ci",
        separators_regex=[
            # Level 1: YAML document separator
            r"\n---",
            # Level 2: Top-level keys (jobs, keywords, templates) with newline
            r"\n[a-zA-Z_.][\w./-]*:\s*\n",
            # Level 3: Job-level keys (2-space indented: script:, stage:, image:)
            r"\n  [a-zA-Z_][\w-]*:",
            # Level 4: Nested keys (4-space indented: only:, except:, rules:)
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

    _COMMENT_LINE = re.compile(r"^\s*#.*$", re.MULTILINE)

    # Top-level key (job name or keyword) at start of line
    # Supports . prefix (templates) and / in names (deploy/staging)
    _TOP_KEY_RE = re.compile(r"^([a-zA-Z_.][\w./-]*):\s*", re.MULTILINE)

    # Job-level key (2-space indented key: script:, stage:, image:)
    _ITEM_RE = re.compile(r"^  ([a-zA-Z_][\w-]*):", re.MULTILINE)

    # Nested key (4+ space indented key: only:, except:, variables:)
    _NESTED_KEY_RE = re.compile(r"^\s{4,}([a-zA-Z_][\w-]*):", re.MULTILINE)

    # YAML list item key (e.g., "- project: mygroup/myproject", "- local: /path")
    _LIST_ITEM_KEY_RE = re.compile(r"^\s*-\s+([a-zA-Z_][\w-]*):", re.MULTILINE)

    # Script line (e.g., "- echo hello", "  - make build")
    _SCRIPT_LINE_RE = re.compile(r"^\s*-\s+(.+)$", re.MULTILINE)

    # GitLab CI top-level keywords (not job names)
    _TOP_LEVEL_KEYS = frozenset(
        {
            "stages",
            "variables",
            "image",
            "services",
            "before_script",
            "after_script",
            "cache",
            "default",
            "include",
            "workflow",
            "pages",
            "trigger",
        }
    )

    def matches(self, filepath: str, content: str | None = None) -> bool:
        """Check if file is a GitLab CI configuration.

        Uses fnmatch with */{pattern} idiom so nested .gitlab-ci.yml files
        are detected at any depth.

        Args:
            filepath: Relative file path within the project.
            content: Optional file content for deeper matching.

        Returns:
            True if this is a GitLab CI configuration file.
        """
        for pattern in self.PATH_PATTERNS:
            if fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(
                filepath, f"*/{pattern}"
            ):
                if content is not None:
                    has_stages = "stages:" in content
                    has_script_combo = "script:" in content and (
                        "image:" in content or "stage:" in content
                    )
                    return has_stages or has_script_combo
                return True
        return False

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from GitLab CI chunk.

        Identifies jobs, job-level keys, nested keys, list items,
        templates, global keywords, and value continuations.

        Args:
            text: The chunk text content.

        Returns:
            Dict with block_type, hierarchy, language_id.

        Examples:
            Job chunk: block_type="job", hierarchy="job:build"
            Job key: block_type="job-key", hierarchy="job-key:script"
            Template: block_type="template", hierarchy="template:.base_job"
            Nested key: block_type="nested-key", hierarchy="nested-key:only"
            List item: block_type="list-item", hierarchy="list-item:project"
        """
        stripped = self._strip_comments(text)

        # Check for job-level key (2-space indented key)
        item_match = self._ITEM_RE.match(stripped)
        if item_match:
            key = item_match.group(1)
            return {
                "block_type": "job-key",
                "hierarchy": f"job-key:{key}",
                "language_id": self.GRAMMAR_NAME,
            }

        # Check for nested key (4+ space indented)
        nested_match = self._NESTED_KEY_RE.match(stripped)
        if nested_match:
            key = nested_match.group(1)
            return {
                "block_type": "nested-key",
                "hierarchy": f"nested-key:{key}",
                "language_id": self.GRAMMAR_NAME,
            }

        # Check for YAML list item key (e.g., "- project: value")
        list_match = self._LIST_ITEM_KEY_RE.match(stripped)
        if list_match:
            key = list_match.group(1)
            return {
                "block_type": "list-item",
                "hierarchy": f"list-item:{key}",
                "language_id": self.GRAMMAR_NAME,
            }

        # Check for top-level keys
        top_match = self._TOP_KEY_RE.match(stripped)
        if top_match:
            key = top_match.group(1)

            # Hidden jobs/templates (start with .)
            if key.startswith("."):
                return {
                    "block_type": "template",
                    "hierarchy": f"template:{key}",
                    "language_id": self.GRAMMAR_NAME,
                }

            # Global keywords
            if key in self._TOP_LEVEL_KEYS:
                return {
                    "block_type": key,
                    "hierarchy": key,
                    "language_id": self.GRAMMAR_NAME,
                }

            # Regular job
            return {
                "block_type": "job",
                "hierarchy": f"job:{key}",
                "language_id": self.GRAMMAR_NAME,
            }

        # YAML document separator (--- chunks)
        if "---" in text:
            return {
                "block_type": "document",
                "hierarchy": "document",
                "language_id": self.GRAMMAR_NAME,
            }

        # Value continuation (chunk has content but no recognizable key)
        if stripped:
            return {
                "block_type": "value",
                "hierarchy": "value",
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
