"""Grammar handler for GitHub Actions workflow files.

Provides domain-specific chunking and metadata extraction for GitHub Actions
workflow YAML files found in .github/workflows/.

Matches: .github/workflows/*.yml, .github/workflows/*.yaml
Content markers: 'on:' and 'jobs:'
"""

import fnmatch
import re

import cocoindex


class GitHubActionsHandler:
    """Grammar handler for GitHub Actions workflow files."""

    GRAMMAR_NAME = "github-actions"
    BASE_LANGUAGE = "yaml"
    PATH_PATTERNS = [".github/workflows/*.yml", ".github/workflows/*.yaml"]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="github-actions",
        separators_regex=[
            # Level 1: Job boundaries (top-level keys under jobs:)
            r"\n  [a-zA-Z_][\w-]*:\n",
            # Level 2: Step boundaries (- name: or - uses:)
            r"\n      - ",
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

    # Match job definition: indented key followed by colon
    _JOB_RE = re.compile(r"^([a-zA-Z_][\w-]*):\s*$", re.MULTILINE)

    # Match step with 'name:' key
    _STEP_NAME_RE = re.compile(r"^\s*-\s+name:\s*(.+)$", re.MULTILINE)

    # Match step with 'uses:' key
    _STEP_USES_RE = re.compile(r"^\s*-?\s*uses:\s*(.+)$", re.MULTILINE)

    # Match top-level keys (name:, on:, jobs:, env:, permissions:, etc.)
    _TOP_LEVEL_RE = re.compile(r"^([a-zA-Z_][\w-]*):", re.MULTILINE)

    def matches(self, filepath: str, content: str | None = None) -> bool:
        """Check if file is a GitHub Actions workflow.

        Args:
            filepath: Relative file path within the project.
            content: Optional file content for deeper matching.

        Returns:
            True if this is a GitHub Actions workflow file.
        """
        for pattern in self.PATH_PATTERNS:
            if fnmatch.fnmatch(filepath, pattern):
                if content is not None:
                    return "on:" in content and "jobs:" in content
                return True
        return False

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from GitHub Actions chunk.

        Identifies jobs (by name) and steps (by name or uses action).

        Args:
            text: The chunk text content.

        Returns:
            Dict with block_type, hierarchy, language_id.

        Examples:
            Job chunk: block_type="job", hierarchy="job:build"
            Step chunk: block_type="step", hierarchy="step:Checkout code"
            Uses chunk: block_type="step", hierarchy="step:actions/checkout@v4"
        """
        stripped = self._strip_comments(text)

        # Check for step (- name: or - uses:)
        step_name = self._STEP_NAME_RE.search(stripped)
        if step_name:
            name = step_name.group(1).strip().strip("'\"")
            return {
                "block_type": "step",
                "hierarchy": f"step:{name}",
                "language_id": self.GRAMMAR_NAME,
            }

        step_uses = self._STEP_USES_RE.search(stripped)
        if step_uses:
            uses = step_uses.group(1).strip().strip("'\"")
            return {
                "block_type": "step",
                "hierarchy": f"step:{uses}",
                "language_id": self.GRAMMAR_NAME,
            }

        # Check for job definition (key at start of line followed by colon)
        job_match = self._JOB_RE.match(stripped)
        if job_match:
            job_name = job_match.group(1)
            # Skip top-level keys that aren't jobs
            if job_name not in (
                "name",
                "on",
                "jobs",
                "env",
                "permissions",
                "concurrency",
                "defaults",
                "true",
                "false",
            ):
                return {
                    "block_type": "job",
                    "hierarchy": f"job:{job_name}",
                    "language_id": self.GRAMMAR_NAME,
                }

        # Check for top-level keys
        top_match = self._TOP_LEVEL_RE.match(stripped)
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
        """Strip leading comments from chunk text."""
        lines = text.lstrip().split("\n")
        for i, line in enumerate(lines):
            if line.strip() and not self._COMMENT_LINE.match(line):
                return "\n".join(lines[i:])
        return ""
