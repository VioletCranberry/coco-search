"""Handler for Dockerfile files.

Provides language-aware chunking and metadata extraction for Dockerfiles
and Containerfiles.

Handles .dockerfile extension and extensionless Dockerfile/Containerfile files
(language routing happens via extract_language() in embedder.py).
"""

import re

import cocoindex


class DockerfileHandler:
    """Handler for Dockerfile files."""

    EXTENSIONS = [".dockerfile"]

    SEPARATOR_SPEC = cocoindex.functions.CustomLanguageSpec(
        language_name="dockerfile",
        separators_regex=[
            # Level 1: FROM (build stage boundaries -- highest priority)
            r"\nFROM ",
            # Level 2: Major instructions (case-sensitive, Dockerfile convention)
            r"\n(?:RUN|COPY|ADD|ENV|EXPOSE|VOLUME|WORKDIR|USER|LABEL|ARG|ENTRYPOINT|CMD|HEALTHCHECK|SHELL|ONBUILD|STOPSIGNAL|MAINTAINER) ",
            # Level 3: Blank lines
            r"\n\n+",
            # Level 4: Comment lines
            r"\n# ",
            # Level 5: Single newlines
            r"\n",
            # Level 6: Whitespace (last resort)
            r" ",
        ],
        aliases=[],
    )

    # Dockerfile comment pattern
    _COMMENT_LINE = re.compile(r"^\s*#.*$", re.MULTILINE)

    # Match any of the 18 Dockerfile instructions at line start
    _INSTRUCTION_RE = re.compile(
        r"^(FROM|RUN|CMD|LABEL|MAINTAINER|EXPOSE|ENV|ADD|COPY|ENTRYPOINT|"
        r"VOLUME|USER|WORKDIR|ARG|ONBUILD|STOPSIGNAL|HEALTHCHECK|SHELL)\b"
    )

    # FROM with optional --platform and optional AS clause
    _FROM_RE = re.compile(
        r"^FROM\s+"
        r"(?:--platform=\S+\s+)?"
        r"(\S+)"  # image reference
        r"(?:\s+[Aa][Ss]\s+(\S+))?",  # optional AS stage_name (case-insensitive AS)
    )

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from Dockerfile chunk.

        Matches Dockerfile instructions. For FROM instructions, extracts stage name
        (AS clause) or image reference for the hierarchy.

        Args:
            text: The chunk text content.

        Returns:
            Dict with metadata fields:
            - block_type: Dockerfile instruction (e.g., "FROM", "RUN")
            - hierarchy: For FROM: "stage:name" or "image:ref"; empty for others
            - language_id: "dockerfile"

        Example:
            Input: 'FROM golang:1.21 AS builder'
            Output: {
                "block_type": "FROM",
                "hierarchy": "stage:builder",
                "language_id": "dockerfile"
            }
        """
        stripped = self._strip_comments(text)
        match = self._INSTRUCTION_RE.match(stripped)
        if not match:
            return {"block_type": "", "hierarchy": "", "language_id": "dockerfile"}

        instruction = match.group(1)

        if instruction == "FROM":
            from_match = self._FROM_RE.match(stripped)
            if from_match:
                stage_name = from_match.group(2)
                if stage_name:
                    hierarchy = f"stage:{stage_name}"
                else:
                    image_ref = from_match.group(1)
                    hierarchy = f"image:{image_ref}"
            else:
                hierarchy = ""
        else:
            # Non-FROM instructions get empty hierarchy in v1.2
            hierarchy = ""

        return {
            "block_type": instruction,
            "hierarchy": hierarchy,
            "language_id": "dockerfile",
        }

    def _strip_comments(self, text: str) -> str:
        """Strip leading comments from chunk text.

        Args:
            text: The chunk text content.

        Returns:
            Text from first non-comment, non-blank line onward
        """
        lines = text.lstrip().split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not self._COMMENT_LINE.match(line):
                return "\n".join(lines[i:])
        return ""
