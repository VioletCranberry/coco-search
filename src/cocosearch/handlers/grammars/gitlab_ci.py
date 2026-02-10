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
            # Level 1: Top-level job/stage boundaries
            r"\n[a-zA-Z_.][\w./-]*:",
            # Level 2: Blank lines
            r"\n\n+",
            # Level 3: Single newlines
            r"\n",
            # Level 4: Whitespace (last resort)
            r" ",
        ],
        aliases=[],
    )

    _COMMENT_LINE = re.compile(r"^\s*#.*$", re.MULTILINE)

    # Top-level key (job name or keyword) at start of line
    _TOP_KEY_RE = re.compile(r"^([a-zA-Z_.][\w./-]*):\s*", re.MULTILINE)

    # stage: value under a job
    _STAGE_RE = re.compile(r"^\s+stage:\s*(.+)$", re.MULTILINE)

    # GitLab CI global keywords (not job names)
    _GLOBAL_KEYWORDS = frozenset(
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

        Args:
            filepath: Relative file path within the project.
            content: Optional file content for deeper matching.

        Returns:
            True if this is a GitLab CI configuration file.
        """
        for pattern in self.PATH_PATTERNS:
            if fnmatch.fnmatch(filepath, pattern):
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

        Identifies jobs, stages, and global keywords.

        Args:
            text: The chunk text content.

        Returns:
            Dict with block_type, hierarchy, language_id.

        Examples:
            Job chunk: block_type="job", hierarchy="job:build"
            Stages block: block_type="stages", hierarchy="stages"
        """
        stripped = self._strip_comments(text)

        top_match = self._TOP_KEY_RE.match(stripped)
        if not top_match:
            return {
                "block_type": "",
                "hierarchy": "",
                "language_id": self.GRAMMAR_NAME,
            }

        key = top_match.group(1)

        # Global keywords
        if key in self._GLOBAL_KEYWORDS:
            return {
                "block_type": key,
                "hierarchy": key,
                "language_id": self.GRAMMAR_NAME,
            }

        # Hidden jobs/templates (start with .)
        if key.startswith("."):
            return {
                "block_type": "template",
                "hierarchy": f"template:{key}",
                "language_id": self.GRAMMAR_NAME,
            }

        # Regular job — try to extract stage
        stage_match = self._STAGE_RE.search(stripped)
        if stage_match:
            return {
                "block_type": "job",
                "hierarchy": f"job:{key}",
                "language_id": self.GRAMMAR_NAME,
            }

        return {
            "block_type": "job",
            "hierarchy": f"job:{key}",
            "language_id": self.GRAMMAR_NAME,
        }

    def _strip_comments(self, text: str) -> str:
        """Strip leading comments from chunk text."""
        lines = text.lstrip().split("\n")
        for i, line in enumerate(lines):
            if line.strip() and not self._COMMENT_LINE.match(line):
                return "\n".join(lines[i:])
        return ""
