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

    # Additional include patterns for extensionless Dockerfiles/Containerfiles
    INCLUDE_PATTERNS = ["Dockerfile", "Dockerfile.*", "Containerfile"]

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

    # COPY --from=<stage>
    _COPY_FROM_RE = re.compile(r"^COPY\s+--from=(\S+)")

    # ARG <name>[=<default>]
    _ARG_RE = re.compile(r"^ARG\s+([A-Za-z_][A-Za-z0-9_]*)")

    # ENV <key>=<value> or ENV <key> <value>
    _ENV_RE = re.compile(r"^ENV\s+([A-Za-z_][A-Za-z0-9_]*)")

    # EXPOSE <port>
    _EXPOSE_RE = re.compile(r"^EXPOSE\s+(\S+)")

    # WORKDIR <path>
    _WORKDIR_RE = re.compile(r"^WORKDIR\s+(\S+)")

    # LABEL <key>=<value> or LABEL <key> <value>
    _LABEL_RE = re.compile(r"^LABEL\s+([A-Za-z_][A-Za-z0-9_./-]*)")

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from Dockerfile chunk.

        Matches Dockerfile instructions. Extracts hierarchy metadata for:
        - FROM: "stage:<name>" or "image:<ref>"
        - COPY --from: "from:<stage>"
        - ARG: "arg:<name>"
        - ENV: "env:<key>"
        - EXPOSE: "port:<port>"
        - WORKDIR: "workdir:<path>"
        - LABEL: "label:<key>"

        Args:
            text: The chunk text content.

        Returns:
            Dict with metadata fields:
            - block_type: Dockerfile instruction (e.g., "FROM", "RUN")
            - hierarchy: Instruction-specific hierarchy or empty string
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
        hierarchy = self._extract_hierarchy(instruction, stripped)

        return {
            "block_type": instruction,
            "hierarchy": hierarchy,
            "language_id": "dockerfile",
        }

    def _extract_hierarchy(self, instruction: str, stripped: str) -> str:
        """Extract hierarchy string for a Dockerfile instruction.

        Args:
            instruction: The instruction keyword (e.g., "FROM", "ARG").
            stripped: The comment-stripped chunk text.

        Returns:
            Hierarchy string or empty string if not applicable.
        """
        if instruction == "FROM":
            from_match = self._FROM_RE.match(stripped)
            if from_match:
                stage_name = from_match.group(2)
                if stage_name:
                    return f"stage:{stage_name}"
                return f"image:{from_match.group(1)}"
            return ""

        if instruction == "COPY":
            m = self._COPY_FROM_RE.match(stripped)
            return f"from:{m.group(1)}" if m else ""

        if instruction == "ARG":
            m = self._ARG_RE.match(stripped)
            return f"arg:{m.group(1)}" if m else ""

        if instruction == "ENV":
            m = self._ENV_RE.match(stripped)
            return f"env:{m.group(1)}" if m else ""

        if instruction == "EXPOSE":
            m = self._EXPOSE_RE.match(stripped)
            return f"port:{m.group(1)}" if m else ""

        if instruction == "WORKDIR":
            m = self._WORKDIR_RE.match(stripped)
            return f"workdir:{m.group(1)}" if m else ""

        if instruction == "LABEL":
            m = self._LABEL_RE.match(stripped)
            return f"label:{m.group(1)}" if m else ""

        return ""

    def _strip_comments(self, text: str) -> str:
        """Strip leading comments from chunk text."""
        from cocosearch.handlers.utils import strip_leading_comments

        return strip_leading_comments(text, [self._COMMENT_LINE])
