"""Grammar handler for GitHub Actions workflow files.

Provides domain-specific chunking and metadata extraction for GitHub Actions
workflow YAML files found in .github/workflows/.

Matches: .github/workflows/*.yml, .github/workflows/*.yaml
Content markers: 'on:' and 'jobs:'
"""

import re

import cocoindex

from cocosearch.handlers.grammars._base import YamlGrammarBase


class GitHubActionsHandler(YamlGrammarBase):
    """Grammar handler for GitHub Actions workflow files."""

    GRAMMAR_NAME = "github-actions"
    PATH_PATTERNS = [".github/workflows/*.yml", ".github/workflows/*.yaml"]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="github-actions",
        separators_regex=[
            # Level 1: YAML document separator
            r"\n---",
            # Level 2: Top-level keys (name:, on:, jobs:, env:, permissions:)
            r"\n[a-zA-Z_][\w-]*:\s*\n",
            # Level 3: Job boundaries (2-space indented keys under jobs:)
            r"\n  [a-zA-Z_][\w-]*:",
            # Level 4: Job-level keys (4-space indented: runs-on:, steps:, env:)
            r"\n    [a-zA-Z_][\w-]*:",
            # Level 5: Step boundaries (- name: or - uses:)
            r"\n      - ",
            # Level 6: Blank lines
            r"\n\n+",
            # Level 7: Single newlines
            r"\n",
            # Level 8: Whitespace (last resort)
            r" ",
        ],
        aliases=[],
    )

    # Match step with 'name:' key
    _STEP_NAME_RE = re.compile(r"^\s*-\s+name:\s*(.+)$", re.MULTILINE)

    # Match step with 'uses:' key
    _STEP_USES_RE = re.compile(r"^\s*-?\s*uses:\s*(.+)$", re.MULTILINE)

    # GitHub Actions top-level keywords (not job names)
    _TOP_LEVEL_KEYS = frozenset(
        {
            "name",
            "on",
            "jobs",
            "env",
            "permissions",
            "concurrency",
            "defaults",
            "run-name",
            "true",
            "false",
        }
    )

    def _has_content_markers(self, content: str) -> bool:
        return "on:" in content and "jobs:" in content

    def _extract_grammar_metadata(self, stripped: str, text: str) -> dict | None:
        """Extract metadata from GitHub Actions chunk.

        Identifies jobs, steps, top-level sections, nested keys,
        list items, and value continuations.

        Examples:
            Job chunk: block_type="job", hierarchy="job:build"
            Step chunk: block_type="step", hierarchy="step:Checkout code"
            Uses chunk: block_type="step", hierarchy="step:actions/checkout@v4"
            Nested key: block_type="nested-key", hierarchy="nested-key:runs-on"
            List item: block_type="list-item", hierarchy="list-item:path"
        """
        # Check for step (- name: or - uses:)
        step_name = self._STEP_NAME_RE.search(stripped)
        if step_name:
            name = step_name.group(1).strip().strip("'\"")
            return self._make_result("step", f"step:{name}")

        step_uses = self._STEP_USES_RE.search(stripped)
        if step_uses:
            uses = step_uses.group(1).strip().strip("'\"")
            return self._make_result("step", f"step:{uses}")

        # Check for job definition (2-space indented key)
        item_match = self._ITEM_RE.match(stripped)
        if item_match:
            return self._make_result("job", f"job:{item_match.group(1)}")

        # Check for nested key (4+ space indented)
        nested_match = self._NESTED_KEY_RE.match(stripped)
        if nested_match:
            key = nested_match.group(1)
            return self._make_result("nested-key", f"nested-key:{key}")

        # Check for YAML list item key (e.g., "- path: value")
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
