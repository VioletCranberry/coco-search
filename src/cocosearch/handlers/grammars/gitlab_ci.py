"""Grammar handler for GitLab CI configuration files.

Provides domain-specific chunking and metadata extraction for GitLab CI/CD
pipeline configuration (.gitlab-ci.yml).

Matches: .gitlab-ci.yml
Content markers: 'stages:' or ('script:' and ('image:' or 'stage:'))
"""

import re

import cocoindex

from cocosearch.handlers.grammars._base import YamlGrammarBase


class GitLabCIHandler(YamlGrammarBase):
    """Grammar handler for GitLab CI configuration files."""

    GRAMMAR_NAME = "gitlab-ci"
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

    # Top-level key (job name or keyword) at start of line
    # Supports . prefix (templates) and / in names (deploy/staging)
    _TOP_KEY_RE = re.compile(r"^([a-zA-Z_.][\w./-]*):\s*", re.MULTILINE)

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

    def _has_content_markers(self, content: str) -> bool:
        has_stages = "stages:" in content
        has_script_combo = "script:" in content and (
            "image:" in content or "stage:" in content
        )
        return has_stages or has_script_combo

    def _extract_grammar_metadata(self, stripped: str, text: str) -> dict | None:
        """Extract metadata from GitLab CI chunk.

        Identifies jobs, job-level keys, nested keys, list items,
        templates, global keywords, and value continuations.

        Examples:
            Job chunk: block_type="job", hierarchy="job:build"
            Job key: block_type="job-key", hierarchy="job-key:script"
            Template: block_type="template", hierarchy="template:.base_job"
            Nested key: block_type="nested-key", hierarchy="nested-key:only"
            List item: block_type="list-item", hierarchy="list-item:project"
        """
        # Check for job-level key (2-space indented key)
        item_match = self._ITEM_RE.match(stripped)
        if item_match:
            key = item_match.group(1)
            return self._make_result("job-key", f"job-key:{key}")

        # Check for nested key (4+ space indented)
        nested_match = self._NESTED_KEY_RE.match(stripped)
        if nested_match:
            key = nested_match.group(1)
            return self._make_result("nested-key", f"nested-key:{key}")

        # Check for YAML list item key (e.g., "- project: value")
        list_match = self._LIST_ITEM_KEY_RE.match(stripped)
        if list_match:
            key = list_match.group(1)
            return self._make_result("list-item", f"list-item:{key}")

        # Check for top-level keys
        top_match = self._TOP_KEY_RE.match(stripped)
        if top_match:
            key = top_match.group(1)

            # Hidden jobs/templates (start with .)
            if key.startswith("."):
                return self._make_result("template", f"template:{key}")

            # Global keywords
            if key in self._TOP_LEVEL_KEYS:
                return self._make_result(key, key)

            # Regular job
            return self._make_result("job", f"job:{key}")

        return None
